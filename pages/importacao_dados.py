# pages/1_📥_importacao_dados.py
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import io
import requests
import re
from urllib.parse import urlparse
import modules.data_processor as processor


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

# nstruções
with st.expander(" Guia Completo de Importação"):
    st.markdown("""
    ##  Métodos de Importação Recomendados
    
    ###  Upload de Arquivos (RECOMENDADO)
    **Quando usar:** Testes iniciais, arquivos locais
    **Vantagens:** 
    - Mais confiável
    - Funciona offline
    - Processamento rápido
    
    ###  Link de Pastas (EXPERIMENTAL)
    **Quando usar:** Arquivos já organizados em pastas na nuvem
    **Pré-requisitos:**
    - Pastas compartilhadas publicamente
    - Arquivos com nomes padronizados
    - Acesso à internet
    
    ##  Formatação dos Arquivos
    
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
    """)

# Inicializar session state
if 'extrato_df' not in st.session_state:
    st.session_state.extrato_df = None
if 'contabil_df' not in st.session_state:
    st.session_state.contabil_df = None
if 'dados_carregados' not in st.session_state:
    st.session_state.dados_carregados = False

# Sidebar com instruções
st.sidebar.header("📋 Instruções Gerais")

st.sidebar.markdown("""
**📊 Dados Necessários:**
1. **Extrato Bancário** - Transações do banco
2. **Lançamentos Contábeis** - Registros do sistema contábil

**⏰ Período:** Ambos devem ser do mesmo mês
""")

# Seleção do método de importação
st.sidebar.header("🔧 Método de Importação")
metodo_importacao = st.sidebar.radio(
    "Como deseja importar os dados?",
    ["📤 Upload de Arquivos", "☁️ Link de Pastas na Nuvem", "🔗 Links Diretos para Arquivos"],
    index=0
)

if metodo_importacao == "📤 Upload de Arquivos":
    st.header("📤 Upload de Arquivos Locais")
    
    st.info("""
    **Recomendado para:** Testes rápidos e quando os arquivos estão no seu computador
    **Formatos suportados:** CSV, Excel (.xlsx, .xls)
    """)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🏦 Extrato Bancário")
        extrato_file = st.file_uploader(
            "Selecione o arquivo do extrato bancário:",
            type=['csv', 'xlsx', 'xls'],
            key="extrato_upload",
            help="Arquivo CSV ou Excel com as transações bancárias"
        )
        
        if extrato_file is not None:
            try:
                if extrato_file.name.endswith('.csv'):
                    extrato_df = pd.read_csv(extrato_file)
                else:
                    extrato_df = pd.read_excel(extrato_file)
                
                st.session_state.extrato_df = extrato_df
                st.success(f"✅ Extrato carregado: {len(extrato_df)} transações")
                st.dataframe(extrato_df.head(), width='stretch')
                
            except Exception as e:
                st.error(f"❌ Erro ao carregar extrato: {e}")
    
    with col2:
        st.subheader("📊 Lançamentos Contábeis")
        contabil_file = st.file_uploader(
            "Selecione o arquivo dos lançamentos contábeis:",
            type=['csv', 'xlsx', 'xls'],
            key="contabil_upload",
            help="Arquivo CSV ou Excel com os lançamentos do sistema contábil"
        )
        
        if contabil_file is not None:
            try:
                if contabil_file.name.endswith('.csv'):
                    contabil_df = pd.read_csv(contabil_file)
                else:
                    contabil_df = pd.read_excel(contabil_file)
                
                st.session_state.contabil_df = contabil_df
                st.success(f"✅ Lançamentos carregados: {len(contabil_df)} registros")
                st.dataframe(contabil_df.head(), width='stretch')
                
            except Exception as e:
                st.error(f"❌ Erro ao carregar lançamentos: {e}")

elif metodo_importacao == "☁️ Link de Pastas na Nuvem":
    st.header("☁️ Importação por Link de Pastas")
    
    st.warning("""
    **⚠️ Funcionalidade Experimental**
    Esta funcionalidade está em desenvolvimento e pode não funcionar em todos os casos.
    Se encontrar problemas, use o método de Upload de Arquivos.
    """)
    
    st.success("""
    **✅ Funciona melhor com:**
    - Google Drive (pastas compartilhadas)
    - SharePoint Online
    - Arquivos com nomes padronizados
    """)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📁 Pasta dos Extratos")
        
        pasta_extratos = st.text_input(
            "Link da pasta com os extratos:",
            placeholder="https://drive.google.com/... OU https://sharepoint.com/...",
            key="pasta_extratos",
            help="Cole o link completo da pasta (não do arquivo)"
        )
        
        st.markdown("**📄 O sistema procurará por:**")
        st.code("extrato_bancario_JANEIRO.csv")
        st.code("extrato_JANEIRO.xlsx")
        st.code("extrato_banco_JANEIRO.csv")
        
        mes_extrato = st.selectbox(
            "Mês dos extratos:",
            ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", 
             "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"],
            key="mes_extrato"
        )

    with col2:
        st.subheader("📁 Pasta dos Lançamentos")
        
        pasta_contabil = st.text_input(
            "Link da pasta com os lançamentos:",
            placeholder="https://drive.google.com/... OU https://sharepoint.com/...",
            key="pasta_contabil",
            help="Cole o link completo da pasta (não do arquivo)"
        )
        
        st.markdown("**📄 O sistema procurará por:**")
        st.code("contabil_JANEIRO.csv")
        st.code("lancamentos_JANEIRO.xlsx")
        st.code("contabilidade_JANEIRO.csv")
        
        mes_contabil = st.selectbox(
            "Mês dos lançamentos:",
            ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
             "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"],
            key="mes_contabil"
        )
    
    # Botão para importar
    if st.button("🔍 Procurar e Importar das Pastas", type="primary", width='stretch'):
        if pasta_extratos:
            with st.spinner(f"Procurando extratos de {mes_extrato}..."):
                try:
                    extrato_df = processor.importar_de_pasta_cloud(
                        folder_url=pasta_extratos,
                        padrao_nome=r".*extrato.*\.(csv|xlsx|xls)$",
                        mes_referencia=mes_extrato,
                        tipo_arquivo="extratos bancários"
                    )
                    
                    if extrato_df is not None:
                        st.session_state.extrato_df = extrato_df
                        st.success(f"✅ Extratos importados: {len(extrato_df)} transações")
                        st.dataframe(extrato_df.head(), width='stretch')
                    else:
                        st.error(f"❌ Nenhum extrato encontrado")
                        st.info("💡 Dica: Verifique se os arquivos estão nomeados corretamente")
                        
                except Exception as e:
                    st.error(f"❌ Erro: {e}")
        
        if pasta_contabil:
            with st.spinner(f"Procurando lançamentos de {mes_contabil}..."):
                try:
                    contabil_df = processor.importar_de_pasta_cloud(
                        folder_url=pasta_contabil,
                        padrao_nome=r".*(contabil|lancamento).*\.(csv|xlsx|xls)$",
                        mes_referencia=mes_contabil,
                        tipo_arquivo="lançamentos contábeis"
                    )
                    
                    if contabil_df is not None:
                        st.session_state.contabil_df = contabil_df
                        st.success(f"✅ Lançamentos importados: {len(contabil_df)} registros")
                        st.dataframe(contabil_df.head(), width='stretch')
                    else:
                        st.error(f"❌ Nenhum lançamento encontrado")
                        st.info("💡 Dica: Verifique se os arquivos estão nomeados corretamente")
                        
                except Exception as e:
                    st.error(f"❌ Erro: {e}")

else:  # 🔗 Links Diretos para Arquivos
    st.header("🔗 Links Diretos para Arquivos")
    
    st.info("""
    **Recomendado quando:** Você tem links diretos para os arquivos específicos
    **Funciona com:** Google Drive, SharePoint, OneDrive, Dropbox
    """)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🏦 Links dos Extratos")
        
        extrato_links = st.text_area(
            "Links diretos para os arquivos de extrato:",
            placeholder="https://drive.google.com/...\nhttps://sharepoint.com/...",
            height=100,
            key="extrato_links",
            help="Um link por linha. Devem ser links diretos para os arquivos."
        )
        
        st.markdown("**📝 Como obter links diretos:**")
        st.markdown("""
        - **Google Drive:** Clique com botão direito → "Obter link" → "Restrito" → "Qualquer pessoa com o link"
        - **SharePoint:** Clique com botão direito → "Compartilhar" → Copiar link
        """)

    with col2:
        st.subheader("📊 Links dos Lançamentos")
        
        contabil_links = st.text_area(
            "Links diretos para os arquivos contábeis:",
            placeholder="https://drive.google.com/...\nhttps://sharepoint.com/...",
            height=100,
            key="contabil_links",
            help="Um link por linha. Devem ser links diretos para os arquivos."
        )
    
    # Esta funcionalidade seria implementada posteriormente
    st.warning("🚧 Funcionalidade em desenvolvimento")
    st.info("""
    **Por enquanto, use:**
    - 📤 **Upload de Arquivos** para testes rápidos
    - ☁️ **Link de Pastas** se seus arquivos estão em pastas compartilhadas
    """)

# Processamento dos dados (comum para todos os métodos)
if st.session_state.extrato_df is not None and st.session_state.contabil_df is not None:
    st.divider()
    st.header("🔧 Configuração das Colunas")
    
    st.info("""
    **Identifique as colunas correspondentes em seus arquivos:**
    - **Data:** Coluna com as datas das transações
    - **Valor:** Coluna com os valores (positivos para crédito, negativos para débito)  
    - **Descrição:** Coluna com a descrição/histórico das transações
    """)
    
    col_config1, col_config2 = st.columns(2)
    
    with col_config1:
        st.markdown("**🏦 Extrato Bancário**")
        extrato_cols = st.session_state.extrato_df.columns.tolist()
        
        col_data_extrato = st.selectbox("Coluna de Data:", extrato_cols, index=0)
        col_valor_extrato = st.selectbox("Coluna de Valor:", extrato_cols, index=1)
        col_descricao_extrato = st.selectbox("Coluna de Descrição:", extrato_cols, index=2)
        
        # Preview
        st.markdown("**Pré-visualização:**")
        st.dataframe(st.session_state.extrato_df[[col_data_extrato, col_valor_extrato, col_descricao_extrato]].head(3))
    
    with col_config2:
        st.markdown("**📊 Lançamentos Contábeis**")
        contabil_cols = st.session_state.contabil_df.columns.tolist()
        
        col_data_contabil = st.selectbox("Coluna de Data:", contabil_cols, index=0, key="contabil_data")
        col_valor_contabil = st.selectbox("Coluna de Valor:", contabil_cols, index=1, key="contabil_valor")
        col_descricao_contabil = st.selectbox("Coluna de Descrição:", contabil_cols, index=2, key="contabil_desc")
        
        # Preview
        st.markdown("**Pré-visualização:**")
        st.dataframe(st.session_state.contabil_df[[col_data_contabil, col_valor_contabil, col_descricao_contabil]].head(3))
    
    # Processar dados
    if st.button("🔄 Processar Dados", type="primary", width='stretch'):
        with st.spinner("Processando e padronizando dados..."):
            try:
                # Processar extrato
                extrato_processado = processor.processar_extrato(
                    st.session_state.extrato_df,
                    col_data_extrato,
                    col_valor_extrato,
                    col_descricao_extrato
                )
                
                # Processar lançamentos contábeis
                contabil_processado = processor.processar_contabil(
                    st.session_state.contabil_df,
                    col_data_contabil,
                    col_valor_contabil,
                    col_descricao_contabil
                )
                
                # Salvar no session state
                st.session_state.extrato_df = extrato_processado
                st.session_state.contabil_df = contabil_processado
                st.session_state.dados_carregados = True
                
                st.success("✅ Dados processados com sucesso!")
                
                # Mostrar resumo
                col_res1, col_res2 = st.columns(2)
                with col_res1:
                    st.metric("Transações Bancárias", len(extrato_processado))
                    st.dataframe(extrato_processado[['data', 'valor', 'descricao']].head(3))
                
                with col_res2:
                    st.metric("Lançamentos Contábeis", len(contabil_processado))
                    st.dataframe(contabil_processado[['data', 'valor', 'descricao']].head(3))
                
            except Exception as e:
                st.error(f"❌ Erro no processamento: {e}")

# Navegação
if st.session_state.dados_carregados:
    st.divider()
    st.success(" Dados prontos para análise!")
    
    col_nav1, col_nav2, col_nav3 = st.columns([1, 2, 1])
    
    with col_nav2:
        if st.button("🔍 Ir para Análise de Dados", type="primary", width='stretch'):
            st.switch_page("pages/analise_dados.py")

