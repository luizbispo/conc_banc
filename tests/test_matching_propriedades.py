"""
Testes de propriedade do matching exato (issue XCRE-49, Fase 5, item 3).

Por instrução explícita desta rodada: SOMENTE testes, sem alterar
`modules/data_analyzer.py`. As propriedades gerais usam dados
sintéticos com seed fixa e SEM ambiguidade de (valor, data) — isto é
proposital: a última seção deste arquivo demonstra que a camada de
fallback `DataAnalyzer._match_valor_data_exata` NÃO é invariante à
ordem das linhas quando há ambiguidade (duas ou mais linhas do mesmo
lado com valor+data idênticos e menos linhas correspondentes do lado
oposto) — um achado real, registrado e não corrigido/mascarado/
enfraquecido aqui (ver docstring de
`test_matching_ambiguidade_mesma_data_e_valor_depende_da_ordem_das_linhas`).

Dados 100% sintéticos.
"""
import random
from datetime import datetime, timedelta

import pandas as pd
import pytest

from modules.data_analyzer import DataAnalyzer

SEEDS = [7, 42, 123, 2024]


def _normalizar_pares(matches):
    """Representação de um conjunto de matches independente da ORDEM das
    linhas de origem e da ORDEM da lista de matches: cada par é a dupla
    (ids_extrato ordenados, ids_contabil ordenados); o conjunto de pares
    é um frozenset dessas duplas. Duas execuções do matching sobre o
    mesmo conjunto de linhas (em qualquer ordem de entrada) devem
    produzir o mesmo frozenset caso a propriedade de invariância valha."""
    return frozenset(
        (tuple(sorted(m['ids_extrato'])), tuple(sorted(m['ids_contabil'])))
        for m in matches
    )


def _gerar_extrato_contabil_sem_ambiguidade(seed: int, n_pares: int = 12, n_extras_cada_lado: int = 4):
    """Gera extrato e contábil sintéticos com seed fixa: `n_pares`
    transações com valor e data IDÊNTICOS entre os dois lados (para
    serem casadas pelo matching exato, camada de fallback por valor+
    data) e `n_extras_cada_lado` linhas sem par em cada lado (ficam
    como divergência). Cada combinação (valor, data) usada é ÚNICA no
    conjunto inteiro — de propósito, para isolar as propriedades gerais
    do caso de ambiguidade documentado como achado mais abaixo."""
    rng = random.Random(seed)
    base_data = datetime(2024, 1, 1)
    combinacoes_usadas = set()

    def _valor_data_unicos():
        while True:
            valor = round(rng.uniform(10, 5000), 2)
            dias = rng.randint(0, 300)
            chave = (valor, dias)
            if chave not in combinacoes_usadas:
                combinacoes_usadas.add(chave)
                return valor, base_data + timedelta(days=dias)

    linhas_extrato = []
    linhas_contabil = []
    proximo_id_extrato = 1
    proximo_id_contabil = 1

    for i in range(n_pares):
        valor, data = _valor_data_unicos()
        linhas_extrato.append({'id': proximo_id_extrato, 'data': data, 'valor': valor, 'descricao': f"Transacao sintetica {i}"})
        linhas_contabil.append({'id': proximo_id_contabil, 'data': data, 'valor': valor, 'descricao': f"Lancamento sintetico {i}"})
        proximo_id_extrato += 1
        proximo_id_contabil += 1

    for i in range(n_extras_cada_lado):
        valor, data = _valor_data_unicos()
        linhas_extrato.append({'id': proximo_id_extrato, 'data': data, 'valor': valor, 'descricao': f"Extrato sem par {i}"})
        proximo_id_extrato += 1

    for i in range(n_extras_cada_lado):
        valor, data = _valor_data_unicos()
        linhas_contabil.append({'id': proximo_id_contabil, 'data': data, 'valor': valor, 'descricao': f"Lancamento sem par {i}"})
        proximo_id_contabil += 1

    return pd.DataFrame(linhas_extrato), pd.DataFrame(linhas_contabil)


# --- Propriedade 1: invariância à inversão/embaralhamento das linhas ---

@pytest.mark.parametrize("seed", SEEDS)
def test_inversao_da_ordem_das_linhas_nao_muda_o_conjunto_de_pares(seed):
    extrato_df, contabil_df = _gerar_extrato_contabil_sem_ambiguidade(seed)

    resultado_original = DataAnalyzer().matching_exato(extrato_df, contabil_df)
    pares_original = _normalizar_pares(resultado_original['matches'])
    assert len(pares_original) > 0  # o cenário sintético realmente gera pares

    extrato_invertido = extrato_df.iloc[::-1].reset_index(drop=True)
    contabil_invertido = contabil_df.iloc[::-1].reset_index(drop=True)
    resultado_invertido = DataAnalyzer().matching_exato(extrato_invertido, contabil_invertido)
    assert _normalizar_pares(resultado_invertido['matches']) == pares_original

    rng = random.Random(seed * 999)
    idx_extrato = list(range(len(extrato_df)))
    idx_contabil = list(range(len(contabil_df)))
    rng.shuffle(idx_extrato)
    rng.shuffle(idx_contabil)
    extrato_embaralhado = extrato_df.iloc[idx_extrato].reset_index(drop=True)
    contabil_embaralhado = contabil_df.iloc[idx_contabil].reset_index(drop=True)
    resultado_embaralhado = DataAnalyzer().matching_exato(extrato_embaralhado, contabil_embaralhado)
    assert _normalizar_pares(resultado_embaralhado['matches']) == pares_original


# --- Propriedade 2: nenhum lançamento aparece em dois pares ---

@pytest.mark.parametrize("seed", SEEDS)
def test_nenhum_lancamento_aparece_em_dois_pares(seed):
    extrato_df, contabil_df = _gerar_extrato_contabil_sem_ambiguidade(seed)
    resultado = DataAnalyzer().matching_exato(extrato_df, contabil_df)

    ids_extrato_em_pares = []
    ids_contabil_em_pares = []
    for match in resultado['matches']:
        ids_extrato_em_pares.extend(match['ids_extrato'])
        ids_contabil_em_pares.extend(match['ids_contabil'])

    assert len(ids_extrato_em_pares) == len(set(ids_extrato_em_pares)), \
        "um id de extrato apareceu em mais de um par"
    assert len(ids_contabil_em_pares) == len(set(ids_contabil_em_pares)), \
        "um id contábil apareceu em mais de um par"


# --- Propriedade 3: casados + divergentes recompõem o total de cada lado ---

@pytest.mark.parametrize("seed", SEEDS)
def test_soma_casados_mais_divergentes_recompoe_total_de_cada_lado(seed):
    extrato_df, contabil_df = _gerar_extrato_contabil_sem_ambiguidade(seed)
    resultado = DataAnalyzer().matching_exato(extrato_df, contabil_df)

    ids_extrato_casados = set()
    ids_contabil_casados = set()
    for match in resultado['matches']:
        ids_extrato_casados.update(match['ids_extrato'])
        ids_contabil_casados.update(match['ids_contabil'])

    soma_extrato_casados = extrato_df[extrato_df['id'].isin(ids_extrato_casados)]['valor'].sum()
    soma_extrato_divergente = resultado['nao_matchados_extrato']['valor'].sum()
    assert soma_extrato_casados + soma_extrato_divergente == pytest.approx(extrato_df['valor'].sum())

    soma_contabil_casados = contabil_df[contabil_df['id'].isin(ids_contabil_casados)]['valor'].sum()
    soma_contabil_divergente = resultado['nao_matchados_contabil']['valor'].sum()
    assert soma_contabil_casados + soma_contabil_divergente == pytest.approx(contabil_df['valor'].sum())

    # também em contagem de linhas, não só em soma de valores
    assert len(ids_extrato_casados) + len(resultado['nao_matchados_extrato']) == len(extrato_df)
    assert len(ids_contabil_casados) + len(resultado['nao_matchados_contabil']) == len(contabil_df)


# --- Propriedade 4: matching exato é idempotente ---

@pytest.mark.parametrize("seed", SEEDS)
def test_matching_exato_e_idempotente(seed):
    extrato_df, contabil_df = _gerar_extrato_contabil_sem_ambiguidade(seed)

    resultado_1 = DataAnalyzer().matching_exato(extrato_df.copy(), contabil_df.copy())
    resultado_2 = DataAnalyzer().matching_exato(extrato_df.copy(), contabil_df.copy())

    assert _normalizar_pares(resultado_1['matches']) == _normalizar_pares(resultado_2['matches'])
    assert sorted(resultado_1['nao_matchados_extrato']['id'].tolist()) == \
        sorted(resultado_2['nao_matchados_extrato']['id'].tolist())
    assert sorted(resultado_1['nao_matchados_contabil']['id'].tolist()) == \
        sorted(resultado_2['nao_matchados_contabil']['id'].tolist())

    # mesma instância reaproveitada nas duas chamadas: garante que não há
    # estado interno (self.matches_identificados/self.excecoes) vazando
    # de uma chamada para a próxima.
    analyzer_compartilhado = DataAnalyzer()
    resultado_a = analyzer_compartilhado.matching_exato(extrato_df.copy(), contabil_df.copy())
    resultado_b = analyzer_compartilhado.matching_exato(extrato_df.copy(), contabil_df.copy())
    assert _normalizar_pares(resultado_a['matches']) == _normalizar_pares(resultado_b['matches'])


# --- Achado: ambiguidade de (valor, data) quebra a invariância de ordem ---

def test_matching_ambiguidade_mesma_data_e_valor_depende_da_ordem_das_linhas():
    """ACHADO real (não corrigido nesta rodada — instrução explícita do
    item 3 da Fase 5 é registrar, não corrigir/mascarar/enfraquecer).

    `DataAnalyzer._match_valor_data_exata` (modules/data_analyzer.py)
    percorre o extrato em `iterrows()` e, a cada linha casada, remove o
    id contábil consumido do pool de candidatos das próximas linhas.
    Quando há AMBIGUIDADE — mais linhas de um lado do que do outro com o
    MESMO (valor, data) —, qual par exato se forma passa a depender da
    ORDEM em que o extrato é iterado, não do conteúdo. Isso viola a
    propriedade "inverter/embaralhar a ordem das linhas não muda o
    conjunto de pares" (testada acima para o caso SEM ambiguidade).

    Reprodução mínima, determinística, sem necessidade de seed: 2 linhas
    de extrato (id 1 e id 2), mesmo valor (100.00) e mesma data; 1 linha
    contábil (id 10) com o mesmo valor e data. Processando o extrato na
    ordem [1, 2], o id 1 do extrato fica casado com o id 10; invertendo
    para [2, 1], é o id 2 que fica casado com o id 10 — o par muda de
    conteúdo (qual id de extrato) mesmo que a FORMA do resultado (1 par
    formado, 1 id de extrato restando como divergência) seja igual nos
    dois casos.

    Impacto: seed/reprodução acima; não afeta o cenário de referência
    B x C usado no resto do projeto — ele não tem duplicatas de
    (valor, data), e o invariante de 77,8% permanece intacto (ver
    tests/test_tolerancia_referencia_b_x_c.py, checado nesta mesma
    rodada). Também não altera TOTAIS (a soma casados+divergentes por
    lado continua correta em qualquer ordem, só muda QUAL id específico
    é marcado como casado) — mas pode fazer o motivo de conciliação
    exibido para uma linha específica variar entre execuções com o
    mesmo arquivo se a ordem de leitura não for estável. Registrado
    para decisão humana/arquiteto; nenhuma alteração de algoritmo feita
    aqui.
    """
    base_data = datetime(2024, 3, 10)
    extrato_ordem_a = pd.DataFrame([
        {'id': 1, 'data': base_data, 'valor': 100.00, 'descricao': 'Transacao A'},
        {'id': 2, 'data': base_data, 'valor': 100.00, 'descricao': 'Transacao B'},
    ])
    contabil = pd.DataFrame([
        {'id': 10, 'data': base_data, 'valor': 100.00, 'descricao': 'Lancamento unico'},
    ])
    extrato_ordem_b = extrato_ordem_a.iloc[::-1].reset_index(drop=True)

    resultado_a = DataAnalyzer().matching_exato(extrato_ordem_a, contabil)
    resultado_b = DataAnalyzer().matching_exato(extrato_ordem_b, contabil)

    pares_a = _normalizar_pares(resultado_a['matches'])
    pares_b = _normalizar_pares(resultado_b['matches'])

    # a FORMA do resultado é igual nos dois casos (1 par formado)...
    assert len(pares_a) == 1
    assert len(pares_b) == 1
    assert len(resultado_a['nao_matchados_extrato']) == 1
    assert len(resultado_b['nao_matchados_extrato']) == 1

    # ...mas o CONTEÚDO do par (qual id de extrato) muda com a ordem de
    # entrada: esta é a assinatura do achado, não uma propriedade
    # desejável do sistema.
    assert pares_a == frozenset({((1,), (10,))})
    assert pares_b == frozenset({((2,), (10,))})
    assert pares_a != pares_b
