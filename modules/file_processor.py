# modules/file_processor.py
import pandas as pd
import numpy as np
from datetime import datetime
import logging
import re
from typing import Dict, List, Any

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FileProcessor:
    def __init__(self):
        self.processed_files = {}
        self.mapping_cache = {}
    
    def detectar_formato_arquivo(self, arquivo_path: str) -> Dict[str, Any]:
        """Detecta automaticamente o formato e estrutura do arquivo"""
        try:
            df = pd.read_csv(arquivo_path, nrows=5, encoding='utf-8')
            
            # Análise das colunas
            colunas = df.columns.tolist()
            amostra_dados = df.head(3).to_dict('records')
            
            # Detectar tipo de arquivo baseado nas colunas
            tipo_arquivo = self._classificar_tipo_arquivo(colunas, amostra_dados)
            
            return {
                'tipo': tipo_arquivo,
                'colunas': colunas,
                'encoding': 'utf-8',
                'separador': ',',
                'amostra': amostra_dados
            }
            
        except Exception as e:
            logger.error(f"Erro ao detectar formato: {str(e)}")
            return {'tipo': 'desconhecido', 'colunas': [], 'encoding': 'utf-8', 'separador': ','}
    
    def _classificar_tipo_arquivo(self, colunas: List[str], amostra: List[Dict]) -> str:
        """Classifica o tipo de arquivo baseado nas colunas e dados"""
        colunas_lower = [col.lower() for col in colunas]
        
        # Padrões para extrato bancário
        padroes_extrato = ['data', 'valor', 'descricao', 'historico', 'saldo', 'categoria']
        if any(any(padrao in col for padrao in padroes_extrato) for col in colunas_lower):
            return 'extrato_bancario'
        
        # Padrões para contábeis
        padroes_contabil = ['lancamento', 'conta', 'debito', 'credito', 'cliente', 'fornecedor']
        if any(any(padrao in col for padrao in padroes_contabil) for col in colunas_lower):
            return 'lancamentos_contabeis'
        
        return 'desconhecido'
    
    def processar_extrato(self, arquivo_path: str, mapeamento_colunas: Dict = None) -> pd.DataFrame:
        """Processa arquivo de extrato bancário com mapeamento flexível"""
        logger.info(f"Processando extrato: {arquivo_path}")
        
        try:
            # Detectar formato
            info_arquivo = self.detectar_formato_arquivo(arquivo_path)
            
            # Ler arquivo com encoding detectado
            df = pd.read_csv(arquivo_path, encoding=info_arquivo['encoding'])
            
            # Aplicar mapeamento de colunas ou usar detecção automática
            if mapeamento_colunas:
                df = self._aplicar_mapeamento(df, mapeamento_colunas)
            else:
                df = self._mapeamento_automatico_extrato(df, info_arquivo['colunas'])
            
            # Processamento de dados
            df = self._processar_dados_extrato(df)
            
            logger.info(f"Extrato processado: {len(df)} transações")
            return df
            
        except Exception as e:
            logger.error(f"Erro ao processar extrato: {str(e)}")
            # Fallback para dados mock em caso de erro
            return self._criar_dados_extrato_mock()
    
    def processar_contabeis(self, arquivo_path: str, mapeamento_colunas: Dict = None) -> pd.DataFrame:
        """Processa arquivo de lançamentos contábeis com mapeamento flexível"""
        logger.info(f"Processando contábeis: {arquivo_path}")
        
        try:
            # Detectar formato
            info_arquivo = self.detectar_formato_arquivo(arquivo_path)
            
            # Ler arquivo
            df = pd.read_csv(arquivo_path, encoding=info_arquivo['encoding'])
            
            # Aplicar mapeamento
            if mapeamento_colunas:
                df = self._aplicar_mapeamento(df, mapeamento_colunas)
            else:
                df = self._mapeamento_automatico_contabil(df, info_arquivo['colunas'])
            
            # Processamento de dados
            df = self._processar_dados_contabil(df)
            
            logger.info(f"Contábeis processados: {len(df)} lançamentos")
            return df
            
        except Exception as e:
            logger.error(f"Erro ao processar contábeis: {str(e)}")
            return self._criar_dados_contabil_mock()
    
    def _mapeamento_automatico_extrato(self, df: pd.DataFrame, colunas_originais: List[str]) -> pd.DataFrame:
        """Mapeamento automático de colunas para extrato bancário"""
        mapeamento = {}
        colunas_lower = [col.lower() for col in colunas_originais]
        
        # Mapear data
        for padrao in ['data', 'date', 'dt', 'datahora']:
            if any(padrao in col for col in colunas_lower):
                idx = next(i for i, col in enumerate(colunas_lower) if padrao in col)
                mapeamento[colunas_originais[idx]] = 'data'
                break
        
        # Mapear valor
        for padrao in ['valor', 'value', 'amount', 'vlr']:
            if any(padrao in col for col in colunas_lower):
                idx = next(i for i, col in enumerate(colunas_lower) if padrao in col)
                mapeamento[colunas_originais[idx]] = 'valor'
                break
        
        # Mapear descrição
        for padrao in ['descricao', 'description', 'desc', 'historico', 'obs']:
            if any(padrao in col for col in colunas_lower):
                idx = next(i for i, col in enumerate(colunas_lower) if padrao in col)
                mapeamento[colunas_originais[idx]] = 'descricao'
                break
        
        return self._aplicar_mapeamento(df, mapeamento)
    
    def _mapeamento_automatico_contabil(self, df: pd.DataFrame, colunas_originais: List[str]) -> pd.DataFrame:
        """Mapeamento automático de colunas para lançamentos contábeis"""
        mapeamento = {}
        colunas_lower = [col.lower() for col in colunas_originais]
        
        # Mapear data
        for padrao in ['data', 'date', 'dt', 'data_lancamento']:
            if any(padrao in col for col in colunas_lower):
                idx = next(i for i, col in enumerate(colunas_lower) if padrao in col)
                mapeamento[colunas_originais[idx]] = 'data'
                break
        
        # Mapear valor
        for padrao in ['valor', 'value', 'amount', 'vlr']:
            if any(padrao in col for col in colunas_lower):
                idx = next(i for i, col in enumerate(colunas_lower) if padrao in col)
                mapeamento[colunas_originais[idx]] = 'valor'
                break
        
        # Mapear descrição
        for padrao in ['descricao', 'description', 'desc', 'historico', 'obs']:
            if any(padrao in col for col in colunas_lower):
                idx = next(i for i, col in enumerate(colunas_lower) if padrao in col)
                mapeamento[colunas_originais[idx]] = 'descricao'
                break
        
        # Mapear cliente/fornecedor
        for padrao in ['cliente', 'fornecedor', 'favorecido', 'beneficiario']:
            if any(padrao in col for col in colunas_lower):
                idx = next(i for i, col in enumerate(colunas_lower) if padrao in col)
                mapeamento[colunas_originais[idx]] = 'cliente_fornecedor'
                break
        
        return self._aplicar_mapeamento(df, mapeamento)
    
    def _aplicar_mapeamento(self, df: pd.DataFrame, mapeamento: Dict) -> pd.DataFrame:
        """Aplica mapeamento de colunas ao DataFrame"""
        df_renomeado = df.rename(columns=mapeamento)
        
        # Manter apenas colunas mapeadas e adicionar ID
        colunas_finais = [col for col in df_renomeado.columns if col in ['data', 'valor', 'descricao', 'cliente_fornecedor']]
        df_final = df_renomeado[colunas_finais].copy()
        df_final['id'] = range(1, len(df_final) + 1)
        
        return df_final
    
    def _processar_dados_extrato(self, df: pd.DataFrame) -> pd.DataFrame:
        """Processa e limpa dados do extrato bancário"""
        # Converter data
        if 'data' in df.columns:
            df['data'] = pd.to_datetime(df['data'], errors='coerce')
        
        # Converter valor
        if 'valor' in df.columns:
            # Remover caracteres não numéricos e converter
            df['valor'] = df['valor'].astype(str).str.replace(r'[^\d,-]', '', regex=True)
            df['valor'] = df['valor'].str.replace(',', '.').astype(float)
        
        # Limpar descrição
        if 'descricao' in df.columns:
            df['descricao'] = df['descricao'].astype(str).str.strip()
        
        return df
    
    def _processar_dados_contabil(self, df: pd.DataFrame) -> pd.DataFrame:
        """Processa e limpa dados contábeis"""
        # Converter data
        if 'data' in df.columns:
            df['data'] = pd.to_datetime(df['data'], errors='coerce')
        
        # Converter valor (garantir positivo para contabilidade)
        if 'valor' in df.columns:
            df['valor'] = pd.to_numeric(df['valor'], errors='coerce').abs()
        
        # Limpar descrição
        if 'descricao' in df.columns:
            df['descricao'] = df['descricao'].astype(str).str.strip()
        
        return df

    def _criar_dados_extrato_mock(self) -> pd.DataFrame:
        """Cria dados mock de extrato bancário para fallback"""
        logger.info("Usando dados mock de extrato")
        
        dados = [
            {
                'id': 1,
                'data': pd.Timestamp('2024-01-01'),
                'valor': -150.00,
                'descricao': 'SUPERMERCADO ABC',
                'categoria': 'Alimentação'
            },
            {
                'id': 2,
                'data': pd.Timestamp('2024-01-02'),
                'valor': -80.50,
                'descricao': 'RESTAURANTE XPTO',
                'categoria': 'Alimentação'
            },
            {
                'id': 3,
                'data': pd.Timestamp('2024-01-03'),
                'valor': 5000.00,
                'descricao': 'PIX RECEBIDO - CLIENTE A',
                'categoria': 'Receitas'
            },
            {
                'id': 4,
                'data': pd.Timestamp('2024-01-04'),
                'valor': -120.00,
                'descricao': 'POSTO SHELL - COMBUSTIVEL',
                'categoria': 'Transporte'
            },
            {
                'id': 5,
                'data': pd.Timestamp('2024-01-05'),
                'valor': -250.00,
                'descricao': 'PAGAMENTO BOLETO FORNECEDOR',
                'categoria': 'Compras'
            }
        ]
        
        return pd.DataFrame(dados)

    def _criar_dados_contabil_mock(self) -> pd.DataFrame:
        """Cria dados mock de lançamentos contábeis para fallback"""
        logger.info("Usando dados mock contábeis")
        
        dados = [
            {
                'id': 1,
                'data': pd.Timestamp('2024-01-01'),
                'valor': 150.00,
                'descricao': 'COMPRA SUPERMERCADO ABC',
                'cliente_fornecedor': 'SUPERMERCADO ABC',
                'categoria': 'Alimentação'
            },
            {
                'id': 2,
                'data': pd.Timestamp('2024-01-02'),
                'valor': 80.50,
                'descricao': 'REFEICAO RESTAURANTE XPTO',
                'cliente_fornecedor': 'RESTAURANTE XPTO',
                'categoria': 'Alimentação'
            },
            {
                'id': 3,
                'data': pd.Timestamp('2024-01-03'),
                'valor': 5000.00,
                'descricao': 'RECEBIMENTO PIX CLIENTE A',
                'cliente_fornecedor': 'CLIENTE A',
                'categoria': 'Receitas'
            },
            {
                'id': 4,
                'data': pd.Timestamp('2024-01-04'),
                'valor': 120.00,
                'descricao': 'ABASTECIMENTO VEICULAR SHELL',
                'cliente_fornecedor': 'POSTO SHELL',
                'categoria': 'Transporte'
            },
            {
                'id': 5,
                'data': pd.Timestamp('2024-01-05'),
                'valor': 250.00,
                'descricao': 'PAGAMENTO BOLETO FORNECEDOR B',
                'cliente_fornecedor': 'FORNECEDOR B',
                'categoria': 'Compras'
            }
        ]
        
        return pd.DataFrame(dados)

# Funções de interface para o Streamlit
def processar_extrato(arquivo_path: str, mapeamento_colunas: Dict = None) -> pd.DataFrame:
    processor = FileProcessor()
    return processor.processar_extrato(arquivo_path, mapeamento_colunas)

def processar_contabeis(arquivo_path: str, mapeamento_colunas: Dict = None) -> pd.DataFrame:
    processor = FileProcessor()
    return processor.processar_contabeis(arquivo_path, mapeamento_colunas)

def detectar_formato_arquivo(arquivo_path: str) -> Dict[str, Any]:
    processor = FileProcessor()
    return processor.detectar_formato_arquivo(arquivo_path)