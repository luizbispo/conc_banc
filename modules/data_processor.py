# modules/data_processor.py
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import requests
import re
import io
import tempfile
import os
from urllib.parse import urlparse, parse_qs, unquote, urlencode, quote
import warnings
import base64
warnings.filterwarnings('ignore')

class CloudImporter:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
        })
    
    def identificar_tipo_url(self, url):
        """Identifica o tipo de URL"""
        url_lower = url.lower()
        
        if 'drive.google.com' in url_lower:
            if '/file/' in url_lower:
                return 'google_drive_file'
            elif '/folders/' in url_lower:
                return 'google_drive_folder'
            else:
                return 'google_drive'
        elif 'sharepoint.com' in url_lower:
            return 'sharepoint_folder'
        elif '1drv.ms' in url_lower:
            return 'onedrive'
        else:
            return 'desconhecido'
    
    def extrair_file_id_google_drive(self, url):
        """Extrai File ID do Google Drive"""
        try:
            # Padrões do Google Drive
            patterns = [
                r'/file/d/([a-zA-Z0-9_-]+)',
                r'/folders/([a-zA-Z0-9_-]+)',
                r'id=([a-zA-Z0-9_-]+)',
                r'/[a-zA-Z0-9_-]{25,}'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, url)
                if match:
                    return match.group(1)
            return None
        except Exception as e:
            print(f"Erro ao extrair file_id: {e}")
            return None
    
    def listar_arquivos_google_drive_folder(self, folder_url):
        """Lista arquivos em uma pasta do Google Drive"""
        try:
            folder_id = self.extrair_file_id_google_drive(folder_url)
            if not folder_id:
                return []
            
            # URL da API do Google Drive (simplificada)
            api_url = f"https://drive.google.com/drive/folders/{folder_id}"
            
            response = self.session.get(api_url)
            if response.status_code == 200:
                # Extrair informações da página (método simplificado)
                files = []
                
                # Procurar por links de arquivos
                file_links = re.findall(r'href="https://drive\.google\.com/file/d/([a-zA-Z0-9_-]+)/view', response.text)
                for file_id in set(file_links):
                    files.append({
                        'id': file_id,
                        'name': f"file_{file_id}",  # Nome será obtido depois
                        'type': 'file'
                    })
                
                return files
            return []
        except Exception as e:
            print(f"Erro listar Google Drive: {e}")
            return []
    
    def baixar_google_drive_file(self, file_id, file_name=None):
        """Baixa arquivo do Google Drive pelo File ID"""
        try:
            # URL de download direto
            download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
            
            response = self.session.get(download_url, allow_redirects=True)
            
            # Verificar se há confirmação de download
            if "confirm=" in response.url:
                # Extrair token de confirmação
                confirm_match = re.search(r'confirm=([^&]+)', response.url)
                if confirm_match:
                    confirm_token = confirm_match.group(1)
                    download_url = f"https://drive.google.com/uc?export=download&id={file_id}&confirm={confirm_token}"
                    response = self.session.get(download_url, allow_redirects=True)
            
            if response.status_code == 200:
                # Tentar obter o nome real do arquivo
                if not file_name:
                    content_disposition = response.headers.get('content-disposition', '')
                    filename_match = re.search(r'filename="([^"]+)"', content_disposition)
                    if filename_match:
                        file_name = filename_match.group(1)
                    else:
                        file_name = f"arquivo_{file_id}.csv"
                
                return response.content, file_name
            return None, None
            
        except Exception as e:
            print(f"Erro download Google Drive: {e}")
            return None, None
    
    def buscar_arquivos_por_padrao(self, folder_url, padrao_nome, mes_referencia, tipo_servico):
        """Busca arquivos por padrão em diferentes serviços"""
        arquivos_encontrados = []
        
        # Mapeamento de meses
        meses_map = {
            'Janeiro': ['janeiro', 'jan', '01', '1'],
            'Fevereiro': ['fevereiro', 'fev', '02', '2'],
            'Março': ['março', 'marco', 'mar', '03', '3'],
            'Abril': ['abril', 'abr', '04', '4'],
            'Maio': ['maio', 'mai', '05', '5'],
            'Junho': ['junho', 'jun', '06', '6'],
            'Julho': ['julho', 'jul', '07', '7'],
            'Agosto': ['agosto', 'ago', '08', '8'],
            'Setembro': ['setembro', 'set', '09', '9'],
            'Outubro': ['outubro', 'out', '10'],
            'Novembro': ['novembro', 'nov', '11'],
            'Dezembro': ['dezembro', 'dez', '12']
        }
        
        padroes_mes = meses_map.get(mes_referencia, [mes_referencia.lower()])
        
        if tipo_servico == 'google_drive_folder':
            # Para Google Drive, tentar nomes específicos
            nomes_tentativas = []
            
            # Gerar combinações de nomes
            prefixos = ['extrato_bancario', 'extrato', 'contabil', 'lancamentos', 'contabilidade']
            extensoes = ['.csv', '.xlsx', '.xls']
            
            for prefixo in prefixos:
                for padrao_mes in padroes_mes:
                    for extensao in extensoes:
                        nomes_tentativas.append(f"{prefixo}_{padrao_mes}{extensao}")
                        nomes_tentativas.append(f"{prefixo}{padrao_mes}{extensao}")
            
            # Tentar baixar cada arquivo
            for nome_arquivo in nomes_tentativas:
                if re.search(padrao_nome, nome_arquivo, re.IGNORECASE):
                    # Para Google Drive, precisamos de uma abordagem diferente
                    # Vamos tentar construir URLs diretas
                    file_id = self.extrair_file_id_google_drive(folder_url)
                    if file_id:
                        # Tentar baixar como se fosse um arquivo específico
                        content, real_name = self.baixar_google_drive_file(file_id, nome_arquivo)
                        if content:
                            arquivos_encontrados.append({
                                'content': content,
                                'name': real_name or nome_arquivo,
                                'source': 'google_drive'
                            })
        
        elif tipo_servico == 'sharepoint_folder':
            # Para SharePoint, tentar URLs diretas
            nomes_tentativas = [
                f"extrato_bancario_{mes_referencia.lower()}.csv",
                f"contabil_{mes_referencia.lower()}.csv",
                f"extrato_{mes_referencia.lower()}.csv",
                f"lancamentos_{mes_referencia.lower()}.csv",
            ]
            
            for nome_arquivo in nomes_tentativas:
                if re.search(padrao_nome, nome_arquivo, re.IGNORECASE):
                    # Construir URL do SharePoint
                    if '/:f:/' in folder_url:
                        parts = folder_url.split('/:f:/')
                        site_url = parts[0]
                        folder_path = parts[1].split('?')[0]
                        
                        tentativa_url = f"{site_url}/:x:/r/personal/{folder_path}/{quote(nome_arquivo)}?csf=1&web=1&e=download"
                        
                        response = self.session.get(tentativa_url, allow_redirects=True)
                        if response.status_code == 200 and len(response.content) > 100:
                            arquivos_encontrados.append({
                                'content': response.content,
                                'name': nome_arquivo,
                                'source': 'sharepoint'
                            })
        
        return arquivos_encontrados
    
    def carregar_dataframe(self, content, file_name):
        """Carrega DataFrame do conteúdo baixado"""
        try:
            file_name_lower = file_name.lower()
            
            if file_name_lower.endswith('.csv'):
                # Tentar diferentes encodings
                encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1', 'windows-1252']
                
                for encoding in encodings:
                    try:
                        df = pd.read_csv(io.BytesIO(content), encoding=encoding)
                        print(f"✅ CSV carregado: {file_name} (encoding: {encoding})")
                        return df
                    except (UnicodeDecodeError, pd.errors.ParserError) as e:
                        continue
                
                # Tentativa final
                try:
                    return pd.read_csv(io.BytesIO(content))
                except Exception as e:
                    print(f"❌ Erro ao ler CSV {file_name}: {e}")
                    return None
                    
            elif file_name_lower.endswith(('.xlsx', '.xls')):
                try:
                    return pd.read_excel(io.BytesIO(content))
                except Exception as e:
                    print(f"❌ Erro ao ler Excel {file_name}: {e}")
                    return None
            else:
                print(f"❌ Formato não suportado: {file_name}")
                return None
                
        except Exception as e:
            print(f"❌ Erro geral ao carregar {file_name}: {e}")
            return None

def importar_de_pasta_cloud(folder_url, padrao_nome, mes_referencia, tipo_arquivo):
    """
    Importa dados de pastas na nuvem (Google Drive, SharePoint)
    """
    importer = CloudImporter()
    tipo_servico = importer.identificar_tipo_url(folder_url)
    
    print(f"\n🎯 Buscando {tipo_arquivo}")
    print(f"📁 URL: {folder_url}")
    print(f"🏷️ Tipo: {tipo_servico}")
    print(f"🔍 Padrão: {padrao_nome}")
    print(f"📅 Mês: {mes_referencia}")
    
    # Buscar arquivos
    arquivos = importer.buscar_arquivos_por_padrao(folder_url, padrao_nome, mes_referencia, tipo_servico)
    
    if not arquivos:
        print(f"❌ Nenhum arquivo encontrado para {tipo_arquivo}")
        return None
    
    print(f"✅ Encontrados {len(arquivos)} arquivo(s)")
    
    # Carregar DataFrames
    dataframes = []
    for arquivo in arquivos:
        df = importer.carregar_dataframe(arquivo['content'], arquivo['name'])
        if df is not None and not df.empty:
            df['_origem_arquivo'] = arquivo['name']
            df['_fonte'] = arquivo['source']
            dataframes.append(df)
            print(f"📊 Carregado: {arquivo['name']} - {len(df)} registros")
    
    # Combinar DataFrames
    if dataframes:
        combined_df = pd.concat(dataframes, ignore_index=True)
        print(f"📈 Total {tipo_arquivo}: {len(combined_df)} registros")
        return combined_df
    else:
        print(f"⚠️ Nenhum arquivo válido carregado para {tipo_arquivo}")
        return None

# Funções de processamento (mantidas)
def processar_extrato(df, col_data, col_valor, col_descricao):
    """Processa e padroniza DataFrame do extrato bancário"""
    df_processed = df.copy()
    
    # Renomear colunas para padrão interno
    df_processed = df_processed.rename(columns={
        col_data: 'data',
        col_valor: 'valor',
        col_descricao: 'descricao'
    })
    
    # Garantir que temos as colunas mínimas
    required_cols = ['data', 'valor', 'descricao']
    for col in required_cols:
        if col not in df_processed.columns:
            raise ValueError(f"Coluna '{col}' não encontrada no extrato")
    
    # Processar data
    df_processed['data'] = pd.to_datetime(df_processed['data'], errors='coerce')
    df_processed = df_processed.dropna(subset=['data'])
    
    # Processar valor
    df_processed['valor'] = pd.to_numeric(df_processed['valor'], errors='coerce')
    df_processed = df_processed.dropna(subset=['valor'])
    
    # Adicionar ID único
    df_processed['id'] = range(1, len(df_processed) + 1)
    
    # Ordenar por data
    df_processed = df_processed.sort_values('data').reset_index(drop=True)
    
    return df_processed[['id', 'data', 'valor', 'descricao'] + 
                       [col for col in df_processed.columns if col not in ['id', 'data', 'valor', 'descricao']]]

def processar_contabil(df, col_data, col_valor, col_descricao):
    """Processa e padroniza DataFrame dos lançamentos contábeis"""
    df_processed = df.copy()
    
    # Renomear colunas para padrão interno
    df_processed = df_processed.rename(columns={
        col_data: 'data',
        col_valor: 'valor',
        col_descricao: 'descricao'
    })
    
    # Garantir que temos as colunas mínimas
    required_cols = ['data', 'valor', 'descricao']
    for col in required_cols:
        if col not in df_processed.columns:
            raise ValueError(f"Coluna '{col}' não encontrada nos lançamentos")
    
    # Processar data
    df_processed['data'] = pd.to_datetime(df_processed['data'], errors='coerce')
    df_processed = df_processed.dropna(subset=['data'])
    
    # Processar valor
    df_processed['valor'] = pd.to_numeric(df_processed['valor'], errors='coerce')
    df_processed = df_processed.dropna(subset=['valor'])
    
    # Adicionar ID único
    df_processed['id'] = range(1, len(df_processed) + 1)
    
    # Ordenar por data
    df_processed = df_processed.sort_values('data').reset_index(drop=True)
    
    return df_processed[['id', 'data', 'valor', 'descricao'] + 
                       [col for col in df_processed.columns if col not in ['id', 'data', 'valor', 'descricao']]]

