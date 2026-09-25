"""
Testes de regressão para modules/export_divergencias.py
(issue XCRE-49, Fase 5, item 2).

Antes, as tabelas de divergência eram exportadas com
`DataFrame.to_csv(index=False)` puro: separador ',', sem BOM (Excel
PT-BR interpreta mal acentos) e sem nenhuma proteção contra formula
injection. `gerar_csv_divergencias` corrige isso; estes testes cobrem
o formato exigido (separador ';', decimal ',', UTF-8 com BOM), a
proteção contra formula injection e o conteúdo (round-trip) das
mesmas divergências B x C usadas no resto do projeto.

Dados 100% sintéticos.
"""
import pandas as pd
import pytest

import pages.analise_dados as pagina
from modules.export_divergencias import gerar_csv_divergencias


BOM_UTF8 = b'\xef\xbb\xbf'


def _tabela_bancario_sem_contabil_sintetica() -> pd.DataFrame:
    """Reproduz o formato real de `_criar_tabela_bancario_sem_contabil`
    em pages/analise_dados.py: Data já como string dd/mm/aaaa, Valor já
    como string "R$ 1.234,56" (decimal ',', milhar '.')."""
    return pd.DataFrame([
        {
            'Tipo_Divergência': '🔴 Mov. Bancária sem Lançamento',
            'Data': '15/01/2024',
            'Valor_Bancário': 'R$ 1.500,00',
            'Descrição_Bancário': 'PIX recebido de Cliente A',
            'Origem': '🏦 Extrato Bancário',
            'Status': 'Não conciliado',
        },
        {
            'Tipo_Divergência': '🔴 Mov. Bancária sem Lançamento',
            'Data': '16/01/2024',
            'Valor_Bancário': 'R$ 250,00',
            'Descrição_Bancário': 'Pagamento Fornecedor B',
            'Origem': '🏦 Extrato Bancário',
            'Status': 'Não conciliado',
        },
    ])


# --- Formato: separador, decimal, BOM ---

def test_csv_usa_ponto_e_virgula_como_separador():
    df = _tabela_bancario_sem_contabil_sintetica()
    csv_bytes = gerar_csv_divergencias(df)
    texto = csv_bytes.decode('utf-8-sig')

    primeira_linha = texto.splitlines()[0]
    assert ';' in primeira_linha
    assert primeira_linha.count(';') == len(df.columns) - 1


def test_csv_usa_virgula_como_decimal_em_coluna_numerica():
    df = pd.DataFrame([{'Descrição': 'Item 1', 'Diferença_Valor': 1234.5}])
    csv_bytes = gerar_csv_divergencias(df)
    texto = csv_bytes.decode('utf-8-sig')

    assert '1234,5' in texto
    assert '1234.5' not in texto


def test_csv_tem_bom_utf8_no_inicio():
    df = _tabela_bancario_sem_contabil_sintetica()
    csv_bytes = gerar_csv_divergencias(df)

    assert csv_bytes.startswith(BOM_UTF8)


def test_datas_ja_formatadas_dd_mm_aaaa_sao_preservadas():
    df = _tabela_bancario_sem_contabil_sintetica()
    csv_bytes = gerar_csv_divergencias(df)
    texto = csv_bytes.decode('utf-8-sig')

    assert '15/01/2024' in texto
    assert '16/01/2024' in texto


# --- Proteção contra formula injection ---

@pytest.mark.parametrize("descricao_maliciosa", [
    "=CMD('calc')",
    "+1+1",
    "-2+3",
    "@SUM(A1:A9)",
])
def test_celula_com_prefixo_de_formula_recebe_apostrofo(descricao_maliciosa):
    df = pd.DataFrame([{'Descrição_Bancário': descricao_maliciosa, 'Valor': 'R$ 10,00'}])
    csv_bytes = gerar_csv_divergencias(df)
    texto = csv_bytes.decode('utf-8-sig')

    assert f"'{descricao_maliciosa}" in texto
    # a célula maliciosa nunca deve aparecer sem o apóstrofo de proteção
    assert texto.count(descricao_maliciosa) == texto.count(f"'{descricao_maliciosa}")


def test_celula_normal_nao_recebe_apostrofo():
    df = _tabela_bancario_sem_contabil_sintetica()
    csv_bytes = gerar_csv_divergencias(df)
    texto = csv_bytes.decode('utf-8-sig')

    assert "'PIX recebido de Cliente A" not in texto
    assert "PIX recebido de Cliente A" in texto


def test_valor_formatado_como_moeda_nao_e_confundido_com_formula():
    """"R$ 1.500,00" não começa com nenhum prefixo de fórmula; não deve
    ganhar apóstrofo (o formato monetário fica intacto)."""
    df = _tabela_bancario_sem_contabil_sintetica()
    csv_bytes = gerar_csv_divergencias(df)
    texto = csv_bytes.decode('utf-8-sig')

    assert "R$ 1.500,00" in texto
    assert "'R$ 1.500,00" not in texto


# --- Ordenação determinística ---

def test_sem_ordenar_por_preserva_ordem_original():
    df = _tabela_bancario_sem_contabil_sintetica()
    csv_bytes = gerar_csv_divergencias(df)
    texto = csv_bytes.decode('utf-8-sig')

    linhas = texto.splitlines()
    assert '15/01/2024' in linhas[1]
    assert '16/01/2024' in linhas[2]


def test_ordenar_por_produz_mesma_saida_independente_da_ordem_de_entrada():
    df_original = _tabela_bancario_sem_contabil_sintetica()
    df_invertido = df_original.iloc[::-1].reset_index(drop=True)

    csv_original = gerar_csv_divergencias(df_original, ordenar_por=['Data'])
    csv_invertido = gerar_csv_divergencias(df_invertido, ordenar_por=['Data'])

    assert csv_original == csv_invertido


# --- Conteúdo B x C: round-trip ---

def test_conteudo_bancario_sem_contabil_preservado_no_round_trip():
    """As mesmas duas divergências bancárias (id 1 e 2, sem par contábil)
    do cenário B x C sintético devem sobreviver ao export/reimport sem
    perda nem alteração de dado."""
    df_original = _tabela_bancario_sem_contabil_sintetica()
    csv_bytes = gerar_csv_divergencias(df_original)

    import io
    df_relido = pd.read_csv(io.BytesIO(csv_bytes), sep=';', encoding='utf-8-sig')

    assert len(df_relido) == 2
    assert list(df_relido['Data']) == ['15/01/2024', '16/01/2024']
    assert list(df_relido['Valor_Bancário']) == ['R$ 1.500,00', 'R$ 250,00']
    assert list(df_relido['Descrição_Bancário']) == [
        'PIX recebido de Cliente A',
        'Pagamento Fornecedor B',
    ]


def test_dataframe_vazio_gera_apenas_cabecalho_com_bom():
    df_vazio = pd.DataFrame(columns=['Tipo_Divergência', 'Data', 'Valor_Bancário'])
    csv_bytes = gerar_csv_divergencias(df_vazio)

    assert csv_bytes.startswith(BOM_UTF8)
    texto = csv_bytes.decode('utf-8-sig')
    linhas = [l for l in texto.splitlines() if l]
    assert len(linhas) == 1
    assert 'Tipo_Divergência' in linhas[0]


# --- CT-F5-05: decimal ',' na saída REAL do fluxo B x C ---
#
# As tabelas sintéticas acima (`_tabela_bancario_sem_contabil_sintetica`)
# já chegam com "Valor_Bancário" no formato pt-BR ("R$ 1.500,00"), o que
# não reproduz o bug real: `pages/analise_dados.py` monta essas células
# com `f"R$ {valor:,.2f}"`, que é formato en-US (milhar ',', decimal
# '.'), ex. "R$ 1,300.00" ou "R$ -60.50". Os testes abaixo chamam as
# MESMAS funções de `pages/analise_dados.py` que constroem as tabelas
# de divergência reais (com DataFrames de entrada sintéticos, sem
# depender de arquivo de exemplo) para garantir que o exportador recebe
# e corrige exatamente essa célula textual.

def _extrato_nao_match_sintetico() -> pd.DataFrame:
    """Linhas de extrato sem par contábil, no formato de entrada real de
    `_criar_tabela_bancario_sem_contabil`/`_criar_tabela_similaridades`
    (colunas `id`, `data` como Timestamp, `valor` numérico, `descricao`).
    Valores escolhidos para cobrir negativo (`-60.50`), milhar
    (`1,300.00`) e zero (`0.00`), como no CSV real documentado no
    CT-F5-05 (`R$ -60.50`, `R$ -4.92`, `R$ 1,300.00`, `R$ -20.80`)."""
    return pd.DataFrame([
        {'id': 1, 'data': pd.Timestamp('2024-01-15'), 'valor': -60.50, 'descricao': 'Uber* Trip'},
        {'id': 2, 'data': pd.Timestamp('2024-01-16'), 'valor': 1300.00, 'descricao': 'Mercadolivre'},
        {'id': 3, 'data': pd.Timestamp('2024-01-17'), 'valor': 0.00, 'descricao': 'Ajuste'},
    ])


def _contabil_nao_match_sintetico() -> pd.DataFrame:
    """Lançamentos contábeis sem par bancário, mesmo formato de entrada
    de `_criar_tabela_contabil_sem_bancario`/`_criar_tabela_similaridades`."""
    return pd.DataFrame([
        {'id': 10, 'data': pd.Timestamp('2024-01-15'), 'valor': -63.00, 'descricao': 'Uber Trip'},
        {'id': 11, 'data': pd.Timestamp('2024-01-16'), 'valor': 1300.00, 'descricao': 'Mercado Livre'},
    ])


def test_moeda_textual_do_fluxo_real_bancario_sem_contabil_vira_pt_br_no_csv():
    """`_criar_tabela_bancario_sem_contabil` é a função REAL de
    pages/analise_dados.py usada no cenário B x C. Sem a correção, a
    célula sai como "R$ -60.50"/"R$ 1,300.00" (decimal '.', não ',')."""
    extrato_nao_match = _extrato_nao_match_sintetico()
    tabela_real = pagina._criar_tabela_bancario_sem_contabil(extrato_nao_match)

    # Confirma a premissa do bug: a função real do fluxo B x C entrega
    # a célula como texto en-US, não numérico e não pt-BR.
    valores_brutos = list(tabela_real['Valor_Bancário'])
    assert valores_brutos == ['R$ -60.50', 'R$ 1,300.00', 'R$ 0.00']

    csv_bytes = gerar_csv_divergencias(tabela_real)
    texto = csv_bytes.decode('utf-8-sig')

    assert 'R$ -60,50' in texto
    assert 'R$ 1.300,00' in texto
    assert 'R$ 0,00' in texto
    # nenhum valor monetário deve sobrar com decimal '.'
    assert 'R$ -60.50' not in texto
    assert 'R$ 1,300.00' not in texto
    assert 'R$ 0.00' not in texto


def test_moeda_textual_do_fluxo_real_contabil_sem_bancario_vira_pt_br_no_csv():
    contabil_nao_match = _contabil_nao_match_sintetico()
    tabela_real = pagina._criar_tabela_contabil_sem_bancario(contabil_nao_match)

    assert list(tabela_real['Valor_Contábil']) == ['R$ -63.00', 'R$ 1,300.00']

    csv_bytes = gerar_csv_divergencias(tabela_real)
    texto = csv_bytes.decode('utf-8-sig')

    assert 'R$ -63,00' in texto
    assert 'R$ 1.300,00' in texto
    assert 'R$ -63.00' not in texto
    assert 'R$ 1,300.00' not in texto


def test_moeda_textual_do_fluxo_real_similaridades_vira_pt_br_no_csv():
    """`_criar_tabela_similaridades` gera duas colunas monetárias
    (`Valor_Bancário`, `Valor_Contábil`) mais `Diferença_Valor` (usa
    `abs()`, sempre positiva) — as três precisam sair com decimal ','."""
    extrato_nao_match = _extrato_nao_match_sintetico()
    contabil_nao_match = _contabil_nao_match_sintetico()
    tabela_real = pagina._criar_tabela_similaridades(extrato_nao_match, contabil_nao_match)

    # Pré-condição do cenário: par (id 1, id 10) é similaridade válida
    # (mesma data, ~4,7% de diferença de valor, descrição parecida).
    assert len(tabela_real) >= 1

    csv_bytes = gerar_csv_divergencias(tabela_real)
    texto = csv_bytes.decode('utf-8-sig')

    assert 'R$ -60,50' in texto
    assert 'R$ -63,00' in texto
    assert 'R$ -60.50' not in texto
    assert 'R$ -63.00' not in texto
    # Diferença_Valor = abs(-60.50 - (-63.00)) = 2.50 -> "R$ 2.50" (en-US) -> "R$ 2,50"
    assert 'R$ 2,50' in texto
    assert 'R$ 2.50' not in texto


def test_moeda_ja_pt_br_nao_e_alterada_pela_normalizacao():
    """Regressão: uma célula que já chegasse pronta em pt-BR (formato
    documentado no docstring do módulo, "R$ 1.234,56") não pode ser
    confundida com milhar en-US e reescrita errado."""
    df = pd.DataFrame([{'Descrição': 'Item', 'Valor': 'R$ 1.234,56'}])
    csv_bytes = gerar_csv_divergencias(df)
    texto = csv_bytes.decode('utf-8-sig')

    assert 'R$ 1.234,56' in texto
