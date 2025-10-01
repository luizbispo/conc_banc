
# pages/3_📋_revisao_resultados.py
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import modules.data_analyzer as analyzer

st.set_page_config(page_title="Revisão de Resultados", page_icon="📋", layout="wide")

st.title("📋 Revisão de Resultados da Conciliação")
st.markdown("Revise e confirme os matches identificados antes de gerar o relatório final")

# Verificar se a análise foi realizada
if 'resultados_analise' not in st.session_state:
    st.error("❌ Análise não realizada. Volte para a página de análise.")
    if st.button("🔍 Fazer Análise"):
        st.switch_page("pages/analise_dados.py")
    st.stop()

resultados = st.session_state['resultados_analise']
extrato_df = st.session_state['extrato_df']
contabil_df = st.session_state['contabil_df']

# Inicializar session state para aprovações
if 'matches_aprovados' not in st.session_state:
    st.session_state['matches_aprovados'] = []
if 'matches_rejeitados' not in st.session_state:
    st.session_state['matches_rejeitados'] = []
if 'matches_pendentes' not in st.session_state:
    st.session_state['matches_pendentes'] = resultados['matches'].copy()

# Sidebar com estatísticas
st.sidebar.header("📊 Status da Revisão")

total_matches = len(resultados['matches'])
aprovados = len(st.session_state['matches_aprovados'])
rejeitados = len(st.session_state['matches_rejeitados'])
pendentes = len(st.session_state['matches_pendentes'])

st.sidebar.metric("Matches Totais", total_matches)
st.sidebar.metric("✅ Aprovados", aprovados)
st.sidebar.metric("❌ Rejeitados", rejeitados)
st.sidebar.metric("⏳ Pendentes", pendentes)

# Barra de progresso
if total_matches > 0:
    progresso = (aprovados + rejeitados) / total_matches
    st.sidebar.progress(progresso)
    st.sidebar.caption(f"Revisão: {progresso:.1%} concluída")

# Filtros e busca
st.sidebar.header("🔍 Filtros")
filtro_camada = st.sidebar.multiselect(
    "Filtrar por Camada",
    ["exata", "heuristica", "ia"],
    default=["exata", "heuristica", "ia"]
)

filtro_tipo = st.sidebar.multiselect(
    "Filtrar por Tipo",
    ["1:1", "1:N", "N:1"],
    default=["1:1", "1:N", "N:1"]
)

filtro_confianca = st.sidebar.slider(
    "Confiança Mínima (%)",
    0, 100, 70
)

# Aplicar filtros aos matches pendentes
matches_filtrados = [
    match for match in st.session_state['matches_pendentes']
    if (match['camada'] in filtro_camada and 
        match['tipo_match'] in filtro_tipo and 
        match['confianca'] >= filtro_confianca)
]

# Área principal de revisão
if not matches_filtrados:
    if pendentes == 0:
        st.success("🎉 Todas as conciliações foram revisadas!")
        st.balloons()
    else:
        st.warning("Nenhum match encontrado com os filtros atuais.")
    
    # Mostrar resumo final
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("✅ Conciliations Aprovadas", aprovados)
    with col2:
        st.metric("❌ Conciliations Rejeitadas", rejeitados)
    with col3:
        st.metric("📊 Taxa de Aprovação", 
                 f"{(aprovados/(aprovados+rejeitados)*100):.1f}%" if (aprovados+rejeitados) > 0 else "0%")
    
    if st.button("📄 Gerar Relatório Final", type="primary", disabled=pendentes>0):
        st.switch_page("pages/gerar_relatorio.py")
    
else:
    # Revisão individual dos matches
    match_atual = matches_filtrados[0]
    idx_global = st.session_state['matches_pendentes'].index(match_atual)
    
    st.header(f"Revisão {aprovados + rejeitados + 1} de {total_matches}")
    
    # Cartão do match
    with st.container():
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            # Informações do match
            st.subheader(f"Match {idx_global + 1} - {match_atual['tipo_match']}")
            
            # Badges de status
            col_badge1, col_badge2, col_badge3 = st.columns(3)
            with col_badge1:
                camada_cor = {
                    'exata': '🟢',
                    'heuristica': '🟡', 
                    'ia': '🔵'
                }
                st.write(f"{camada_cor.get(match_atual['camada'], '⚪')} **Camada:** {match_atual['camada'].upper()}")
            
            with col_badge2:
                st.write(f"🎯 **Confiança:** {match_atual['confianca']}%")
            
            with col_badge3:
                st.write(f"💡 **Tipo:** {match_atual['tipo_match']}")
        
        with col2:
            st.metric("Valor Total", f"R$ {match_atual['valor_total']:,.2f}")
        
        with col3:
            st.metric("Transações", 
                     f"{len(match_atual['ids_extrato'])} : {len(match_atual['ids_contabil'])}")
    
    # Explicação do match
    st.info(f"**Explicação:** {match_atual['explicacao']}")
    
    # Detalhes das transações
    col_detalhes1, col_detalhes2 = st.columns(2)
    
    with col_detalhes1:
        st.subheader("🏦 Transações Bancárias")
        transacoes_extrato = extrato_df[extrato_df['id'].isin(match_atual['ids_extrato'])]
        
        for _, transacao in transacoes_extrato.iterrows():
            with st.expander(f"💰 R$ {transacao['valor']:,.2f} - {transacao['data']}", expanded=True):
                col_t1, col_t2 = st.columns(2)
                with col_t1:
                    st.write(f"**Data:** {transacao['data']}")
                    st.write(f"**Valor:** R$ {transacao['valor']:,.2f}")
                with col_t2:
                    st.write(f"**Descrição:** {transacao.get('descricao', 'N/A')}")
                    if 'categoria' in transacao:
                        st.write(f"**Categoria:** {transacao['categoria']}")
    
    with col_detalhes2:
        st.subheader("📊 Lançamentos Contábeis")
        transacoes_contabil = contabil_df[contabil_df['id'].isin(match_atual['ids_contabil'])]
        
        for _, lancamento in transacoes_contabil.iterrows():
            with st.expander(f"📝 R$ {lancamento['valor']:,.2f} - {lancamento['data']}", expanded=True):
                col_l1, col_l2 = st.columns(2)
                with col_l1:
                    st.write(f"**Data:** {lancamento['data']}")
                    st.write(f"**Valor:** R$ {lancamento['valor']:,.2f}")
                with col_l2:
                    st.write(f"**Descrição:** {lancamento.get('descricao', 'N/A')}")
                    if 'cliente_fornecedor' in lancamento:
                        st.write(f"**Cliente/Fornecedor:** {lancamento['cliente_fornecedor']}")
    
    # Análise de correspondência
    st.subheader("🔍 Análise de Correspondência")
    
    # Calcular métricas de matching
    if len(match_atual['ids_extrato']) == 1 and len(match_atual['ids_contabil']) == 1:
        trans_extrato = extrato_df[extrato_df['id'] == match_atual['ids_extrato'][0]].iloc[0]
        trans_contabil = contabil_df[contabil_df['id'] == match_atual['ids_contabil'][0]].iloc[0]
        
        col_met1, col_met2, col_met3 = st.columns(3)
        
        with col_met1:
            diff_dias = abs((trans_contabil['data'] - trans_extrato['data']).days)
            st.metric("Diferença de Dias", diff_dias, 
                     delta="Dentro da tolerância" if diff_dias <= 2 else "Fora da tolerância")
        
        with col_met2:
            diff_valor = abs(trans_contabil['valor'] - trans_extrato['valor'])
            st.metric("Diferença de Valor", f"R$ {diff_valor:.2f}",
                     delta="Dentro da tolerância" if diff_valor <= 0.02 else "Fora da tolerância")
        
        with col_met3:
            data_analyzer = analyzer.DataAnalyzer()
            similaridade = data_analyzer._calcular_similaridade(
                trans_extrato.get('descricao', ''),
                trans_contabil.get('descricao', '')
            )
            st.metric("Similaridade Textual", f"{similaridade:.1f}%")
    
    # Ações do usuário
    st.divider()
    st.subheader("✅ Tomada de Decisão")
    
    col_acao1, col_acao2, col_acao3 = st.columns(3)
    
    with col_acao1:
        if st.button("✅ Aprovar Conciliação", type="primary", use_container_width=True):
            # Mover para aprovados
            st.session_state['matches_aprovados'].append(match_atual)
            st.session_state['matches_pendentes'].pop(idx_global)
            st.rerun()
    
    with col_acao2:
        if st.button("❌ Rejeitar Conciliação", type="secondary", use_container_width=True):
            # Mover para rejeitados
            st.session_state['matches_rejeitados'].append(match_atual)
            st.session_state['matches_pendentes'].pop(idx_global)
            st.rerun()
    
    with col_acao3:
        if st.button("⏭️ Pular para Próximo", use_container_width=True):
            # Manter como pendente e ir para próximo
            st.rerun()
    
    # Comentários e justificativa
    with st.expander("💬 Adicionar Comentário (Opcional)"):
        comentario = st.text_area(
            "Comentários sobre esta conciliação:",
            placeholder="Ex: Aprovo com ressalvas porque... / Rejeito porque...",
            key=f"comentario_{idx_global}"
        )
        
        if comentario:
            st.info(f"Comentário salvo: {comentario}")

# Seção de exceções (se houver)
if resultados.get('excecoes'):
    st.divider()
    st.header("⚠️ Exceções Identificadas")
    
    for i, excecao in enumerate(resultados['excecoes']):
        with st.expander(f"{excecao['tipo']} - {excecao['severidade']}", expanded=i==0):
            col_ex1, col_ex2 = st.columns([3, 1])
            
            with col_ex1:
                st.write(f"**Descrição:** {excecao['descricao']}")
                st.write(f"**Ação Sugerida:** {excecao['acao_sugerida']}")
            
            with col_ex2:
                st.write(f"**Transações Envolvidas:** {len(excecao['ids_envolvidos'])}")
            
            # Mostrar transações relacionadas à exceção
            if 'extrato' in excecao['descricao'].lower():
                transacoes_excecao = extrato_df[extrato_df['id'].isin(excecao['ids_envolvidos'])]
            else:
                transacoes_excecao = contabil_df[contabil_df['id'].isin(excecao['ids_envolvidos'])]
            
            if len(transacoes_excecao) > 0:
                st.dataframe(transacoes_excecao[['data', 'valor', 'descricao']].head(5), 
                           use_container_width=True)

# Navegação
st.divider()
col_nav1, col_nav2, col_nav3 = st.columns(3)

with col_nav1:
    if st.button("↩️ Voltar para Análise"):
        st.switch_page("pages/analise_dados.py")

with col_nav2:
    st.info(f"⏳ {pendentes} conciliações pendentes")

with col_nav3:
    if pendentes == 0 and st.button("📄 Gerar Relatório Final", type="primary"):
        st.switch_page("pages/gerar_relatorio.py")

# Instruções
with st.expander("ℹ️ Instruções de Revisão"):
    st.markdown("""
    **Como revisar as conciliações:**
    
    1. **✅ Aprovar** - Quando a correspondência está correta
    2. **❌ Rejeitar** - Quando a correspondência está incorreta
    3. **⏭️ Pular** - Para revisar depois
    
    **Critérios para aprovação:**
    - Correspondência faz sentido comercialmente
    - Datas e valores são consistentes
    - Descrições são relacionadas
    - Não há indícios de duplicidade
    
    **O relatório final incluirá apenas as conciliações aprovadas.**
    """)