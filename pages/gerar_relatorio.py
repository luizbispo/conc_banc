# pages/4_📄_gerar_relatorio.py
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import tempfile
import os
import base64
import modules.report_generator as report_gen
import locale

try:
    locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_TIME, 'pt_BR')
    except locale.Error:
        try:
            locale.setlocale(locale.LC_TIME, 'Portuguese_Brazil')
        except locale.Error:
            print("Aviso: Não foi possível definir o locale para Português. Usando solução manual...")


st.set_page_config(page_title="Relatório de Análise", page_icon="📄", layout="wide")

# --- Menu Customizado ---
with st.sidebar:
    st.markdown("### Navegação Principal") 
    st.page_link("app.py", label="Início (Home)", icon="🏠")
    
    st.page_link("pages/importacao_dados.py", label="📥 Importação de Dados", icon=None)
    st.page_link("pages/analise_dados.py", label="📊 Análise de Divergências", icon=None)
    st.page_link("pages/gerar_relatorio.py", label="📝 Relatório Final", icon=None)
# --- Fim do Menu Customizado ---

st.title("📄 Relatório de Análise de Correspondências")
st.markdown("Gere o relatório completo com todas as correspondências identificadas e divergências")

# Instruções
with st.expander("Sobre este Relatório"):
    st.markdown("""
    ## Objetivo do Relatório
    
    Este relatório fornece uma **análise completa** das correspondências identificadas entre:
    - Transações bancárias
    - Lançamentos contábeis
    
    ##  Conteúdo Incluído:
    
    - **Correspondências identificadas** - Itens que provavelmente se relacionam
    - **Divergências** - Itens que precisam de atenção manual  
    - **Estatísticas** - Visão geral da análise
    - **Recomendações** - Próximos passos sugeridos
    
    ##  Como Usar:
    
    1. **Revise as correspondências** - Confirme as relações identificadas
    2. **Analise as divergências** - Investigue itens sem correspondência
    3. **Use como base** para a conciliação manual final
    
    **⚠️ Importante:** Este é um relatório de **análise**, não de conciliação final.
    O contador deve validar todas as correspondências antes do encerramento.
    """)

# Verificar se há resultados de análise
if 'resultados_analise' not in st.session_state:
    st.error("❌ Nenhuma análise realizada. Volte para a página de análise.")
    st.info("Execute a análise de correspondências primeiro para gerar o relatório.")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔍 Fazer Análise", key="btn_ir_analise"):
            st.switch_page("pages/analise_dados.py")
    st.stop()

# Dados para o relatório
resultados_analise = st.session_state['resultados_analise']
extrato_df = st.session_state['extrato_df']
contabil_df = st.session_state['contabil_df']
extrato_filtrado = st.session_state.get('extrato_filtrado', extrato_df)
contabil_filtrado = st.session_state.get('contabil_filtrado', contabil_df)

# Configurações do relatório
st.sidebar.header("⚙️ Configurações do Relatório")

empresa_nome = st.sidebar.text_input("Nome da Empresa", "")
contador_nome = st.sidebar.text_input("Nome do Contador", "")
periodo_relatorio = st.sidebar.text_input("Período da Análise", 
                                         f"{datetime.now().strftime('%B/%Y')}")

# Opções de conteúdo
st.sidebar.header("📋 Conteúdo do Relatório")
incluir_detalhes_matches = st.sidebar.checkbox("Incluir detalhes das correspondências", True)
incluir_divergencias = st.sidebar.checkbox("Incluir análise de divergências", True)
incluir_estatisticas = st.sidebar.checkbox("Incluir estatísticas detalhadas", True)
incluir_recomendacoes = st.sidebar.checkbox("Incluir recomendações", True)

# Pré-visualização do relatório
st.header("📋 Resumo da Análise")

# Métricas do relatório
col1, col2, col3, col4 = st.columns(4)

with col1:
    total_extrato = len(extrato_filtrado)
    match_extrato = len(resultados_analise['matches'])
    st.metric("Transações Analisadas", total_extrato)

with col2:
    total_contabil = len(contabil_filtrado)
    match_contabil = sum(len(match['ids_contabil']) for match in resultados_analise['matches'])
    st.metric("Lançamentos Analisados", total_contabil)

with col3:
    taxa_cobertura = (match_extrato / total_extrato * 100) if total_extrato > 0 else 0
    st.metric("Cobertura de Análise", f"{taxa_cobertura:.1f}%")

with col4:
    excecoes = len(resultados_analise['excecoes'])
    st.metric("Divergências Identificadas", excecoes)

# Sumário executivo
st.subheader("📊 Sumário Executivo")

# --- CSS de Estilização das Abas ---
st.markdown("""
<style>
/* 1. Estilo para o container principal (a lista de abas) */
.stTabs [data-baseweb="tab-list"] {
    gap: 10px; /* Espaço entre as abas */
    justify-content: center; /* Centraliza as abas (opcional) */
}

/* 2. Estilo para a ABA INDIVIDUAL (não selecionada) */
.stTabs [data-baseweb="tab"] {
    height: 40px;
    background-color: #F0F2F6; /* Cor de fundo da aba */
    border-radius: 8px 8px 0px 0px; /* Cantos arredondados no topo */
    gap: 10px;
    padding: 10px 15px; /* Preenchimento interno */
    color: #4B4B4B; /* Cor do texto da aba */
    font-size: 16px;
    font-weight: 500;
    transition: background-color 0.3s, color 0.3s; /* Transição suave */
}

/* 3. Estilo para a ABA ATIVA (selecionada) */
.stTabs [aria-selected="true"] {
    background-color: #0078D4; /* Cor de fundo da aba selecionada (azul do Windows) */
    color: #FFFFFF; /* Cor do texto da aba selecionada (branco) */
    font-weight: bold;
    border-bottom: 4px solid #FF4B4B; /* Adiciona uma linha inferior colorida */
}
</style>
""", unsafe_allow_html=True)
# --- Fim do CSS ---

aba_sumario, aba_correspondencias, aba_divergencias = st.tabs([" Visão Geral", " Correspondências", "⚠️ Divergências"])

with aba_sumario:
    col_a, col_b = st.columns(2)
    
    with col_a:
        st.markdown("**Distribuição por Tipo de Correspondência**")
        tipos_data = {
            'Tipo': ['1:1', '1:N', 'N:1'],
            'Quantidade': [
                len([m for m in resultados_analise['matches'] if m['tipo_match'] == '1:1']),
                len([m for m in resultados_analise['matches'] if m['tipo_match'] == '1:N']),
                len([m for m in resultados_analise['matches'] if m['tipo_match'] == 'N:1'])
            ]
        }
        st.bar_chart(pd.DataFrame(tipos_data).set_index('Tipo'))
    
    with col_b:
        st.markdown("**Efetividade por Camada de Análise**")
        camadas_data = {
            'Camada': ['Exata', 'Similaridade', 'Avançada'],
            'Correspondências': [
                len([m for m in resultados_analise['matches'] if m['camada'] == 'exata']),
                len([m for m in resultados_analise['matches'] if m['camada'] == 'heuristica']),
                len([m for m in resultados_analise['matches'] if m['camada'] == 'ia'])
            ]
        }
        st.bar_chart(pd.DataFrame(camadas_data).set_index('Camada'))

with aba_correspondencias:
    if resultados_analise['matches']:
        st.markdown("**Correspondências Identificadas**")
        
        dados_tabela = []
        for i, match in enumerate(resultados_analise['matches']):
            transacoes_extrato = extrato_filtrado[extrato_filtrado['id'].isin(match['ids_extrato'])]
            transacoes_contabil = contabil_filtrado[contabil_filtrado['id'].isin(match['ids_contabil'])]
            
            dados_tabela.append({
                'ID': i + 1,
                'Tipo': match['tipo_match'],
                'Camada': match['camada'],
                'Confiança': f"{match['confianca']}%",
                'Valor Total': f"R$ {match['valor_total']:,.2f}",
                'Transações Banco': len(match['ids_extrato']),
                'Lançamentos': len(match['ids_contabil']),
                'Justificativa': match['explicacao'][:80] + "..." if len(match['explicacao']) > 80 else match['explicacao']
            })
        
        st.dataframe(pd.DataFrame(dados_tabela), width='stretch')
    else:
        st.info("Nenhuma correspondência identificada")

with aba_divergencias:
    if resultados_analise.get('excecoes'):
        st.markdown("**Divergências Identificadas**")
        
        for excecao in resultados_analise['excecoes']:
            with st.expander(f"{excecao['tipo']} - {excecao['severidade']}"):
                st.write(f"**Descrição:** {excecao['descricao']}")
                st.write(f"**Recomendação:** {excecao['acao_sugerida']}")
                st.write(f"**Itens Envolvidos:** {len(excecao['ids_envolvidos'])}")
    else:
        st.success("✅ Nenhuma divergência crítica identificada")

if resultados_analise.get('excecoes'):
    st.markdown("---")
    st.subheader("📊 Tabela de Divergências Detalhada")
    
    try:
        # Criar tabela de divergências manualmente (mais confiável)
        divergencias_detalhadas = []
        
        for excecao in resultados_analise['excecoes']:
            if excecao['tipo'] == 'TRANSAÇÃO_SEM_CORRESPONDÊNCIA':
                # Para transações sem correspondência
                transacoes_divergentes = extrato_filtrado[extrato_filtrado['id'].isin(excecao['ids_envolvidos'])]
                for _, transacao in transacoes_divergentes.iterrows():
                    data_str = transacao['data'].strftime('%d/%m/%Y') if hasattr(transacao['data'], 'strftime') else str(transacao['data'])
                    divergencias_detalhadas.append({
                        'Tipo_Divergência': excecao['tipo'],
                        'Severidade': excecao['severidade'],
                        'Data': data_str,
                        'Descrição': transacao.get('descricao', 'N/A'),
                        'Valor': f"R$ {transacao['valor']:,.2f}",
                        'Origem': 'Extrato Bancário',
                        'Ação_Recomendada': excecao['acao_sugerida']
                    })
            
            elif excecao['tipo'] == 'LANÇAMENTO_SEM_CORRESPONDÊNCIA':
                # Para lançamentos sem correspondência
                lancamentos_divergentes = contabil_filtrado[contabil_filtrado['id'].isin(excecao['ids_envolvidos'])]
                for _, lancamento in lancamentos_divergentes.iterrows():
                    data_str = lancamento['data'].strftime('%d/%m/%Y') if hasattr(lancamento['data'], 'strftime') else str(lancamento['data'])
                    divergencias_detalhadas.append({
                        'Tipo_Divergência': excecao['tipo'],
                        'Severidade': excecao['severidade'],
                        'Data': data_str,
                        'Descrição': lancamento.get('descricao', 'N/A'),
                        'Valor': f"R$ {lancamento['valor']:,.2f}",
                        'Origem': 'Contábil',
                        'Ação_Recomendada': excecao['acao_sugerida']
                    })
            else:
                # Para outros tipos de divergência
                divergencias_detalhadas.append({
                    'Tipo_Divergência': excecao['tipo'],
                    'Severidade': excecao['severidade'],
                    'Data': 'Múltiplas',
                    'Descrição': excecao['descricao'],
                    'Valor': 'N/A',
                    'Origem': 'Sistema',
                    'Ação_Recomendada': excecao['acao_sugerida'],
                    'Itens_Envolvidos': len(excecao['ids_envolvidos'])
                })
        
        # Criar DataFrame e exibir
        if divergencias_detalhadas:
            df_divergencias_detalhadas = pd.DataFrame(divergencias_detalhadas)
            st.dataframe(df_divergencias_detalhadas, width='stretch', hide_index=True)
            
            # Adicionar ao session state para uso no relatório
            st.session_state['divergencias_tabela'] = df_divergencias_detalhadas
            
            # Botão para exportar
            csv_divergencias = df_divergencias_detalhadas.to_csv(index=False, encoding='utf-8')
            st.download_button(
                label="📥 Exportar Divergências (CSV)",
                data=csv_divergencias,
                file_name=f"divergencias_detalhadas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
            
    except Exception as e:
        st.error(f"Erro ao gerar tabela de divergências: {e}")
        st.info("As divergências estão disponíveis no formato de relatório acima.")

# Geração do PDF
st.divider()
st.header("📄 Gerar Relatório PDF")

col_gerar1, col_gerar2 = st.columns([2, 1])

with col_gerar1:
    st.subheader("Configurações Finais")
    
    observacoes = st.text_area(
        "Observações e Contexto para o Relatório:",
        placeholder="Ex: Contexto específico da análise, considerações importantes, períodos atípicos...",
        height=100
    )
    
    formato_relatorio = st.selectbox(
        "Formato do Relatório",
        ["Completo", "Executivo", "Resumido"]
    )

with col_gerar2:
    st.subheader("Gerar PDF")
    
    if st.button(" Gerar Relatório de Análise", type="primary", width='stretch', key="btn_gerar_relatorio_analise"):
        with st.spinner("Gerando relatório PDF..."):
            try:
                # CORREÇÃO: Obter a tabela de divergências se existir
                divergencias_tabela = None
                if 'divergencias_tabela' in st.session_state:
                    divergencias_tabela = st.session_state['divergencias_tabela']
                    st.info(f"📊 Incluindo tabela com {len(divergencias_tabela)} divergências detalhadas")
                else:
                    st.info("ℹ️ Gerando relatório sem tabela de divergências detalhada")
                
                # CORREÇÃO: Usar a função correta com todos os parâmetros
                pdf_path = report_gen.gerar_relatorio_analise(
                    resultados_analise=resultados_analise,
                    extrato_df=extrato_filtrado,
                    contabil_df=contabil_filtrado,
                    empresa_nome=empresa_nome,
                    contador_nome=contador_nome,
                    periodo=periodo_relatorio,
                    observacoes=observacoes,
                    formato=formato_relatorio.lower(),
                    divergencias_tabela=divergencias_tabela  
                )
                
                # Verificar se o pdf_path é válido
                if pdf_path is None:
                    st.error("❌ Erro: Não foi possível gerar o caminho do arquivo PDF")
                    st.stop()
                
                # Verificar se o arquivo foi criado
                if not os.path.exists(pdf_path):
                    st.error(f"❌ Erro: Arquivo PDF não foi criado em {pdf_path}")
                    st.stop()
                
                # Ler o PDF gerado
                with open(pdf_path, "rb") as pdf_file:
                    pdf_bytes = pdf_file.read()
                
                # Verificar se o conteúdo foi lido
                if len(pdf_bytes) == 0:
                    st.error("❌ Erro: Arquivo PDF está vazio")
                    st.stop()
                
                # Criar download link
                b64_pdf = base64.b64encode(pdf_bytes).decode()
                href = f'<a href="data:application/pdf;base64,{b64_pdf}" download="relatorio_analise_{datetime.now().strftime("%Y%m%d_%H%M")}.pdf" style="background-color: #4CAF50; color: white; padding: 14px 20px; text-align: center; text-decoration: none; display: inline-block; border-radius: 5px; font-size: 16px;">📥 Baixar Relatório de Análise</a>'
                
                st.markdown(href, unsafe_allow_html=True)
                st.success("✅ Relatório gerado com sucesso!")
                
                # Pré-visualização embutida
                st.subheader("👁️ Pré-visualização do PDF")
                base64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
                pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="600" type="application/pdf"></iframe>'
                st.markdown(pdf_display, unsafe_allow_html=True)
                
            except Exception as e:
                st.error(f"❌ Erro ao gerar relatório: {str(e)}")
                # Debug adicional
                st.code(f"Tipo do erro: {type(e).__name__}")
                import traceback
                st.code(traceback.format_exc())

# Navegação
st.divider()
st.header("🚪 Próximas Ações")

col_acao1, col_acao2, col_acao3 = st.columns(3)

with col_acao1:
    if st.button("↩️ Voltar para Análise", key="btn_voltar_analise"):
        st.switch_page("pages/analise_dados.py")

with col_acao2:
    if st.button("🔄 Nova Importação", key="btn_nova_importacao"):
        # Limpar session state para nova análise
        keys_to_clear = ['resultados_analise', 'extrato_filtrado', 'contabil_filtrado']
        for key in keys_to_clear:
            if key in st.session_state:
                del st.session_state[key]
        st.switch_page("pages/importacao_dados.py")

with col_acao3:
    if st.button("🏠 Início", key="btn_inicio"):
        st.switch_page("app.py")

