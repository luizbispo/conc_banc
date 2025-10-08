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

# --- Menu Customizado ---
with st.sidebar:
    st.markdown("### Navegação Principal") # Título (opcional)
    st.page_link("app.py", label="Início (Home)", icon="🏠")
    
    # Use o nome do arquivo exato no primeiro parâmetro, e o que quiser no 'label'
    st.page_link("pages/importacao_dados.py", label="📥 Importação de Dados", icon=None)
    st.page_link("pages/analise_dados.py", label="📊 Análise de Divergências", icon=None)
    st.page_link("pages/gerar_relatorio.py", label="📝 Relatório Final", icon=None)
# --- Fim do Menu Customizado ---


# Título principal
st.title("🏦 Sistema de Conciliação Bancária")
st.markdown("""
### Sistema para análise e conciliação de extratos bancários e lançamentos contábeis

**Funcionalidades principais:**
- **Importação** de extratos bancários e lançamentos contábeis
- **Análise inteligente** com matching em múltiplas camadas
- **Relatórios em PDF** para documentação

**Fluxo recomendado:**
1. **Importação** → Carregue os arquivos bancários e contábeis
2. **Análise** → Sistema identifica correspondências automaticamente
3. **Relatório** → Gere PDF para documentação e auditoria
""")

# Navegação entre páginas
st.divider()
st.subheader("Iniciar Conciliação")

col1, col2, col3 = st.columns(3)

with col1:
    if st.button("Importação de Dados", width='stretch'):
        st.switch_page("pages/importacao_dados.py")

with col2:
    if st.button("Análise de Dados", width='stretch'):
        st.switch_page("pages/analise_dados.py")

with col3:
    if st.button(" Gerar Relatório", width='stretch'):
        st.switch_page("pages/gerar_relatorio.py")

# Informações do sistema
with st.sidebar:
    st.header("ℹ️ Sobre o Sistema")
    st.markdown("""
    **Versão:** 2.0.0      
    **Desenvolvido para:** Empresas e contadores  
    **Desenvolvido por:** Luiz Bispo (X-Testing)
                
    **Funcionalidades:**
    - Suporte a OFX, CSV, CNAB
    - Matching inteligente
    - Auditoria completa
    - Relatórios em PDF
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
if st.sidebar.button("🔄 Nova Análise", width='stretch'):
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