# pages/1_📥_importacao_dados.py
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import csv
import io
import requests
import re
from urllib.parse import urlparse
import modules.data_processor as processor
import tempfile
import os
import time
from typing import Optional, Tuple
from modules.performance_optimizer import chunker, cache_manager
from modules.auth_middleware import enforce_auth, get_current_user
from modules.audit_logger import get_audit_logger
from modules.structured_logger import get_structured_logger

# Esta página processa uploads de arquivos (a principal superfície de dado
# externo não confiável do sistema) e, diferente das demais páginas
# (análise, relatório), NÃO tinha NENHUM guard de autenticação — era
# acessível diretamente por URL sem login. enforce_auth() bloqueia a
# execução do restante do script (st.stop()) se não houver sessão válida.
enforce_auth()

audit = get_audit_logger()
_usuario_logado = get_current_user()
usuario_atual = _usuario_logado['username'] if _usuario_logado else 'desconhecido'

# Limite de tamanho de arquivo: antes não havia nenhum limite explícito de
# bytes no caminho de importação, apesar de ser dado externo não confiável.
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB

def validar_tamanho_arquivo(arquivo):
    """Retorna (valido, motivo). motivo é None quando válido."""
    tamanho = getattr(arquivo, 'size', None)
    if tamanho is not None and tamanho > MAX_FILE_SIZE_BYTES:
        limite_mb = MAX_FILE_SIZE_BYTES / (1024 * 1024)
        tamanho_mb = tamanho / (1024 * 1024)
        return False, f"Arquivo '{arquivo.name}' excede o limite de {limite_mb:.0f}MB ({tamanho_mb:.1f}MB)."
    return True, None

# Limite de páginas/linhas para PDF e CNAB: o limite de tamanho em bytes
# acima não protege contra um arquivo pequeno em disco mas com um número
# extremo de páginas/linhas (ex.: um PDF majoritariamente texto), que
# fazia processar_pdf/processar_cnab iterar sem nenhum teto — consumo de
# CPU proporcional ao conteúdo, não ao tamanho em bytes validado.
MAX_PDF_PAGINAS = int(os.getenv("CONCILIACAO_MAX_PDF_PAGINAS", "200"))
MAX_CNAB_LINHAS = int(os.getenv("CONCILIACAO_MAX_CNAB_LINHAS", "50000"))

# Limites ESTRUTURAIS de OFX/CSV (revisão de segurança, SEC-R-03,
# XCRE-52): MAX_FILE_SIZE_BYTES acima só limita o tamanho em bytes do
# upload — um OFX de 50.000 transações cabe folgado nesses 10 MiB e
# levava ~119s no `ofxparse` (crescimento pior que linear), uma negação
# de serviço barata de montar. As constantes abaixo rejeitam ANTES do
# parsing pesado, com mensagem fixa em português.
#
# OFX: contagem LITERAL (case-sensitive) de ocorrências de `<STMTTRN>`
# nos bytes crus — decisão deliberada do contrato desta issue: é uma
# contagem "barata" (sem decodificar/parsear nada) que cobre o formato
# real emitido pelos bancos (tag em maiúsculas, conforme o padrão OFX);
# uma variante de grafia (minúsculas) não seria contada aqui e passaria
# para o `ofxparse` normalmente.
LIMITE_OFX_MAX_TRANSACOES = int(os.getenv("CONCILIACAO_LIMITE_OFX_TRANSACOES", "20000"))
# CSV: linhas totais (contadas via csv.reader, inclui o cabeçalho),
# colunas do cabeçalho, e caracteres de um único campo — qualquer um
# dos três acima do limite rejeita o arquivo inteiro.
LIMITE_CSV_MAX_LINHAS = int(os.getenv("CONCILIACAO_LIMITE_CSV_LINHAS", "100000"))
LIMITE_CSV_MAX_COLUNAS = int(os.getenv("CONCILIACAO_LIMITE_CSV_COLUNAS", "200"))
LIMITE_CSV_MAX_CARACTERES_CAMPO = int(os.getenv("CONCILIACAO_LIMITE_CSV_CAMPO_CARACTERES", "10000"))

def _contar_linhas_arquivo(arquivo) -> int:
    """Conta as linhas do arquivo (tentando os mesmos encodings dos
    parsers CNAB) e devolve o cursor ao início, para que o processamento
    normal leia o conteúdo completo depois."""
    arquivo.seek(0)
    content = arquivo.read()
    arquivo.seek(0)
    for encoding in ['latin-1', 'iso-8859-1', 'cp1252', 'utf-8']:
        try:
            return len(content.decode(encoding).split('\n'))
        except UnicodeDecodeError:
            continue
    return 0

# Validação de entrada para OFX/CSV: antes destas funções, um arquivo
# vazio, binário, com encoding não suportado ou sem as colunas mínimas
# (data/valor) só era detectado quando o parser correspondente (pandas,
# ofxparse) já tinha lançado uma exceção — cuja mensagem crua (em inglês,
# às vezes citando estrutura interna do parser) chegava direto ao
# usuário via `st.error(f"...: {e}")`. As funções abaixo validam ANTES
# do parsing e devolvem mensagens fixas em português, sem stack trace e
# sem caminho de arquivo (apenas o nome do upload, que o usuário já viu).
ENCODINGS_SUPORTADOS_CSV = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']

# Padrões de nome de coluna já usados em modules/file_processor.py para
# mapeamento automático; aqui servem para decidir se o CSV tem, no
# mínimo, uma coluna de data e uma de valor reconhecíveis.
_PADROES_COLUNA_DATA = ['data', 'date', 'dt']
_PADROES_COLUNA_VALOR = ['valor', 'value', 'amount', 'vlr']


def _detectar_conteudo_binario(conteudo: bytes) -> bool:
    """Heurística para distinguir texto (CSV/OFX) de binário: byte NUL ou
    proporção alta de bytes fora da faixa imprimível/latin nos primeiros
    4KB. Não decodifica nada, então funciona mesmo com encoding inválido."""
    if b'\x00' in conteudo:
        return True
    if not conteudo:
        return False
    amostra = conteudo[:4096]
    texto_ok = sum(1 for b in amostra if b in (9, 10, 13) or 32 <= b <= 126 or b >= 160)
    return (texto_ok / len(amostra)) < 0.85


@st.cache_data(show_spinner=False)
def _parsear_csv_cacheado(conteudo: bytes, encoding: str) -> pd.DataFrame:
    """Núcleo de parsing do CSV: isolado (só bytes + encoding, sem
    Streamlit, sem sessão, sem arquivo em disco) e cacheado.

    Sem este cache, o Streamlit reexecuta o script inteiro a cada
    interação na página (mudar um filtro, clicar em outro botão etc.),
    e o MESMO upload seria relido e reparseado do zero em cada rerun.
    `st.cache_data` calcula um hash determinístico dos argumentos — aqui
    os bytes crus do arquivo e o encoding já detectado por
    `validar_entrada_csv` — como chave de cache: o mesmo conteúdo com o
    mesmo encoding reaproveita o DataFrame já parseado; qualquer byte
    diferente OU encoding diferente (mesmo conteúdo, parâmetro
    diferente) gera uma chave nova e reprocessa. `st.cache_data` (ao
    contrário de `st.cache_resource`) devolve uma CÓPIA do valor
    cacheado em cada chamada, então mutar o DataFrame retornado (ex.:
    adicionar coluna em `processar_arquivo`) nunca contamina o cache.
    Não recebe nem guarda nada além dos bytes e do encoding — nenhuma
    credencial, sessão ou objeto mutável do Streamlit passa por aqui."""
    texto = conteudo.decode(encoding)
    return pd.read_csv(io.StringIO(texto))


def _validar_limites_estruturais_csv(texto: str, nome: str) -> Optional[str]:
    """Uma única passada pelo CSV com `csv.reader` checando linhas
    totais, colunas do cabeçalho e o maior campo (SEC-R-03, XCRE-52).
    Devolve a mensagem de rejeição (fixa, em português) se algum limite
    for ultrapassado, ou None se estiver tudo dentro dos limites.

    Levanta temporariamente o teto interno do módulo `csv`
    (`field_size_limit`, 131072 por padrão) para bater com
    LIMITE_CSV_MAX_CARACTERES_CAMPO: sem isso, um campo maior que esse
    padrão faria o próprio `csv.reader` estourar `csv.Error` ("field
    larger than field limit") ANTES do nosso `len(campo)` conseguir
    rodar — um stack trace vazando em vez da mensagem fixa. Sempre
    restaura o valor anterior no `finally`, porque é um estado global
    do processo, não local desta função."""
    limite_anterior = csv.field_size_limit(max(LIMITE_CSV_MAX_CARACTERES_CAMPO, 1))
    try:
        num_colunas_cabecalho = None
        num_linhas = 0
        for linha in csv.reader(io.StringIO(texto)):
            num_linhas += 1
            if num_colunas_cabecalho is None:
                num_colunas_cabecalho = len(linha)
                if num_colunas_cabecalho > LIMITE_CSV_MAX_COLUNAS:
                    return (
                        f"Arquivo '{nome}' tem {num_colunas_cabecalho} colunas, acima do limite de "
                        f"{LIMITE_CSV_MAX_COLUNAS} colunas por importação."
                    )
            if num_linhas > LIMITE_CSV_MAX_LINHAS:
                return (
                    f"Arquivo '{nome}' tem mais de {LIMITE_CSV_MAX_LINHAS} linhas, acima do limite "
                    "permitido por importação."
                )
            for campo in linha:
                if len(campo) > LIMITE_CSV_MAX_CARACTERES_CAMPO:
                    return (
                        f"Arquivo '{nome}' tem um campo com mais de {LIMITE_CSV_MAX_CARACTERES_CAMPO} "
                        "caracteres, acima do limite permitido por campo."
                    )
        return None
    except csv.Error:
        return (
            f"Arquivo '{nome}' tem um campo com mais de {LIMITE_CSV_MAX_CARACTERES_CAMPO} "
            "caracteres, acima do limite permitido por campo."
        )
    finally:
        csv.field_size_limit(limite_anterior)


def validar_entrada_csv(arquivo) -> Tuple[bool, str, Optional[str], Optional[pd.DataFrame]]:
    """Valida um upload CSV antes de usá-lo na conciliação.

    Retorna (valido, motivo, encoding_usado, dataframe). Quando válido,
    motivo é "" e dataframe já vem lido (evita ler o conteúdo duas vezes
    com encodings diferentes)."""
    nome = getattr(arquivo, 'name', 'arquivo')

    if not nome.lower().endswith('.csv'):
        return False, f"Arquivo '{nome}' não tem extensão .csv.", None, None

    arquivo.seek(0)
    conteudo = arquivo.read()
    arquivo.seek(0)

    if len(conteudo) == 0:
        return False, f"Arquivo '{nome}' está vazio.", None, None

    if _detectar_conteudo_binario(conteudo):
        return False, f"Arquivo '{nome}' parece conter dados binários, não um CSV de texto válido.", None, None

    texto = None
    encoding_usado = None
    for encoding in ENCODINGS_SUPORTADOS_CSV:
        try:
            texto = conteudo.decode(encoding)
            encoding_usado = encoding
            break
        except (UnicodeDecodeError, LookupError):
            continue

    if texto is None:
        return (
            False,
            f"Não foi possível identificar o encoding do arquivo '{nome}'. "
            "Salve o arquivo em UTF-8, Latin-1 ou CP1252 e tente novamente.",
            None,
            None,
        )

    # Limites estruturais ANTES do parsing pesado do pandas (SEC-R-03,
    # XCRE-52): uma única passada com csv.reader (mais barata que
    # pd.read_csv, que faz inferência de tipo e indexação) contando
    # linhas totais, colunas do cabeçalho e o maior campo — rejeita
    # assim que o primeiro limite é ultrapassado, sem ler o arquivo
    # inteiro quando não é preciso.
    motivo_limite = _validar_limites_estruturais_csv(texto, nome)
    if motivo_limite:
        return False, motivo_limite, encoding_usado, None

    try:
        df = _parsear_csv_cacheado(conteudo, encoding_usado)
    except (pd.errors.EmptyDataError, pd.errors.ParserError):
        return False, f"Arquivo '{nome}' não pôde ser interpretado como CSV válido.", encoding_usado, None

    if df.empty or len(df.columns) == 0:
        return False, f"Arquivo '{nome}' não contém dados.", encoding_usado, None

    colunas_lower = [str(c).lower() for c in df.columns]
    tem_data = any(any(padrao in col for padrao in _PADROES_COLUNA_DATA) for col in colunas_lower)
    tem_valor = any(any(padrao in col for padrao in _PADROES_COLUNA_VALOR) for col in colunas_lower)

    faltando = [nome_col for nome_col, ok in (("data", tem_data), ("valor", tem_valor)) if not ok]
    if faltando:
        return (
            False,
            f"Arquivo '{nome}' não contém as colunas obrigatórias: {', '.join(faltando)}. "
            f"Colunas encontradas: {', '.join(str(c) for c in df.columns)}.",
            encoding_usado,
            None,
        )

    return True, "", encoding_usado, df


def validar_entrada_ofx(arquivo) -> Tuple[bool, str]:
    """Valida um upload OFX antes de enviá-lo ao ofxparse.

    Retorna (valido, motivo); motivo é "" quando válido."""
    nome = getattr(arquivo, 'name', 'arquivo')

    if not nome.lower().endswith('.ofx'):
        return False, f"Arquivo '{nome}' não tem extensão .ofx."

    arquivo.seek(0)
    conteudo = arquivo.read()
    arquivo.seek(0)

    if len(conteudo) == 0:
        return False, f"Arquivo '{nome}' está vazio."

    if _detectar_conteudo_binario(conteudo):
        return False, f"Arquivo '{nome}' parece conter dados binários, não um OFX de texto válido."

    if b'ofx' not in conteudo[:2048].lower():
        return False, f"Arquivo '{nome}' não parece ser um OFX válido (cabeçalho OFX não encontrado)."

    num_transacoes = conteudo.count(b'<STMTTRN>')
    if num_transacoes > LIMITE_OFX_MAX_TRANSACOES:
        return (
            False,
            f"Arquivo '{nome}' tem {num_transacoes} transações, acima do limite de "
            f"{LIMITE_OFX_MAX_TRANSACOES} transações por importação.",
        )

    return True, ""


def _categorizar_motivo_carga_arquivo(mensagem: str) -> str:
    """Mapeia uma mensagem de erro (livre, já pensada para o usuário —
    ver validar_entrada_csv/validar_entrada_ofx/validar_tamanho_arquivo)
    para uma categoria fixa e curta, sem o nome do arquivo, para uso no
    log estruturado (item 5): o log nunca grava a mensagem original,
    que pode conter o nome do upload. As frases comparadas aqui são
    templates fixos definidos neste mesmo módulo (item 1), não texto
    livre do usuário — o casamento por substring é estável."""
    texto = mensagem.lower()
    if 'excede o limite' in texto:
        return 'tamanho_excedido'
    if 'não tem extensão' in texto:
        return 'extensao_invalida'
    if 'está vazio' in texto:
        return 'arquivo_vazio'
    if 'binári' in texto:
        return 'arquivo_binario'
    if 'cabeçalho' in texto:
        return 'cabecalho_invalido'
    if 'encoding' in texto:
        return 'encoding_invalido'
    if 'colunas obrigatórias' in texto:
        return 'colunas_obrigatorias_faltando'
    if 'transações, acima do limite' in texto:
        return 'limite_transacoes_excedido'
    if 'linhas, acima do limite' in texto:
        return 'limite_linhas_excedido'
    if 'colunas, acima do limite' in texto:
        return 'limite_colunas_excedido'
    if 'caracteres, acima do limite' in texto:
        return 'limite_campo_excedido'
    if 'não contém dados' in texto or 'não pôde ser interpretado' in texto:
        return 'erro_parsing'
    return 'erro_desconhecido'


# Categorias de rejeição por limite estrutural (OFX: transações; CSV:
# linhas, colunas, tamanho de campo). Achado do E2E da fase 5c: subir
# um OFX de 25.000 transações mostrava a mensagem certa MAS TAMBÉM duas
# redundantes por cima ("motivo de carga de arquivo desconhecido" e
# "Não foi possível extrair dados do arquivo") — o fluxo seguia depois
# da rejeição em vez de parar. `processar_arquivo` devolve o sentinela
# abaixo (em vez de None) para esses motivos, para o chamador do fluxo
# de upload único (mais abaixo neste módulo) saber que uma mensagem
# específica JÁ foi exibida e não mostrar por cima a mensagem genérica.
_MOTIVOS_LIMITE_CARGA_ARQUIVO = {
    'limite_transacoes_excedido', 'limite_linhas_excedido',
    'limite_colunas_excedido', 'limite_campo_excedido',
}


class _ArquivoRejeitadoPorLimite:
    """Sentinela: distingue "rejeitado por limite, mensagem específica
    já mostrada" de None ("nenhum dado extraído", sem mensagem própria
    exibida por processar_arquivo)."""


ARQUIVO_REJEITADO_POR_LIMITE = _ArquivoRejeitadoPorLimite()

# --- Menu Customizado ---
with st.sidebar:
    st.markdown("### Navegação Principal") 
    st.page_link("app.py", label="Início (Home)", icon="🏠")
    
    st.page_link("pages/importacao_dados.py", label="📥 Importação de Dados", icon=None)
    st.page_link("pages/analise_dados.py", label="📊 Análise de Divergências", icon=None)
    st.page_link("pages/gerar_relatorio.py", label="📝 Relatório Final", icon=None)
# --- Fim do Menu Customizado ---

st.set_page_config(page_title="Importação de Dados", page_icon="📥", layout="wide")

st.title("📥 Importação de Dados para Conciliação")
st.markdown("Escolha o método de importação e siga as instruções para carregar seus dados")

# Inicializar session state
if 'extrato_df' not in st.session_state:
    st.session_state.extrato_df = None
if 'contabil_df' not in st.session_state:
    st.session_state.contabil_df = None
if 'dados_carregados' not in st.session_state:
    st.session_state.dados_carregados = False
if 'conta_selecionada' not in st.session_state:
    st.session_state.conta_selecionada = None

# Sidebar com instruções
st.sidebar.header("📋 Instruções Gerais")

st.sidebar.markdown("""
**📊 Formatos Suportados:**
- **Extrato Bancário:** OFX, CNAB (RET), CSV, Excel, PDF (com texto)
- **Lançamentos Contábeis:** CSV, Excel, PDF (com texto)

**⏰ Período:** Ambos devem ser do mesmo mês
""")

# Seleção do método de importação - DEFINIR ANTES DE USAR
st.sidebar.header("🔧 Método de Importação")
metodo_importacao = st.sidebar.radio(
    "Como deseja importar os dados?",
    ["📤 Upload de Arquivos", "☁️ Link de Pastas na Nuvem", "🔗 Links Diretos para Arquivos"],
    index=0
)

# NOVO SISTEMA DE VALIDAÇÃO
st.sidebar.header("🎯 Novo Sistema de Validação")
sistema_validacao = st.sidebar.checkbox(
    "Usar sistema de validação por nome de arquivo", 
    value=False,
    help="Ative para usar o formato B_12345678.extensão e C_12345678.extensão"
)

# ADICIONAR OPÇÃO PARA PERMITIR OFX NO CONTÁBIL
permitir_ofx_contabil = st.sidebar.checkbox(
    "Permitir OFX no lado contábil", 
    value=True,
    help="Permitir arquivos OFX como lançamentos contábeis (pode desativar depois)"
)

# Instruções
with st.expander("📋 Guia Completo de Importação"):
    st.markdown("""
    ## 📊 Métodos de Importação Recomendados
    
    ### 📤 Upload de Arquivos (RECOMENDADO)
    **Quando usar:** Testes iniciais, arquivos locais
                
    **Vantagens:** 
    - Mais confiável
    - Funciona offline
    - Processamento rápido
    
    ### ☁️ Link de Pastas (EXPERIMENTAL)
    **Quando usar:** Arquivos já organizados em pastas na nuvem
                
    **Pré-requisitos:**
    - Pastas compartilhadas publicamente
    - Arquivos com nomes padronizados
    - Acesso à internet
    
    ## 📄 Formatação dos Arquivos
    
    ### Extrato Bancário
    ```csv
    Data,Valor,Descrição
    2024-01-15,1500.00,Depósito Cliente A
    2024-01-16,-250.00,Pagamento Fornecedor B
    ```
    
    ### Lançamentos Contábeis  
    ```csv
    Data,Valor,Descrição,Conta Débito,Conta Crédito
    2024-01-15,1500.00,Receita Venda,1.01.01,3.01.01
    2024-01-16,250.00,Despesa Fornecedor,4.01.01,1.01.01
    ```
    
    ## 🔧 Solução de Problemas
    
    **❌ Erro ao carregar arquivos:**
    - Verifique o formato (CSV/Excel)
    - Confirme que o arquivo não está corrompido
    - Tente salvar como CSV UTF-8
    
    **❌ Nenhum arquivo encontrado na nuvem:**
    - Verifique se a pasta está compartilhada publicamente
    - Confirme os nomes dos arquivos
    - Use o método de Upload como alternativa
                
    ## 🔧 Modo Desenvolvedor
    - Configuração manual das colunas de identificação dos arquivos de fatura e de lançamento contábil
    """)

# SISTEMA DE VALIDAÇÃO POR NOME DE ARQUIVO
def validar_formato_nome(nome_arquivo):
    """
    Valida se o nome do arquivo segue o formato correto
    Retorna: (é_valido, tipo, numero_conta, extensao)
    """
    # CORREÇÃO: Remover espaços e converter para maiúsculo, mas manter a extensão original
    nome_arquivo = nome_arquivo.strip()
    
    # CORREÇÃO: Padrão mais flexível que aceita números de conta variados
    padrao = r'^(B|C)_(\d+)\.(ofx|csv|xlsx|xls|pdf|ret|cnab)$'
    match = re.match(padrao, nome_arquivo, re.IGNORECASE)  # CORREÇÃO: Adicionar ignore case
    
    if match:
        tipo = match.group(1).upper()  # B ou C
        numero_conta = match.group(2)  # Número da conta
        extensao = match.group(3).lower()  # Extensão do arquivo
        print(f"✅ Arquivo válido: {nome_arquivo} -> Tipo: {tipo}, Conta: {numero_conta}, Ext: {extensao}")
        return True, tipo, numero_conta, extensao
    else:
        print(f"❌ Formato inválido: {nome_arquivo} - Padrão esperado: B_12345678.extensão ou C_12345678.extensão")
        return False, None, None, None

def extrair_info_arquivos(arquivos):
    """
    Extrai informações dos arquivos carregados
    Retorna: dicionário com arquivos agrupados por conta
    """
    info_arquivos = {
        'bancarios': {},  # {conta: [arquivos]}
        'contabeis': {},  # {conta: [arquivos]}
        'contas_disponiveis': set(),
        'erros': []
    }
    
    for arquivo in arquivos:
        if arquivo is not None:
            valido, tipo, conta, extensao = validar_formato_nome(arquivo.name)
            
            if valido:
                if tipo == 'B':
                    if conta not in info_arquivos['bancarios']:
                        info_arquivos['bancarios'][conta] = []
                    info_arquivos['bancarios'][conta].append(arquivo)
                    info_arquivos['contas_disponiveis'].add(conta)
                elif tipo == 'C':
                    if conta not in info_arquivos['contabeis']:
                        info_arquivos['contabeis'][conta] = []
                    info_arquivos['contabeis'][conta].append(arquivo)
                    info_arquivos['contas_disponiveis'].add(conta)
            else:
                info_arquivos['erros'].append(f"❌ Formato inválido: {arquivo.name}")
    
    return info_arquivos

# Função para detectar tipo de arquivo
def detectar_tipo_arquivo(nome_arquivo):
    """Detecta o tipo de arquivo baseado na extensão"""
    nome_lower = nome_arquivo.lower()
    if nome_lower.endswith('.ofx'):
        return 'ofx'
    elif nome_lower.endswith('.ret') or nome_lower.endswith('.cnab'):
        return 'cnab'
    elif nome_lower.endswith('.csv'):
        return 'csv'
    elif nome_lower.endswith(('.xlsx', '.xls')):
        return 'excel'
    elif nome_lower.endswith('.pdf'):
        return 'pdf'
    else:
        return 'desconhecido'

@st.cache_data(show_spinner=False)
def _parsear_ofx_cacheado(conteudo: bytes) -> pd.DataFrame:
    """Núcleo de parsing do OFX: isolado (só os bytes do arquivo, sem
    Streamlit, sem sessão, sem nome de arquivo/conta) e cacheado por
    hash dos bytes — mesmo motivo e mesma garantia de cópia-por-chamada
    de `_parsear_csv_cacheado` acima. Informação dependente de sessão
    (modo de validação por nome de arquivo, nome do upload) é aplicada
    DEPOIS, em `processar_ofx`, nunca entra no que é cacheado aqui."""
    from ofxparse import OfxParser
    ofx = OfxParser.parse(io.BytesIO(conteudo))

    transacoes = []
    for account in ofx.accounts:
        for transaction in account.statement.transactions:
            transacoes.append({
                'data': transaction.date,
                'valor': float(transaction.amount),
                'descricao': transaction.memo or transaction.payee or '',
                'tipo': transaction.type,
                'id': transaction.id
            })

    return pd.DataFrame(transacoes)


# Função para processar arquivo OFX
def processar_ofx(arquivo):
    """Processa arquivo OFX"""
    try:
        arquivo.seek(0)
        conteudo = arquivo.read()
        arquivo.seek(0)

        df = _parsear_ofx_cacheado(conteudo)
        if not df.empty:
            # Adicionar informação da conta ao DataFrame se estiver no modo validação
            if sistema_validacao:
                valido, tipo, conta, extensao = validar_formato_nome(arquivo.name)
                if valido:
                    df['conta_bancaria'] = conta
                    df['origem_arquivo'] = arquivo.name
                    df['tipo_arquivo'] = tipo

        return df
    except Exception as e:
        st.error(f"Erro ao processar OFX: {e}")
        return None

# FUNÇÕES CNAB CORRIGIDAS 
def _processar_valor_cnab_corrigido(valor_str):
    """Processa valor CNAB CORRETAMENTE - últimos 2 dígitos são centavos"""
    try:
        print(f"💰 Processando valor CNAB: {valor_str}")
        
        if not valor_str or valor_str == '0000000000000':
            return 0.0
        
        # Em CNAB, os últimos 2 dígitos são centavos
        parte_inteira = valor_str[:-2]  # Todos exceto últimos 2 dígitos
        parte_decimal = valor_str[-2:]  # Últimos 2 dígitos
        
        # Remover zeros à esquerda da parte inteira
        parte_inteira_limpa = parte_inteira.lstrip('0')
        if not parte_inteira_limpa:
            parte_inteira_limpa = "0"
        
        valor_final = float(parte_inteira_limpa + '.' + parte_decimal)
        print(f"✅ Valor processado: {parte_inteira_limpa}.{parte_decimal} = R$ {valor_final:,.2f}")
        
        return valor_final
        
    except Exception as e:
        print(f"❌ Erro no processamento do valor: {e}")
        # Fallback: tentar divisão por 100
        try:
            valor_fallback = float(valor_str) / 100.0
            print(f"🔄 Fallback (divisão por 100): R$ {valor_fallback:,.2f}")
            return valor_fallback
        except:
            return 0.0

def _extrair_valor_caixa_completo(linha):
    """Extrai valor do CNAB da Caixa - Versão CORRIGIDA"""
    try:
        print(f"🔍 Analisando linha: {linha[:100]}...")
        
        # NOVA ESTRATÉGIA: Buscar por padrões específicos do CNAB Caixa
        # No exemplo: "0010000001250000" onde "0000001250000" = R$ 1.250,00
        # Formato: 13 dígitos onde os últimos 2 são centavos
        
        # Padrão 1: Buscar sequência de 13 dígitos após texto descritivo
        padrao_1 = r'PAGAMENTO [A-Z]+\s+(\d{3})(\d{13})'
        match_1 = re.search(padrao_1, linha)
        if match_1:
            codigo = match_1.group(1)
            valor_str = match_1.group(2)
            print(f"✅ Padrão 1 encontrado: {codigo} | {valor_str}")
            
            # CORREÇÃO: Processar como valor monetário CNAB (últimos 2 dígitos = centavos)
            return _processar_valor_cnab_corrigido(valor_str)
        
        # Padrão 2: Buscar qualquer sequência de 13 dígitos significativa
        padrao_2 = r'(\d{13})'
        matches_2 = re.findall(padrao_2, linha)
        for valor_str in matches_2:
            if valor_str != '0000000000000' and len(valor_str) == 13:
                # Verificar contexto - deve estar após texto descritivo
                idx = linha.find(valor_str)
                if idx > 50:  # Deve estar depois da descrição
                    print(f"✅ Padrão 2 encontrado: {valor_str}")
                    return _processar_valor_cnab_corrigido(valor_str)
        
        # Padrão 3: Buscar em posição específica (mais confiável)
        if len(linha) >= 83:
            # Tentar diferentes posições baseadas no exemplo
            posicoes_tentativas = [
                (65, 78),  # Posição mais comum: após "PAGAMENTO FORNECEDOR"
                (70, 83),  # Posição alternativa
                (60, 73),  # Outra tentativa
            ]
            
            for inicio, fim in posicoes_tentativas:
                if len(linha) >= fim:
                    valor_str = linha[inicio:fim].strip()
                    if valor_str.isdigit() and len(valor_str) == 13 and valor_str != '0000000000000':
                        print(f"✅ Posição {inicio}-{fim}: {valor_str}")
                        return _processar_valor_cnab_corrigido(valor_str)
        
        print("❌ Nenhum valor válido encontrado")
        return 0.0
        
    except Exception as e:
        print(f"❌ Erro na extração: {e}")
        return 0.0

def _extrair_data_caixa_corrigida(linha):
    """Extrai data do CNAB da Caixa - Versão CORRIGIDA"""
    try:
        # NOVA ESTRATÉGIA: Buscar data em posição específica
        # No exemplo: "08102025" = 08/10/2025
        
        # Primeiro tentar posição específica baseada no exemplo
        if len(linha) >= 83:
            # Data geralmente vem após o valor
            posicoes_data = [
                (78, 86),  # Posição mais provável: após os 13 dígitos do valor
                (80, 88),  # Posição alternativa
                (75, 83),  # Outra tentativa
            ]
            
            for inicio, fim in posicoes_data:
                if len(linha) >= fim:
                    data_str = linha[inicio:fim].strip()
                    if len(data_str) == 8 and data_str.isdigit():
                        try:
                            # Tentar interpretar como DDMMAAAA
                            dia = int(data_str[0:2])
                            mes = int(data_str[2:4])
                            ano = int(data_str[4:8])
                            
                            if 1 <= dia <= 31 and 1 <= mes <= 12 and 2020 <= ano <= 2030:
                                data = datetime(ano, mes, dia)
                                print(f"📅 Data encontrada (posição {inicio}-{fim}): {data.strftime('%d/%m/%Y')}")
                                return data
                        except:
                            continue
        
        # Fallback: buscar padrão DDMMAAAA em qualquer lugar
        padrao_data = r'(\d{2}\d{2}\d{4})'
        matches = re.findall(padrao_data, linha)
        
        for data_str in matches:
            try:
                dia = int(data_str[0:2])
                mes = int(data_str[2:4])
                ano = int(data_str[4:8])
                
                if 1 <= dia <= 31 and 1 <= mes <= 12 and 2020 <= ano <= 2030:
                    data = datetime(ano, mes, dia)
                    print(f"📅 Data encontrada (padrão): {data.strftime('%d/%m/%Y')}")
                    return data
            except:
                continue
        
        print("❌ Nenhuma data válida encontrada, usando data atual")
        return datetime.now()
        
    except Exception as e:
        print(f"❌ Erro na extração de data: {e}")
        return datetime.now()

def _extrair_descricao_melhorada(linha, numero_sequencial):
    """Extrai descrição do CNAB - Versão melhorada"""
    try:
        # Padrão 1: Texto entre sequências numéricas
        padrao_1 = r'\d{10,20}([A-Z\s]{15,40})\d{10,20}'
        match_1 = re.search(padrao_1, linha)
        if match_1:
            descricao = match_1.group(1).strip()
            if len(descricao) >= 5:
                print(f"📝 Descrição padrão 1: {descricao}")
                return descricao
        
        # Padrão 2: Buscar texto após "0000000000001" (exemplo do seu arquivo)
        padrao_2 = r'0000000000001([A-Z\s]{15,40})'
        match_2 = re.search(padrao_2, linha)
        if match_2:
            descricao = match_2.group(1).strip()
            if len(descricao) >= 5:
                print(f"📝 Descrição padrão 2: {descricao}")
                return descricao
        
        # Padrão 3: Buscar qualquer texto em maiúsculo significativo
        padrao_3 = r'([A-Z][A-Z\s]{10,50}[A-Z])'
        matches_3 = re.findall(padrao_3, linha)
        for descricao in matches_3:
            descricao_limpa = descricao.strip()
            # Pular textos que são só siglas ou muito curtos
            if len(descricao_limpa) >= 8 and ' ' in descricao_limpa:
                print(f"📝 Descrição padrão 3: {descricao_limpa}")
                return descricao_limpa
        
        # Fallback
        descricao_fallback = f"Lançamento {numero_sequencial}"
        print(f"📝 Descrição fallback: {descricao_fallback}")
        return descricao_fallback
        
    except Exception as e:
        print(f"❌ Erro na extração de descrição: {e}")
        return f"Transação {numero_sequencial}"

def _extrair_transacao_caixa_corrigida(linha, numero_sequencial):
    """Extrai transação do CNAB da Caixa - Versão CORRIGIDA"""
    try:
        print(f"\n🎯 PROCESSANDO TRANSAÇÃO {numero_sequencial}")
        print(f"📄 Linha: {linha[:80]}...")
        
        transacao = {}
        
        # 1. Extrair segmento
        segmento = linha[13:14] if len(linha) >= 14 else 'E'
        
        # 2. Extrair descrição
        descricao = _extrair_descricao_melhorada(linha, numero_sequencial)
        
        # 3. Extrair valor (USANDO MÉTODO CORRIGIDO)
        valor = _extrair_valor_caixa_completo(linha)
        
        # 4. Extrair data (USANDO MÉTODO CORRIGIDO) - NOME CORRETO
        data = _extrair_data_caixa_corrigida(linha)  # CORRIGIDO: era _extrair_data_caixa_melhorada
        
        # 5. Determinar sinal do valor (CORRIGIDO)
        # No CNAB, débitos geralmente têm valores positivos, mas no extrato aparecem negativos
        if 'D' in linha.upper() or any(palavra in descricao.upper() for palavra in ['PAGAMENTO', 'DEBITO', 'DÉBITO', 'PAGTO', 'FORNECEDOR']):
            valor_final = -abs(valor)  # Negativo para pagamentos
            tipo_operacao = 'Débito'
            print(f"🔴 Operação: DÉBITO")
        elif 'C' in linha.upper() or any(palavra in descricao.upper() for palavra in ['CREDITO', 'CRÉDITO', 'RECEBIMENTO', 'DEPOSITO']):
            valor_final = abs(valor)   # Positivo para recebimentos
            tipo_operacao = 'Crédito'
            print(f"🟢 Operação: CRÉDITO")
        else:
            # Se não conseguiu determinar, usar lógica baseada na descrição
            if 'PAGAMENTO' in descricao.upper() or 'FORNECEDOR' in descricao.upper():
                valor_final = -abs(valor)
                tipo_operacao = 'Débito'
            else:
                valor_final = abs(valor)
                tipo_operacao = 'Crédito'
            print(f"🟡 Operação: {tipo_operacao} (inferido por descrição)")
        
        # 6. Montar transação
        transacao.update({
            'id': f"caixa_{numero_sequencial:04d}",
            'data': data,
            'valor': valor_final,
            'descricao': f"{tipo_operacao} - {descricao}",
            'tipo': f'CNAB_CAIXA_{segmento}',
            'numero_sequencial': numero_sequencial,
            '_valor_cru': valor,
            '_linha_original': linha[:100] + "..." if len(linha) > 100 else linha
        })
        
        print(f"✅ TRANSAÇÃO {numero_sequencial} EXTRAÍDA:")
        print(f"   📝 Descrição: {descricao}")
        print(f"   💰 Valor: R$ {valor_final:,.2f}")
        print(f"   📅 Data: {data.strftime('%d/%m/%Y')}")
        print(f"   🏷️ Tipo: {tipo_operacao}")
        
        return transacao
        
    except Exception as e:
        print(f"❌ ERRO na transação {numero_sequencial}: {e}")
        import traceback
        print(f"🔍 Detalhes: {traceback.format_exc()}")
        return None

def processar_cnab_caixa_especifico(arquivo):
    """Processa arquivo CNAB da Caixa Econômica Federal - Versão corrigida"""
    try:
        # Ler o conteúdo do arquivo
        arquivo.seek(0)
        content = arquivo.read()
        
        # Tentar diferentes encodings
        encodings = ['latin-1', 'iso-8859-1', 'cp1252', 'utf-8']
        texto = None
        
        for encoding in encodings:
            try:
                texto = content.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        
        if texto is None:
            st.error("❌ Não foi possível decodificar o arquivo CNAB")
            return None
        
        linhas = texto.split('\n')
        
        transacoes = []
        numero_sequencial = 1
        
        st.info(f"📁 Processando {len(linhas)} linhas do arquivo CNAB...")
        
        for linha in linhas:
            linha = linha.strip()
            if not linha:
                continue
                
            # Verificar se é linha de detalhe com transação
            if linha.startswith('10400013'):  # Linha de detalhe
                transacao = _extrair_transacao_caixa_corrigida(linha, numero_sequencial)
                if transacao and transacao['valor'] != 0:
                    transacoes.append(transacao)
                    numero_sequencial += 1
        
        if transacoes:
            df = pd.DataFrame(transacoes)
            st.success(f"✅ CNAB Caixa processado: {len(df)} transações extraídas")
            
            # Mostrar estatísticas detalhadas
            if 'valor' in df.columns:
                total_credito = df[df['valor'] > 0]['valor'].sum()
                total_debito = df[df['valor'] < 0]['valor'].abs().sum()
                saldo = df['valor'].sum()
                
                st.info(f"""
                📊 ESTATÍSTICAS FINAIS:
                • Créditos: R$ {total_credito:,.2f}
                • Débitos: R$ {total_debito:,.2f}  
                • Saldo: R$ {saldo:,.2f}
                • Média: R$ {df['valor'].mean():,.2f}
                """)
            
            return df
        else:
            st.error("❌ Nenhuma transação válida encontrada no arquivo CNAB")
            return None
            
    except Exception as e:
        st.error(f"❌ Erro ao processar CNAB Caixa: {str(e)}")
        import traceback
        st.code(f"Detalhes do erro: {traceback.format_exc()}")
        return None

def processar_cnab_generico(arquivo):
    """Processamento genérico para CNAB quando o específico falhar"""
    try:
        arquivo.seek(0)
        content = arquivo.read()
        
        # Tentar diferentes encodings
        encodings = ['latin-1', 'iso-8859-1', 'cp1252', 'utf-8']
        texto = None
        
        for encoding in encodings:
            try:
                texto = content.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        
        if texto is None:
            return None
        
        linhas = texto.split('\n')
        transacoes = []
        
        for linha in linhas:
            linha = linha.strip()
            if not linha:
                continue
            
            # Tentar extrair dados genéricos
            transacao = {}
            
            # Procurar por padrões de data
            padrao_data = r'(\d{2}/\d{2}/\d{4})|(\d{2}\.\d{2}\.\d{4})|(\d{8})'
            datas = re.findall(padrao_data, linha)
            if datas:
                for grupo in datas:
                    for data_str in grupo:
                        if data_str:
                            try:
                                if '/' in data_str:
                                    transacao['data'] = datetime.strptime(data_str, '%d/%m/%Y')
                                elif '.' in data_str:
                                    transacao['data'] = datetime.strptime(data_str, '%d.%m.%Y')
                                elif len(data_str) == 8:
                                    transacao['data'] = datetime.strptime(data_str, '%d%m%Y')
                                break
                            except:
                                continue
            
            # Procurar por padrões de valor
            padrao_valor = r'(\d{1,3}(?:\.\d{3})*,\d{2})|(\d+,\d{2})'
            valores = re.findall(padrao_valor, linha)
            if valores:
                for grupo in valores:
                    for valor_str in grupo:
                        if valor_str:
                            try:
                                valor_clean = valor_str.replace('.', '').replace(',', '.')
                                transacao['valor'] = float(valor_clean)
                                break
                            except:
                                continue
            
            # Descrição genérica
            if len(linha) > 0:
                transacao['descricao'] = linha[:100]
                transacao['tipo'] = 'CNAB_GENERICO'
                transacao['_linha_original'] = linha[:50] + "..." if len(linha) > 50 else linha
                
                transacoes.append(transacao)
        
        if transacoes:
            return pd.DataFrame(transacoes)
        else:
            return None
            
    except Exception as e:
        st.error(f"❌ Erro no processamento genérico CNAB: {e}")
        return None

def processar_cnab(arquivo):
    """Processa arquivo CNAB (.RET) com fallback"""
    try:
        num_linhas = _contar_linhas_arquivo(arquivo)
        if num_linhas > MAX_CNAB_LINHAS:
            st.error(
                f"❌ Arquivo CNAB com {num_linhas} linhas excede o limite de "
                f"{MAX_CNAB_LINHAS} linhas por importação."
            )
            return None

        # Primeira tentativa: processamento específico Caixa
        resultado = processar_cnab_caixa_especifico(arquivo)
        if resultado is not None and not resultado.empty:
            return resultado
        
        # Segunda tentativa: processamento genérico
        st.warning("⚠️ Tentando processamento genérico do CNAB...")
        resultado = processar_cnab_generico(arquivo)
        if resultado is not None and not resultado.empty:
            st.info("✅ Arquivo CNAB processado com método genérico")
            return resultado
        
        st.error("❌ Não foi possível processar o arquivo CNAB com nenhum método")
        return None
        
    except Exception as e:
        st.error(f"❌ Erro geral no processamento CNAB: {e}")
        return None
    
def analisar_estrutura_cnab(arquivo):
    """Analisa a estrutura do arquivo CNAB para debugging"""
    try:
        arquivo.seek(0)
        content = arquivo.read()
        
        # Tentar diferentes encodings
        encodings = ['latin-1', 'iso-8859-1', 'cp1252', 'utf-8']
        texto = None
        
        for encoding in encodings:
            try:
                texto = content.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        
        if texto is None:
            return "❌ Não foi possível decodificar o arquivo"
        
        linhas = texto.split('\n')
        
        analise = {
            'total_linhas': len(linhas),
            'linhas_nao_vazias': len([l for l in linhas if l.strip()]),
            'tamanho_linhas': [],
            'tipos_registro': {},
            'primeiras_linhas': linhas[:5]
        }
        
        for i, linha in enumerate(linhas[:10]):
            if linha.strip():
                analise['tamanho_linhas'].append(len(linha))
                # Classificar por prefixo
                if len(linha) >= 8:
                    prefixo = linha[:8]
                    analise['tipos_registro'][prefixo] = analise['tipos_registro'].get(prefixo, 0) + 1
        
        resultado = f"""
        📊 ANÁLISE DO ARQUIVO CNAB:
        
        • Total de linhas: {analise['total_linhas']}
        • Linhas não vazias: {analise['linhas_nao_vazias']}
        • Tamanhos de linha: {set(analise['tamanho_linhas'])}
        • Tipos de registro: {analise['tipos_registro']}
        
        Primeiras linhas:
        """
        
        for i, linha in enumerate(analise['primeiras_linhas']):
            resultado += f"\n  {i+1}: {linha[:100]}..."
            
            # Análise específica para linhas de detalhe
            if linha.startswith('10400013'):
                resultado += f"\n     → Possível transação: {_analisar_linha_detalhe(linha)}"
        
        return resultado
        
    except Exception as e:
        return f"❌ Erro na análise: {str(e)}"

def _analisar_linha_detalhe(linha):
    """Analisa uma linha de detalhe do CNAB"""
    try:
        analise = []
        
        # Procurar valores
        padrao_valor = r'(\d{13})'
        valores = re.findall(padrao_valor, linha)
        for valor_str in valores:
            if valor_str != '0000000000000':
                valor = float(valor_str) / 100.0
                analise.append(f"Valor: R$ {valor:,.2f}")
        
        # Procurar datas
        padrao_data = r'(\d{8})'
        datas = re.findall(padrao_data, linha)
        for data_str in datas:
            try:
                datetime.strptime(data_str, '%d%m%Y')
                analise.append(f"Data: {data_str}")
            except:
                pass
        
        # Procurar texto descritivo
        texto_match = re.search(r'([A-Z\s]{10,40})', linha)
        if texto_match:
            descricao = texto_match.group(1).strip()
            analise.append(f"Desc: {descricao}")
        
        return " | ".join(analise) if analise else "Sem dados identificáveis"
        
    except Exception as e:
        return f"Erro na análise: {e}"

# Função para processar PDF
def processar_pdf(arquivo):
    """Tenta extrair dados de PDF com texto"""
    try:
        import pypdf
        pdf_reader = pypdf.PdfReader(io.BytesIO(arquivo.read()))

        num_paginas = len(pdf_reader.pages)
        if num_paginas > MAX_PDF_PAGINAS:
            st.error(
                f"❌ PDF com {num_paginas} páginas excede o limite de {MAX_PDF_PAGINAS} "
                f"páginas por importação."
            )
            return None

        texto = ""
        for page in pdf_reader.pages:
            texto += page.extract_text() + "\n"
        
        # Tentar encontrar padrões de transações no texto
        linhas = texto.split('\n')
        transacoes = []
        
        for linha in linhas:
            # Padrão simples para datas e valores
            padrao_data = r'(\d{1,2}/\d{1,2}/\d{2,4})'
            padrao_valor = r'R?\$?\s*([\d.,]+)'
            
            datas = re.findall(padrao_data, linha)
            valores = re.findall(padrao_valor, linha)
            
            if datas and valores:
                try:
                    data = datetime.strptime(datas[0], '%d/%m/%Y')
                    valor_str = valores[0].replace('.', '').replace(',', '.')
                    valor = float(valor_str)
                    
                    transacoes.append({
                        'data': data,
                        'valor': valor,
                        'descricao': linha[:100],  # Primeiros 100 caracteres
                        'tipo': 'PDF'
                    })
                except:
                    continue
        
        return pd.DataFrame(transacoes) if transacoes else None
    except Exception as e:
        st.error(f"Erro ao processar PDF: {e}")
        return None

# FUNÇÃO PROCESSAR ARQUIVO ATUALIZADA
def processar_arquivo(arquivo, tipo_arquivo):
    """Processa arquivo baseado no tipo"""
    tamanho_arquivo = getattr(arquivo, 'size', 0) or 0
    _inicio_carga = time.time()

    valido, motivo = validar_tamanho_arquivo(arquivo)
    if not valido:
        st.error(f"❌ {motivo}")
        audit.log_file_upload(
            file_name=arquivo.name, file_type=tipo_arquivo, file_size=tamanho_arquivo,
            user=usuario_atual, success=False, error_message=motivo,
        )
        get_structured_logger().log_carga_arquivo(
            formato=tipo_arquivo, sucesso=False, motivo='tamanho_excedido',
            registros=0, tamanho_bytes=tamanho_arquivo,
            duracao_segundos=time.time() - _inicio_carga,
        )
        return None

    try:
        df = None

        if tipo_arquivo == 'ofx':
            valido_entrada, motivo_entrada = validar_entrada_ofx(arquivo)
            if not valido_entrada:
                st.error(f"❌ {motivo_entrada}")
                audit.log_file_upload(
                    file_name=arquivo.name, file_type=tipo_arquivo, file_size=tamanho_arquivo,
                    user=usuario_atual, success=False, error_message=motivo_entrada,
                )
                motivo_categoria = _categorizar_motivo_carga_arquivo(motivo_entrada)
                get_structured_logger().log_carga_arquivo(
                    formato=tipo_arquivo, sucesso=False, motivo=motivo_categoria,
                    registros=0, tamanho_bytes=tamanho_arquivo,
                    duracao_segundos=time.time() - _inicio_carga,
                )
                if motivo_categoria in _MOTIVOS_LIMITE_CARGA_ARQUIVO:
                    return ARQUIVO_REJEITADO_POR_LIMITE
                return None
            df = processar_ofx(arquivo)
        elif tipo_arquivo == 'cnab':
            df = processar_cnab(arquivo)
        elif tipo_arquivo == 'pdf':
            df = processar_pdf(arquivo)
        elif tipo_arquivo in ['csv', 'excel']:
            if tipo_arquivo == 'csv':
                valido_entrada, motivo_entrada, _encoding_usado, df = validar_entrada_csv(arquivo)
                if not valido_entrada:
                    st.error(f"❌ {motivo_entrada}")
                    audit.log_file_upload(
                        file_name=arquivo.name, file_type=tipo_arquivo, file_size=tamanho_arquivo,
                        user=usuario_atual, success=False, error_message=motivo_entrada,
                    )
                    motivo_categoria = _categorizar_motivo_carga_arquivo(motivo_entrada)
                    get_structured_logger().log_carga_arquivo(
                        formato=tipo_arquivo, sucesso=False, motivo=motivo_categoria,
                        registros=0, tamanho_bytes=tamanho_arquivo,
                        duracao_segundos=time.time() - _inicio_carga,
                    )
                    if motivo_categoria in _MOTIVOS_LIMITE_CARGA_ARQUIVO:
                        return ARQUIVO_REJEITADO_POR_LIMITE
                    return None
            else:
                df = pd.read_excel(arquivo)
        
        # ADICIONAR INFORMAÇÕES DA CONTA SE O ARQUIVO FOR VÁLIDO E ESTIVER NO MODO VALIDAÇÃO
        if df is not None and not df.empty and sistema_validacao:
            valido, tipo, conta, extensao = validar_formato_nome(arquivo.name)
            if valido:
                df['conta_bancaria'] = conta
                df['origem_arquivo'] = arquivo.name
                df['tipo_arquivo'] = tipo  # B ou C
        
        if df is not None and not df.empty:
            audit.log_file_upload(
                file_name=arquivo.name, file_type=tipo_arquivo, file_size=tamanho_arquivo,
                user=usuario_atual, success=True,
            )
            get_structured_logger().log_carga_arquivo(
                formato=tipo_arquivo, sucesso=True, motivo='sucesso',
                registros=len(df), tamanho_bytes=tamanho_arquivo,
                duracao_segundos=time.time() - _inicio_carga,
            )
        else:
            audit.log_file_upload(
                file_name=arquivo.name, file_type=tipo_arquivo, file_size=tamanho_arquivo,
                user=usuario_atual, success=False, error_message="Nenhum dado extraído do arquivo",
            )
            get_structured_logger().log_carga_arquivo(
                formato=tipo_arquivo, sucesso=False, motivo='nenhum_dado_extraido',
                registros=0, tamanho_bytes=tamanho_arquivo,
                duracao_segundos=time.time() - _inicio_carga,
            )

        return df

    except Exception as e:
        st.error(f"Erro ao processar {tipo_arquivo.upper()}: {e}")
        audit.log_file_upload(
            file_name=arquivo.name, file_type=tipo_arquivo, file_size=tamanho_arquivo,
            user=usuario_atual, success=False, error_message=str(e),
        )
        get_structured_logger().log_carga_arquivo(
            formato=tipo_arquivo, sucesso=False, motivo='erro_desconhecido',
            registros=0, tamanho_bytes=tamanho_arquivo,
            duracao_segundos=time.time() - _inicio_carga,
        )
        return None

# INTERFACE PRINCIPAL - SISTEMA DE UPLOAD
if metodo_importacao == "📤 Upload de Arquivos":
    
    if sistema_validacao:
        # NOVO SISTEMA DE VALIDAÇÃO
        st.header("📤 Upload com Validação por Nome de Arquivo")
        
        st.info("""
        **📋 Formato Obrigatório:**
        - **Extrato Bancário:** `B_[NÚMERO_DA_CONTA].[extensão]`  
        - **Lançamentos Contábeis:** `C_[NÚMERO_DA_CONTA].[extensão]`
        
        **✅ Formatos suportados:** OFX, CSV, Excel, PDF, CNAB
        """)
        
        # Upload múltiplo de arquivos
        arquivos_upload = st.file_uploader(
            "Selecione os arquivos para conciliação:",
            type=['ofx', 'csv', 'xlsx', 'xls', 'pdf', 'ret', 'cnab'],
            accept_multiple_files=True,
            key="upload_validacao",
            help="Selecione arquivos no formato: B_12345678.extensão (Bancário) ou C_12345678.extensão (Contábil)"
        )
        
        if arquivos_upload:
            # Extrair informações dos arquivos
            info_arquivos = extrair_info_arquivos(arquivos_upload)
            
            # Mostrar erros
            for erro in info_arquivos['erros']:
                st.error(erro)
            
            # Mostrar resumo dos arquivos carregados
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("🏦 Arquivos Bancários")
                if info_arquivos['bancarios']:
                    for conta, arquivos in info_arquivos['bancarios'].items():
                        st.success(f"✅ Conta {conta}: {len(arquivos)} arquivo(s)")
                        for arquivo in arquivos:
                            st.write(f"   📄 {arquivo.name}")
                else:
                    st.warning("Nenhum arquivo bancário válido encontrado")
            
            with col2:
                st.subheader("📊 Arquivos Contábeis")
                if info_arquivos['contabeis']:
                    for conta, arquivos in info_arquivos['contabeis'].items():
                        st.success(f"✅ Conta {conta}: {len(arquivos)} arquivo(s)")
                        for arquivo in arquivos:
                            st.write(f"   📄 {arquivo.name}")
                else:
                    st.warning("Nenhum arquivo contábil válido encontrado")
            
            # Seleção da conta para conciliação
            contas_validas = []
            for conta in info_arquivos['contas_disponiveis']:
                if (conta in info_arquivos['bancarios'] and 
                    conta in info_arquivos['contabeis']):
                    contas_validas.append(conta)
            
            if contas_validas:
                st.subheader("🎯 Seleção para Conciliação")
                
                conta_selecionada = st.selectbox(
                    "Selecione a conta para conciliar:",
                    contas_validas,
                    index=0,
                    help="Apenas contas com arquivos bancários E contábeis estão disponíveis"
                )
                
                # Mostrar detalhes da conta selecionada
                st.info(f"""
                **Conta Selecionada:** {conta_selecionada}
                
                **Arquivos Bancários:** {len(info_arquivos['bancarios'][conta_selecionada])}
                **Arquivos Contábeis:** {len(info_arquivos['contabeis'][conta_selecionada])}
                """)
                
                # Botão para processar
                if st.button("🔄 Processar Conciliação", type="primary", key="btn_processar_validacao"):
                    with st.spinner("Processando arquivos..."):
                        try:
                            # Processar arquivos bancários
                            dfs_bancarios = []
                            for arquivo in info_arquivos['bancarios'][conta_selecionada]:
                                tipo_arquivo = detectar_tipo_arquivo(arquivo.name)
                                df = processar_arquivo(arquivo, tipo_arquivo)
                                if isinstance(df, pd.DataFrame) and not df.empty:
                                    dfs_bancarios.append(df)
                            
                            # Processar arquivos contábeis
                            dfs_contabeis = []
                            for arquivo in info_arquivos['contabeis'][conta_selecionada]:
                                tipo_arquivo = detectar_tipo_arquivo(arquivo.name)
                                # Se não permitir OFX no contábil, pular arquivos OFX
                                if not permitir_ofx_contabil and tipo_arquivo == 'ofx':
                                    st.warning(f"⚠️ OFX ignorado no contábil: {arquivo.name}")
                                    continue
                                df = processar_arquivo(arquivo, tipo_arquivo)
                                if isinstance(df, pd.DataFrame) and not df.empty:
                                    dfs_contabeis.append(df)
                            
                            # Combinar DataFrames
                            if dfs_bancarios and dfs_contabeis:
                                extrato_final = pd.concat(dfs_bancarios, ignore_index=True)
                                contabil_final = pd.concat(dfs_contabeis, ignore_index=True)
                                
                                # Salvar no session state
                                st.session_state.extrato_df = extrato_final
                                st.session_state.contabil_df = contabil_final
                                st.session_state.conta_selecionada = conta_selecionada
                                st.session_state.dados_carregados = True
                                
                                st.success(f"✅ Dados processados com sucesso!")
                                st.success(f"📊 Conta {conta_selecionada}: {len(extrato_final)} transações bancárias × {len(contabil_final)} lançamentos contábeis")
                                
                                # Mostrar preview
                                col_preview1, col_preview2 = st.columns(2)
                                
                                with col_preview1:
                                    st.write("**🏦 Transações Bancárias (primeiras 5):**")
                                    colunas_exibir = ['data', 'valor', 'descricao'] if all(col in extrato_final.columns for col in ['data', 'valor', 'descricao']) else extrato_final.columns.tolist()[:3]
                                    st.dataframe(extrato_final[colunas_exibir].head())
                                
                                with col_preview2:
                                    st.write("**📊 Lançamentos Contábeis (primeiras 5):**")
                                    colunas_exibir = ['data', 'valor', 'descricao'] if all(col in contabil_final.columns for col in ['data', 'valor', 'descricao']) else contabil_final.columns.tolist()[:3]
                                    st.dataframe(contabil_final[colunas_exibir].head())
                            
                            else:
                                st.error("❌ Não foi possível processar os arquivos para conciliação")
                                
                        except Exception as e:
                            st.error(f"❌ Erro no processamento: {e}")
            
            else:
                st.error("""
                ❌ **Nenhuma conta válida para conciliação**
                
                Para conciliar, você precisa ter:
                - Pelo menos 1 arquivo bancário (B_[CONTA].extensão)  
                - Pelo menos 1 arquivo contábil (C_[CONTA].extensão)
                - Ambos com o **mesmo número de conta**
                """)
    
    else:
        # SISTEMA ORIGINAL (MANTIDO)
        st.header("📤 Upload de Arquivos Locais")
        
        st.info("""
        **Formatos suportados:**
        - **OFX, CNAB (.RET), CSV, Excel, PDF** - Extrato bancário
        - **CSV, Excel, PDF** - Lançamentos contábeis
        """)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("🏦 Extrato Bancário")
            extrato_file = st.file_uploader(
                "Selecione o arquivo do extrato bancário:",
                type=['ofx', 'ret', 'cnab', 'csv', 'xlsx', 'xls', 'pdf'],
                key="extrato_upload",
                help="Arquivo OFX, CNAB, CSV, Excel ou PDF com transações bancárias"
            )
            
            if extrato_file is not None:
                try:
                    tipo_arquivo = detectar_tipo_arquivo(extrato_file.name)
                    st.info(f"📄 Tipo detectado: {tipo_arquivo.upper()}")
                    
                    # Botão de análise para CNAB
                    if tipo_arquivo == 'cnab':
                        if st.button("🔍 Analisar Estrutura do CNAB", key="btn_analisar_cnab"):
                            analise = analisar_estrutura_cnab(extrato_file)
                            st.text_area("Análise da Estrutura", analise, height=300)
                    
                    with st.spinner(f"Processando {extrato_file.name}..."):
                        extrato_df = processar_arquivo(extrato_file, tipo_arquivo)
                    
                    if isinstance(extrato_df, pd.DataFrame) and not extrato_df.empty:
                        st.session_state.extrato_df = extrato_df
                        st.success(f"✅ Extrato carregado: {len(extrato_df)} transações")

                        # Mostrar preview dos dados
                        st.dataframe(extrato_df.head(), width='stretch')
                    elif extrato_df is None:
                        # ARQUIVO_REJEITADO_POR_LIMITE: mensagem específica já
                        # exibida dentro de processar_arquivo — não duplicar.
                        st.error("❌ Não foi possível extrair dados do arquivo")
            
                except Exception as e:
                    st.error(f"❌ Erro ao carregar extrato: {e}")
        
        with col2:
            st.subheader("📊 Lançamentos Contábeis")
            # ATUALIZAR PARA PERMITIR OFX SE A OPÇÃO ESTIVER ATIVA
            tipos_contabil = ['csv', 'xlsx', 'xls', 'pdf']
            if permitir_ofx_contabil:
                tipos_contabil.append('ofx')
                
            contabil_file = st.file_uploader(
                "Selecione o arquivo dos lançamentos contábeis:",
                type=tipos_contabil,
                key="contabil_upload",
                help="Arquivo CSV, Excel, PDF" + (", OFX" if permitir_ofx_contabil else "") + " com lançamentos do sistema contábil"
            )
            
            if contabil_file is not None:
                try:
                    tipo_arquivo = detectar_tipo_arquivo(contabil_file.name)
                    st.info(f"📄 Tipo detectado: {tipo_arquivo.upper()}")
                    
                    with st.spinner(f"Processando {contabil_file.name}..."):
                        contabil_df = processar_arquivo(contabil_file, tipo_arquivo)
                    
                    if isinstance(contabil_df, pd.DataFrame) and not contabil_df.empty:
                        st.session_state.contabil_df = contabil_df
                        st.success(f"✅ Lançamentos carregados: {len(contabil_df)} registros")
                        st.dataframe(contabil_df.head(), width='stretch')
                    elif contabil_df is None:
                        # ARQUIVO_REJEITADO_POR_LIMITE: mensagem específica já
                        # exibida dentro de processar_arquivo — não duplicar.
                        st.error("❌ Não foi possível extrair dados do arquivo")
                    
                except Exception as e:
                    st.error(f"❌ Erro ao carregar lançamentos: {e}")

elif metodo_importacao == "☁️ Link de Pastas na Nuvem":
    st.header("☁️ Importação por Link de Pastas")
    
    st.warning("""
    **⚠️ Funcionalidade Experimental**
    Para arquivos bancários (OFX, CNAB), use o método de Upload.
    """)
    

else:  # 🔗 Links Diretos para Arquivos
    st.header("🔗 Links Diretos para Arquivos")
    
    st.info("""
    **Recomendado quando:** Você tem links diretos para os arquivos específicos
    **Funciona com:** Google Drive, SharePoint, OneDrive, Dropbox
    """)
    
# NO PROCESSAMENTO DOS DADOS (COMUM PARA AMBOS OS SISTEMAS)
if st.session_state.extrato_df is not None and st.session_state.contabil_df is not None:
    st.divider()
    st.header("📊 Visualização dos Dados Carregados")
    
    if sistema_validacao and st.session_state.conta_selecionada:
        st.success(f"✅ Dados da conta {st.session_state.conta_selecionada} carregados com sucesso!")
        
        #  SALVAR A CONTA NO SESSION STATE PARA USO NO RELATÓRIO
        st.session_state.conta_analisada = st.session_state.conta_selecionada
        st.info(f"📋 Conta selecionada para análise: **{st.session_state.conta_selecionada}**")
        
    else:
        st.success("✅ Dados carregados com sucesso! Visualização das informações:")
        
        # PARA SISTEMA SEM VALIDAÇÃO, TENTAR DETECTAR A CONTA
        if 'conta_bancaria' in st.session_state.extrato_df.columns:
            contas_encontradas = st.session_state.extrato_df['conta_bancaria'].unique()
            if len(contas_encontradas) == 1:
                conta_detectada = contas_encontradas[0]
                st.session_state.conta_analisada = conta_detectada
                st.info(f"📋 Conta detectada automaticamente: **{conta_detectada}**")
            else:
                st.session_state.conta_analisada = "Múltiplas contas"
                st.info("📋 Múltiplas contas detectadas nos arquivos")
        else:
            st.session_state.conta_analisada = "Não identificada"
            st.info("📋 Conta não identificada - use o sistema de validação para melhor precisão")
    
    # Processamento automático sem configuração do usuário
    with st.spinner("Processando e padronizando dados automaticamente..."):
        try:
            def detectar_colunas_automaticamente(df, tipo):
                """Detecta automaticamente colunas de data, valor e descrição"""
                colunas = df.columns.tolist()
                colunas_lower = [str(col).lower() for col in colunas]  # GARANTIR QUE É STRING
                
                # Mapeamento de padrões com pesos
                padroes_data = ['data', 'date', 'dt', 'datahora', 'data_transacao', 'vencimento']
                padroes_valor = ['valor', 'value', 'amount', 'vlr', 'montante', 'saldo', 'total']
                padroes_descricao = ['descricao', 'description', 'desc', 'historico', 'observacao', 'memo', 'payee', 'nome']
                
                # Encontrar colunas correspondentes com scoring
                col_data = None
                col_valor = None
                col_descricao = None
                melhor_score_data = 0
                melhor_score_valor = 0
                melhor_score_desc = 0
                
                for i, col in enumerate(colunas_lower):
                    col_original = colunas[i]
                    
                    # Verificar padrões de data
                    for j, padrao in enumerate(padroes_data):
                        if padrao in col:
                            score = len(padrao)  # Score baseado no tamanho do padrão
                            if score > melhor_score_data:
                                melhor_score_data = score
                                col_data = col_original
                    
                    # Verificar padrões de valor
                    for j, padrao in enumerate(padroes_valor):
                        if padrao in col:
                            score = len(padrao)
                            if score > melhor_score_valor:
                                melhor_score_valor = score
                                col_valor = col_original
                    
                    # Verificar padrões de descrição
                    for j, padrao in enumerate(padroes_descricao):
                        if padrao in col:
                            score = len(padrao)
                            if score > melhor_score_desc:
                                melhor_score_desc = score
                                col_descricao = col_original
                
                # Fallbacks inteligentes
                if not col_data:
                    # Procurar colunas que parecem ser datas
                    for col in colunas:
                        if df[col].dtype == 'datetime64[ns]':
                            col_data = col
                            break
                        elif len(df) > 0 and isinstance(df[col].iloc[0], (datetime, pd.Timestamp)):
                            col_data = col
                            break
                
                if not col_valor and len(colunas) > 0:
                    # Procurar colunas numéricas
                    for col in colunas:
                        if pd.api.types.is_numeric_dtype(df[col]):
                            col_valor = col
                            break
                
                if not col_descricao and len(colunas) > 0:
                    # Procurar colunas de texto
                    for col in colunas:
                        if pd.api.types.is_string_dtype(df[col]):
                            col_descricao = col
                            break
                
                # Últimos fallbacks
                if not col_data and len(colunas) > 0:
                    col_data = colunas[0]
                if not col_valor and len(colunas) > 1:
                    col_valor = colunas[1]
                if not col_descricao and len(colunas) > 2:
                    col_descricao = colunas[2]
                
                st.info(f"🔍 {tipo} - Colunas detectadas: Data='{col_data}', Valor='{col_valor}', Descrição='{col_descricao}'")
                return col_data, col_valor, col_descricao
            
            # Detectar colunas automaticamente
            col_data_extrato, col_valor_extrato, col_descricao_extrato = detectar_colunas_automaticamente(
                st.session_state.extrato_df, "Extrato Bancário"
            )
            col_data_contabil, col_valor_contabil, col_descricao_contabil = detectar_colunas_automaticamente(
                st.session_state.contabil_df, "Lançamentos Contábeis"
            )
            
            def processar_extrato_em_chunks(df):
                """Processa em chunks preservando o relatório honesto de
                rejeições (processor.processar_extrato agora retorna
                (df, relatorio) em vez de só df; DataChunker.process_in_chunks
                é genérico e faria pd.concat() sobre tuplas, o que quebraria,
                então a soma dos relatórios por chunk é feita aqui)."""
                chunk_size = chunker.config.CHUNK_SIZE
                if len(df) <= chunk_size:
                    return processor.processar_extrato(
                        df, col_data_extrato, col_valor_extrato, col_descricao_extrato
                    )

                dfs, relatorios = [], []
                for i in range(0, len(df), chunk_size):
                    chunk_df, chunk_relatorio = processor.processar_extrato(
                        df.iloc[i:i + chunk_size].copy(),
                        col_data_extrato, col_valor_extrato, col_descricao_extrato
                    )
                    dfs.append(chunk_df)
                    relatorios.append(chunk_relatorio)

                relatorio_combinado = {
                    'dataset': 'extrato bancário',
                    'total_recebido': sum(r['total_recebido'] for r in relatorios),
                    'total_aceito': sum(r['total_aceito'] for r in relatorios),
                    'rejeitado_data_invalida': sum(r['rejeitado_data_invalida'] for r in relatorios),
                    'rejeitado_valor_invalido': sum(r['rejeitado_valor_invalido'] for r in relatorios),
                    'total_rejeitado': sum(r['total_rejeitado'] for r in relatorios),
                }
                return pd.concat(dfs, ignore_index=True), relatorio_combinado

            # Processar extrato
            extrato_processado, relatorio_extrato = processar_extrato_em_chunks(st.session_state.extrato_df)

            # Processar lançamentos contábeis
            contabil_processado, relatorio_contabil = processor.processar_contabil(
                st.session_state.contabil_df,
                col_data_contabil,
                col_valor_contabil,
                col_descricao_contabil
            )

            # Salvar no session state
            st.session_state.extrato_df = extrato_processado
            st.session_state.contabil_df = contabil_processado
            st.session_state.dados_carregados = True

            st.success("✅ Dados processados automaticamente com sucesso!")

            # Relatório honesto de linhas rejeitadas — antes, linhas com
            # data/valor inválidos eram simplesmente descartadas sem
            # nenhum aviso visível.
            for relatorio in (relatorio_extrato, relatorio_contabil):
                if relatorio['total_rejeitado'] > 0:
                    st.warning(
                        f"⚠️ {relatorio['dataset'].capitalize()}: "
                        f"{relatorio['total_rejeitado']} de {relatorio['total_recebido']} linha(s) "
                        f"rejeitada(s) e não incluída(s) na conciliação "
                        f"({relatorio['rejeitado_data_invalida']} com data inválida, "
                        f"{relatorio['rejeitado_valor_invalido']} com valor inválido)."
                    )
                audit.log_data_processing(
                    process_type=relatorio['dataset'],
                    input_records=relatorio['total_recebido'],
                    output_records=relatorio['total_aceito'],
                    processing_time=0.0,
                    user=usuario_atual,
                    errors=(
                        [f"{relatorio['rejeitado_data_invalida']} linha(s) com data inválida"] if relatorio['rejeitado_data_invalida'] else []
                    ) + (
                        [f"{relatorio['rejeitado_valor_invalido']} linha(s) com valor inválido"] if relatorio['rejeitado_valor_invalido'] else []
                    ),
                )

            # Visualização completa dos dados
            st.subheader("📈 Visualização Completa dos Dados")
            
            col_viz1, col_viz2 = st.columns(2)
            
            with col_viz1:
                st.markdown("**🏦 Extrato Bancário - Todas as Transações**")
                if 'data' in extrato_processado.columns and 'valor' in extrato_processado.columns and 'descricao' in extrato_processado.columns:
                    viz_extrato = extrato_processado[['data', 'valor', 'descricao']].copy()
                    if hasattr(viz_extrato['data'].iloc[0], 'strftime'):
                        viz_extrato['data'] = viz_extrato['data'].dt.strftime('%d/%m/%Y')
                    st.dataframe(viz_extrato, height=400, width='stretch')
                else:
                    st.dataframe(extrato_processado, height=400, width='stretch')
                
                st.metric("Total de Transações", len(extrato_processado))
                if 'valor' in extrato_processado.columns:
                    valor_total = extrato_processado['valor'].sum()
                    valor_total_abs = extrato_processado['valor'].abs().sum()
                    st.metric("Valor Total (Líquido)", f"R$ {valor_total:,.2f}")
                    st.metric("Valor Total Absoluto", f"R$ {valor_total_abs:,.2f}")
            
            with col_viz2:
                st.markdown("**📊 Lançamentos Contábeis - Todos os Registros**")
                if 'data' in contabil_processado.columns and 'valor' in contabil_processado.columns and 'descricao' in contabil_processado.columns:
                    viz_contabil = contabil_processado[['data', 'valor', 'descricao']].copy()
                    if hasattr(viz_contabil['data'].iloc[0], 'strftime'):
                        viz_contabil['data'] = viz_contabil['data'].dt.strftime('%d/%m/%Y')
                    st.dataframe(viz_contabil, height=400, width='stretch')
                else:
                    st.dataframe(contabil_processado, height=400, width='stretch')
                
                st.metric("Total de Lançamentos", len(contabil_processado))
                if 'valor' in contabil_processado.columns:
                    valor_total_contabil = contabil_processado['valor'].sum()
                    valor_total_contabil_abs = contabil_processado['valor'].abs().sum()
                    st.metric("Valor Total Contábil", f"R$ {valor_total_contabil:,.2f}")
                    st.metric("Valor Total Contábil Absoluto", f"R$ {valor_total_contabil_abs:,.2f}")

                
            # Estatísticas resumidas
            st.subheader("📊 Estatísticas dos Dados")
            
            col_stat1, col_stat2, col_stat3 = st.columns(3)
            
            with col_stat1:
                if 'data' in extrato_processado.columns:
                    try:
                        data_min = extrato_processado['data'].min()
                        data_max = extrato_processado['data'].max()
                        if hasattr(data_min, 'strftime'):
                            periodo = f"{data_min.strftime('%d/%m/%Y')} a {data_max.strftime('%d/%m/%Y')}"
                        else:
                            periodo = f"{data_min} a {data_max}"
                        st.metric("Período do Extrato", periodo)
                    except:
                        st.metric("Período do Extrato", "Não disponível")
                if 'data' in contabil_processado.columns:
                    try:
                        data_min = contabil_processado['data'].min()
                        data_max = contabil_processado['data'].max()
                        if hasattr(data_min, 'strftime'):
                            periodo = f"{data_min.strftime('%d/%m/%Y')} a {data_max.strftime('%d/%m/%Y')}"
                        else:
                            periodo = f"{data_min} a {data_max}"
                        st.metric("Período Contábil", periodo)
                    except:
                        st.metric("Período Contábil", "Não disponível")

            with col_stat2:
                if 'valor' in extrato_processado.columns:
                    valor_medio = extrato_processado['valor'].mean()
                    st.metric("Valor Médio Extrato", f"R$ {valor_medio:,.2f}")
                if 'valor' in contabil_processado.columns:
                    valor_medio = contabil_processado['valor'].mean()
                    st.metric("Valor Médio Contábil", f"R$ {valor_medio:,.2f}")
            
            with col_stat3:
                if 'valor' in extrato_processado.columns:
                    negativos = len(extrato_processado[extrato_processado['valor'] < 0])
                    positivos = len(extrato_processado[extrato_processado['valor'] > 0])
                    st.metric("Transações Extrato", f"Entradas: {positivos} |  Saídas: {negativos}")
                if 'valor' in contabil_processado.columns:
                    negativos = len(contabil_processado[contabil_processado['valor'] < 0])
                    positivos = len(contabil_processado[contabil_processado['valor'] > 0])
                    st.metric("Lançamentos Contábeis", f"Entradas: {positivos} | Saídas: {negativos}")
            
        except Exception as e:
            st.error(f"❌ Erro no processamento automático: {e}")
            st.info("💡 Use a seção 'Modo Desenvolvedor' para configurar manualmente as colunas")

# Navegação
if st.session_state.dados_carregados:
    st.divider()
    st.success("Dados prontos para análise!")
    
    col_nav1, col_nav2, col_nav3 = st.columns([1, 2, 1])
    
    with col_nav2:
        if st.button("Ir para Análise de Dados", type="primary", width='stretch'):
            st.switch_page("pages/analise_dados.py")

# Seção de desenvolvedor (oculta do usuário normal)
with st.expander("🔧 Modo Desenvolvedor (Configuração Avançada)", expanded=False):
    st.warning("⚠️ Esta seção é apenas para configurações manuais avançadas de colunas caso haja falha de correspondência")
    
    if st.session_state.extrato_df is not None and st.session_state.contabil_df is not None:
        st.subheader("Configuração Manual de Colunas")
        
        col_dev1, col_dev2 = st.columns(2)
        
        with col_dev1:
            st.markdown("**🏦 Extrato Bancário**")
            extrato_cols = st.session_state.extrato_df.columns.tolist()
            
            col_data_extrato_dev = st.selectbox("Coluna de Data:", extrato_cols, index=0, key="dev_data_extrato")
            col_valor_extrato_dev = st.selectbox("Coluna de Valor:", extrato_cols, index=1, key="dev_valor_extrato")
            col_descricao_extrato_dev = st.selectbox("Coluna de Descrição:", extrato_cols, index=2, key="dev_desc_extrato")
        
        with col_dev2:
            st.markdown("**📊 Lançamentos Contábeis**")
            contabil_cols = st.session_state.contabil_df.columns.tolist()
            
            col_data_contabil_dev = st.selectbox("Coluna de Data:", contabil_cols, index=0, key="dev_data_contabil")
            col_valor_contabil_dev = st.selectbox("Coluna de Valor:", contabil_cols, index=1, key="dev_valor_contabil")
            col_descricao_contabil_dev = st.selectbox("Coluna de Descrição:", contabil_cols, index=2, key="dev_desc_contabil")
        
        if st.button("🔄 Reprocessar com Configuração Manual", type="secondary"):
            with st.spinner("Reprocessando dados com configuração manual..."):
                try:
                    extrato_reprocessado, relatorio_extrato_dev = processor.processar_extrato(
                        st.session_state.extrato_df,
                        col_data_extrato_dev,
                        col_valor_extrato_dev,
                        col_descricao_extrato_dev
                    )

                    contabil_reprocessado, relatorio_contabil_dev = processor.processar_contabil(
                        st.session_state.contabil_df,
                        col_data_contabil_dev,
                        col_valor_contabil_dev,
                        col_descricao_contabil_dev
                    )

                    st.session_state.extrato_df = extrato_reprocessado
                    st.session_state.contabil_df = contabil_reprocessado

                    for relatorio in (relatorio_extrato_dev, relatorio_contabil_dev):
                        if relatorio['total_rejeitado'] > 0:
                            st.warning(
                                f"⚠️ {relatorio['dataset'].capitalize()}: "
                                f"{relatorio['total_rejeitado']} de {relatorio['total_recebido']} linha(s) rejeitada(s)."
                            )

                    st.success("✅ Dados reprocessados com configuração manual!")
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"❌ Erro no reprocessamento: {e}")

# ADICIONAR SEÇÃO DE AJUDA PARA O NOVO SISTEMA
with st.expander("📋 Ajuda - Sistema de Validação por Nome"):
    st.markdown("""
    ### ✅ Formatos Corretos:
    
    **Arquivos Bancários:**
    - `B_12344332.ofx`
    - `B_55443322.csv` 
    - `B_99887766.xlsx`
    - `B_11223344.pdf`
    
    **Arquivos Contábeis:**
    - `C_12344332.csv`
    - `C_55443322.xlsx`
    - `C_99887766.ofx` *(se permitido)*
    - `C_11223344.pdf`
    
    ### ❌ Formatos Incorretos:
    - `extrato.pdf` (falta prefixo)
    - `B12344332.csv` (falta underline)
    - `B_conta123.csv` (conta não é numérica)
    - `X_12344332.ofx` (prefixo inválido)
    
    ### 💡 Dica:
    Renomeie seus arquivos antes do upload usando o padrão:
    - Bancário: `B_[NÚMERO_DA_CONTA].[extensão]`
    - Contábil: `C_[NÚMERO_DA_CONTA].[extensão]`
    """)