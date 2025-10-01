# pages/2_🛠️_analise_dados.py
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import tempfile
import modules.data_analyzer as analyzer
import modules.file_processor as processor

st.set_page_config(page_title="Análise de Dados", page_icon="🔍", layout="wide")

st.title("🔍 Análise para Conciliação Bancária")
st.markdown("Aplicando regras de matching para identificar correspondências")

# Verificar se os dados foram carregados
if not st.session_state.get('extrato_carregado') or not st.session_state.get('contabil_carregado'):
    st.error("❌ Dados não carregados. Volte para a página de importação.")
    if st.button("📥 Ir para Importação de Dados"):
        st.switch_page("pages/importacao_dados.py")
    st.stop()

# Barra de progresso
progress_bar = st.progress(0)
status_text = st.empty()

# Processar dados
status_text.text("📂 Lendo arquivos...")
progress_bar.progress(10)

try:
    # Processar extrato bancário
    extrato_df = processor.processar_extrato(st.session_state['caminho_extrato'])
    progress_bar.progress(30)
    
    # Processar lançamentos contábeis
    contabil_df = processor.processar_contabeis(st.session_state['caminho_contabil'])
    progress_bar.progress(50)
    
    status_text.text("🔄 Aplicando regras de conciliação...")
    
    # Configurações de tolerância
    st.sidebar.header("⚙️ Configurações de Matching")
    
    with st.sidebar.expander("🔧 Tolerâncias"):
        tolerancia_data = st.slider("Tolerância de Data (dias)", 0, 5, 2)
        tolerancia_valor = st.number_input("Tolerância de Valor (R$)", 0.0, 10.0, 0.02, 0.01)
        similaridade_minima = st.slider("Similaridade Mínima de Texto (%)", 70, 95, 80)
    
    with st.sidebar.expander("📋 Políticas"):
        policy_1n = st.checkbox("Permitir 1:N (Parcelamentos)", True)
        policy_n1 = st.checkbox("Permitir N:1 (Consolidações)", True)
        considerar_taxas = st.checkbox("Considerar Taxas/IOF no matching", True)
    
    # Executar análise em camadas
    status_text.text("🎯 Camada 1/3: Matching Exato...")
    resultados_exato = analyzer.matching_exato(extrato_df, contabil_df)
    progress_bar.progress(60)
    
    status_text.text("🎯 Camada 2/3: Matching Heurístico...")
    resultados_heurístico = analyzer.matching_heuristico(
        extrato_df, 
        contabil_df, 
        resultados_exato['nao_matchados_extrato'],
        resultados_exato['nao_matchados_contabil'],
        tolerancia_data,
        tolerancia_valor,
        similaridade_minima
    )
    progress_bar.progress(80)
    
    status_text.text("🎯 Camada 3/3: Análise com IA...")
    resultados_ia = analyzer.matching_ia(
        extrato_df,
        contabil_df,
        resultados_heurístico['nao_matchados_extrato'],
        resultados_heurístico['nao_matchados_contabil']
    )
    progress_bar.progress(95)
    
    # Consolidar resultados
    status_text.text("📊 Consolidando resultados...")
    resultados_finais = analyzer.consolidar_resultados(
        resultados_exato, resultados_heurístico, resultados_ia
    )
    
    # Salvar na sessão
    st.session_state['resultados_analise'] = resultados_finais
    st.session_state['extrato_df'] = extrato_df
    st.session_state['contabil_df'] = contabil_df
    
    progress_bar.progress(100)
    status_text.text("✅ Análise concluída!")
    
except Exception as e:
    st.error(f"❌ Erro na análise: {str(e)}")
    st.stop()

# Mostrar resultados
st.divider()
st.header("📊 Resultados da Análise")

# Métricas principais
col1, col2, col3, col4 = st.columns(4)

with col1:
    total_extrato = len(extrato_df)
    match_extrato = len(resultados_finais['matches'])
    st.metric("Transações Bancárias", total_extrato, f"{match_extrato} matched")

with col2:
    total_contabil = len(contabil_df)
    match_contabil = sum(len(match['ids_contabil']) for match in resultados_finais['matches'])
    st.metric("Lançamentos Contábeis", total_contabil, f"{match_contabil} matched")

with col3:
    taxa_sucesso = (match_extrato / total_extrato * 100) if total_extrato > 0 else 0
    st.metric("Taxa de Matching", f"{taxa_sucesso:.1f}%")

with col4:
    excecoes = len(resultados_finais['excecoes'])
    st.metric("Exceções Identificadas", excecoes)

# Abas de detalhamento
aba1, aba2, aba3, aba4 = st.tabs(["🎯 Matches Propostos", "⚠️ Exceções", "📈 Estatísticas", "🔍 Detalhes Técnicos"])

with aba1:
    st.subheader("Matches Identificados")
    
    if resultados_finais['matches']:
        # Tabela resumida de matches
        matches_data = []
        for match in resultados_finais['matches']:
            matches_data.append({
                'Tipo': match['tipo_match'],
                'Camada': match['camada'],
                'Transações Banco': len(match['ids_extrato']),
                'Lançamentos Contábeis': len(match['ids_contabil']),
                'Valor Total': match['valor_total'],
                'Confiança': f"{match['confianca']}%",
                'Explicação': match['explicacao'][:50] + "..." if len(match['explicacao']) > 50 else match['explicacao']
            })
        
        matches_df = pd.DataFrame(matches_data)
        st.dataframe(matches_df, use_container_width=True)
        
        # Detalhes expandíveis
        with st.expander("🔍 Ver Detalhes Completos dos Matches"):
            for i, match in enumerate(resultados_finais['matches']):
                st.markdown(f"**Match {i+1} - {match['tipo_match']}**")
                st.write(f"**Camada:** {match['camada']} | **Confiança:** {match['confianca']}%")
                st.write(f"**Explicação:** {match['explicacao']}")
                
                # Mostrar transações envolvidas
                col_a, col_b = st.columns(2)
                with col_a:
                    st.write("**Transações Bancárias:**")
                    transacoes_extrato = extrato_df[extrato_df['id'].isin(match['ids_extrato'])]
                    st.dataframe(transacoes_extrato[['data', 'valor', 'descricao']])
                
                with col_b:
                    st.write("**Lançamentos Contábeis:**")
                    transacoes_contabil = contabil_df[contabil_df['id'].isin(match['ids_contabil'])]
                    st.dataframe(transacoes_contabil[['data', 'valor', 'descricao']])
                
                st.divider()
    else:
        st.warning("Nenhum match identificado")

with aba2:
    st.subheader("Exceções e Divergências")
    
    if resultados_finais['excecoes']:
        excecoes_data = []
        for excecao in resultados_finais['excecoes']:
            excecoes_data.append({
                'Tipo': excecao['tipo'],
                'Severidade': excecao['severidade'],
                'Descrição': excecao['descricao'],
                'Transações Envolvidas': len(excecao['ids_envolvidos']),
                'Ação Sugerida': excecao['acao_sugerida']
            })
        
        excecoes_df = pd.DataFrame(excecoes_data)
        st.dataframe(excecoes_df, use_container_width=True)
        
        # Detalhes das exceções
        with st.expander("📋 Detalhes das Exceções"):
            for excecao in resultados_finais['excecoes']:
                st.write(f"**{excecao['tipo']}** - {excecao['severidade']}")
                st.write(f"**Descrição:** {excecao['descricao']}")
                st.write(f"**Ação Sugerida:** {excecao['acao_sugerida']}")
                st.divider()
    else:
        st.success("✅ Nenhuma exceção crítica identificada")

with aba3:
    st.subheader("Estatísticas Detalhadas")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**📈 Distribuição por Camada**")
        camadas_data = {
            'Camada': ['Exata', 'Heurística', 'IA'],
            'Matches': [
                len([m for m in resultados_finais['matches'] if m['camada'] == 'exata']),
                len([m for m in resultados_finais['matches'] if m['camada'] == 'heuristica']),
                len([m for m in resultados_finais['matches'] if m['camada'] == 'ia'])
            ]
        }
        st.bar_chart(pd.DataFrame(camadas_data).set_index('Camada'))
    
    with col2:
        st.markdown("**🔧 Tipos de Matching**")
        tipos_data = {
            'Tipo': ['1:1', '1:N', 'N:1'],
            'Quantidade': [
                len([m for m in resultados_finais['matches'] if m['tipo_match'] == '1:1']),
                len([m for m in resultados_finais['matches'] if m['tipo_match'] == '1:N']),
                len([m for m in resultados_finais['matches'] if m['tipo_match'] == 'N:1'])
            ]
        }
        st.bar_chart(pd.DataFrame(tipos_data).set_index('Tipo'))

with aba4:
    st.subheader("Detalhes Técnicos da Análise")
    
    st.json({
        "configuracoes_aplicadas": {
            "tolerancia_data_dias": tolerancia_data,
            "tolerancia_valor_reais": tolerancia_valor,
            "similaridade_minima_percentual": similaridade_minima,
            "politica_1n_habilitada": policy_1n,
            "politica_n1_habilitada": policy_n1
        },
        "estatisticas_processamento": {
            "transacoes_processadas_extrato": total_extrato,
            "lancamentos_processados_contabil": total_contabil,
            "tempo_analise_estimado": "15-30 segundos"
        }
    })

# Navegação para próxima etapa
st.divider()
st.subheader("Próxima Etapa")

if st.button("📋 Revisar e Gerar Relatório", type="primary", use_container_width=True):
    st.switch_page("pages/revisao_resultados.py")

