"""
Testes de propriedade do matching exato (issue XCRE-49/XCRE-50, Fase 5
e Fase 5b, item 3/2).

As propriedades gerais usam dados sintéticos com seed fixa e SEM
ambiguidade de (valor, data) — isto é proposital: a última seção deste
arquivo cobre o caso COM ambiguidade (duas ou mais linhas do mesmo
lado com valor+data idênticos e menos linhas correspondentes do lado
oposto).

Achado da Fase 5 (registrado, não corrigido naquela rodada): a camada
de fallback `DataAnalyzer._match_valor_data_exata` processava o
extrato na ordem física de chegada das linhas (`iterrows()`), então,
havendo ambiguidade, o par formado dependia de QUAL linha chegava
primeiro, não do conteúdo.

Correção da Fase 5b (item 2, XCRE-50): `_match_valor_data_exata` agora
ordena as linhas do extrato por uma CHAVE CANÔNICA de conteúdo
(descrição normalizada, depois id só como último desempate) antes de
processá-las, então o par escolhido passa a ser função do conteúdo das
linhas, não da ordem física em que chegam — sem alterar nenhum
critério de valor/data do matching. Os testes abaixo cobrem as duas
ordens (original e invertida) e confirmam que o resultado agora é
idêntico nos dois casos.

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


# --- Correção: ambiguidade de (valor, data) resolvida por chave canônica ---

def test_matching_ambiguidade_mesma_data_e_valor_e_deterministico_independente_da_ordem():
    """Regressão da correção do item 2 (Fase 5b, XCRE-50): antes, o par
    formado em caso de ambiguidade de (valor, data) dependia da ORDEM
    física das linhas do extrato (ver histórico no docstring do módulo
    e commit da Fase 5). Agora `_match_valor_data_exata` ordena o
    extrato por uma chave canônica de conteúdo (descrição normalizada,
    depois id) antes de processá-lo, então o mesmo par deve se formar
    nas duas ordens.

    Reprodução mínima, determinística, sem necessidade de seed: 2
    linhas de extrato (id 1 "Transacao A", id 2 "Transacao B"), mesmo
    valor (100.00) e mesma data; 1 linha contábil (id 10) com o mesmo
    valor e data. "transacao a" < "transacao b" na ordenação canônica
    (case-insensitive), então o id 1 do extrato deve casar com o id 10
    em QUALQUER ordem de entrada — inclusive com as linhas invertidas.

    Impacto no cenário de referência B x C: nenhum — o cenário de
    referência não tem duplicatas de (valor, data), e o invariante de
    77,8% permanece intacto (ver
    tests/test_tolerancia_referencia_b_x_c.py, checado nesta mesma
    rodada). Os totais por lado (casados + divergentes) também não
    mudam com a correção, só a identidade do id específico que fica
    marcado como casado deixa de depender da ordem física de chegada.
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

    assert len(pares_a) == 1
    assert len(pares_b) == 1
    assert len(resultado_a['nao_matchados_extrato']) == 1
    assert len(resultado_b['nao_matchados_extrato']) == 1

    # o par escolhido agora é o MESMO nas duas ordens (id 1, "Transacao
    # A", vence por ordenação canônica de descrição) — a propriedade
    # de invariância à ordem, antes violada, agora vale também para o
    # caso ambíguo.
    assert pares_a == frozenset({((1,), (10,))})
    assert pares_b == frozenset({((1,), (10,))})
    assert pares_a == pares_b

    # o id que sobra como divergência bancária também é o mesmo nos
    # dois casos (id 2, "Transacao B").
    assert resultado_a['nao_matchados_extrato']['id'].tolist() == [2]
    assert resultado_b['nao_matchados_extrato']['id'].tolist() == [2]


def test_desempate_usa_descricao_normalizada_e_nao_apenas_o_id_ou_a_posicao():
    """A chave canônica precisa ser estável mesmo quando o id "menor"
    não é o vencedor por descrição — prova de que o desempate é por
    CONTEÚDO (descrição normalizada), não um alias disfarçado de "menor
    id" nem da posição física da linha.

    Aqui o id 1 tem descrição "Zebra" e o id 2 tem descrição "Abacaxi";
    "abacaxi" < "zebra", então o id 2 deve vencer em QUALQUER ordem de
    entrada, mesmo sendo o id numericamente maior."""
    base_data = datetime(2024, 5, 20)
    extrato_ordem_a = pd.DataFrame([
        {'id': 1, 'data': base_data, 'valor': 250.00, 'descricao': 'Zebra'},
        {'id': 2, 'data': base_data, 'valor': 250.00, 'descricao': 'Abacaxi'},
    ])
    contabil = pd.DataFrame([
        {'id': 20, 'data': base_data, 'valor': 250.00, 'descricao': 'Lancamento unico'},
    ])
    extrato_ordem_b = extrato_ordem_a.iloc[::-1].reset_index(drop=True)

    resultado_a = DataAnalyzer().matching_exato(extrato_ordem_a, contabil)
    resultado_b = DataAnalyzer().matching_exato(extrato_ordem_b, contabil)

    pares_a = _normalizar_pares(resultado_a['matches'])
    pares_b = _normalizar_pares(resultado_b['matches'])

    assert pares_a == frozenset({((2,), (20,))})
    assert pares_b == frozenset({((2,), (20,))})
    assert pares_a == pares_b
