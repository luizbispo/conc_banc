"""
Teste de regressão + sensibilidade para a tolerância de valor do matching
heurístico (issue XCRE-42, decisão do arquiteto sobre o item 4 da Parte
A): a suíte de execução real (E2E) identificou que a tolerância
percentual pura (2%, depois 10% isolado) não reproduz ao mesmo tempo
TODOS os pares de referência do cenário B×C — em especial, um percentual
alto o bastante para aceitar o par "Dell" (8,73% de diferença) também
aceitaria "Pagamento recebido" (7,69%), que deve continuar como mera
sugestão, não como correspondência aceita.

A decisão registrada pelo arquiteto (issue XCRE-42) foi: tolerância
efetiva = MENOR valor entre um percentual (10%) e um teto absoluto fixo
em R$ (5,00). Isso reproduz exatamente os números de referência do
cenário B×C (arquivos reais Exemplos/B_1234490.ofx e C_1234490.ofx,
dados sintéticos): 18×18 transações, 11 matches exatos, 3 heurísticos
aceitos (Águia Branca, Dell, Uber* Trip 0%), 4 divergências bancárias e
4 contábeis somando R$ 1.386,22 e R$ 1.538,93.

Este arquivo cobre dois ângulos:
1. Regressão: a configuração padrão (TOLERANCIA_VALOR_PERCENTUAL_PADRAO +
   TOLERANCIA_VALOR_ABSOLUTA_MAXIMA_PADRAO) reproduz esses números com os
   arquivos REAIS do cenário de referência.
2. Sensibilidade: como o resultado muda variando o percentual e o teto
   absoluto isoladamente — documenta por que os dois limites são
   necessários (nenhum dos dois sozinho resolve todos os pares).
"""
import os

import pandas as pd
import pytest
from ofxparse import OfxParser

from modules.data_analyzer import (
    DataAnalyzer,
    TOLERANCIA_VALOR_PERCENTUAL_PADRAO,
    TOLERANCIA_VALOR_ABSOLUTA_MAXIMA_PADRAO,
)

EXEMPLOS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Exemplos")


def _carregar_ofx(nome_arquivo: str) -> pd.DataFrame:
    caminho = os.path.join(EXEMPLOS_DIR, nome_arquivo)
    with open(caminho, "rb") as f:
        ofx = OfxParser.parse(f)
    linhas = []
    for account in ofx.accounts:
        for transacao in account.statement.transactions:
            linhas.append({
                "data": transacao.date,
                "valor": float(transacao.amount),
                "descricao": transacao.memo or transacao.payee or "",
            })
    df = pd.DataFrame(linhas)
    df["id"] = range(1, len(df) + 1)
    return df


@pytest.fixture(scope="module")
def dados_b_x_c():
    extrato = _carregar_ofx("B_1234490.ofx")
    contabil = _carregar_ofx("C_1234490.ofx")
    return extrato, contabil


def _rodar_matching(extrato, contabil, tolerancia_valor_percentual, tolerancia_valor_absoluta_maxima, similaridade_minima=70):
    analyzer = DataAnalyzer()
    exato = analyzer.matching_exato(extrato, contabil)
    heuristico = analyzer.matching_heuristico(
        extrato, contabil,
        exato["nao_matchados_extrato"], exato["nao_matchados_contabil"],
        tolerancia_dias=2,
        tolerancia_valor_percentual=tolerancia_valor_percentual,
        similaridade_minima=similaridade_minima,
        tolerancia_valor_absoluta_maxima=tolerancia_valor_absoluta_maxima,
    )
    return exato, heuristico


def _somar_nao_matchados(df) -> float:
    return df["valor"].abs().sum()


# --- Regressão: reproduz a referência B×C com o padrão do sistema ---

def test_padrao_do_sistema_reproduz_referencia_b_x_c(dados_b_x_c):
    extrato, contabil = dados_b_x_c
    exato, heuristico = _rodar_matching(
        extrato, contabil,
        TOLERANCIA_VALOR_PERCENTUAL_PADRAO, TOLERANCIA_VALOR_ABSOLUTA_MAXIMA_PADRAO,
    )

    assert len(extrato) == 18
    assert len(contabil) == 18
    assert len(exato["matches"]) == 11
    assert len(heuristico["matches"]) == 3  # Águia Branca, Dell, Uber* Trip (0%)

    total_matches = len(exato["matches"]) + len(heuristico["matches"])
    assert total_matches == 14
    assert total_matches / len(extrato) == pytest.approx(0.7777777777777778)  # 77,8%

    nao_matchados_extrato = heuristico["nao_matchados_extrato"]
    nao_matchados_contabil = heuristico["nao_matchados_contabil"]
    assert len(nao_matchados_extrato) == 4
    assert len(nao_matchados_contabil) == 4

    assert _somar_nao_matchados(nao_matchados_extrato) == pytest.approx(1386.22, abs=0.01)
    assert _somar_nao_matchados(nao_matchados_contabil) == pytest.approx(1538.93, abs=0.01)


def test_padrao_do_sistema_aceita_os_tres_pares_heuristicos_aprovados(dados_b_x_c):
    extrato, contabil = dados_b_x_c
    _, heuristico = _rodar_matching(
        extrato, contabil,
        TOLERANCIA_VALOR_PERCENTUAL_PADRAO, TOLERANCIA_VALOR_ABSOLUTA_MAXIMA_PADRAO,
    )
    descricoes_aceitas = {m["explicacao"] for m in heuristico["matches"]}
    valores_aceitos = sorted(round(m["valor_total"], 2) for m in heuristico["matches"])

    # Águia Branca (R$40,30), Dell (R$22,90) e Uber* Trip com 0% de diferença (R$7,89)
    assert valores_aceitos == [7.89, 22.90, 40.30]
    for explicacao in descricoes_aceitas:
        assert "similaridade" in explicacao.lower()


def test_padrao_do_sistema_rejeita_uber_trip_com_24_porcento_e_pagamento_recebido(dados_b_x_c):
    extrato, contabil = dados_b_x_c
    _, heuristico = _rodar_matching(
        extrato, contabil,
        TOLERANCIA_VALOR_PERCENTUAL_PADRAO, TOLERANCIA_VALOR_ABSOLUTA_MAXIMA_PADRAO,
    )
    valores_extrato_nao_matchados = set(heuristico["nao_matchados_extrato"]["valor"].round(2))

    # Uber* Trip -20,80 (24% de diferença) e Pagamento recebido 1300,00
    # continuam como divergência/sugestão, não como match aceito.
    assert -20.80 in valores_extrato_nao_matchados
    assert 1300.00 in valores_extrato_nao_matchados


# --- Sensibilidade: por que os DOIS limites (percentual E teto absoluto) são necessários ---
#
# Diferenças reais dos pares heurísticos do cenário B×C (para referência
# dos limiares abaixo): Uber* Trip 0% aceito (R$0,00) sempre entra; Águia
# Branca precisa de pelo menos 7,44% (R$3,00/R$40,30); Dell precisa de
# pelo menos 8,73% (R$2,00/R$22,90); Uber* Trip com 24% tem uma diferença
# de exatamente R$5,00 — mesmo valor do teto absoluto padrão, por
# coincidência dos dados de exemplo (ver teste de fronteira abaixo).

@pytest.mark.parametrize("percentual,total_heuristicos_esperado", [
    (2.0, 1),    # padrão ANTERIOR a esta decisão: só Uber* Trip (0%) — Águia Branca/Dell ficam de fora
    (7.0, 1),    # abaixo dos 7,44% que Águia Branca precisa
    (8.0, 2),    # cobre Águia Branca (7,44%), ainda não cobre Dell (8,73%)
    (10.0, 3),   # padrão do sistema: os 3 pares aprovados; teto absoluto barra Pagamento recebido
    (20.0, 3),   # limite máximo do slider da UI: teto absoluto ainda barra Uber* Trip (24%) e Pagamento recebido
])
def test_sensibilidade_percentual_com_teto_absoluto_fixo(dados_b_x_c, percentual, total_heuristicos_esperado):
    extrato, contabil = dados_b_x_c
    _, heuristico = _rodar_matching(extrato, contabil, percentual, TOLERANCIA_VALOR_ABSOLUTA_MAXIMA_PADRAO)
    assert len(heuristico["matches"]) == total_heuristicos_esperado


def test_sensibilidade_fronteira_percentual_alto_o_bastante_iguala_teto_e_diferenca_do_par_rejeitado(dados_b_x_c):
    """Fronteira real do código, não um cenário de produção: a diferença
    do par Uber* Trip (24%) é EXATAMENTE R$5,00 nos dados de exemplo —
    coincide com o teto absoluto padrão. A partir de ~24,04% de
    percentual (bem acima do máximo de 20% exposto no slider da UI), o
    teto passa a ser exatamente igual à diferença do par, e a comparação
    `<=` aceita esse empate. Isso não afeta o comportamento padrão do
    sistema (10%, dentro do range da UI até 20%), mas documenta que o
    teto sozinho, se algum dia igualar uma diferença real, aceita no
    empate — vale considerar `<` estrito se essa coincidência se tornar
    um problema real."""
    extrato, contabil = dados_b_x_c
    _, heuristico = _rodar_matching(extrato, contabil, 25.0, TOLERANCIA_VALOR_ABSOLUTA_MAXIMA_PADRAO)
    valores_aceitos = sorted(round(m["valor_total"], 2) for m in heuristico["matches"])
    assert 20.80 in valores_aceitos  # Uber* Trip (24%) só entra nessa fronteira incomum


def test_sensibilidade_sem_teto_absoluto_aceitaria_pagamento_recebido_indevidamente(dados_b_x_c):
    """Demonstra por que o percentual sozinho NÃO basta: com teto absoluto
    "infinito" (equivalente a removê-lo), um percentual alto o bastante
    para aceitar Dell (8,73%) também aceita Pagamento recebido (7,69%,
    R$100,00 de diferença) — que deve continuar como sugestão."""
    extrato, contabil = dados_b_x_c
    _, heuristico = _rodar_matching(extrato, contabil, TOLERANCIA_VALOR_PERCENTUAL_PADRAO, tolerancia_valor_absoluta_maxima=float("inf"))

    valores_aceitos = sorted(round(m["valor_total"], 2) for m in heuristico["matches"])
    assert 1300.00 in valores_aceitos  # Pagamento recebido indevidamente aceito sem o teto


def test_sensibilidade_teto_absoluto_baixo_rejeita_ate_os_pares_aprovados(dados_b_x_c):
    """Do outro lado: um teto absoluto baixo demais (ex.: R$1,00) rejeita
    até os pares aprovados (Dell difere R$2,00; Águia Branca R$3,00),
    mostrando que o teto sozinho também não basta — precisa do percentual
    generoso o bastante (10%) combinado com um teto que caiba os pares
    aprovados mas não os rejeitados (R$5,00)."""
    extrato, contabil = dados_b_x_c
    _, heuristico = _rodar_matching(extrato, contabil, TOLERANCIA_VALOR_PERCENTUAL_PADRAO, tolerancia_valor_absoluta_maxima=1.00)
    assert len(heuristico["matches"]) == 1  # só Uber* Trip com 0% de diferença sobrevive
