# pages/1_📥_importacao_dados.py
import streamlit as st
import pandas as pd
import tempfile
import os
from datetime import datetime

st.set_page_config(page_title="Importação de Dados", page_icon="📥", layout="wide")

st.title("📥 Importação de Dados para Análise")
st.markdown("Faça upload dos documentos para análise de conciliação")

# Configuração do período
st.sidebar.header("⚙️ Período de Análise")
data_inicio = st.sidebar.date_input("Data Início", value=datetime.now().replace(day=1))
data_fim = st.sidebar.date_input("Data Fim", value=datetime.now())

# Conta bancária
st.sidebar.header("🏦 Conta Bancária")
conta_info = st.sidebar.text_input("Identificação da Conta", placeholder="Ex: Itaú 12345-6")

# Área principal de upload
col1, col2 = st.columns(2)

with col1:
    st.subheader("📊 Extrato Bancário")
    st.markdown("""
    **Formatos suportados:**
    - OFX/CSV (extrato bancário)
    - CNAB 240/400 (retorno)
    - PDF (com OCR)
    """)
    
    tipo_extrato = st.selectbox("Tipo de Arquivo", ["OFX", "CSV", "CNAB 240", "CNAB 400", "PDF"])
    arquivo_extrato = st.file_uploader(
        f"Upload do Extrato ({tipo_extrato})", 
        type=['ofx', 'csv', 'txt', 'pdf', 'ret'],
        key="extrato"
    )
    
    if arquivo_extrato:
        # Salvar arquivo temporariamente
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{tipo_extrato.lower()}") as tmp_file:
            tmp_file.write(arquivo_extrato.getvalue())
            st.session_state['caminho_extrato'] = tmp_file.name
        
        st.success(f"✅ Extrato carregado: {arquivo_extrato.name}")
        st.session_state['extrato_carregado'] = True

with col2:
    st.subheader("📈 Lançamentos Contábeis")
    st.markdown("""
    **Fontes suportadas:**
    - CSV/Excel (exportação ERP)
    - PDF (relatório contábil)
    - Outros formatos
    """)
    
    tipo_contabil = st.selectbox("Tipo de Arquivo Contábil", ["CSV", "Excel", "PDF"])
    arquivo_contabil = st.file_uploader(
        f"Upload Lançamentos ({tipo_contabil})",
        type=['csv', 'xlsx', 'xls', 'pdf'],
        key="contabil"
    )
    
    if arquivo_contabil:
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{tipo_contabil.lower()}") as tmp_file:
            tmp_file.write(arquivo_contabil.getvalue())
            st.session_state['caminho_contabil'] = tmp_file.name
        
        st.success(f"✅ Lançamentos carregados: {arquivo_contabil.name}")
        st.session_state['contabil_carregado'] = True

# Status e próxima etapa
st.divider()
st.subheader("📋 Status do Carregamento")

status_col1, status_col2, status_col3 = st.columns(3)

with status_col1:
    if st.session_state.get('extrato_carregado'):
        st.success("✅ Extrato Bancário")
        st.caption("Pronto para análise")
    else:
        st.warning("📥 Aguardando extrato")

with status_col2:
    if st.session_state.get('contabil_carregado'):
        st.success("✅ Lançamentos Contábeis")
        st.caption("Pronto para análise")
    else:
        st.warning("📥 Aguardando lançamentos")

with status_col3:
    if st.session_state.get('extrato_carregado') and st.session_state.get('contabil_carregado'):
        st.success("✅ Dados Completos")
        st.caption("Próximo: Análise dos dados")
        
        if st.button("🔍 Iniciar Análise", type="primary", use_container_width=True):
            st.switch_page("pages/analise_dados.py")
    else:
        st.warning("⏳ Aguardando arquivos")

# Informações adicionais
with st.expander("ℹ️ Instruções de Upload"):
    st.markdown("""
    **Para melhor análise:**
    
    1. **Extrato Bancário** deve conter:
       - Data da transação
       - Valor 
       - Descrição/Histórico
       - Identificadores (NSU, TXID PIX, Nosso Número)
    
    2. **Lançamentos Contábeis** devem conter:
       - Data do lançamento
       - Valor
       - Descrição
       - Cliente/Fornecedor
       - Número do documento
       
    **📝 O sistema irá:**
    - Analisar correspondências
    - Identificar divergências  
    - Sugerir conciliações
    - Gerar relatório para sua decisão final
    """)