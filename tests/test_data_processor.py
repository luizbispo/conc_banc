"""
Testes de regressão para modules/data_processor.py.

Cobrem a correção do fallback silencioso: antes, linhas com data ou valor
inválidos eram descartadas via dropna() sem nenhuma contagem visível para
quem chamava a função. Agora processar_extrato/processar_contabil retornam
(df, relatorio) com as contagens de linhas recebidas/aceitas/rejeitadas.

Usa apenas dados sintéticos criados no próprio teste.
"""
import pandas as pd
import pytest

from modules import data_processor as dp


def test_processar_extrato_accepts_all_valid_rows():
    df = pd.DataFrame({
        "Data": ["2024-01-01", "2024-01-02", "2024-01-03"],
        "Valor": [100.0, -50.5, 200.25],
        "Descricao": ["PIX recebido", "Pagamento boleto", "Depósito"],
    })

    resultado, relatorio = dp.processar_extrato(df, "Data", "Valor", "Descricao")

    assert len(resultado) == 3
    assert relatorio["total_recebido"] == 3
    assert relatorio["total_aceito"] == 3
    assert relatorio["total_rejeitado"] == 0


def test_processar_extrato_reports_invalid_date_rejection():
    df = pd.DataFrame({
        "Data": ["2024-01-01", "data-invalida", "2024-01-03"],
        "Valor": [100.0, -50.5, 200.25],
        "Descricao": ["A", "B", "C"],
    })

    resultado, relatorio = dp.processar_extrato(df, "Data", "Valor", "Descricao")

    assert len(resultado) == 2
    assert relatorio["total_recebido"] == 3
    assert relatorio["total_aceito"] == 2
    assert relatorio["rejeitado_data_invalida"] == 1
    assert relatorio["total_rejeitado"] == 1


def test_processar_extrato_reports_invalid_value_rejection():
    df = pd.DataFrame({
        "Data": ["2024-01-01", "2024-01-02", "2024-01-03"],
        "Valor": [100.0, "não é número", 200.25],
        "Descricao": ["A", "B", "C"],
    })

    resultado, relatorio = dp.processar_extrato(df, "Data", "Valor", "Descricao")

    assert len(resultado) == 2
    assert relatorio["rejeitado_valor_invalido"] == 1
    assert relatorio["total_rejeitado"] == 1


def test_processar_extrato_never_silently_returns_full_row_count_when_rows_rejected():
    """Trava de regressão: o total 'aceito' relatado nunca pode ser igual
    ao total 'recebido' quando existiam linhas inválidas — isso é
    exatamente o comportamento que a auditoria honesta precisa detectar."""
    df = pd.DataFrame({
        "Data": ["2024-01-01", "invalida", "invalida"],
        "Valor": [100.0, 50.0, 30.0],
        "Descricao": ["A", "B", "C"],
    })

    _, relatorio = dp.processar_extrato(df, "Data", "Valor", "Descricao")

    assert relatorio["total_aceito"] < relatorio["total_recebido"]
    assert relatorio["total_rejeitado"] == 2


def test_processar_extrato_raises_on_missing_required_column():
    df = pd.DataFrame({"Data": ["2024-01-01"], "Descricao": ["A"]})
    with pytest.raises(ValueError):
        dp.processar_extrato(df, "Data", "ColunaQueNaoExiste", "Descricao")


def test_processar_contabil_same_contract_as_extrato():
    df = pd.DataFrame({
        "DataLanc": ["2024-01-01", "2024-01-02"],
        "Vlr": [10.0, 20.0],
        "Hist": ["Compra A", "Compra B"],
    })

    resultado, relatorio = dp.processar_contabil(df, "DataLanc", "Vlr", "Hist")

    assert len(resultado) == 2
    assert relatorio["dataset"] == "lançamentos contábeis"
    assert relatorio["total_rejeitado"] == 0
