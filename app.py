# app.py - Aplicação Principal Streamlit
import streamlit as st
from streamlit import Page

# Configuração da página
st.set_page_config(
    page_title="Sistema de Conciliação Bancária",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Título principal
st.title("🏦 Sistema de Conciliação Bancária")
st.markdown("""
### Sistema profissional para análise e conciliação de extratos bancários

**Funcionalidades principais:**
- 📥 **Importação** de extratos bancários e lançamentos contábeis
- 🔍 **Análise inteligente** com matching em múltiplas camadas
- 📋 **Revisão assistida** para validação do contador
- 📄 **Relatórios PDF** profissionais para documentação

**Fluxo recomendado:**
1. **Importação** → Carregue os arquivos bancários e contábeis
2. **Análise** → Sistema identifica correspondências automaticamente
3. **Revisão** → Valide as conciliações propostas
4. **Relatório** → Gere PDF para documentação e auditoria
""")

# Navegação entre páginas
st.divider()
st.subheader("🚀 Iniciar Conciliação")

col1, col2, col3, col4 = st.columns(4)

with col1:
    if st.button("📥 Importação de Dados", use_container_width=True):
        st.switch_page("pages/importacao_dados.py")

with col2:
    if st.button("🔍 Análise de Dados", use_container_width=True):
        st.switch_page("pages/analise_dados.py")

with col3:
    if st.button("📋 Revisão de Resultados", use_container_width=True):
        st.switch_page("pages/revisao_resultados.py")

with col4:
    if st.button("📄 Gerar Relatório", use_container_width=True):
        st.switch_page("pages/gerar_relatorio.py")

# Informações do sistema
with st.sidebar:
    st.header("ℹ️ Sobre o Sistema")
    st.markdown("""
    **Versão:** 1.0.0
    **Desenvolvido para:** Empresas e contadores
    **Funcionalidades:**
    - Suporte a OFX, CSV, CNAB
    - Matching inteligente
    - Auditoria completa
    - Relatórios PDF
    """)
    
    # Status da sessão atual
    st.divider()
    st.subheader("📊 Status da Sessão")
    
    if 'extrato_carregado' in st.session_state:
        st.success("✅ Extrato carregado")
    else:
        st.warning("📥 Aguardando extrato")
    
    if 'contabil_carregado' in st.session_state:
        st.success("✅ Lançamentos carregados")
    else:
        st.warning("📥 Aguardando lançamentos")
    
    if 'resultados_analise' in st.session_state:
        st.success("✅ Análise concluída")
    
    if 'matches_aprovados' in st.session_state:
        st.success(f"✅ {len(st.session_state.matches_aprovados)} conciliações aprovadas")

# Limpar sessão
st.sidebar.divider()
if st.sidebar.button("🔄 Nova Análise", use_container_width=True):
    keys_to_clear = [
        'extrato_carregado', 'contabil_carregado', 'caminho_extrato', 
        'caminho_contabil', 'resultados_analise', 'extrato_df', 
        'contabil_df', 'matches_aprovados', 'matches_rejeitados', 
        'matches_pendentes'
    ]
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()