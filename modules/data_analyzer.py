# modules/data_analyzer.py
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import re
from difflib import SequenceMatcher
import logging
from typing import Dict, List, Tuple, Any

# Configurar logging apenas para erros
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

# ADICIONAR IMPORT DO NOVO MODULO
try:
    from modules.ai_matcher import matching_ia_avancado
except ImportError:
    def matching_ia_avancado(*args, **kwargs):
        return {'matches': [], 'matches_semanticos': 0, 'matches_temporais': 0, 
                'matches_agrupados': 0, 'matches_entidades': 0}

# Tolerância padrão de valor para o matching heurístico: MENOR valor entre
# um percentual do valor da transação bancária e um teto absoluto em R$
# (não mais derivada da média do lote — ver histórico de correção em
# pages/analise_dados.py). Documentado aqui como a fonte única de verdade
# do padrão; ambos os valores podem ser sobrepostos por chamador (ex.: o
# slider "Tolerância de Valor (%)" da página de análise).
#
# Por que os DOIS limites, e não só um percentual: um percentual sozinho
# trata igualmente uma diferença de R$2,00 numa transação de R$22,90
# (8,7%) e uma diferença de R$100,00 numa transação de R$1.300,00
# (7,7%) — mas a segunda é uma divergência muito mais material em termos
# absolutos, e o cenário de referência B×C (ver
# tests/test_data_analyzer.py::test_tolerancia_reproduz_referencia_b_x_c)
# exige aceitar a primeira como match heurístico (par "Dell") e manter a
# segunda como mera sugestão, não como correspondência aceita (par
# "Pagamento recebido"). O teto absoluto é o que separa os dois casos; o
# percentual sozinho não consegue.
#
# Valores escolhidos para satisfazer TODOS os pares de referência do
# cenário B×C ao mesmo tempo (ver teste de sensibilidade acima):
# aceitar Águia Branca (diferença R$3,00 / 7,44%) e Dell (R$2,00 / 8,73%);
# rejeitar Uber* Trip com 24% (R$5,00 / 24,04%) e Pagamento recebido
# (R$100,00 / 7,69% — dentro do percentual, mas muito acima do teto
# absoluto).
TOLERANCIA_VALOR_PERCENTUAL_PADRAO = 10.0
TOLERANCIA_VALOR_ABSOLUTA_MAXIMA_PADRAO = 5.00  # R$


class DataAnalyzer:
    def __init__(self):
        self.matches_identificados = []
        self.excecoes = []
        self.audit_trail = []
        
    def _garantir_coluna_id(self, df: pd.DataFrame, nome_df: str = "DataFrame") -> pd.DataFrame:
        """Garante que o DataFrame tenha coluna 'id'"""
        df = df.copy()
        if 'id' not in df.columns:
            df['id'] = range(1, len(df) + 1)
        return df

    def matching_exato(self, extrato_df: pd.DataFrame, contabil_df: pd.DataFrame) -> Dict:
        """Camada 1: Matching exato usando identificadores únicos"""
        extrato_df = self._garantir_coluna_id(extrato_df, "extrato_df")
        contabil_df = self._garantir_coluna_id(contabil_df, "contabil_df")
        
        matches = []
        extrato_match_ids = set()
        contabil_match_ids = set()
        
        extrato_df = self._normalizar_identificadores(extrato_df)
        contabil_df = self._normalizar_identificadores(contabil_df)
        
        # 1. Matching por TXID PIX
        matches_txid = self._match_por_txid(extrato_df, contabil_df)
        matches.extend(matches_txid)
        
        # 2. Matching por NSU (cartões)
        matches_nsu = self._match_por_nsu(extrato_df, contabil_df)
        matches.extend(matches_nsu)
        
        # 3. Matching por Nosso Número (boletos)
        matches_nosso_numero = self._match_por_nosso_numero(extrato_df, contabil_df)
        matches.extend(matches_nosso_numero)
        
        # 4. Matching por valor e data exata (fallback)
        matches_valor_exato = self._match_valor_data_exata(extrato_df, contabil_df, 
                                                          extrato_match_ids, contabil_match_ids)
        matches.extend(matches_valor_exato)
        
        # Atualizar IDs já matchados
        for match in matches:
            extrato_match_ids.update(match['ids_extrato'])
            contabil_match_ids.update(match['ids_contabil'])
        
        # Identificar não matchados
        nao_matchados_extrato = extrato_df[~extrato_df['id'].isin(extrato_match_ids)]
        nao_matchados_contabil = contabil_df[~contabil_df['id'].isin(contabil_match_ids)]
        
        return {
            'matches': matches,
            'nao_matchados_extrato': nao_matchados_extrato,
            'nao_matchados_contabil': nao_matchados_contabil
        }
    
    def matching_heuristico(self, extrato_df: pd.DataFrame, contabil_df: pd.DataFrame,
                          nao_matchados_extrato: pd.DataFrame, nao_matchados_contabil: pd.DataFrame,
                          tolerancia_dias: int = 2,
                          tolerancia_valor_percentual: float = TOLERANCIA_VALOR_PERCENTUAL_PADRAO,
                          similaridade_minima: int = 80,
                          tolerancia_valor_absoluta_maxima: float = TOLERANCIA_VALOR_ABSOLUTA_MAXIMA_PADRAO) -> Dict:
        """Camada 2: Matching heurístico com tolerâncias.

        A tolerância de valor efetiva de cada par é o MENOR entre
        tolerancia_valor_percentual (% do valor da transação bancária) e
        tolerancia_valor_absoluta_maxima (teto fixo em R$) — não mais um
        valor absoluto derivado da média do lote, nem um percentual puro
        (ver TOLERANCIA_VALOR_ABSOLUTA_MAXIMA_PADRAO para o porquê do
        teto). Cada par é comparado contra sua PRÓPRIA tolerância, então
        o resultado não muda dependendo de quais outras transações estão
        no mesmo lote."""
        matches = []
        extrato_match_ids = set()
        contabil_match_ids = set()

        # 1. Matching 1:1 com tolerâncias
        matches_1_1 = self._match_heuristico_1_1(
            nao_matchados_extrato, nao_matchados_contabil,
            tolerancia_dias, tolerancia_valor_percentual, similaridade_minima,
            tolerancia_valor_absoluta_maxima
        )
        matches.extend(matches_1_1)

        # 2. Matching 1:N (parcelamentos)
        matches_1_n = self._match_1_n(
            nao_matchados_extrato, nao_matchados_contabil,
            tolerancia_dias, tolerancia_valor_percentual
        )
        matches.extend(matches_1_n)

        # 3. Matching N:1 (consolidações)
        matches_n_1 = self._match_n_1(
            nao_matchados_extrato, nao_matchados_contabil,
            tolerancia_dias, tolerancia_valor_percentual
        )
        matches.extend(matches_n_1)
        
        # Atualizar IDs matchados
        for match in matches:
            extrato_match_ids.update(match['ids_extrato'])
            contabil_match_ids.update(match['ids_contabil'])
        
        # Identificar não matchados restantes
        nao_matchados_extrato_final = nao_matchados_extrato[~nao_matchados_extrato['id'].isin(extrato_match_ids)]
        nao_matchados_contabil_final = nao_matchados_contabil[~nao_matchados_contabil['id'].isin(contabil_match_ids)]
        
        return {
            'matches': matches,
            'nao_matchados_extrato': nao_matchados_extrato_final,
            'nao_matchados_contabil': nao_matchados_contabil_final
        }
    
    def matching_ia(self, extrato_df: pd.DataFrame, contabil_df: pd.DataFrame,
                   nao_matchados_extrato: pd.DataFrame, nao_matchados_contabil: pd.DataFrame) -> Dict:
        """Camada 3: Matching com IA para casos complexos"""
        resultados_ia = matching_ia_avancado(
            extrato_df, contabil_df, nao_matchados_extrato, nao_matchados_contabil
        )
        
        matches = resultados_ia['matches']
        
        # Identificar exceções nos não matchados restantes
        extrato_match_ids = set()
        contabil_match_ids = set()
        
        for match in matches:
            extrato_match_ids.update(match['ids_extrato'])
            contabil_match_ids.update(match['ids_contabil'])
        
        nao_matchados_extrato_final = nao_matchados_extrato[~nao_matchados_extrato['id'].isin(extrato_match_ids)]
        nao_matchados_contabil_final = nao_matchados_contabil[~nao_matchados_contabil['id'].isin(contabil_match_ids)]
        
        excecoes = self._identificar_excecoes_melhorado(
            nao_matchados_extrato_final, nao_matchados_contabil_final
        )
        
        return {
            'matches': matches,
            'excecoes': excecoes,
            'estatisticas_ia': resultados_ia
        }
    
    def _identificar_excecoes_melhorado(self, extrato_df: pd.DataFrame, contabil_df: pd.DataFrame) -> List[Dict]:
        """Identifica exceções e divergências com contagem correta"""
        excecoes = []
        
        # 1. Transações bancárias sem correspondência
        if len(extrato_df) > 0:
            total_valor_extrato = extrato_df['valor'].abs().sum()
            
            # CORREÇÃO: Criar uma exceção por transação individual
            for _, transacao in extrato_df.iterrows():
                data_str = transacao['data'].strftime('%d/%m/%Y') if hasattr(transacao['data'], 'strftime') else str(transacao['data'])
                
                excecoes.append({
                    'tipo': 'MOVIMENTAÇÃO_BANCÁRIA_SEM_LANÇAMENTO',
                    'severidade': 'ALTA',
                    'descricao': f"Movimentação bancária sem lançamento contábil",
                    'detalhes': f"Data: {data_str} | Valor: R$ {transacao['valor']:,.2f} | Descrição: {transacao.get('descricao', 'N/A')}",
                    'ids_envolvidos': [transacao['id']],
                    'acao_sugerida': 'Verificar se é despesa não contabilizada ou receita não identificada',
                    'categoria': 'Bancário → Contábil',
                    'valor_individual': abs(transacao['valor'])
                })
        
        # 2. Lançamentos contábeis sem movimentação bancária
        if len(contabil_df) > 0:
            for _, lancamento in contabil_df.iterrows():
                data_str = lancamento['data'].strftime('%d/%m/%Y') if hasattr(lancamento['data'], 'strftime') else str(lancamento['data'])
                
                excecoes.append({
                    'tipo': 'LANÇAMENTO_CONTÁBIL_SEM_MOVIMENTAÇÃO',
                    'severidade': 'ALTA',
                    'descricao': f"Lançamento contábil sem movimentação bancária",
                    'detalhes': f"Data: {data_str} | Valor: R$ {lancamento['valor']:,.2f} | Descrição: {lancamento.get('descricao', 'N/A')}",
                    'ids_envolvidos': [lancamento['id']],
                    'acao_sugerida': 'Verificar provisionamentos ou lançamentos futuros',
                    'categoria': 'Contábil → Bancário',
                    'valor_individual': abs(lancamento['valor'])
                })
        
        return excecoes

    def _normalizar_identificadores(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normaliza identificadores para matching"""
        df = df.copy()
        if 'descricao' in df.columns:
            df['txid_pix'] = df['descricao'].apply(self._extrair_txid_pix)
            df['nsu'] = df['descricao'].apply(self._extrair_nsu)
            df['nosso_numero'] = df['descricao'].apply(self._extrair_nosso_numero)
            df['cpf_cnpj'] = df['descricao'].apply(self._extrair_cpf_cnpj)
        return df
    
    def _extrair_txid_pix(self, texto: str) -> str:
        """Extrai TXID de transações PIX"""
        if not isinstance(texto, str): return ""
        padroes = [
            r'[A-Z0-9]{8}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{12}',
            r'TXID[:\s]*([A-Z0-9]+)', r'ID[:\s]*([A-Z0-9]{32})'
        ]
        for padrao in padroes:
            match = re.search(padrao, texto.upper())
            if match: return match.group(0) if padrao.startswith('[A-Z]') else match.group(1)
        return ""
    
    def _extrair_nsu(self, texto: str) -> str:
        """Extrai NSU de transações de cartão"""
        if not isinstance(texto, str): return ""
        padroes = [r'NSU[:\s]*(\d{6,})', r'NS\s*(\d{6,})', r'(\d{6,})\s*NSU']
        for padrao in padroes:
            match = re.search(padrao, texto.upper())
            if match: return match.group(1)
        return ""
    
    def _extrair_nosso_numero(self, texto: str) -> str:
        """Extrai Nosso Número de boletos"""
        if not isinstance(texto, str): return ""
        padroes = [r'NOSSO\s*N[ÚU]MERO[:\s]*(\d+)', r'NOSSO\s*NRO[:\s]*(\d+)', r'NN[:\s]*(\d+)']
        for padrao in padroes:
            match = re.search(padrao, texto.upper())
            if match: return match.group(1)
        return ""
    
    def _extrair_cpf_cnpj(self, texto: str) -> str:
        """Extrai CPF/CNPJ da descrição"""
        if not isinstance(texto, str): return ""
        cpf_match = re.search(r'(\d{3}\.\d{3}\.\d{3}-\d{2})|(\d{11})', texto)
        if cpf_match: return cpf_match.group(0)
        cnpj_match = re.search(r'(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})|(\d{14})', texto)
        if cnpj_match: return cnpj_match.group(0)
        return ""
    
    def _match_por_txid(self, extrato_df: pd.DataFrame, contabil_df: pd.DataFrame) -> List[Dict]:
        """Matching por TXID PIX"""
        matches = []
        extrato_com_txid = extrato_df[extrato_df['txid_pix'] != ""]
        contabil_com_txid = contabil_df[contabil_df['txid_pix'] != ""]
        
        for txid in extrato_com_txid['txid_pix'].unique():
            if txid == "": continue
            extrato_matches = extrato_com_txid[extrato_com_txid['txid_pix'] == txid]
            contabil_matches = contabil_com_txid[contabil_com_txid['txid_pix'] == txid]
            
            if len(extrato_matches) > 0 and len(contabil_matches) > 0:
                matches.append({
                    'tipo_match': '1:1', 'camada': 'exata',
                    'ids_extrato': extrato_matches['id'].tolist(),
                    'ids_contabil': contabil_matches['id'].tolist(),
                    'valor_total': extrato_matches['valor'].sum(),
                    'confianca': 100,
                    'explicacao': f"Match exato por TXID PIX: {txid}",
                    'chave_match': f"TXID_{txid}"
                })
        return matches
    
    def _match_por_nsu(self, extrato_df: pd.DataFrame, contabil_df: pd.DataFrame) -> List[Dict]:
        """Matching por NSU"""
        matches = []
        extrato_com_nsu = extrato_df[extrato_df['nsu'] != ""]
        contabil_com_nsu = contabil_df[contabil_df['nsu'] != ""]
        
        for nsu in extrato_com_nsu['nsu'].unique():
            if nsu == "": continue
            extrato_matches = extrato_com_nsu[extrato_com_nsu['nsu'] == nsu]
            contabil_matches = contabil_com_nsu[contabil_com_nsu['nsu'] == nsu]
            
            if len(extrato_matches) > 0 and len(contabil_matches) > 0:
                matches.append({
                    'tipo_match': '1:1', 'camada': 'exata',
                    'ids_extrato': extrato_matches['id'].tolist(),
                    'ids_contabil': contabil_matches['id'].tolist(),
                    'valor_total': extrato_matches['valor'].sum(),
                    'confianca': 100,
                    'explicacao': f"Match exato por NSU: {nsu}",
                    'chave_match': f"NSU_{nsu}"
                })
        return matches
    
    def _match_por_nosso_numero(self, extrato_df: pd.DataFrame, contabil_df: pd.DataFrame) -> List[Dict]:
        """Matching por Nosso Número"""
        matches = []
        extrato_com_nn = extrato_df[extrato_df['nosso_numero'] != ""]
        contabil_com_nn = contabil_df[contabil_df['nosso_numero'] != ""]
        
        for nn in extrato_com_nn['nosso_numero'].unique():
            if nn == "": continue
            extrato_matches = extrato_com_nn[extrato_com_nn['nosso_numero'] == nn]
            contabil_matches = contabil_com_nn[contabil_com_nn['nosso_numero'] == nn]
            
            if len(extrato_matches) > 0 and len(contabil_matches) > 0:
                matches.append({
                    'tipo_match': '1:1', 'camada': 'exata',
                    'ids_extrato': extrato_matches['id'].tolist(),
                    'ids_contabil': contabil_matches['id'].tolist(),
                    'valor_total': extrato_matches['valor'].sum(),
                    'confianca': 100,
                    'explicacao': f"Match exato por Nosso Número: {nn}",
                    'chave_match': f"NN_{nn}"
                })
        return matches
    
    def _match_valor_data_exata(self, extrato_df: pd.DataFrame, contabil_df: pd.DataFrame,
                           extrato_match_ids: set, contabil_match_ids: set) -> List[Dict]:
        """Matching por valor e data exata.

        Desempate determinístico (achado da Fase 5, corrigido na Fase
        5b/XCRE-50): quando há AMBIGUIDADE de (valor, data) — mais
        linhas de um lado do que candidatos disponíveis do outro —,
        qual linha específica "vence" a disputa pelo(s) candidato(s)
        restante(s) não pode depender da ORDEM FÍSICA de chegada das
        linhas do extrato, só do seu CONTEÚDO. Por isso o extrato é
        processado em ordem canônica (descrição normalizada e, só como
        último desempate, id) em vez da ordem de iteração original.
        Isso não altera nenhum critério de valor/data do matching, só
        a ordem em que candidatos empatados são consumidos.
        """
        matches = []
        extrato_nao_match = extrato_df[~extrato_df['id'].isin(extrato_match_ids)].copy()
        contabil_nao_match = contabil_df[~contabil_df['id'].isin(contabil_match_ids)]

        if 'descricao' in extrato_nao_match.columns:
            chave_descricao = extrato_nao_match['descricao'].fillna('').astype(str).str.strip().str.casefold()
        else:
            chave_descricao = ''
        extrato_nao_match = extrato_nao_match.assign(_chave_desempate=chave_descricao).sort_values(
            by=['_chave_desempate', 'id'], kind='mergesort', ignore_index=True
        )

        for _, extrato_row in extrato_nao_match.iterrows():
            if extrato_row['id'] in extrato_match_ids: continue
            valor_extrato_abs = abs(extrato_row['valor'])
            
            contabil_correspondentes = contabil_nao_match[
                (abs(contabil_nao_match['valor']) == valor_extrato_abs) &
                (contabil_nao_match['data'] == extrato_row['data']) &
                (~contabil_nao_match['id'].isin(contabil_match_ids))
            ]
            
            if len(contabil_correspondentes) == 1:
                contabil_row = contabil_correspondentes.iloc[0]
                matches.append({
                    'tipo_match': '1:1', 'camada': 'exata',
                    'ids_extrato': [extrato_row['id']],
                    'ids_contabil': [contabil_row['id']],
                    'valor_total': valor_extrato_abs,
                    'confianca': 95,
                    'explicacao': f"Match exato por valor (R$ {valor_extrato_abs:.2f}) e data",
                    'chave_match': f"VALOR_DATA_{valor_extrato_abs}_{extrato_row['data']}"
                })
                extrato_match_ids.add(extrato_row['id'])
                contabil_match_ids.add(contabil_row['id'])
        return matches

    def _match_heuristico_1_1(self, extrato_df: pd.DataFrame, contabil_df: pd.DataFrame,
                            tolerancia_dias: int, tolerancia_valor_percentual: float, similaridade_minima: int,
                            tolerancia_valor_absoluta_maxima: float = TOLERANCIA_VALOR_ABSOLUTA_MAXIMA_PADRAO) -> List[Dict]:
        """Matching heurístico 1:1.

        A tolerância de valor é aplicada por par: o MENOR entre percentual
        × valor da transação bancária daquele par específico e o teto
        absoluto em R$ — não um R$ fixo calculado sobre a média de todo o
        lote (instável — o mesmo par podia ser aceito ou rejeitado
        dependendo de quais outras transações estavam no lote), nem um
        percentual puro sem teto (aceitaria diferenças grandes em R$ só
        porque a transação também é grande — ver
        TOLERANCIA_VALOR_ABSOLUTA_MAXIMA_PADRAO)."""
        matches = []
        extrato_match_ids = set()
        contabil_match_ids = set()

        for _, extrato_row in extrato_df.iterrows():
            if extrato_row['id'] in extrato_match_ids: continue
            valor_extrato_abs = abs(extrato_row['valor'])
            tolerancia_valor_absoluta = min(
                valor_extrato_abs * (tolerancia_valor_percentual / 100),
                tolerancia_valor_absoluta_maxima,
            )

            contabil_candidatos = contabil_df[
                (~contabil_df['id'].isin(contabil_match_ids)) &
                (abs(abs(contabil_df['valor']) - valor_extrato_abs) <= tolerancia_valor_absoluta)
            ]
            
            for _, contabil_row in contabil_candidatos.iterrows():
                if contabil_row['id'] in contabil_match_ids: continue
                data_diff = abs((contabil_row['data'] - extrato_row['data']).days)
                if data_diff > tolerancia_dias: continue
                
                similaridade = self._calcular_similaridade(
                    extrato_row.get('descricao', ''), contabil_row.get('descricao', '')
                )
                
                if similaridade >= similaridade_minima:
                    diff_valor = abs(abs(contabil_row['valor']) - valor_extrato_abs)
                    confianca = self._calcular_confianca_heuristica(data_diff, diff_valor, similaridade)

                    matches.append({
                        'tipo_match': '1:1', 'camada': 'heuristica',
                        'ids_extrato': [extrato_row['id']],
                        'ids_contabil': [contabil_row['id']],
                        'valor_total': valor_extrato_abs,
                        'confianca': confianca,
                        'explicacao': self._justificar_match_heuristico(similaridade, diff_valor, data_diff),
                        'chave_match': f"HEUR_{extrato_row['id']}_{contabil_row['id']}"
                    })
                    extrato_match_ids.add(extrato_row['id'])
                    contabil_match_ids.add(contabil_row['id'])
                    break
        return matches
    
    def _match_1_n(self, extrato_df: pd.DataFrame, contabil_df: pd.DataFrame,
                  tolerancia_dias: int, tolerancia_valor_percentual: float) -> List[Dict]:
        """Matching 1:N (parcelamentos)"""
        return []  # Implementação simplificada

    def _match_n_1(self, extrato_df: pd.DataFrame, contabil_df: pd.DataFrame,
                  tolerancia_dias: int, tolerancia_valor_percentual: float) -> List[Dict]:
        """Matching N:1 (consolidações)"""
        return []  # Implementação simplificada
    
    def _calcular_similaridade(self, texto1: str, texto2: str) -> float:
        """Calcula similaridade entre dois textos"""
        if not texto1 or not texto2: return 0.0
        return SequenceMatcher(None, texto1.lower(), texto2.lower()).ratio() * 100
    
    def _justificar_match_heuristico(self, similaridade: float, diff_valor: float, diff_dias: int) -> str:
        """Monta a justificativa textual de um match heurístico.

        Antes a justificativa dizia só "Match por similaridade: X%", sem
        indicar QUANTO o valor e a data divergem entre os dois lados —
        obrigando o contador a comparar as linhas manualmente para
        auditar a decisão. Agora cita explicitamente as três dimensões
        usadas no cálculo de confiança (texto, valor e data), no formato
        "Match por similaridade: 90%; valor difere R$ 3,00; data difere 0
        dias"."""
        valor_str = f"{diff_valor:,.2f}".replace(",", "@").replace(".", ",").replace("@", ".")
        dia_plural = "dia" if diff_dias == 1 else "dias"
        return (
            f"Match por similaridade: {similaridade:.0f}%; "
            f"valor difere R$ {valor_str}; "
            f"data difere {diff_dias} {dia_plural}"
        )

    def _calcular_confianca_heuristica(self, diff_dias: int, diff_valor: float, similaridade: float) -> float:
        """Calcula confiança do match heurístico"""
        confianca = 100
        confianca -= diff_dias * 5
        confianca -= diff_valor * 10
        confianca = confianca * (similaridade / 100)
        return max(0, min(100, confianca))

# Funções de interface simplificadas
def matching_exato(extrato_df: pd.DataFrame, contabil_df: pd.DataFrame) -> Dict:
    return DataAnalyzer().matching_exato(extrato_df, contabil_df)

def matching_heuristico(extrato_df: pd.DataFrame, contabil_df: pd.DataFrame,
                       nao_matchados_extrato: pd.DataFrame, nao_matchados_contabil: pd.DataFrame,
                       tolerancia_dias: int, tolerancia_valor_percentual: float, similaridade_minima: int) -> Dict:
    return DataAnalyzer().matching_heuristico(extrato_df, contabil_df, nao_matchados_extrato,
                                      nao_matchados_contabil, tolerancia_dias, tolerancia_valor_percentual, similaridade_minima)

def matching_ia(extrato_df: pd.DataFrame, contabil_df: pd.DataFrame,
               nao_matchados_extrato: pd.DataFrame, nao_matchados_contabil: pd.DataFrame) -> Dict:
    return DataAnalyzer().matching_ia(extrato_df, contabil_df, nao_matchados_extrato, nao_matchados_contabil)

def consolidar_resultados(resultados_exato: Dict, resultados_heurístico: Dict, resultados_ia: Dict) -> Dict:
    matches = resultados_exato['matches'] + resultados_heurístico['matches'] + resultados_ia['matches']
    excecoes = resultados_ia.get('excecoes', [])
    return {
        'matches': matches,
        'excecoes': excecoes,
        'estatisticas': {
            'total_matches': len(matches),
            'matches_exatos': len(resultados_exato['matches']),
            'matches_heuristicos': len(resultados_heurístico['matches']),
            'matches_ia': len(resultados_ia.get('matches', [])),
            'total_excecoes': len(excecoes)
        }
    }

def identificar_pares_provaveis_similaridade(
    extrato_nao_match: pd.DataFrame,
    contabil_nao_match: pd.DataFrame,
    *,
    diff_valor_percentual_maximo: float = 10.0,
    diff_dias_maximo: int = 5,
    similaridade_minima: float = 40.0,
) -> List[Dict]:
    """Fonte ÚNICA da regra "possíveis correspondências por similaridade"
    entre itens ainda em aberto (issue XCRE-44, item A2): mesmos limiares
    e fórmula de confiança que pages/analise_dados.py já usa e expõe na
    UI/CSV (diferença de valor <=10%, diferença de data <=5 dias,
    similaridade textual >=40%) — extraída para cá para que o relatório
    Executivo REUTILIZE este cálculo em vez de recalcular de forma
    divergente. Retorna valores BRUTOS (não formatados como string), um
    dict por par candidato; não é pareamento exclusivo (um item pode
    aparecer em mais de um par candidato)."""
    pares = []
    for _, linha_extrato in extrato_nao_match.iterrows():
        valor_extrato = abs(linha_extrato["valor"])
        data_extrato = linha_extrato.get("data")
        for _, linha_contabil in contabil_nao_match.iterrows():
            valor_contabil = abs(linha_contabil["valor"])
            data_contabil = linha_contabil.get("data")

            diff_valor_percent = (
                abs(valor_extrato - valor_contabil) / valor_extrato * 100 if valor_extrato > 0 else 100
            )
            if hasattr(data_extrato, "strftime") and hasattr(data_contabil, "strftime"):
                diff_dias = abs((data_extrato - data_contabil).days)
            else:
                diff_dias = 30

            if diff_valor_percent > diff_valor_percentual_maximo or diff_dias > diff_dias_maximo:
                continue

            similaridade = SequenceMatcher(
                None,
                str(linha_extrato.get("descricao", "") or "").lower(),
                str(linha_contabil.get("descricao", "") or "").lower(),
            ).ratio() * 100
            if similaridade < similaridade_minima:
                continue

            confianca = (100 - diff_valor_percent) * (100 - diff_dias * 2) * similaridade / 10000
            pares.append({
                "id_extrato": linha_extrato["id"],
                "id_contabil": linha_contabil["id"],
                "data_extrato": data_extrato,
                "data_contabil": data_contabil,
                "valor_extrato": float(linha_extrato["valor"]),
                "valor_contabil": float(linha_contabil["valor"]),
                "descricao_extrato": str(linha_extrato.get("descricao", "") or ""),
                "descricao_contabil": str(linha_contabil.get("descricao", "") or ""),
                "diferenca_valor": round(abs(valor_extrato - valor_contabil), 2),
                "diferenca_dias": diff_dias,
                "similaridade": round(similaridade, 1),
                "confianca": round(max(0.0, min(100.0, confianca)), 1),
            })
    return pares


def get_detalhes_divergencias_tabela(excecoes: List[Dict],
                                   extrato_df: pd.DataFrame, 
                                   contabil_df: pd.DataFrame) -> pd.DataFrame:
    """Retorna detalhes das divergências em formato tabular limpo"""
    divergencias_detalhadas = []
    
    mapa_tipos = {
        'MOVIMENTAÇÃO_BANCÁRIA_SEM_LANÇAMENTO': '🔴 Mov. Bancária s/Lançamento',
        'LANÇAMENTO_CONTÁBIL_SEM_MOVIMENTAÇÃO': '🔴 Lançamento s/Mov. Bancária'
    }
    
    for excecao in excecoes:
        tipo_amigavel = mapa_tipos.get(excecao['tipo'], excecao['tipo'])
        
        if excecao['tipo'] == 'MOVIMENTAÇÃO_BANCÁRIA_SEM_LANÇAMENTO':
            transacoes = extrato_df[extrato_df['id'].isin(excecao['ids_envolvidos'])]
            for _, transacao in transacoes.iterrows():
                data_str = transacao['data'].strftime('%d/%m/%Y') if hasattr(transacao['data'], 'strftime') else str(transacao['data'])
                divergencias_detalhadas.append({
                    'Tipo': tipo_amigavel,
                    'Data': data_str,
                    'Valor': f"R$ {transacao['valor']:,.2f}",
                    'Descrição': transacao.get('descricao', '')[:60] + "..." if len(transacao.get('descricao', '')) > 60 else transacao.get('descricao', ''),
                    'Origem': '🏦 Bancário',
                    'Ação': excecao['acao_sugerida'][:50] + "..." if len(excecao['acao_sugerida']) > 50 else excecao['acao_sugerida']
                })
        
        elif excecao['tipo'] == 'LANÇAMENTO_CONTÁBIL_SEM_MOVIMENTAÇÃO':
            lancamentos = contabil_df[contabil_df['id'].isin(excecao['ids_envolvidos'])]
            for _, lancamento in lancamentos.iterrows():
                data_str = lancamento['data'].strftime('%d/%m/%Y') if hasattr(lancamento['data'], 'strftime') else str(lancamento['data'])
                divergencias_detalhadas.append({
                    'Tipo': tipo_amigavel,
                    'Data': data_str,
                    'Valor': f"R$ {lancamento['valor']:,.2f}",
                    'Descrição': lancamento.get('descricao', '')[:60] + "..." if len(lancamento.get('descricao', '')) > 60 else lancamento.get('descricao', ''),
                    'Origem': '📊 Contábil',
                    'Ação': excecao['acao_sugerida'][:50] + "..." if len(excecao['acao_sugerida']) > 50 else excecao['acao_sugerida']
                })
    
    return pd.DataFrame(divergencias_detalhadas)