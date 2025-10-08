# pages/2_🔍_analise_dados.py
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import tempfile
import modules.data_analyzer as analyzer

st.set_page_config(page_title="Análise de Correspondências", page_icon="🔍", layout="wide")

# --- Menu Customizado ---
with st.sidebar:
    st.markdown("### Navegação Principal") 
    st.page_link("app.py", label="Início (Home)", icon="🏠")
    
    st.page_link("pages/importacao_dados.py", label="📥 Importação de Dados", icon=None)
    st.page_link("pages/analise_dados.py", label="📊 Análise de Divergências", icon=None)
    st.page_link("pages/gerar_relatorio.py", label="📝 Relatório Final", icon=None)
# --- Fim do Menu Customizado ---

st.title("🔍 Análise de Correspondências Bancárias")
st.markdown("Identifique automaticamente as correspondências entre extrato bancário e lançamentos contábeis")

# Instruções
with st.expander(" Guia de Análise"): 
    st.markdown(""" 
    ## Objetivo desta Análise 

    Esta ferramenta **identifica automaticamente** correspondências entre: 
    - **🏦 Transações Bancárias** (extrato) 
    - **📊 Lançamentos Contábeis** (sistema contábil) 
     
    ## O que a análise faz: 
     
    1. **Correspondências Exatas** - Mesmo valor + mesma data 
        - Identificadores únicos (PIX, NSU, etc.) 
     
    2. **Correspondências por Similaridade** - Valores próximos + datas próximas 
        - Descrições semelhantes 
     
    3. **Análise de Padrões Complexos** - Parcelamentos (1 transação → N lançamentos) 
        - Consolidações (N transações → 1 lançamento) 
     
    ## Resultados Esperados: 
     
    - ✅ **Correspondências identificadas** - Itens que provavelmente se relacionam 
    - ⚠️ **Divergências** - Itens que precisam de atenção manual 
    - 📈 **Estatísticas** - Visão geral da conciliação 
     
    **💡 Importante:** Esta é uma ferramenta de **análise e identificação**, não de conciliação automática. 
    O contador deve revisar os resultados e fazer a conciliação final manualmente. 
    """)

# Verificar se os dados foram carregados
if ('extrato_df' not in st.session_state or 
    'contabil_df' not in st.session_state or 
    not st.session_state.get('dados_carregados', False)):
    
    st.error("❌ Dados não carregados ou processados. Volte para a página de importação.")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📥 Ir para Importação de Dados"):
            st.switch_page("pages/importacao_dados.py")
    with col2:
        if st.button("🔄 Recarregar Página"):
            st.rerun()
    st.stop()

# Mostrar estatísticas iniciais
st.success("✅ Dados carregados com sucesso! Configure a análise abaixo.")

extrato_df = st.session_state['extrato_df']
contabil_df = st.session_state['contabil_df']

# Converter colunas para minúsculo antes da verificação
extrato_df.columns = [col.lower() for col in extrato_df.columns]
contabil_df.columns = [col.lower() for col in contabil_df.columns]

# Verificar se as colunas necessárias existem
colunas_necessarias = ['data', 'valor', 'descricao']
colunas_extrato = extrato_df.columns.tolist()
colunas_contabil = contabil_df.columns.tolist()

colunas_faltantes_extrato = [col for col in colunas_necessarias if col not in colunas_extrato]
colunas_faltantes_contabil = [col for col in colunas_necessarias if col not in colunas_contabil]

if colunas_faltantes_extrato or colunas_faltantes_contabil:
    st.error("❌ Colunas necessárias não encontradas nos dados:")
    if colunas_faltantes_extrato:
        st.write(f"**Extrato bancário faltando:** {', '.join(colunas_faltantes_extrato)}")
        st.write(f"Colunas disponíveis no extrato: {', '.join(colunas_extrato)}")
    if colunas_faltantes_contabil:
        st.write(f"**Lançamentos contábeis faltando:** {', '.join(colunas_faltantes_contabil)}")
        st.write(f"Colunas disponíveis nos lançamentos: {', '.join(colunas_contabil)}")
    st.stop()
else:
    st.success("✅ Colunas necessárias encontradas!")

#  Preparar dados - garantir que datas e valores estão no formato correto
try:
    # Converter datas para datetime
    extrato_df['data'] = pd.to_datetime(extrato_df['data'], errors='coerce')
    contabil_df['data'] = pd.to_datetime(contabil_df['data'], errors='coerce')

    # Converter valores para numérico
    extrato_df['valor'] = pd.to_numeric(extrato_df['valor'], errors='coerce')
    contabil_df['valor'] = pd.to_numeric(contabil_df['valor'], errors='coerce')

    # Criar coluna 'id' se não existir
    if 'id' not in extrato_df.columns:
        extrato_df['id'] = [f"extrato_{i+1}" for i in range(len(extrato_df))]

    if 'id' not in contabil_df.columns:
        contabil_df['id'] = [f"contabil_{i+1}" for i in range(len(contabil_df))]

    # Remover linhas com dados inválidos
    extrato_df = extrato_df.dropna(subset=['data', 'valor'])
    contabil_df = contabil_df.dropna(subset=['data', 'valor'])

    # Processar valores para matching considerando sinal negativo do extrato
    def processar_valores_para_matching(extrato_df, contabil_df):
        """Processa valores para matching considerando sinal negativo do extrato"""
        
        # Criar coluna com valor absoluto para matching
        extrato_df['valor_abs'] = extrato_df['valor'].abs()
        contabil_df['valor_abs'] = contabil_df['valor'].abs()
        
        # Manter o valor original para exibição
        extrato_df['valor_original'] = extrato_df['valor']
        contabil_df['valor_original'] = contabil_df['valor']
        
        # Para o matching, usar o valor absoluto
        extrato_df['valor_matching'] = extrato_df['valor_abs']
        contabil_df['valor_matching'] = contabil_df['valor_abs']
        
        st.info("🔧 Valores processados para matching: usando valor absoluto para comparação")
        
        return extrato_df, contabil_df

    # Chamar a função de processamento de valores
    extrato_df, contabil_df = processar_valores_para_matching(extrato_df, contabil_df)

    # Atualizar session state
    st.session_state.extrato_df = extrato_df
    st.session_state.contabil_df = contabil_df

    st.success("✅ Dados preparados com sucesso para análise!")

except Exception as e:
    st.error(f"❌ Erro ao preparar dados: {e}")
    st.stop()

# Mostrar estatísticas
col_stat1, col_stat2, col_stat3 = st.columns(3)
with col_stat1:
    st.metric("Transações Bancárias", len(extrato_df))
with col_stat2:
    st.metric("Lançamentos Contábeis", len(contabil_df))
with col_stat3:
    try:
        if 'data' in extrato_df.columns and not extrato_df['data'].isna().all():
            data_min = extrato_df['data'].min()
            data_max = extrato_df['data'].max()
            if pd.notna(data_min) and pd.notna(data_max):
                periodo_extrato = f"{data_min.strftime('%d/%m')} a {data_max.strftime('%d/%m/%Y')}"
            else:
                periodo_extrato = "Período não disponível"
        else:
            periodo_extrato = "Período não disponível"
    except Exception as e:
        periodo_extrato = "Período não disponível"
    
    st.metric("Período Analisado", periodo_extrato)

# Mostrar informações sobre os dados
with st.expander("Informações dos Dados"):
    col_info1, col_info2 = st.columns(2)
    
    with col_info1:
        st.write("**🏦 Extrato Bancário**")
        st.write(f"- Total de transações: {len(extrato_df)}")
        st.write(f"- Período: {periodo_extrato}")
        st.write(f"- Valores negativos: {len(extrato_df[extrato_df['valor_original'] < 0])}")
        st.write(f"- Valores positivos: {len(extrato_df[extrato_df['valor_original'] > 0])}")
        
    with col_info2:
        st.write("**📊 Lançamentos Contábeis**")
        st.write(f"- Total de lançamentos: {len(contabil_df)}")
        if 'data' in contabil_df.columns and not contabil_df['data'].isna().all():
            data_min_cont = contabil_df['data'].min()
            data_max_cont = contabil_df['data'].max()
            if pd.notna(data_min_cont) and pd.notna(data_max_cont):
                periodo_contabil = f"{data_min_cont.strftime('%d/%m')} a {data_max_cont.strftime('%d/%m/%Y')}"
            else:
                periodo_contabil = "Período não disponível"
        else:
            periodo_contabil = "Período não disponível"
        st.write(f"- Período: {periodo_contabil}")

# Mostrar prévia dos dados
with st.expander("Prévia dos Dados Carregados"):
    col_previa1, col_previa2 = st.columns(2)
    
    with col_previa1:
        st.write("**🏦 Extrato Bancário (primeiras 5 linhas):**")
        display_cols = ['id', 'data', 'valor_original', 'descricao'] if 'descricao' in extrato_df.columns else ['id', 'data', 'valor_original']
        st.dataframe(extrato_df[display_cols].head(), width='stretch')
    
    with col_previa2:
        st.write("**📊 Lançamentos Contábeis (primeiras 5 linhas):**")
        display_cols = ['id', 'data', 'valor_original', 'descricao'] if 'descricao' in contabil_df.columns else ['id', 'data', 'valor_original']
        st.dataframe(contabil_df[display_cols].head(), width='stretch')

# Configurações de análise
st.sidebar.header("⚙️ Configurações de Análise")

with st.sidebar.expander("🔧 Tolerâncias de Matching"):
    tolerancia_data = st.slider("Tolerância de Data (dias)", 0, 7, 2)
    tolerancia_valor = st.number_input("Tolerância de Valor (R$)", 0.0, 50.0, 0.10, 0.01)
    similaridade_minima = st.slider("Similaridade Mínima de Texto (%)", 50, 95, 70)

with st.sidebar.expander("📋 Regras de Correspondência"):
    considerar_1n = st.checkbox("Identificar parcelamentos (1:N)", True)
    considerar_n1 = st.checkbox("Identificar consolidações (N:1)", True)
    match_exato_prioritario = st.checkbox("Priorizar matches exatos", True)

with st.sidebar.expander("🎯 Filtros de Análise"):
    valor_minimo = st.number_input("Valor mínimo (R$)", 0.0, 1000.0, 1.0, 1.0)
    analisar_apenas_mes_corrente = st.checkbox("Analisar apenas mês corrente", False)

# Botão para executar análise 
st.markdown("---")
st.header("Executar Análise")

if st.button("Executar Análise de Correspondências", type="primary", width='stretch'):
    
    # Barra de progresso
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    try:
        status_text.text("📊 Preparando dados para análise...")
        progress_bar.progress(10)
        
        # Aplicar filtro de valor mínimo se configurado
        if valor_minimo > 0:
            extrato_filtrado = extrato_df[extrato_df['valor_matching'] >= valor_minimo].copy()
            contabil_filtrado = contabil_df[contabil_df['valor_matching'] >= valor_minimo].copy()
            status_text.text(f"✅ Filtro aplicado: {len(extrato_filtrado)} transações x {len(contabil_filtrado)} lançamentos")
        else:
            extrato_filtrado = extrato_df.copy()
            contabil_filtrado = contabil_df.copy()
        
        # Aplicar filtro de mês corrente se configurado
        if analisar_apenas_mes_corrente:
            try:
                mes_atual = datetime.now().month
                extrato_filtrado = extrato_filtrado[extrato_filtrado['data'].dt.month == mes_atual]
                contabil_filtrado = contabil_filtrado[contabil_filtrado['data'].dt.month == mes_atual]
                status_text.text(f"📅 Filtro de mês aplicado: {len(extrato_filtrado)} transações x {len(contabil_filtrado)} lançamentos")
            except Exception as e:
                st.warning(f"⚠️ Não foi possível aplicar filtro de mês: {e}")
        
        progress_bar.progress(30)
        
        # Verificar se há dados após os filtros
        if len(extrato_filtrado) == 0 or len(contabil_filtrado) == 0:
            st.error("❌ Não há dados suficientes para análise após aplicar os filtros.")
            st.info("💡 Ajuste os filtros de valor mínimo ou mês corrente.")
            progress_bar.progress(100)
            st.stop()
        
        status_text.text(f"📈 Iniciando análise: {len(extrato_filtrado)} transações x {len(contabil_filtrado)} lançamentos")
        
        # Executar análise em camadas
        status_text.text("🎯 Camada 1/3: Identificação de Correspondências Exatas...")
        resultados_exato = analyzer.matching_exato(extrato_filtrado, contabil_filtrado)
        progress_bar.progress(50)
        
        status_text.text("🎯 Camada 2/3: Identificação de Correspondências por Similaridade...")
        resultados_heurístico = analyzer.matching_heuristico(
            extrato_filtrado, 
            contabil_filtrado, 
            resultados_exato['nao_matchados_extrato'],
            resultados_exato['nao_matchados_contabil'],
            tolerancia_data,
            tolerancia_valor,
            similaridade_minima
        )
        progress_bar.progress(75)
        
        status_text.text("🎯 Camada 3/3: Análise de Casos Complexos...")
        resultados_ia = analyzer.matching_ia(
            extrato_filtrado,
            contabil_filtrado,
            resultados_heurístico['nao_matchados_extrato'],
            resultados_heurístico['nao_matchados_contabil']
        )
        progress_bar.progress(90)
        
        # Consolidar resultados
        status_text.text("📊 Consolidando resultados...")
        resultados_finais = analyzer.consolidar_resultados(
            resultados_exato, resultados_heurístico, resultados_ia
        )
        
        # Salvar na sessão
        st.session_state['resultados_analise'] = resultados_finais
        st.session_state['extrato_filtrado'] = extrato_filtrado
        st.session_state['contabil_filtrado'] = contabil_filtrado
        
        progress_bar.progress(100)
        status_text.text("✅ Análise concluída!")
        
        # Mostrar resultados imediatamente
        st.balloons()
        st.success("🎉 Análise de correspondências concluída com sucesso!")
        
        # Forçar atualização da página para mostrar resultados
        st.rerun()
        
    except Exception as e:
        st.error(f"❌ Erro na análise: {str(e)}")
        st.info("💡 Dica: Verifique se os dados foram importados corretamente")
        import traceback
        st.code(traceback.format_exc())

# Mostrar resultados se disponíveis
if 'resultados_analise' in st.session_state:
    st.divider()
    st.header("📊 Resultados da Análise")
    
    resultados_finais = st.session_state['resultados_analise']
    extrato_filtrado = st.session_state.get('extrato_filtrado', extrato_df)
    contabil_filtrado = st.session_state.get('contabil_filtrado', contabil_df)
    
    # Métricas principais
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_extrato = len(extrato_filtrado)
        match_extrato = len(resultados_finais['matches'])
        st.metric("Transações Analisadas", total_extrato, f"{match_extrato} com correspondência")
    
    with col2:
        total_contabil = len(contabil_filtrado)
        match_contabil = sum(len(match['ids_contabil']) for match in resultados_finais['matches'])
        st.metric("Lançamentos Analisados", total_contabil, f"{match_contabil} com correspondência")
    
    with col3:
        taxa_cobertura = (match_extrato / total_extrato * 100) if total_extrato > 0 else 0
        st.metric("Cobertura de Análise", f"{taxa_cobertura:.1f}%")
    
    with col4:
        excecoes = len(resultados_finais['excecoes'])
        st.metric("Divergências Identificadas", excecoes)
    
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

    # Abas de detalhamento
    aba1, aba2, aba3, aba4 = st.tabs(["Correspondências Identificadas", "⚠️ Divergências", "Estatísticas", " Detalhes Técnicos"])
    
    with aba1:
        st.subheader("Correspondências Identificadas")
        
        if resultados_finais['matches']:
            # Tabela resumida de matches
            matches_data = []
            for i, match in enumerate(resultados_finais['matches']):
                matches_data.append({
                    'ID': i + 1,
                    'Tipo': match['tipo_match'],
                    'Camada': match['camada'],
                    'Transações Banco': len(match['ids_extrato']),
                    'Lançamentos': len(match['ids_contabil']),
                    'Valor Total': f"R$ {match['valor_total']:,.2f}",
                    'Confiança': f"{match['confianca']}%",
                    'Explicação': match['explicacao'][:60] + "..." if len(match['explicacao']) > 60 else match['explicacao']
                })
            
            matches_df = pd.DataFrame(matches_data)
            st.dataframe(matches_df, width='stretch')
            
            # Detalhes expandíveis
            with st.expander("🔍 Ver Detalhes Completos das Correspondências"):
                for i, match in enumerate(resultados_finais['matches']):
                    st.markdown(f"**Correspondência {i+1} - {match['tipo_match']}**")
                    st.write(f"**Camada:** {match['camada']} | **Confiança:** {match['confianca']}%")
                    st.write(f"**Justificativa:** {match['explicacao']}")
                    
                    # Mostrar transações envolvidas
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.write("**🏦 Transações Bancárias:**")
                        transacoes_extrato = extrato_filtrado[extrato_filtrado['id'].isin(match['ids_extrato'])]
                        for _, transacao in transacoes_extrato.iterrows():
                            descricao = transacao.get('descricao', 'N/A')
                            data_str = transacao['data'].strftime('%d/%m') if hasattr(transacao['data'], 'strftime') else str(transacao['data'])
                            valor_original = transacao.get('valor_original', transacao['valor'])
                            st.write(f"• R$ {valor_original:,.2f} | {data_str} | {descricao[:30]}...")
                    
                    with col_b:
                        st.write("**📊 Lançamentos Contábeis:**")
                        transacoes_contabil = contabil_filtrado[contabil_filtrado['id'].isin(match['ids_contabil'])]
                        for _, lancamento in transacoes_contabil.iterrows():
                            descricao = lancamento.get('descricao', 'N/A')
                            data_str = lancamento['data'].strftime('%d/%m') if hasattr(lancamento['data'], 'strftime') else str(lancamento['data'])
                            valor_original = lancamento.get('valor_original', lancamento['valor'])
                            st.write(f"• R$ {valor_original:,.2f} | {data_str} | {descricao[:30]}...")
                    
                    st.divider()
        else:
            st.info("ℹ️ Nenhuma correspondência identificada com os critérios atuais.")
    
    with aba2:
        st.subheader("Divergências e Itens Não Correspondentes")
        
        if resultados_finais['excecoes']:
            # Tabela detalhada de divergências
            st.markdown("**📋 Tabela de Divergências Detalhada**")
            
            divergencias_detalhadas = []
            for i, excecao in enumerate(resultados_finais['excecoes']):
                # Para cada item nas divergências, criar entrada detalhada
                if excecao['tipo'] == 'TRANSAÇÃO_SEM_CORRESPONDÊNCIA':
                    # Para transações sem correspondência, mostrar cada transação
                    transacoes_divergentes = extrato_filtrado[extrato_filtrado['id'].isin(excecao['ids_envolvidos'])]
                    for _, transacao in transacoes_divergentes.iterrows():
                        data_str = transacao['data'].strftime('%d/%m/%Y') if hasattr(transacao['data'], 'strftime') else str(transacao['data'])
                        valor_original = transacao.get('valor_original', transacao['valor'])
                        divergencias_detalhadas.append({
                            'Tipo_Divergência': excecao['tipo'],
                            'Severidade': excecao['severidade'],
                            'Data': data_str,
                            'Descrição': transacao.get('descricao', 'N/A'),
                            'Valor': f"R$ {valor_original:,.2f}",
                            'Origem': 'Extrato Bancário',
                            'Ação_Recomendada': excecao['acao_sugerida']
                        })
                
                elif excecao['tipo'] == 'LANÇAMENTO_SEM_CORRESPONDÊNCIA':
                    # Para lançamentos sem correspondência, mostrar cada lançamento
                    lancamentos_divergentes = contabil_filtrado[contabil_filtrado['id'].isin(excecao['ids_envolvidos'])]
                    for _, lancamento in lancamentos_divergentes.iterrows():
                        data_str = lancamento['data'].strftime('%d/%m/%Y') if hasattr(lancamento['data'], 'strftime') else str(lancamento['data'])
                        valor_original = lancamento.get('valor_original', lancamento['valor'])
                        divergencias_detalhadas.append({
                            'Tipo_Divergência': excecao['tipo'],
                            'Severidade': excecao['severidade'],
                            'Data': data_str,
                            'Descrição': lancamento.get('descricao', 'N/A'),
                            'Valor': f"R$ {valor_original:,.2f}",
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
                        'Origem': 'Múltiplas',
                        'Ação_Recomendada': excecao['acao_sugerida']
                    })
            
            # Exibir tabela detalhada
            if divergencias_detalhadas:
                df_divergencias_detalhadas = pd.DataFrame(divergencias_detalhadas)
                st.dataframe(
                    df_divergencias_detalhadas,
                    width='stretch',
                    hide_index=True
                )
                
                #  SALVAR NO SESSION STATE 
                st.session_state['divergencias_tabela'] = df_divergencias_detalhadas
                st.success(f"✅ Tabela de divergências salva ({len(df_divergencias_detalhadas)} itens)")
                
                # Botão para exportar divergências
                csv_divergencias = df_divergencias_detalhadas.to_csv(index=False)
                st.download_button(
                    label="📥 Exportar Divergências (CSV)",
                    data=csv_divergencias,
                    file_name=f"divergencias_detalhadas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
            
            # Relatório textual original (mantido para compatibilidade)
            st.markdown("**📝 Relatório de Divergências**")
            for i, excecao in enumerate(resultados_finais['excecoes']):
                st.write(f"**Divergência {i+1}: {excecao['tipo']} - {excecao['severidade']}**")
                st.write(f"**Descrição:** {excecao['descricao']}")
                st.write(f"**Recomendação:** {excecao['acao_sugerida']}")
                st.write(f"**Itens envolvidos:** {len(excecao['ids_envolvidos'])}")
                st.write("---")
        else:
            st.success("✅ Nenhuma divergência crítica identificada")
            # Limpar tabela de divergências se não houver
            if 'divergencias_tabela' in st.session_state:
                del st.session_state['divergencias_tabela']
    
    with aba3:
        st.subheader("Estatísticas Detalhadas")
        
        col_stat1, col_stat2 = st.columns(2)
        
        with col_stat1:
            st.markdown("**📈 Distribuição por Tipo de Correspondência**")
            tipos_data = {
                'Tipo': ['1:1', '1:N', 'N:1'],
                'Quantidade': [
                    len([m for m in resultados_finais['matches'] if m['tipo_match'] == '1:1']),
                    len([m for m in resultados_finais['matches'] if m['tipo_match'] == '1:N']),
                    len([m for m in resultados_finais['matches'] if m['tipo_match'] == 'N:1'])
                ]
            }
            st.bar_chart(pd.DataFrame(tipos_data).set_index('Tipo'))
        
        with col_stat2:
            st.markdown("**🔍 Efetividade por Camada de Análise**")
            camadas_data = {
                'Camada': ['Exata', 'Similaridade', 'Avançada'],
                'Correspondências': [
                    len([m for m in resultados_finais['matches'] if m['camada'] == 'exata']),
                    len([m for m in resultados_finais['matches'] if m['camada'] == 'heuristica']),
                    len([m for m in resultados_finais['matches'] if m['camada'] == 'ia'])
                ]
            }
            st.bar_chart(pd.DataFrame(camadas_data).set_index('Camada'))
    
    with aba4:
        st.subheader("Detalhes Técnicos da Análise")
        
        st.json({
            "configuracoes_aplicadas": {
                "tolerancia_data_dias": tolerancia_data,
                "tolerancia_valor_reais": tolerancia_valor,
                "similaridade_minima_percentual": similaridade_minima
            },
            "estatisticas_processamento": {
                "transacoes_analisadas": len(extrato_filtrado),
                "lancamentos_analisados": len(contabil_filtrado),
                "correspondencias_identificadas": len(resultados_finais['matches']),
                "divergencias_identificadas": len(resultados_finais['excecoes'])
            }
        })

    # Navegação e Ações 
    st.markdown("---")
    st.header(" Ações e Navegação")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if st.button("🔄 Nova Análise", width='stretch'):
            keys_to_clear = ['resultados_analise', 'extrato_filtrado', 'contabil_filtrado', 'divergencias_tabela']
            for key in keys_to_clear:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()

    with col2:
        if st.button("📥 Voltar para Importação", width='stretch'):
            st.switch_page("pages/importacao_dados.py")

    with col3:
        if st.button("🏠 Ir para Início", width='stretch'):
            st.switch_page("app.py")

    with col4:
        # Botão de relatório - sempre visível
        analise_concluida = 'resultados_analise' in st.session_state
        
        if analise_concluida:
            if st.button("📄 GERAR RELATÓRIO", type="primary", width='stretch'):
                st.switch_page("pages/gerar_relatorio.py")
        else:
            st.button("📄 Gerar Relatório", disabled=True, width='stretch')
            st.caption("Execute a análise primeiro")


