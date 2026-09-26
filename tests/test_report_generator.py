"""
Testes de regressão para as correções do relatório PDF (issue XCRE-42,
Parte A, itens 1 e 2):

1. O campo "Período" deve refletir o intervalo real das datas dos dados
   analisados, não o mês em que o PDF foi gerado (bug real observado no
   E2E: "September/2026" em vez de "15/06/2025 a 14/07/2025").
2. O PDF deve imprimir a SOMA em R$ das divergências de cada lado
   (bancário sem contábil e contábil sem bancário), não só as contagens
   (a tela já mostrava a soma; o PDF não).

Dados 100% sintéticos.
"""
import pandas as pd
import pytest
from pypdf import PdfReader

from pages.gerar_relatorio import calcular_periodo_real
from modules.report_generator import (
    formatar_valor_brl,
    _somar_coluna_valor,
    gerar_relatorio_analise,
)


# --- calcular_periodo_real ---

def test_calcula_periodo_a_partir_do_intervalo_real_das_datas():
    extrato_df = pd.DataFrame({
        'id': [1, 2],
        'data': pd.to_datetime(['2025-06-20', '2025-07-10']),
        'valor': [100.0, -50.0],
    })
    contabil_df = pd.DataFrame({
        'id': [1, 2],
        'data': pd.to_datetime(['2025-06-15', '2025-07-14']),
        'valor': [100.0, 50.0],
    })
    assert calcular_periodo_real(extrato_df, contabil_df) == "15/06/2025 a 14/07/2025"


def test_periodo_ignora_datas_invalidas():
    extrato_df = pd.DataFrame({'id': [1], 'data': ['nao-e-uma-data'], 'valor': [1.0]})
    contabil_df = pd.DataFrame({'id': [1], 'data': pd.to_datetime(['2025-01-05']), 'valor': [1.0]})
    assert calcular_periodo_real(extrato_df, contabil_df) == "05/01/2025 a 05/01/2025"


# --- XCRE-54 item 2: campo/override manual de período removido; o
# período do relatório passa a ser SEMPRE o automático de
# calcular_periodo_real (capa, seção de auditoria e lote da auditoria em
# pages/gerar_relatorio.py). Casos de borda pedidos na issue: anos
# diferentes, um lado vazio, datas inválidas. ---

def test_periodo_calcula_corretamente_entre_anos_diferentes():
    extrato_df = pd.DataFrame({
        'id': [1, 2],
        'data': pd.to_datetime(['2024-12-10', '2025-01-02']),
        'valor': [100.0, -50.0],
    })
    contabil_df = pd.DataFrame({
        'id': [1],
        'data': pd.to_datetime(['2025-03-20']),
        'valor': [100.0],
    })
    assert calcular_periodo_real(extrato_df, contabil_df) == "10/12/2024 a 20/03/2025"


def test_periodo_usa_somente_o_lado_com_dados_quando_outro_lado_esta_vazio():
    extrato_com_dados = pd.DataFrame({
        'id': [1, 2],
        'data': pd.to_datetime(['2025-06-15', '2025-07-16']),
        'valor': [100.0, -50.0],
    })
    contabil_vazio = pd.DataFrame(columns=['id', 'data', 'valor'])
    # Lado vazio não quebra o cálculo — usa só o lado com dados (valor
    # claro: o intervalo real, não uma mensagem de erro).
    assert calcular_periodo_real(extrato_com_dados, contabil_vazio) == "15/06/2025 a 16/07/2025"
    assert calcular_periodo_real(contabil_vazio, extrato_com_dados) == "15/06/2025 a 16/07/2025"
    assert calcular_periodo_real(extrato_com_dados, None) == "15/06/2025 a 16/07/2025"


def test_periodo_mensagem_clara_em_portugues_quando_nenhum_lado_tem_data_valida():
    from datetime import datetime

    casos = [
        (pd.DataFrame({'id': [], 'data': [], 'valor': []}), pd.DataFrame({'id': [], 'data': [], 'valor': []})),
        (pd.DataFrame({'id': [1], 'data': ['nao-e-uma-data'], 'valor': [1.0]}),
         pd.DataFrame({'id': [1], 'data': ['tambem-invalida'], 'valor': [1.0]})),
        (None, None),
    ]
    mes_de_geracao = datetime.now().strftime('%B/%Y')
    for extrato_df, contabil_df in casos:
        resultado = calcular_periodo_real(extrato_df, contabil_df)
        # Sem override manual (removido nesta issue), o automático nunca
        # pode fingir silenciosamente que o mês de geração do PDF é o
        # período dos dados — precisa de uma mensagem clara em português.
        assert resultado != mes_de_geracao
        assert "não determinado" in resultado.lower()


# --- formatar_valor_brl / _somar_coluna_valor ---

def test_formatar_valor_brl():
    assert formatar_valor_brl(1386.22) == "R$ 1.386,22"
    assert formatar_valor_brl(0) == "R$ 0,00"


def test_somar_coluna_valor_ignora_linhas_invalidas():
    df = pd.DataFrame({'Valor': ["R$ 60.50", "R$ 1,300.00", "não é valor"]})
    assert _somar_coluna_valor(df) == pytest.approx(1360.50)


def test_somar_coluna_valor_dataframe_vazio_retorna_zero():
    assert _somar_coluna_valor(pd.DataFrame()) == 0.0


# --- Integração: PDF gerado imprime período real e somas monetárias ---

def _extrair_texto_pdf(pdf_path: str) -> str:
    reader = PdfReader(pdf_path)
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def test_pdf_gerado_contem_periodo_real_e_somas_das_divergencias():
    extrato_df = pd.DataFrame({
        'id': [1, 2],
        'data': pd.to_datetime(['2025-06-15', '2025-07-14']),
        'valor': [60.50, 1300.00],
        'descricao': ['Pagamento A', 'Pagamento B'],
    })
    contabil_df = pd.DataFrame({
        'id': [1],
        'data': pd.to_datetime(['2025-06-20']),
        'valor': [500.00],
        'descricao': ['Lançamento C'],
    })
    resultados_analise = {'matches': [], 'excecoes': [{}, {}, {}]}
    divergencias_tabela = pd.DataFrame([
        {'Data': '15/06/2025', 'Valor': 'R$ 60.50', 'Descrição': 'Pagamento A', 'Status': 'Sem correspondência', 'Origem': 'Extrato Bancário'},
        {'Data': '14/07/2025', 'Valor': 'R$ 1,300.00', 'Descrição': 'Pagamento B', 'Status': 'Sem correspondência', 'Origem': 'Extrato Bancário'},
        {'Data': '20/06/2025', 'Valor': 'R$ 500.00', 'Descrição': 'Lançamento C', 'Status': 'Sem correspondência', 'Origem': 'Sistema Contábil'},
    ])
    periodo = calcular_periodo_real(extrato_df, contabil_df)

    pdf_path = gerar_relatorio_analise(
        resultados_analise=resultados_analise,
        extrato_df=extrato_df,
        contabil_df=contabil_df,
        empresa_nome="Empresa Teste",
        contador_nome="Contador Teste",
        periodo=periodo,
        divergencias_tabela=divergencias_tabela,
        conta_analisada="1234490",
    )

    texto = _extrair_texto_pdf(pdf_path)

    assert "15/06/2025 a 14/07/2025" in texto
    assert "September" not in texto and "2026" not in texto.split("Período:")[-1][:20]
    assert "R$ 1.360,50" in texto  # soma bancária: 60,50 + 1.300,00
    assert "R$ 500,00" in texto    # soma contábil
