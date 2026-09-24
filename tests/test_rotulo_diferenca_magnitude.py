"""Testes do item A1 (issue XCRE-44): rótulo de diferença de valor nos
casamentos por similaridade deve comparar MAGNITUDE (|contábil| vs
|extrato|), não o sinal algébrico (contábil - extrato). O sinal
algébrico sozinho inverte o resultado para despesas (valores negativos):
uma despesa maior no contábil (-43,30 contra -40,30 no extrato) é uma
diferença NEGATIVA (contábil - extrato = -3,00), mas o contábil está
"a mais", não "a menos".

Cobre débito (despesa) e crédito (receita), nos dois sentidos, e o caso
de igualdade — inclusive o cenário de referência B×C (Águia Branca e
Dell) citado na issue.
"""
import pandas as pd
import pytest

from modules.report_executivo import (
    _linha_match_similaridade,
    _rotulo_diferenca_por_magnitude,
    montar_contexto_executivo,
)


# --- Unidade: _rotulo_diferenca_por_magnitude ---

def test_despesa_maior_no_contabil_e_a_mais_nao_a_menos():
    # Águia Branca (B×C): extrato -40,30 / contábil -43,30 — despesa MAIOR
    # no contábil. O sinal algébrico (contábil-extrato=-3,00) é negativo,
    # mas o rótulo correto é "a mais", porque |43,30| > |40,30|.
    rotulo, magnitude = _rotulo_diferenca_por_magnitude(valor_contabil=-43.30, valor_extrato=-40.30)
    assert rotulo == "R$ 3,00 a mais no contábil"
    assert magnitude == pytest.approx(3.00)


def test_despesa_menor_no_contabil_e_a_menos():
    # Dell (B×C): extrato -22,90 / contábil -20,90 — despesa MENOR no
    # contábil. Sinal algébrico (contábil-extrato=+2,00) é positivo, mas
    # o rótulo correto é "a menos", porque |20,90| < |22,90|.
    rotulo, magnitude = _rotulo_diferenca_por_magnitude(valor_contabil=-20.90, valor_extrato=-22.90)
    assert rotulo == "R$ 2,00 a menos no contábil"
    assert magnitude == pytest.approx(-2.00)


def test_despesa_igual_sem_diferenca_de_valor():
    rotulo, magnitude = _rotulo_diferenca_por_magnitude(valor_contabil=-7.89, valor_extrato=-7.89)
    assert rotulo == "Sem diferença de valor"
    assert magnitude == 0.0


def test_receita_maior_no_contabil_e_a_mais():
    rotulo, magnitude = _rotulo_diferenca_por_magnitude(valor_contabil=1400.00, valor_extrato=1300.00)
    assert rotulo == "R$ 100,00 a mais no contábil"
    assert magnitude == pytest.approx(100.00)


def test_receita_menor_no_contabil_e_a_menos():
    rotulo, magnitude = _rotulo_diferenca_por_magnitude(valor_contabil=1300.00, valor_extrato=1400.00)
    assert rotulo == "R$ 100,00 a menos no contábil"
    assert magnitude == pytest.approx(-100.00)


def test_receita_igual_sem_diferenca_de_valor():
    rotulo, magnitude = _rotulo_diferenca_por_magnitude(valor_contabil=1300.00, valor_extrato=1300.00)
    assert rotulo == "Sem diferença de valor"
    assert magnitude == 0.0


def test_sinais_opostos_usa_magnitude_nao_o_sinal():
    # Caso extremo: sinais diferentes entre contábil e extrato (não deve
    # acontecer na prática do matching heurístico, mas a fórmula deve
    # continuar comparando magnitudes, não os sinais).
    rotulo, magnitude = _rotulo_diferenca_por_magnitude(valor_contabil=10.00, valor_extrato=-8.00)
    assert rotulo == "R$ 2,00 a mais no contábil"
    assert magnitude == pytest.approx(2.00)


# --- Integração: _linha_match_similaridade com o par completo ---

def _match(ids_extrato, ids_contabil):
    return {"ids_extrato": ids_extrato, "ids_contabil": ids_contabil, "camada": "heuristica", "confianca": 75}


def test_linha_match_similaridade_aguia_branca_e_dell_b_x_c():
    extrato_df = pd.DataFrame({
        "id": [14, 12],
        "data": pd.to_datetime(["2025-06-15", "2025-06-15"]),
        "valor": [-40.30, -22.90],
        "descricao": ["Aguia Branca - Passage - Parcela 6/6", "Dell - Parcela 8/10"],
    })
    contabil_df = pd.DataFrame({
        "id": [13, 11],
        "data": pd.to_datetime(["2025-06-15", "2025-06-16"]),
        "valor": [-43.30, -20.90],
        "descricao": ["Aguia Branca - Passage - Parcela 6/6", "Dell - Parcela 8/10"],
    })

    linha_aguia = _linha_match_similaridade(_match([14], [13]), extrato_df, contabil_df)
    assert linha_aguia["rotulo_diferenca"] == "R$ 3,00 a mais no contábil"
    assert linha_aguia["diferenca"] == pytest.approx(-3.00)  # ponte continua algébrica

    linha_dell = _linha_match_similaridade(_match([12], [11]), extrato_df, contabil_df)
    assert linha_dell["rotulo_diferenca"] == "R$ 2,00 a menos no contábil"
    assert linha_dell["diferenca"] == pytest.approx(2.00)  # ponte continua algébrica


def test_montar_contexto_executivo_nao_muda_ponte_com_o_fix_de_rotulo():
    """A ponte usa a diferença ALGÉBRICA (contábil - extrato), que não
    muda com o fix do rótulo — só a legenda exibida muda. Garante que o
    invariante 'ponte fecha com resíduo 0,00' não foi afetado."""
    extrato_df = pd.DataFrame({
        "id": [1, 2],
        "data": pd.to_datetime(["2025-06-15", "2025-06-16"]),
        "valor": [-40.30, -22.90],
        "descricao": ["Aguia Branca", "Dell"],
    })
    contabil_df = pd.DataFrame({
        "id": [1, 2],
        "data": pd.to_datetime(["2025-06-15", "2025-06-16"]),
        "valor": [-43.30, -20.90],
        "descricao": ["Aguia Branca", "Dell"],
    })
    resultados = {"matches": [_match([1], [1]), _match([2], [2])], "excecoes": []}
    ctx = montar_contexto_executivo(
        resultados_analise=resultados, extrato_df=extrato_df, contabil_df=contabil_df,
        empresa_nome="Empresa QA", analista_nome="Analista QA",
        classificacao_documento="Documento interno", periodo="p", conta_analisada="1",
    )
    assert ctx["ponte"]["fecha"] is True
    assert ctx["ponte"]["residuo"] == pytest.approx(0.0, abs=0.01)
    rotulos = {l["rotulo_diferenca"] for l in ctx["matches_similaridade_linhas"]}
    assert rotulos == {"R$ 3,00 a mais no contábil", "R$ 2,00 a menos no contábil"}
