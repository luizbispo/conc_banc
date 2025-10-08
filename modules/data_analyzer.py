# modules/data_analyzer.py
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import re
from difflib import SequenceMatcher
import logging
from typing import Dict, List, Tuple, Any

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DataAnalyzer:
    def __init__(self):
        self.matches_identificados = []
        self.excecoes = []
        self.audit_trail = []
        
    def _garantir_coluna_id(self, df: pd.DataFrame, nome_df: str = "DataFrame") -> pd.DataFrame:
        """Garante que o DataFrame tenha coluna 'id'"""
        df = df.copy()
        
        if 'id' not in df.columns:
            logger.warning(f"Coluna 'id' não encontrada em {nome_df}. Criando automaticamente.")
            df['id'] = range(1, len(df) + 1)
        
        return df

    def matching_exato(self, extrato_df: pd.DataFrame, contabil_df: pd.DataFrame) -> Dict:
        """
        Camada 1: Matching exato usando identificadores únicos
        TXID PIX, NSU, Nosso Número, etc.
        """
        logger.info("Iniciando matching exato")
        
        # CORREÇÃO: Garantir que as colunas 'id' existem
        extrato_df = self._garantir_coluna_id(extrato_df, "extrato_df")
        contabil_df = self._garantir_coluna_id(contabil_df, "contabil_df")
        
        matches = []
        extrato_match_ids = set()
        contabil_match_ids = set()
        
        # Normalizar identificadores
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
        
        logger.info(f"Matching exato: {len(matches)} matches identificados")
        
        return {
            'matches': matches,
            'nao_matchados_extrato': nao_matchados_extrato,
            'nao_matchados_contabil': nao_matchados_contabil
        }
    
    def matching_heuristico(self, extrato_df: pd.DataFrame, contabil_df: pd.DataFrame,
                          nao_matchados_extrato: pd.DataFrame, nao_matchados_contabil: pd.DataFrame,
                          tolerancia_dias: int = 2, tolerancia_valor: float = 0.02,
                          similaridade_minima: int = 80) -> Dict:
        """
        Camada 2: Matching heurístico com tolerâncias
        """
        logger.info("Iniciando matching heurístico")
        matches = []
        extrato_match_ids = set()
        contabil_match_ids = set()
        
        # 1. Matching 1:1 com tolerâncias
        matches_1_1 = self._match_heuristico_1_1(
            nao_matchados_extrato, nao_matchados_contabil,
            tolerancia_dias, tolerancia_valor, similaridade_minima
        )
        matches.extend(matches_1_1)
        
        # 2. Matching 1:N (parcelamentos)
        matches_1_n = self._match_1_n(
            nao_matchados_extrato, nao_matchados_contabil,
            tolerancia_dias, tolerancia_valor
        )
        matches.extend(matches_1_n)
        
        # 3. Matching N:1 (consolidações)
        matches_n_1 = self._match_n_1(
            nao_matchados_extrato, nao_matchados_contabil,
            tolerancia_dias, tolerancia_valor
        )
        matches.extend(matches_n_1)
        
        # Atualizar IDs matchados
        for match in matches:
            extrato_match_ids.update(match['ids_extrato'])
            contabil_match_ids.update(match['ids_contabil'])
        
        # Identificar não matchados restantes
        nao_matchados_extrato_final = nao_matchados_extrato[~nao_matchados_extrato['id'].isin(extrato_match_ids)]
        nao_matchados_contabil_final = nao_matchados_contabil[~nao_matchados_contabil['id'].isin(contabil_match_ids)]
        
        logger.info(f"Matching heurístico: {len(matches)} matches identificados")
        
        return {
            'matches': matches,
            'nao_matchados_extrato': nao_matchados_extrato_final,
            'nao_matchados_contabil': nao_matchados_contabil_final
        }
    
    def matching_ia(self, extrato_df: pd.DataFrame, contabil_df: pd.DataFrame,
                   nao_matchados_extrato: pd.DataFrame, nao_matchados_contabil: pd.DataFrame) -> Dict:
        """
        Camada 3: Matching com IA para casos complexos
        """
        logger.info("Iniciando matching com IA")
        matches = []
        
        # Aqui integraríamos com LLM para análise semântica
        # Por enquanto, implementamos regras avançadas
        
        # 1. Matching por similaridade textual avançada
        matches_similaridade = self._match_similaridade_avancada(
            nao_matchados_extrato, nao_matchados_contabil
        )
        matches.extend(matches_similaridade)
        
        # 2. Matching por padrões temporais
        matches_temporais = self._match_padroes_temporais(
            nao_matchados_extrato, nao_matchados_contabil
        )
        matches.extend(matches_temporais)
        
        # 3. Identificar exceções nos não matchados
        excecoes = self._identificar_excecoes(
            nao_matchados_extrato, nao_matchados_contabil
        )
        self.excecoes.extend(excecoes)
        
        logger.info(f"Matching IA: {len(matches)} matches identificados")
        logger.info(f"Exceções identificadas: {len(excecoes)}")
        
        return {
            'matches': matches,
            'excecoes': excecoes
        }
    
    def _normalizar_identificadores(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normaliza identificadores para matching"""
        df = df.copy()
        
        if 'descricao' in df.columns:
            # Extrair TXID PIX
            df['txid_pix'] = df['descricao'].apply(self._extrair_txid_pix)
            
            # Extrair NSU
            df['nsu'] = df['descricao'].apply(self._extrair_nsu)
            
            # Extrair Nosso Número
            df['nosso_numero'] = df['descricao'].apply(self._extrair_nosso_numero)
            
            # Extrair CPF/CNPJ
            df['cpf_cnpj'] = df['descricao'].apply(self._extrair_cpf_cnpj)
        
        return df
    
    def _extrair_txid_pix(self, texto: str) -> str:
        """Extrai TXID de transações PIX"""
        if not isinstance(texto, str):
            return ""
        
        # Padrões comuns de TXID PIX
        padroes = [
            r'[A-Z0-9]{8}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{12}',
            r'TXID[:\s]*([A-Z0-9]+)',
            r'ID[:\s]*([A-Z0-9]{32})'
        ]
        
        for padrao in padroes:
            match = re.search(padrao, texto.upper())
            if match:
                return match.group(0) if padrao.startswith('[A-Z]') else match.group(1)
        
        return ""
    
    def _extrair_nsu(self, texto: str) -> str:
        """Extrai NSU de transações de cartão"""
        if not isinstance(texto, str):
            return ""
        
        padroes = [
            r'NSU[:\s]*(\d{6,})',
            r'NS\s*(\d{6,})',
            r'(\d{6,})\s*NSU'
        ]
        
        for padrao in padroes:
            match = re.search(padrao, texto.upper())
            if match:
                return match.group(1)
        
        return ""
    
    def _extrair_nosso_numero(self, texto: str) -> str:
        """Extrai Nosso Número de boletos"""
        if not isinstance(texto, str):
            return ""
        
        padroes = [
            r'NOSSO\s*N[ÚU]MERO[:\s]*(\d+)',
            r'NOSSO\s*NRO[:\s]*(\d+)',
            r'NN[:\s]*(\d+)'
        ]
        
        for padrao in padroes:
            match = re.search(padrao, texto.upper())
            if match:
                return match.group(1)
        
        return ""
    
    def _extrair_cpf_cnpj(self, texto: str) -> str:
        """Extrai CPF/CNPJ da descrição"""
        if not isinstance(texto, str):
            return ""
        
        # CPF: 11 dígitos
        cpf_match = re.search(r'(\d{3}\.\d{3}\.\d{3}-\d{2})|(\d{11})', texto)
        if cpf_match:
            return cpf_match.group(0)
        
        # CNPJ: 14 dígitos
        cnpj_match = re.search(r'(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})|(\d{14})', texto)
        if cnpj_match:
            return cnpj_match.group(0)
        
        return ""
    
    def _match_por_txid(self, extrato_df: pd.DataFrame, contabil_df: pd.DataFrame) -> List[Dict]:
        """Matching por TXID PIX"""
        matches = []
        
        extrato_com_txid = extrato_df[extrato_df['txid_pix'] != ""]
        contabil_com_txid = contabil_df[contabil_df['txid_pix'] != ""]
        
        for txid in extrato_com_txid['txid_pix'].unique():
            if txid == "":
                continue
                
            extrato_matches = extrato_com_txid[extrato_com_txid['txid_pix'] == txid]
            contabil_matches = contabil_com_txid[contabil_com_txid['txid_pix'] == txid]
            
            if len(extrato_matches) > 0 and len(contabil_matches) > 0:
                match = {
                    'tipo_match': '1:1',
                    'camada': 'exata',
                    'ids_extrato': extrato_matches['id'].tolist(),
                    'ids_contabil': contabil_matches['id'].tolist(),
                    'valor_total': extrato_matches['valor'].sum(),
                    'confianca': 100,
                    'explicacao': f"Match exato por TXID PIX: {txid}",
                    'chave_match': f"TXID_{txid}"
                }
                matches.append(match)
        
        return matches
    
    def _match_por_nsu(self, extrato_df: pd.DataFrame, contabil_df: pd.DataFrame) -> List[Dict]:
        """Matching por NSU"""
        matches = []
        
        extrato_com_nsu = extrato_df[extrato_df['nsu'] != ""]
        contabil_com_nsu = contabil_df[contabil_df['nsu'] != ""]
        
        for nsu in extrato_com_nsu['nsu'].unique():
            if nsu == "":
                continue
                
            extrato_matches = extrato_com_nsu[extrato_com_nsu['nsu'] == nsu]
            contabil_matches = contabil_com_nsu[contabil_com_nsu['nsu'] == nsu]
            
            if len(extrato_matches) > 0 and len(contabil_matches) > 0:
                match = {
                    'tipo_match': '1:1',
                    'camada': 'exata',
                    'ids_extrato': extrato_matches['id'].tolist(),
                    'ids_contabil': contabil_matches['id'].tolist(),
                    'valor_total': extrato_matches['valor'].sum(),
                    'confianca': 100,
                    'explicacao': f"Match exato por NSU: {nsu}",
                    'chave_match': f"NSU_{nsu}"
                }
                matches.append(match)
        
        return matches
    
    def _match_por_nosso_numero(self, extrato_df: pd.DataFrame, contabil_df: pd.DataFrame) -> List[Dict]:
        """Matching por Nosso Número"""
        matches = []
        
        extrato_com_nn = extrato_df[extrato_df['nosso_numero'] != ""]
        contabil_com_nn = contabil_df[contabil_df['nosso_numero'] != ""]
        
        for nn in extrato_com_nn['nosso_numero'].unique():
            if nn == "":
                continue
                
            extrato_matches = extrato_com_nn[extrato_com_nn['nosso_numero'] == nn]
            contabil_matches = contabil_com_nn[contabil_com_nn['nosso_numero'] == nn]
            
            if len(extrato_matches) > 0 and len(contabil_matches) > 0:
                match = {
                    'tipo_match': '1:1',
                    'camada': 'exata',
                    'ids_extrato': extrato_matches['id'].tolist(),
                    'ids_contabil': contabil_matches['id'].tolist(),
                    'valor_total': extrato_matches['valor'].sum(),
                    'confianca': 100,
                    'explicacao': f"Match exato por Nosso Número: {nn}",
                    'chave_match': f"NN_{nn}"
                }
                matches.append(match)
        
        return matches
    
    def _match_valor_data_exata(self, extrato_df: pd.DataFrame, contabil_df: pd.DataFrame,
                           extrato_match_ids: set, contabil_match_ids: set) -> List[Dict]:
        """Matching por valor e data exata - CORREÇÃO: considerar valor absoluto"""
        matches = []
        
        # Filtrar não matchados
        extrato_nao_match = extrato_df[~extrato_df['id'].isin(extrato_match_ids)]
        contabil_nao_match = contabil_df[~contabil_df['id'].isin(contabil_match_ids)]
        
        for _, extrato_row in extrato_nao_match.iterrows():
            if extrato_row['id'] in extrato_match_ids:
                continue
                
            # CORREÇÃO: Usar valor absoluto para comparação
            valor_extrato_abs = abs(extrato_row['valor'])
            
            # Buscar correspondência exata
            contabil_correspondentes = contabil_nao_match[
                (abs(contabil_nao_match['valor']) == valor_extrato_abs) &
                (contabil_nao_match['data'] == extrato_row['data']) &
                (~contabil_nao_match['id'].isin(contabil_match_ids))
            ]
            
            if len(contabil_correspondentes) == 1:
                contabil_row = contabil_correspondentes.iloc[0]
                
                match = {
                    'tipo_match': '1:1',
                    'camada': 'exata',
                    'ids_extrato': [extrato_row['id']],
                    'ids_contabil': [contabil_row['id']],
                    'valor_total': valor_extrato_abs,  # Usar valor absoluto
                    'confianca': 95,
                    'explicacao': f"Match exato por valor (R$ {valor_extrato_abs:.2f}) e data ({extrato_row['data']}) - considerando valor absoluto",
                    'chave_match': f"VALOR_DATA_{valor_extrato_abs}_{extrato_row['data']}"
                }
                matches.append(match)
                
                # Marcar como matchados
                extrato_match_ids.add(extrato_row['id'])
                contabil_match_ids.add(contabil_row['id'])
        
        return matches

    def _match_heuristico_1_1(self, extrato_df: pd.DataFrame, contabil_df: pd.DataFrame,
                            tolerancia_dias: int, tolerancia_valor: float, similaridade_minima: int) -> List[Dict]:
        """Matching heurístico 1:1 - CORREÇÃO: considerar valor absoluto"""
        matches = []
        extrato_match_ids = set()
        contabil_match_ids = set()
        
        for _, extrato_row in extrato_df.iterrows():
            if extrato_row['id'] in extrato_match_ids:
                continue
                
            # CORREÇÃO: Usar valor absoluto para comparação
            valor_extrato_abs = abs(extrato_row['valor'])
            
            # Buscar correspondências com tolerâncias
            contabil_candidatos = contabil_df[
                (~contabil_df['id'].isin(contabil_match_ids)) &
                (abs(abs(contabil_df['valor']) - valor_extrato_abs) <= tolerancia_valor)
            ]
            
            for _, contabil_row in contabil_candidatos.iterrows():
                if contabil_row['id'] in contabil_match_ids:
                    continue
                
                # Verificar tolerância de data
                data_diff = abs((contabil_row['data'] - extrato_row['data']).days)
                if data_diff > tolerancia_dias:
                    continue
                
                # Verificar similaridade textual
                similaridade = self._calcular_similaridade(
                    extrato_row.get('descricao', ''),
                    contabil_row.get('descricao', '')
                )
                
                if similaridade >= similaridade_minima:
                    # CORREÇÃO: Calcular diferença usando valores absolutos
                    diff_valor = abs(abs(contabil_row['valor']) - valor_extrato_abs)
                    confianca = self._calcular_confianca_heuristica(data_diff, diff_valor, similaridade)
                    
                    match = {
                        'tipo_match': '1:1',
                        'camada': 'heuristica',
                        'ids_extrato': [extrato_row['id']],
                        'ids_contabil': [contabil_row['id']],
                        'valor_total': valor_extrato_abs,
                        'confianca': confianca,
                        'explicacao': f"Match heurístico: similaridade {similaridade}%, diferença de {data_diff} dias, diferença de R$ {diff_valor:.2f} (valor absoluto)",
                        'chave_match': f"HEUR_{extrato_row['id']}_{contabil_row['id']}"
                    }
                    matches.append(match)
                    
                    extrato_match_ids.add(extrato_row['id'])
                    contabil_match_ids.add(contabil_row['id'])
                    break
        
        return matches
    
    def _match_1_n(self, extrato_df: pd.DataFrame, contabil_df: pd.DataFrame,
                  tolerancia_dias: int, tolerancia_valor: float) -> List[Dict]:
        """Matching 1:N (parcelamentos)"""
        matches = []
        
        # Agrupar transações por padrões de parcelamento
        # Implementação simplificada - na prática seria mais complexa
        
        return matches
    
    def _match_n_1(self, extrato_df: pd.DataFrame, contabil_df: pd.DataFrame,
                  tolerancia_dias: int, tolerancia_valor: float) -> List[Dict]:
        """Matching N:1 (consolidações)"""
        matches = []
        
        # Agrupar múltiplas entradas pequenas que somam um lançamento maior
        # Implementação simplificada
        
        return matches
    
    def _calcular_similaridade(self, texto1: str, texto2: str) -> float:
        """Calcula similaridade entre dois textos"""
        if not texto1 or not texto2:
            return 0.0
        return SequenceMatcher(None, texto1.lower(), texto2.lower()).ratio() * 100
    
    def _calcular_confianca_heuristica(self, diff_dias: int, diff_valor: float, similaridade: float) -> float:
        """Calcula confiança do match heurístico"""
        confianca = 100
        
        # Penalizar por diferença de dias
        confianca -= diff_dias * 5
        
        # Penalizar por diferença de valor
        confianca -= diff_valor * 10
        
        # Ajustar por similaridade
        confianca = confianca * (similaridade / 100)
        
        return max(0, min(100, confianca))
    
    def _match_similaridade_avancada(self, extrato_df: pd.DataFrame, contabil_df: pd.DataFrame) -> List[Dict]:
        """Matching por similaridade textual avançada"""
        # Implementação para casos complexos de descrição
        return []
    
    def _match_padroes_temporais(self, extrato_df: pd.DataFrame, contabil_df: pd.DataFrame) -> List[Dict]:
        """Matching por padrões temporais"""
        # Identificar padrões como mensalidades, assinaturas, etc.
        return []
    
    def _identificar_excecoes(self, extrato_df: pd.DataFrame, contabil_df: pd.DataFrame) -> List[Dict]:
        """Identifica exceções e divergências"""
        excecoes = []
        
        # 1. Transações sem correspondência
        if len(extrato_df) > 0:
            excecoes.append({
                'tipo': 'TRANSAÇÃO_SEM_CORRESPONDÊNCIA',
                'severidade': 'ALTA',
                'descricao': f"{len(extrato_df)} transações bancárias sem correspondência contábil",
                'ids_envolvidos': extrato_df['id'].tolist(),
                'acao_sugerida': 'Verificar se são despesas não contabilizadas ou receitas não identificadas'
            })
        
        if len(contabil_df) > 0:
            excecoes.append({
                'tipo': 'LANÇAMENTO_SEM_CORRESPONDÊNCIA',
                'severidade': 'ALTA',
                'descricao': f"{len(contabil_df)} lançamentos contábeis sem correspondência bancária",
                'ids_envolvidos': contabil_df['id'].tolist(),
                'acao_sugerida': 'Verificar se são provisionamentos, lançamentos futuros ou erros de lançamento'
            })
        
        # 2. Diferenças de valor significativas (seriam identificadas durante o matching)
        # 3. Duplicidades (seriam identificadas durante o matching)
        
        return excecoes

# Funções de interface para o Streamlit
def matching_exato(extrato_df: pd.DataFrame, contabil_df: pd.DataFrame) -> Dict:
    analyzer = DataAnalyzer()
    return analyzer.matching_exato(extrato_df, contabil_df)

def matching_heuristico(extrato_df: pd.DataFrame, contabil_df: pd.DataFrame,
                       nao_matchados_extrato: pd.DataFrame, nao_matchados_contabil: pd.DataFrame,
                       tolerancia_dias: int, tolerancia_valor: float, similaridade_minima: int) -> Dict:
    analyzer = DataAnalyzer()
    return analyzer.matching_heuristico(extrato_df, contabil_df, nao_matchados_extrato, 
                                      nao_matchados_contabil, tolerancia_dias, tolerancia_valor, similaridade_minima)

def matching_ia(extrato_df: pd.DataFrame, contabil_df: pd.DataFrame,
               nao_matchados_extrato: pd.DataFrame, nao_matchados_contabil: pd.DataFrame) -> Dict:
    analyzer = DataAnalyzer()
    return analyzer.matching_ia(extrato_df, contabil_df, nao_matchados_extrato, nao_matchados_contabil)

def consolidar_resultados(resultados_exato: Dict, resultados_heurístico: Dict, resultados_ia: Dict) -> Dict:
    """Consolida resultados de todas as camadas"""
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

def get_detalhes_divergencias_tabela(self, excecoes: List[Dict], 
                                   extrato_df: pd.DataFrame, 
                                   contabil_df: pd.DataFrame) -> pd.DataFrame:
    """Retorna detalhes das divergências em formato tabular"""
    divergencias_detalhadas = []
    
    for excecao in excecoes:
        if excecao['tipo'] == 'TRANSAÇÃO_SEM_CORRESPONDÊNCIA':
            transacoes = extrato_df[extrato_df['id'].isin(excecao['ids_envolvidos'])]
            for _, transacao in transacoes.iterrows():
                divergencias_detalhadas.append({
                    'Tipo_Divergência': excecao['tipo'],
                    'Severidade': excecao['severidade'],
                    'Data': transacao['data'],
                    'Descrição': transacao.get('descricao', ''),
                    'Valor': transacao['valor'],
                    'Origem': 'Extrato Bancário',
                    'Ação_Recomendada': excecao['acao_sugerida']
                })
        
        elif excecao['tipo'] == 'LANÇAMENTO_SEM_CORRESPONDÊNCIA':
            lancamentos = contabil_df[contabil_df['id'].isin(excecao['ids_envolvidos'])]
            for _, lancamento in lancamentos.iterrows():
                divergencias_detalhadas.append({
                    'Tipo_Divergência': excecao['tipo'],
                    'Severidade': excecao['severidade'],
                    'Data': lancamento['data'],
                    'Descrição': lancamento.get('descricao', ''),
                    'Valor': lancamento['valor'],
                    'Origem': 'Contábil',
                    'Ação_Recomendada': excecao['acao_sugerida']
                })
        else:
            divergencias_detalhadas.append({
                'Tipo_Divergência': excecao['tipo'],
                'Severidade': excecao['severidade'],
                'Data': None,
                'Descrição': excecao['descricao'],
                'Valor': 0,
                'Origem': 'Sistema',
                'Ação_Recomendada': excecao['acao_sugerida']
            })
    
    return pd.DataFrame(divergencias_detalhadas)

def get_detalhes_divergencias_tabela(self, excecoes: List[Dict], 
                                   extrato_df: pd.DataFrame, 
                                   contabil_df: pd.DataFrame) -> pd.DataFrame:
    """Retorna detalhes das divergências em formato tabular"""
    divergencias_detalhadas = []
    
    for excecao in excecoes:
        if excecao['tipo'] == 'TRANSAÇÃO_SEM_CORRESPONDÊNCIA':
            transacoes = extrato_df[extrato_df['id'].isin(excecao['ids_envolvidos'])]
            for _, transacao in transacoes.iterrows():
                divergencias_detalhadas.append({
                    'Tipo_Divergência': excecao['tipo'],
                    'Severidade': excecao['severidade'],
                    'Data': transacao['data'],
                    'Descrição': transacao.get('descricao', ''),
                    'Valor': transacao['valor'],
                    'Origem': 'Extrato Bancário',
                    'Ação_Recomendada': excecao['acao_sugerida']
                })
        
        elif excecao['tipo'] == 'LANÇAMENTO_SEM_CORRESPONDÊNCIA':
            lancamentos = contabil_df[contabil_df['id'].isin(excecao['ids_envolvidos'])]
            for _, lancamento in lancamentos.iterrows():
                divergencias_detalhadas.append({
                    'Tipo_Divergência': excecao['tipo'],
                    'Severidade': excecao['severidade'],
                    'Data': lancamento['data'],
                    'Descrição': lancamento.get('descricao', ''),
                    'Valor': lancamento['valor'],
                    'Origem': 'Contábil',
                    'Ação_Recomendada': excecao['acao_sugerida']
                })
        else:
            # Para outros tipos de divergência
            divergencias_detalhadas.append({
                'Tipo_Divergência': excecao['tipo'],
                'Severidade': excecao['severidade'],
                'Data': None,
                'Descrição': excecao['descricao'],
                'Valor': 0,
                'Origem': 'Sistema',
                'Ação_Recomendada': excecao['acao_sugerida'],
                'Itens_Envolvidos': len(excecao['ids_envolvidos'])
            })
    
    return pd.DataFrame(divergencias_detalhadas)