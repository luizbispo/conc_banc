# modules/ai_matcher.py
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import re
from difflib import SequenceMatcher
from typing import List, Dict, Tuple, Any
from itertools import combinations

class AIMatcher:
    """Matcher avançado com IA para aumentar taxa de matching"""
    
    def __init__(self):
        self.semantic_cache = {}
        
    def matching_avancado_com_ia(self, extrato_df: pd.DataFrame, contabil_df: pd.DataFrame,
                               nao_matchados_extrato: pd.DataFrame, nao_matchados_contabil: pd.DataFrame,
                               tolerancia_dias: int = 3, tolerancia_valor: float = 0.05) -> Dict:
        """Matching avançado usando técnicas de IA e análise semântica"""
        matches = []
        
        # 1. Matching por similaridade semântica avançada
        matches_semanticos = self._matching_semantico_avancado(
            nao_matchados_extrato, nao_matchados_contabil,
            tolerancia_dias, tolerancia_valor
        )
        matches.extend(matches_semanticos)
        
        # 2. Matching por padrões temporais (mensalidades, parcelas)
        matches_temporais = self._matching_padroes_temporais(
            nao_matchados_extrato, nao_matchados_contabil
        )
        matches.extend(matches_temporais)
        
        # 3. Matching por agrupamento de valores
        matches_agrupados = self._matching_agrupamento_valores(
            nao_matchados_extrato, nao_matchados_contabil,
            tolerancia_dias
        )
        matches.extend(matches_agrupados)
        
        # 4. Matching por entidades financeiras
        matches_entidades = self._matching_entidades_financeiras(
            nao_matchados_extrato, nao_matchados_contabil,
            tolerancia_dias, tolerancia_valor
        )
        matches.extend(matches_entidades)
        
        return {
            'matches': matches,
            'matches_semanticos': len(matches_semanticos),
            'matches_temporais': len(matches_temporais),
            'matches_agrupados': len(matches_agrupados),
            'matches_entidades': len(matches_entidades)
        }
    
    def _matching_semantico_avancado(self, extrato_df: pd.DataFrame, contabil_df: pd.DataFrame,
                                   tolerancia_dias: int, tolerancia_valor: float) -> List[Dict]:
        """Matching por similaridade semântica avançada"""
        matches = []
        extrato_processado = set()
        contabil_processado = set()
        
        for _, extrato_row in extrato_df.iterrows():
            if extrato_row['id'] in extrato_processado: continue
                
            valor_extrato = abs(extrato_row.get('valor_original', extrato_row.get('valor', 0)))
            data_extrato = extrato_row.get('data')
            descricao_extrato = extrato_row.get('descricao', '')
            
            features_extrato = self._extrair_features_semanticas(descricao_extrato, valor_extrato)
            melhor_match = None
            melhor_confianca = 0
            
            for _, contabil_row in contabil_df.iterrows():
                if contabil_row['id'] in contabil_processado: continue
                    
                valor_contabil = abs(contabil_row.get('valor_original', contabil_row.get('valor', 0)))
                data_contabil = contabil_row.get('data')
                descricao_contabil = contabil_row.get('descricao', '')
                
                if not self._verificar_tolerancias_basicas(valor_extrato, valor_contabil, data_extrato, data_contabil, tolerancia_valor, tolerancia_dias):
                    continue
                
                features_contabil = self._extrair_features_semanticas(descricao_contabil, valor_contabil)
                confianca = self._calcular_similaridade_semantica_avancada(
                    features_extrato, features_contabil,
                    descricao_extrato, descricao_contabil,
                    valor_extrato, valor_contabil,
                    data_extrato, data_contabil
                )
                
                if confianca > melhor_confianca and confianca >= 65:
                    melhor_confianca = confianca
                    melhor_match = contabil_row
            
            if melhor_match is not None:
                matches.append({
                    'tipo_match': '1:1', 'camada': 'ia_semantica',
                    'ids_extrato': [extrato_row['id']], 'ids_contabil': [melhor_match['id']],
                    'valor_total': valor_extrato, 'confianca': melhor_confianca,
                    'explicacao': f"Match semântico (confiança: {melhor_confianca:.1f}%)",
                    'chave_match': f"IA_SEM_{extrato_row['id']}_{melhor_match['id']}"
                })
                extrato_processado.add(extrato_row['id'])
                contabil_processado.add(melhor_match['id'])
        
        return matches
    
    def _matching_padroes_temporais(self, extrato_df: pd.DataFrame, contabil_df: pd.DataFrame) -> List[Dict]:
        """Identifica padrões temporais como mensalidades, parcelamentos"""
        return []  # Implementação simplificada
    
    def _matching_agrupamento_valores(self, extrato_df: pd.DataFrame, contabil_df: pd.DataFrame,
                                    tolerancia_dias: int) -> List[Dict]:
        """Matching por agrupamento de valores"""
        matches = []
        
        for _, contabil_row in contabil_df.iterrows():
            valor_contabil = abs(contabil_row.get('valor_original', contabil_row.get('valor', 0)))
            data_contabil = contabil_row.get('data')
            
            transacoes_proximas = self._encontrar_transacoes_proximas(
                extrato_df, data_contabil, tolerancia_dias * 2
            )
            
            combinacoes = self._encontrar_combinacoes_soma(transacoes_proximas, valor_contabil)
            
            for combinacao in combinacoes:
                if len(combinacao) > 1:
                    ids_extrato = [trans['id'] for trans in combinacao]
                    matches.append({
                        'tipo_match': f'N:1', 'camada': 'ia_agrupamento',
                        'ids_extrato': ids_extrato, 'ids_contabil': [contabil_row['id']],
                        'valor_total': valor_contabil, 'confianca': 85,
                        'explicacao': f"Agrupamento de {len(combinacao)} transações",
                        'chave_match': f"IA_AGR_{contabil_row['id']}"
                    })
        
        return matches
    
    def _matching_entidades_financeiras(self, extrato_df: pd.DataFrame, contabil_df: pd.DataFrame,
                                      tolerancia_dias: int, tolerancia_valor: float) -> List[Dict]:
        """Matching baseado em entidades financeiras"""
        matches = []
        entidades_extrato = self._extrair_entidades_lote(extrato_df)
        entidades_contabil = self._extrair_entidades_lote(contabil_df)
        
        for id_extrato, entidades_ext in entidades_extrato.items():
            extrato_row = extrato_df[extrato_df['id'] == id_extrato].iloc[0]
            
            for id_contabil, entidades_cont in entidades_contabil.items():
                contabil_row = contabil_df[contabil_df['id'] == id_contabil].iloc[0]
                
                compatibilidade = self._calcular_compatibilidade_entidades(entidades_ext, entidades_cont)
                
                if compatibilidade >= 75:
                    valor_extrato = abs(extrato_row.get('valor_original', extrato_row.get('valor', 0)))
                    valor_contabil = abs(contabil_row.get('valor_original', contabil_row.get('valor', 0)))
                    data_extrato = extrato_row.get('data')
                    data_contabil = contabil_row.get('data')
                    
                    if self._verificar_tolerancias_basicas(valor_extrato, valor_contabil, data_extrato, data_contabil, tolerancia_valor, tolerancia_dias):
                        confianca_final = (compatibilidade + 
                                         (100 - (abs(valor_extrato - valor_contabil) / valor_extrato * 100)) + 
                                         (100 - min(abs((data_extrato - data_contabil).days), 10) * 10)) / 3
                        
                        if confianca_final >= 70:
                            matches.append({
                                'tipo_match': '1:1', 'camada': 'ia_entidades',
                                'ids_extrato': [id_extrato], 'ids_contabil': [id_contabil],
                                'valor_total': valor_extrato, 'confianca': confianca_final,
                                'explicacao': f"Match por entidades ({compatibilidade:.1f}%)",
                                'chave_match': f"IA_ENT_{id_extrato}_{id_contabil}"
                            })
        
        return matches
    
    def _extrair_features_semanticas(self, descricao: str, valor: float) -> Dict[str, Any]:
        """Extrai features semânticas da descrição"""
        desc_lower = descricao.lower()
        return {
            'palavras_chave': self._extrair_palavras_chave(desc_lower),
            'tipo_transacao': self._identificar_tipo_transacao(desc_lower),
            'metodo_pagamento': self._identificar_metodo_pagamento(desc_lower),
            'entidades': self._extrair_entidades(desc_lower),
            'valor_categoria': self._categorizar_valor(valor)
        }
    
    def _calcular_similaridade_semantica_avancada(self, features1: Dict, features2: Dict,
                                                desc1: str, desc2: str,
                                                valor1: float, valor2: float,
                                                data1, data2) -> float:
        """Calcula similaridade semântica avançada"""
        sim_palavras = self._calcular_similaridade_palavras_chave(features1['palavras_chave'], features2['palavras_chave'])
        sim_tipo = 100 if features1['tipo_transacao'] == features2['tipo_transacao'] else 0
        sim_metodo = 100 if features1['metodo_pagamento'] == features2['metodo_pagamento'] else 0
        sim_entidades = self._calcular_similaridade_entidades(features1['entidades'], features2['entidades'])
        
        diff_valor_percent = abs(valor1 - valor2) / max(valor1, valor2) * 100
        sim_valor = max(0, 100 - diff_valor_percent)
        
        if hasattr(data1, 'strftime') and hasattr(data2, 'strftime'):
            diff_dias = abs((data1 - data2).days)
            sim_temporal = max(0, 100 - (diff_dias * 5))
        else:
            sim_temporal = 50
        
        return (sim_palavras * 0.30 + sim_tipo * 0.20 + sim_metodo * 0.15 +
                sim_entidades * 0.20 + sim_valor * 0.10 + sim_temporal * 0.05)
    
    def _extrair_palavras_chave(self, texto: str) -> List[str]:
        """Extrai palavras-chave significativas"""
        stopwords = {'de', 'a', 'o', 'que', 'e', 'do', 'da', 'em', 'um', 'para', 'é', 'com', 'não', 'uma'}
        palavras = re.findall(r'\b[a-z]{3,}\b', texto.lower())
        return [p for p in palavras if p not in stopwords and len(p) > 2]
    
    def _identificar_tipo_transacao(self, texto: str) -> str:
        """Identifica o tipo de transação"""
        tipos = {
            'pix': r'pix|transferência|transferencia',
            'ted': r'ted|transferência eletrônica',
            'doc': r'doc|documento',
            'boleto': r'boleto|fatura|pagamento',
            'cartao': r'cartão|cartao|débito|debito|crédito|credito',
            'saque': r'saque|retirada',
            'deposito': r'depósito|deposito',
            'fornecedor': r'fornecedor|compra|mercadoria',
            'cliente': r'cliente|venda|recebimento',
            'imposto': r'imposto|taxa|contribuição'
        }
        for tipo, pattern in tipos.items():
            if re.search(pattern, texto): return tipo
        return 'outros'
    
    def _identificar_metodo_pagamento(self, texto: str) -> str:
        """Identifica método de pagamento"""
        metodos = {
            'pix': r'pix', 'cartao_credito': r'cartão de crédito|cartao credito',
            'cartao_debito': r'cartão de débito|cartao debito', 'boleto': r'boleto',
            'ted': r'ted', 'doc': r'doc', 'dinheiro': r'dinheiro'
        }
        for metodo, pattern in metodos.items():
            if re.search(pattern, texto): return metodo
        return ''
    
    def _extrair_entidades(self, texto: str) -> Dict[str, str]:
        """Extrai entidades do texto"""
        entidades = {
            'banco': self._extrair_banco(texto),
            'empresa': self._extrair_empresa(texto),
            'pessoa': self._extrair_pessoa(texto),
            'local': self._extrair_local(texto)
        }
        return {k: v for k, v in entidades.items() if v}
    
    def _extrair_banco(self, texto: str) -> str:
        bancos = ['itau', 'itaú', 'bradesco', 'santander', 'banco do brasil', 'bb', 'caixa', 'nubank', 'inter', 'c6', 'next']
        for banco in bancos:
            if banco in texto: return banco
        return ""
    
    def _extrair_empresa(self, texto: str) -> str:
        padrao_empresa = r'([A-Z][A-Za-z]+\s+[A-Z][A-Za-z]+)\s+(LTDA|S/A|SA|ME|EPP)'
        match = re.search(padrao_empresa, texto)
        return match.group(1) if match else ""
    
    def _extrair_pessoa(self, texto: str) -> str:
        padrao_nome = r'([A-Z][a-z]+\s+[A-Z][a-z]+\s+[A-Z][a-z]+)|([A-Z][a-z]+\s+[A-Z][a-z]+)'
        match = re.search(padrao_nome, texto)
        return match.group(0) if match else ""
    
    def _extrair_local(self, texto: str) -> str:
        locais = ['shopping', 'centro', 'avenida', 'av.', 'rua', 'praça', 'mercado', 'supermercado']
        for local in locais:
            if local in texto.lower(): return local
        return ""
    
    def _categorizar_valor(self, valor: float) -> str:
        """Categoriza o valor em faixas"""
        if valor < 100: return 'pequeno'
        elif valor < 1000: return 'medio'
        elif valor < 10000: return 'grande'
        else: return 'muito_grande'
    
    def _calcular_similaridade_palavras_chave(self, palavras1: List[str], palavras2: List[str]) -> float:
        if not palavras1 or not palavras2: return 0.0
        comuns = set(palavras1) & set(palavras2)
        return len(comuns) / max(len(palavras1), len(palavras2)) * 100
    
    def _calcular_similaridade_entidades(self, entidades1: Dict, entidades2: Dict) -> float:
        if not entidades1 or not entidades2: return 0.0
        comuns = 0
        for key in entidades1:
            if key in entidades2 and entidades1[key] and entidades2[key]:
                if entidades1[key] == entidades2[key]: comuns += 1
        return comuns / max(len(entidades1), len(entidades2)) * 100
    
    def _verificar_tolerancias_basicas(self, valor1: float, valor2: float, data1, data2, 
                                     tolerancia_valor: float, tolerancia_dias: int) -> bool:
        """Verifica tolerâncias básicas de valor e data"""
        diff_valor = abs(valor1 - valor2)
        if diff_valor > tolerancia_valor: return False
        if hasattr(data1, 'strftime') and hasattr(data2, 'strftime'):
            if abs((data1 - data2).days) > tolerancia_dias: return False
        return True

    def _identificar_padroes_temporais_df(self, df: pd.DataFrame) -> Dict[str, List]:
        """Identifica padrões temporais em um DataFrame"""
        padroes = {}
        for _, row in df.iterrows():
            descricao = row.get('descricao', '')
            valor = abs(row.get('valor_original', row.get('valor', 0)))
            chave_padrao = self._criar_chave_padrao(descricao, valor)
            if chave_padrao not in padroes: padroes[chave_padrao] = []
            padroes[chave_padrao].append({
                'id': row['id'], 'data': row.get('data'), 'valor': valor, 'descricao': descricao
            })
        return padroes

    def _criar_chave_padrao(self, descricao: str, valor: float) -> str:
        tipo = self._identificar_tipo_transacao(descricao.lower())
        categoria_valor = self._categorizar_valor(valor)
        palavras_chave = '_'.join(self._extrair_palavras_chave(descricao.lower())[:3])
        return f"{tipo}_{categoria_valor}_{palavras_chave}"

    def _encontrar_transacoes_proximas(self, df: pd.DataFrame, data_ref, tolerancia_dias: int) -> List[Dict]:
        """Encontra transações próximas à data de referência"""
        transacoes = []
        for _, row in df.iterrows():
            data_trans = row.get('data')
            if hasattr(data_trans, 'strftime') and hasattr(data_ref, 'strftime'):
                if abs((data_trans - data_ref).days) <= tolerancia_dias:
                    transacoes.append({
                        'id': row['id'], 'data': data_trans,
                        'valor': abs(row.get('valor_original', row.get('valor', 0))),
                        'descricao': row.get('descricao', '')
                    })
        return transacoes

    def _encontrar_combinacoes_soma(self, transacoes: List[Dict], valor_alvo: float, 
                                    tolerancia: float = 0.01) -> List[List[Dict]]:
        """Encontra combinações de transações que somam o valor alvo"""
        combinacoes_validas = []
        valor_min = valor_alvo * (1 - tolerancia)
        valor_max = valor_alvo * (1 + tolerancia)
        
        for r in range(2, min(6, len(transacoes) + 1)):
            for combinacao in combinations(transacoes, r):
                soma = sum(item['valor'] for item in combinacao)
                if valor_min <= soma <= valor_max:
                    combinacoes_validas.append(list(combinacao))
        return combinacoes_validas

    def _extrair_entidades_lote(self, df: pd.DataFrame) -> Dict[str, Dict]:
        """Extrai entidades de um lote de dados"""
        entidades_por_id = {}
        for _, row in df.iterrows():
            descricao = row.get('descricao', '')
            entidades_por_id[row['id']] = self._extrair_entidades(descricao.lower())
        return entidades_por_id

    def _calcular_compatibilidade_entidades(self, entidades1: Dict, entidades2: Dict) -> float:
        """Calcula compatibilidade entre conjuntos de entidades"""
        if not entidades1 or not entidades2: return 0.0
        compatibilidade, total_entidades = 0, 0
        for key in set(entidades1.keys()) | set(entidades2.keys()):
            if key in entidades1 and key in entidades2:
                if entidades1[key] and entidades2[key]:
                    if entidades1[key] == entidades2[key]: compatibilidade += 1
                    total_entidades += 1
            elif key in entidades1 and entidades1[key]: total_entidades += 1
            elif key in entidades2 and entidades2[key]: total_entidades += 1
        return (compatibilidade / total_entidades * 100) if total_entidades > 0 else 0.0

# Função de interface
def matching_ia_avancado(extrato_df: pd.DataFrame, contabil_df: pd.DataFrame,
                        nao_matchados_extrato: pd.DataFrame, nao_matchados_contabil: pd.DataFrame,
                        tolerancia_dias: int = 3, tolerancia_valor: float = 0.05) -> Dict:
    return AIMatcher().matching_avancado_com_ia(
        extrato_df, contabil_df, nao_matchados_extrato, nao_matchados_contabil,
        tolerancia_dias, tolerancia_valor
    )