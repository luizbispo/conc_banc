"""
Testes de regressão para modules/data_analyzer.py (issue XCRE-42, Parte A,
item 3): a justificativa de um match heurístico dizia só "Match por
similaridade: X%", sem citar a diferença de valor nem de data entre os
dois lados — o caderno de casos de teste (CT-CON-02) marcou isso como
FAIL porque o contador não conseguia auditar a decisão sem comparar as
linhas manualmente.

Dados 100% sintéticos.
"""
import pandas as pd
import pytest

from modules.data_analyzer import DataAnalyzer, TOLERANCIA_VALOR_PERCENTUAL_PADRAO


def test_justificar_match_heuristico_formato_esperado():
    analyzer = DataAnalyzer()
    texto = analyzer._justificar_match_heuristico(similaridade=90.0, diff_valor=3.0, diff_dias=0)
    assert texto == "Match por similaridade: 90%; valor difere R$ 3,00; data difere 0 dias"


def test_justificar_match_heuristico_dia_singular():
    analyzer = DataAnalyzer()
    texto = analyzer._justificar_match_heuristico(similaridade=75.0, diff_valor=2.0, diff_dias=1)
    assert "data difere 1 dia" in texto
    assert "1 dias" not in texto


def test_matching_heuristico_inclui_diferenca_de_valor_e_data_na_justificativa():
    """Reproduz o par 'Águia Branca' do cenário B x C do caderno de casos
    de teste: -40,30 (extrato) / -43,30 (contábil), mesma data —
    justificativa esperada cita 'valor difere R$ 3,00; data difere 0
    dias'."""
    extrato_df = pd.DataFrame({
        'id': [1],
        'data': pd.to_datetime(['2025-07-01']),
        'valor': [-40.30],
        'descricao': ['Aguia Branca Transportes'],
    })
    contabil_df = pd.DataFrame({
        'id': [1],
        'data': pd.to_datetime(['2025-07-01']),
        'valor': [-43.30],
        'descricao': ['Aguia Branca Transportes'],
    })

    analyzer = DataAnalyzer()
    resultado = analyzer.matching_heuristico(
        extrato_df, contabil_df, extrato_df, contabil_df,
        tolerancia_dias=2, tolerancia_valor_percentual=10.0, similaridade_minima=70,
    )

    assert len(resultado['matches']) == 1
    explicacao = resultado['matches'][0]['explicacao']
    assert "valor difere R$ 3,00" in explicacao
    assert "data difere 0 dias" in explicacao
    assert "similaridade" in explicacao.lower()


# --- Tolerância de valor explícita/percentual (issue XCRE-42, Parte A, item 4) ---
# Antes a tolerância era um R$ fixo derivado da média de TODO o lote
# (`(tolerancia_percentual / 100) * extrato_filtrado['valor_matching'].mean()`
# em pages/analise_dados.py), o que tornava a decisão de um par instável:
# o mesmo par podia ser aceito ou rejeitado dependendo de quais outras
# transações estavam no lote. Agora a tolerância é percentual e aplicada
# por par (percentual × valor daquele par), com padrão fixo documentado
# em TOLERANCIA_VALOR_PERCENTUAL_PADRAO.

def _par_uber_trip():
    """Par 'Uber* Trip' do caderno de casos de teste (CT-CON-04): -20,80
    (extrato) / -25,80 (contábil), diferença de 24% — deve permanecer
    NÃO conciliado com a tolerância padrão de 2%."""
    extrato_df = pd.DataFrame({
        'id': [1],
        'data': pd.to_datetime(['2025-07-11']),
        'valor': [-20.80],
        'descricao': ['Uber* Trip'],
    })
    contabil_df = pd.DataFrame({
        'id': [1],
        'data': pd.to_datetime(['2025-07-11']),
        'valor': [-25.80],
        'descricao': ['Uber* Trip'],
    })
    return extrato_df, contabil_df


def test_par_acima_da_tolerancia_padrao_nao_e_aceito():
    extrato_df, contabil_df = _par_uber_trip()
    analyzer = DataAnalyzer()
    resultado = analyzer.matching_heuristico(
        extrato_df, contabil_df, extrato_df, contabil_df,
        tolerancia_dias=2,
        tolerancia_valor_percentual=TOLERANCIA_VALOR_PERCENTUAL_PADRAO,
        similaridade_minima=70,
    )
    assert resultado['matches'] == []
    assert len(resultado['nao_matchados_extrato']) == 1


def test_tolerancia_e_aplicada_por_par_nao_pela_media_do_lote():
    """Regressão do bug real: adicionar transações grandes e não
    relacionadas ao mesmo lote não deve mudar a decisão sobre o par
    Uber* Trip (24% de diferença), porque a tolerância não depende mais
    da média do lote."""
    extrato_uber, contabil_uber = _par_uber_trip()

    extrato_ruido = pd.DataFrame({
        'id': [2, 3],
        'data': pd.to_datetime(['2025-07-01', '2025-07-02']),
        'valor': [-5000.00, -8000.00],
        'descricao': ['Transferencia Grande A', 'Transferencia Grande B'],
    })
    contabil_ruido = pd.DataFrame({
        'id': [2, 3],
        'data': pd.to_datetime(['2025-07-01', '2025-07-02']),
        'valor': [-5000.00, -8000.00],
        'descricao': ['Transferencia Grande A', 'Transferencia Grande B'],
    })

    extrato_df = pd.concat([extrato_uber, extrato_ruido], ignore_index=True)
    contabil_df = pd.concat([contabil_uber, contabil_ruido], ignore_index=True)

    analyzer = DataAnalyzer()
    resultado = analyzer.matching_heuristico(
        extrato_df, contabil_df, extrato_df, contabil_df,
        tolerancia_dias=2,
        tolerancia_valor_percentual=TOLERANCIA_VALOR_PERCENTUAL_PADRAO,
        similaridade_minima=70,
    )

    ids_extrato_aceitos = {i for m in resultado['matches'] for i in m['ids_extrato']}
    assert 1 not in ids_extrato_aceitos  # par Uber* Trip continua não conciliado


def test_par_dentro_da_tolerancia_padrao_e_aceito():
    extrato_df = pd.DataFrame({
        'id': [1], 'data': pd.to_datetime(['2025-07-01']),
        'valor': [-100.00], 'descricao': ['Fornecedor X'],
    })
    contabil_df = pd.DataFrame({
        'id': [1], 'data': pd.to_datetime(['2025-07-01']),
        'valor': [-101.00], 'descricao': ['Fornecedor X'],  # 1% de diferença
    })
    analyzer = DataAnalyzer()
    resultado = analyzer.matching_heuristico(
        extrato_df, contabil_df, extrato_df, contabil_df,
        tolerancia_dias=2,
        tolerancia_valor_percentual=TOLERANCIA_VALOR_PERCENTUAL_PADRAO,
        similaridade_minima=70,
    )
    assert len(resultado['matches']) == 1
