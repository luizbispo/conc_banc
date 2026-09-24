"""Testes do item A3 (issue XCRE-44): helper único de pluralização,
usado no módulo report_executivo e no template Jinja. Cobre 0, 1 e N,
inclusive formas irregulares (item -> itens), e garante que o PDF
gerado não contém mais os placeholders "(s)"/"(ns)"/"(es)".
"""
import pandas as pd
import pytest

from modules.report_executivo import (
    _env,
    _fmt_contagem,
    montar_contexto_executivo,
    pluralizar,
)


# --- Unidade: pluralizar / _fmt_contagem ---

@pytest.mark.parametrize("quantidade,esperado", [(0, "casamentos"), (1, "casamento"), (2, "casamentos"), (11, "casamentos")])
def test_pluralizar_forma_regular(quantidade, esperado):
    assert pluralizar(quantidade, "casamento") == esperado


@pytest.mark.parametrize("quantidade,esperado", [(0, "itens"), (1, "item"), (8, "itens")])
def test_pluralizar_forma_irregular(quantidade, esperado):
    assert pluralizar(quantidade, "item", "itens") == esperado


@pytest.mark.parametrize("quantidade,esperado", [(0, "0 itens"), (1, "1 item"), (8, "8 itens")])
def test_fmt_contagem(quantidade, esperado):
    assert _fmt_contagem(quantidade, "item", "itens") == esperado


def test_pluralizar_exposto_como_global_do_jinja():
    assert _env.globals["pluralizar"] is pluralizar


# --- Integração: nenhum placeholder "(s)/(ns)/(es)" sobrevive no contexto/HTML ---

def _contexto_com(n_exatos, n_similaridade, n_extrato_aberto, n_contabil_aberto):
    linhas = []
    ids_extrato, ids_contabil = [], []
    next_id = 1
    matches = []
    for _ in range(n_exatos):
        linhas.append((next_id, "2025-06-15", -10.0, "Exato"))
        matches.append({"ids_extrato": [next_id], "ids_contabil": [next_id], "camada": "exata", "confianca": 100})
        next_id += 1
    for _ in range(n_similaridade):
        linhas.append((next_id, "2025-06-16", -20.0, "Similar"))
        matches.append({"ids_extrato": [next_id], "ids_contabil": [next_id], "camada": "heuristica", "confianca": 80})
        next_id += 1
    ids_extrato_aberto = []
    for _ in range(n_extrato_aberto):
        linhas.append((next_id, "2025-06-17", -5.0, "Aberto extrato"))
        ids_extrato_aberto.append(next_id)
        next_id += 1
    ids_contabil_aberto = []
    for _ in range(n_contabil_aberto):
        linhas.append((next_id, "2025-06-18", 5.0, "Aberto contábil"))
        ids_contabil_aberto.append(next_id)
        next_id += 1

    todos_ids = [l[0] for l in linhas]
    extrato_ids = [i for i in todos_ids if i not in ids_contabil_aberto]
    contabil_ids = [i for i in todos_ids if i not in ids_extrato_aberto]

    def montar_df(ids):
        rows = [l for l in linhas if l[0] in ids]
        return pd.DataFrame({
            "id": [r[0] for r in rows],
            "data": pd.to_datetime([r[1] for r in rows]),
            "valor": [r[2] for r in rows],
            "descricao": [r[3] for r in rows],
        })

    extrato_df = montar_df(extrato_ids)
    contabil_df = montar_df(contabil_ids)
    resultados = {"matches": matches, "excecoes": []}
    return montar_contexto_executivo(
        resultados_analise=resultados, extrato_df=extrato_df, contabil_df=contabil_df,
        empresa_nome="Empresa QA", analista_nome="Analista QA",
        classificacao_documento="Documento interno", periodo="p", conta_analisada="1",
    )


@pytest.mark.parametrize("n_exatos,n_similaridade,n_aberto_extrato,n_aberto_contabil", [
    (1, 0, 0, 0),  # singular em tudo que dá pra singularizar
    (0, 0, 0, 0),  # zero casamentos, zero abertos
    (3, 2, 1, 4),  # plural misto
])
def test_headline_e_takeaways_sem_placeholder_de_plural(n_exatos, n_similaridade, n_aberto_extrato, n_aberto_contabil):
    if n_exatos + n_similaridade + n_aberto_extrato + n_aberto_contabil == 0:
        pytest.skip("gerar_relatorio_executivo exige DataFrames não vazios")
    ctx = _contexto_com(n_exatos, n_similaridade, n_aberto_extrato, n_aberto_contabil)
    textos = [ctx["headline"]] + [t["titulo"] + t["texto"] for t in ctx["takeaways"]]
    for texto in textos:
        assert "(s)" not in texto
        assert "(ns)" not in texto
        assert "(es)" not in texto


def test_headline_singular_quando_ha_exatamente_um_de_cada():
    ctx = _contexto_com(1, 0, 0, 0)
    assert "1 casamento é exato" in ctx["headline"]


def test_template_renderizado_sem_nenhum_placeholder_de_plural():
    ctx = _contexto_com(3, 2, 1, 4)
    template = _env.get_template("relatorio_executivo.html.j2")
    html = template.render(**ctx)
    assert "(s)" not in html
    assert "(ns)" not in html
    assert "(es)" not in html
