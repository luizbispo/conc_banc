"""Testes do item A2 (issue XCRE-44): pares prováveis apontados pelo
sistema (seção 5a), ponte detalhada linha a linha (seção 5b) e
exposição agrupada por natureza (seção 5c, usada em alertas, manchete/
takeaways e recomendações).

Cenário de referência: fixture sintético B×C (Exemplos/B_1234490.ofx e
C_1234490.ofx), 4 itens em aberto de cada lado:
- extrato: Uber* Trip -20,80 (11/07); Pagamento recebido 1300,00
  (30/06); Uber Uber *Trip Help.U -4,92 (29/06); Salonlin -60,50
  (15/06).
- contábil: Uber* Trip -25,80 (11/07); Pagamento recebido 1400,00
  (30/06); Pagamento recebido 50,63 (15/06); Salonlin -62,50 (18/06).

Valores esperados documentados na issue: pares prováveis do sistema =
Salonlin (dif. 2,00) e Pagamento recebido (dif. 100,00); ponte
detalhada acrescenta Uber* Trip como "hipótese do analista" (dif.
5,00); exposição principal = recebimentos, R$ 150,63 (100,00 do par +
50,63 do item sem par).
"""
import pandas as pd
import pytest

from modules.data_analyzer import identificar_pares_provaveis_similaridade
from modules.report_executivo import (
    ALERTA_DIVERGENCIA_VALOR_MINIMA,
    _calcular_alertas,
    _calcular_exposicao_agrupada,
    _construir_ponte_detalhada,
    _montar_ponte_detalhada,
    _rotulo_diferenca_por_magnitude,
    montar_contexto_executivo,
)


def _df(rows):
    return pd.DataFrame({
        "id": [r[0] for r in rows],
        "data": pd.to_datetime([r[1] for r in rows]),
        "valor": [r[2] for r in rows],
        "descricao": [r[3] for r in rows],
    })


@pytest.fixture
def abertos_b_x_c():
    extrato_aberto = _df([
        (3, "2025-07-11", -20.80, "Uber* Trip"),
        (4, "2025-06-30", 1300.00, "Pagamento recebido"),
        (6, "2025-06-29", -4.92, "Uber Uber *Trip Help.U"),
        (18, "2025-06-15", -60.50, "Mercadolivre*Salonlin - Parcela 8/10"),
    ])
    contabil_aberto = _df([
        (3, "2025-07-11", -25.80, "Uber* Trip"),
        (4, "2025-06-30", 1400.00, "Pagamento recebido"),
        (14, "2025-06-15", 50.63, "Pagamento recebido"),
        (18, "2025-06-18", -62.50, "Mercadolivre*Salonlin - Parcela 8/10"),
    ])
    return extrato_aberto, contabil_aberto


# --- A2a: identificar_pares_provaveis_similaridade (modules.data_analyzer) ---

def test_pares_provaveis_encontra_salonlin_e_pagamento_recebido(abertos_b_x_c):
    extrato_aberto, contabil_aberto = abertos_b_x_c
    pares = identificar_pares_provaveis_similaridade(extrato_aberto, contabil_aberto)

    chaves = {(p["id_extrato"], p["id_contabil"]) for p in pares}
    assert (18, 18) in chaves  # Salonlin
    assert (4, 4) in chaves  # Pagamento recebido 1300/1400

    salonlin = next(p for p in pares if p["id_extrato"] == 18)
    assert salonlin["diferenca_valor"] == pytest.approx(2.00)
    assert salonlin["diferenca_dias"] == 3

    pagamento = next(p for p in pares if p["id_extrato"] == 4)
    assert pagamento["diferenca_valor"] == pytest.approx(100.00)
    assert pagamento["diferenca_dias"] == 0


def test_pares_provaveis_nao_inclui_uber_trip_24_porcento(abertos_b_x_c):
    """A diferença de 24% do par Uber* Trip (-20,80 / -25,80) excede o
    limiar de 10% do sistema — não deve aparecer nos pares prováveis
    (só na ponte detalhada, como hipótese do analista)."""
    extrato_aberto, contabil_aberto = abertos_b_x_c
    pares = identificar_pares_provaveis_similaridade(extrato_aberto, contabil_aberto)
    chaves = {(p["id_extrato"], p["id_contabil"]) for p in pares}
    assert (3, 3) not in chaves


def test_pares_provaveis_nao_inclui_item_sem_candidato(abertos_b_x_c):
    """O item contábil 'Pagamento recebido' de 50,63 (15/06) não tem
    nenhum candidato dentro dos limiares (nem por valor, nem por data) —
    deve seguir como item sem par, não como par provável forçado."""
    extrato_aberto, contabil_aberto = abertos_b_x_c
    pares = identificar_pares_provaveis_similaridade(extrato_aberto, contabil_aberto)
    ids_contabil_em_pares = {p["id_contabil"] for p in pares}
    assert 14 not in ids_contabil_em_pares


def _par_sintetico(diff_valor_percentual, diff_dias, mesma_descricao=True):
    valor_extrato = 100.0
    valor_contabil = round(valor_extrato * (1 + diff_valor_percentual / 100), 2)
    descricao_extrato = "Fornecedor Teste Ltda"
    descricao_contabil = descricao_extrato if mesma_descricao else "Zzz Zzz Zzz Zzz Zzz"
    extrato_aberto = _df([(1, "2025-06-15", valor_extrato, descricao_extrato)])
    contabil_aberto = _df([(1, f"2025-06-{15 + diff_dias:02d}", valor_contabil, descricao_contabil)])
    return extrato_aberto, contabil_aberto


@pytest.mark.parametrize("diff_valor_percentual,esperado", [(10.0, True), (10.01, False)])
def test_pares_provaveis_respeita_limiar_de_valor(diff_valor_percentual, esperado):
    extrato_aberto, contabil_aberto = _par_sintetico(diff_valor_percentual, diff_dias=0)
    pares = identificar_pares_provaveis_similaridade(
        extrato_aberto, contabil_aberto,
        diff_valor_percentual_maximo=10.0, diff_dias_maximo=5, similaridade_minima=40.0,
    )
    assert len(pares) == (1 if esperado else 0)


@pytest.mark.parametrize("diff_dias,esperado", [(5, True), (6, False)])
def test_pares_provaveis_respeita_limiar_de_dias(diff_dias, esperado):
    extrato_aberto, contabil_aberto = _par_sintetico(diff_valor_percentual=0.0, diff_dias=diff_dias)
    pares = identificar_pares_provaveis_similaridade(
        extrato_aberto, contabil_aberto,
        diff_valor_percentual_maximo=10.0, diff_dias_maximo=5, similaridade_minima=40.0,
    )
    assert len(pares) == (1 if esperado else 0)


def test_pares_provaveis_respeita_limiar_de_similaridade():
    # Mesmo valor e data, mas descrições sem nenhuma semelhança textual:
    # similaridade real (SequenceMatcher) fica bem abaixo de 40% — deve
    # ser rejeitado mesmo com valor/data idênticos.
    extrato_aberto, contabil_aberto = _par_sintetico(diff_valor_percentual=0.0, diff_dias=0, mesma_descricao=False)
    pares = identificar_pares_provaveis_similaridade(
        extrato_aberto, contabil_aberto,
        diff_valor_percentual_maximo=10.0, diff_dias_maximo=5, similaridade_minima=40.0,
    )
    assert len(pares) == 0

    # As mesmas duas linhas, mas com o limiar de similaridade desligado
    # (0%), devem virar um par — confirma que o filtro acima era mesmo o
    # de similaridade, não outro.
    pares_sem_filtro_texto = identificar_pares_provaveis_similaridade(
        extrato_aberto, contabil_aberto,
        diff_valor_percentual_maximo=10.0, diff_dias_maximo=5, similaridade_minima=0.0,
    )
    assert len(pares_sem_filtro_texto) == 1


# --- A2b: _construir_ponte_detalhada / _montar_ponte_detalhada ---

def test_ponte_detalhada_rotula_uber_trip_como_hipotese_do_analista(abertos_b_x_c):
    extrato_aberto, contabil_aberto = abertos_b_x_c
    pares_provaveis = identificar_pares_provaveis_similaridade(extrato_aberto, contabil_aberto)
    linhas_pares, nao_pareados_extrato, nao_pareados_contabil = _construir_ponte_detalhada(
        extrato_aberto, contabil_aberto, pares_provaveis
    )

    por_descricao = {l["descricao"]: l for l in linhas_pares}
    assert "Uber* Trip" in por_descricao
    assert por_descricao["Uber* Trip"]["origem"] == "hipotese"
    assert por_descricao["Uber* Trip"]["origem_label"] == "Hipótese do analista"
    assert por_descricao["Uber* Trip"]["rotulo_diferenca"] == "R$ 5,00 a mais no contábil"

    assert por_descricao["Pagamento recebido"]["origem"] == "sistema"
    assert por_descricao["Mercadolivre*Salonlin - Parcela 8/10"]["origem"] == "sistema"

    assert len(linhas_pares) == 3
    assert len(nao_pareados_extrato) == 1
    assert len(nao_pareados_contabil) == 1
    assert nao_pareados_extrato.iloc[0]["descricao"] == "Uber Uber *Trip Help.U"
    assert nao_pareados_contabil.iloc[0]["valor"] == pytest.approx(50.63)


def test_ponte_detalhada_pareamento_e_exclusivo_cada_id_usado_uma_vez(abertos_b_x_c):
    """Nenhum id de extrato ou contábil pode aparecer em mais de um par
    da ponte detalhada — mesmo que fosse elegível para mais de um
    candidato (não é o caso do B×C, mas a garantia estrutural importa)."""
    extrato_aberto, contabil_aberto = abertos_b_x_c
    pares_provaveis = identificar_pares_provaveis_similaridade(extrato_aberto, contabil_aberto)
    linhas_pares, nao_pareados_extrato, nao_pareados_contabil = _construir_ponte_detalhada(
        extrato_aberto, contabil_aberto, pares_provaveis
    )
    ids_extrato_usados = [3, 4, 18]  # Uber Trip, Pagamento recebido, Salonlin
    ids_contabil_usados = [3, 4, 18]
    todos_ids_extrato_nas_linhas = []
    todos_ids_extrato_nas_linhas += list(nao_pareados_extrato["id"])
    assert sorted(todos_ids_extrato_nas_linhas + ids_extrato_usados) == sorted(extrato_aberto["id"].tolist())
    todos_ids_contabil_nas_linhas = list(nao_pareados_contabil["id"])
    assert sorted(todos_ids_contabil_nas_linhas + ids_contabil_usados) == sorted(contabil_aberto["id"].tolist())


def test_ponte_detalhada_fecha_com_residuo_zero_no_b_x_c(abertos_b_x_c):
    extrato_aberto, contabil_aberto = abertos_b_x_c
    pares_provaveis = identificar_pares_provaveis_similaridade(extrato_aberto, contabil_aberto)
    linhas_pares, nao_pareados_extrato, nao_pareados_contabil = _construir_ponte_detalhada(
        extrato_aberto, contabil_aberto, pares_provaveis
    )
    liquido_contabil_aberto = float(contabil_aberto["valor"].sum())
    liquido_extrato_aberto = float(extrato_aberto["valor"].sum())
    ponte_detalhada = _montar_ponte_detalhada(
        linhas_pares, nao_pareados_extrato, nao_pareados_contabil,
        liquido_contabil_aberto, liquido_extrato_aberto,
    )
    assert ponte_detalhada["fecha"] is True
    assert ponte_detalhada["residuo"] == pytest.approx(0.0, abs=0.01)
    assert ponte_detalhada["total_detalhado_fmt"] == ponte_detalhada["alvo_aberto_fmt"]


def test_ponte_detalhada_mostra_residuo_quando_nao_fecha():
    """Se a decomposição não bater (dado sintético inconsistente), o
    resíduo deve aparecer — nunca ser escondido, no mesmo espírito do
    CT-F3-07 aplicado à ponte compacta."""
    linhas_pares = [{"diferenca": 10.0}]
    nao_pareados_extrato = pd.DataFrame({"valor": [5.0]})
    nao_pareados_contabil = pd.DataFrame({"valor": [0.0]})
    ponte_detalhada = _montar_ponte_detalhada(
        linhas_pares, nao_pareados_extrato, nao_pareados_contabil,
        liquido_contabil_aberto=999.0, liquido_extrato_aberto=0.0,
    )
    assert ponte_detalhada["fecha"] is False
    assert ponte_detalhada["residuo_fmt"] != "R$ 0,00"


# --- A2c: _calcular_exposicao_agrupada ---

def test_exposicao_agrupada_principal_e_recebimentos_150_63_no_b_x_c(abertos_b_x_c):
    extrato_aberto, contabil_aberto = abertos_b_x_c
    pares_provaveis = identificar_pares_provaveis_similaridade(extrato_aberto, contabil_aberto)
    linhas_pares, nao_pareados_extrato, nao_pareados_contabil = _construir_ponte_detalhada(
        extrato_aberto, contabil_aberto, pares_provaveis
    )
    exposicao = _calcular_exposicao_agrupada(linhas_pares, nao_pareados_extrato, nao_pareados_contabil)

    assert exposicao["natureza_principal"] == "recebimentos"
    assert exposicao["total_principal"] == pytest.approx(150.63)
    assert exposicao["total_principal_fmt"] == "R$ 150,63"
    assert exposicao["totais"]["pagamentos"] == pytest.approx(11.92)

    referencias_recebimentos = sorted(
        item["valor_referencia_fmt"] for item in exposicao["buckets"]["recebimentos"]
    )
    assert referencias_recebimentos == ["R$ 1.400,00", "R$ 50,63"]


# --- Integração completa via montar_contexto_executivo ---

def test_contexto_completo_b_x_c_bate_com_a_issue():
    from ofxparse import OfxParser
    import os as _os

    exemplos_dir = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "Exemplos")

    def carregar(nome):
        with open(_os.path.join(exemplos_dir, nome), "rb") as f:
            ofx = OfxParser.parse(f)
        linhas = []
        for account in ofx.accounts:
            for t in account.statement.transactions:
                linhas.append({"data": t.date, "valor": float(t.amount), "descricao": t.memo or t.payee or ""})
        df = pd.DataFrame(linhas)
        df["id"] = range(1, len(df) + 1)
        return df

    from modules.data_analyzer import DataAnalyzer, TOLERANCIA_VALOR_PERCENTUAL_PADRAO, TOLERANCIA_VALOR_ABSOLUTA_MAXIMA_PADRAO

    extrato = carregar("B_1234490.ofx")
    contabil = carregar("C_1234490.ofx")
    analyzer = DataAnalyzer()
    exato = analyzer.matching_exato(extrato, contabil)
    heuristico = analyzer.matching_heuristico(
        extrato, contabil, exato["nao_matchados_extrato"], exato["nao_matchados_contabil"],
        tolerancia_dias=2, tolerancia_valor_percentual=TOLERANCIA_VALOR_PERCENTUAL_PADRAO,
        similaridade_minima=70, tolerancia_valor_absoluta_maxima=TOLERANCIA_VALOR_ABSOLUTA_MAXIMA_PADRAO,
    )
    resultados = {"matches": exato["matches"] + heuristico["matches"], "excecoes": []}

    ctx = montar_contexto_executivo(
        resultados_analise=resultados, extrato_df=extrato, contabil_df=contabil,
        empresa_nome="Empresa QA", analista_nome="Analista QA",
        classificacao_documento="Documento interno", periodo="15/06/2025 a 16/07/2025",
        conta_analisada="1234490",
    )

    # Invariantes B×C não podem mudar.
    assert ctx["total_matches"] == 14
    assert ctx["cobertura_sistema"] == pytest.approx(77.77777777777779)
    assert ctx["cobertura_efetiva"] == pytest.approx(61.111111111111114)
    assert ctx["total_extrato_aberto"] == 4
    assert ctx["total_contabil_aberto"] == 4
    assert ctx["ponte"]["fecha"] is True
    assert ctx["ponte"]["residuo"] == pytest.approx(0.0, abs=0.01)

    # A2a: pares prováveis do sistema.
    descricoes_pares_provaveis = {p["descricao"] for p in ctx["pares_provaveis_linhas"]}
    assert descricoes_pares_provaveis == {"Pagamento recebido", "Mercadolivre*Salonlin - Parcela 8/10"}

    # A2b: ponte detalhada.
    assert ctx["ponte_detalhada"]["fecha"] is True
    assert ctx["ponte_detalhada"]["residuo"] == pytest.approx(0.0, abs=0.01)
    origens = {l["descricao"]: l["origem"] for l in ctx["ponte_detalhada"]["linhas_pares"]}
    assert origens["Uber* Trip"] == "hipotese"

    # A2c: exposição agrupada.
    assert ctx["exposicao"]["natureza_principal"] == "recebimentos"
    assert ctx["exposicao"]["total_principal_fmt"] == "R$ 150,63"

    # Alerta crítico (revisado): agora baseado na exposição JÁ AGRUPADA,
    # não mais no maior item bruto isolado (que era R$1.400,00, acima do
    # limiar). A exposição agrupada do B×C é R$150,63, abaixo do limiar
    # de R$500,00 — o alerta crítico não deve disparar (o par que
    # explicava R$1.400,00 já está refletido, com o valor real de
    # R$100,00, na ponte detalhada).
    titulos_alertas = [a["titulo"] for a in ctx["alertas"]]
    assert not any(a["severidade"] == "critico" for a in ctx["alertas"])
    assert not any("1.400,00" in t for t in titulos_alertas)

    # Recomendação de prioridade alta esperada literalmente pela issue.
    recomendacao_alta = next(r for r in ctx["recomendacoes"] if r["prioridade"] == "alta")
    assert recomendacao_alta["titulo"] == "Investigar os recebimentos de R$ 1.400,00 e R$ 50,63"
    assert recomendacao_alta["impacto"] == "R$ 150,63"

    # Manchete/takeaways usam a exposição agrupada (issue: "Principal
    # exposição: recebimentos, R$ 150,63").
    titulos_takeaways = [t["titulo"] for t in ctx["takeaways"]]
    assert "Principal exposição: recebimentos, R$ 150,63" in titulos_takeaways


def test_alerta_critico_dispara_quando_exposicao_agrupada_excede_limiar():
    """Complementa o teste do B×C (onde a exposição fica abaixo do
    limiar e o alerta NÃO dispara): com uma exposição agrupada acima de
    ALERTA_DIVERGENCIA_VALOR_MINIMA, o alerta crítico deve aparecer,
    citando a natureza e o valor agrupado."""
    exposicao_alta = {
        "natureza_principal": "pagamentos",
        "totais": {"pagamentos": ALERTA_DIVERGENCIA_VALOR_MINIMA + 1.0, "recebimentos": 0.0},
        "total_principal_fmt": "R$ 501,00",
    }
    alertas = _calcular_alertas(
        extrato_df=pd.DataFrame(), contabil_df=pd.DataFrame(),
        cobertura_sistema=100.0, cobertura_efetiva=100.0,
        empresa_nome="Empresa QA", analista_nome="Analista QA",
        extrato_aberto=pd.DataFrame(columns=["id", "data", "valor", "descricao"]),
        contabil_aberto=pd.DataFrame(columns=["id", "data", "valor", "descricao"]),
        exposicao=exposicao_alta,
    )
    criticos = [a for a in alertas if a["severidade"] == "critico"]
    assert len(criticos) == 1
    assert "pagamentos" in criticos[0]["titulo"]
    assert "501,00" in criticos[0]["titulo"]


def test_natureza_e_rotulo_helpers_cobrem_credito_e_debito():
    rotulo, magnitude = _rotulo_diferenca_por_magnitude(valor_contabil=100.0, valor_extrato=90.0)
    assert magnitude == pytest.approx(10.0)
    assert "a mais" in rotulo
