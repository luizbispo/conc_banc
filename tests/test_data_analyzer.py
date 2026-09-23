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

from modules.data_analyzer import DataAnalyzer


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
        tolerancia_dias=2, tolerancia_valor=5.0, similaridade_minima=70,
    )

    assert len(resultado['matches']) == 1
    explicacao = resultado['matches'][0]['explicacao']
    assert "valor difere R$ 3,00" in explicacao
    assert "data difere 0 dias" in explicacao
    assert "similaridade" in explicacao.lower()
