# pages/2_🔍_analise_dados.py
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import tempfile
import modules.data_analyzer as analyzer
from difflib import SequenceMatcher
from modules.auth_middleware import require_auth
import plotly.express as px
import plotly.graph_objects as go
from modules.interactive_dashboard import get_dashboard


@require_auth

def main():
    st.set_page_config(page_title="Análise de Correspondências", page_icon="🔍", layout="wide")

    # --- Menu Customizado ---
    with st.sidebar:
        st.markdown("### Navegação Principal") 
        st.page_link("app.py", label="Início (Home)", icon="🏠")
        
        st.page_link("pages/importacao_dados.py", label="📥 Importação de Dados", icon=None)
        st.page_link("pages/analise_dados.py", label="📊 Análise de Divergências", icon=None)
        st.page_link("pages/gerar_relatorio.py", label="📝 Relatório Final", icon=None)
    # --- Fim do Menu Customizado ---

    # --- FUNÇÕES PARA TABELAS MELHORADAS ---
    def gerar_tabelas_divergencias_melhoradas(resultados_analise, extrato_df, contabil_df):
        """
        Gera tabelas de divergências mais explicativas e organizadas
        """
        # Identificar transações não matchadas
        extrato_match_ids = set()
        contabil_match_ids = set()
        
        for match in resultados_analise['matches']:
            extrato_match_ids.update(match['ids_extrato'])
            contabil_match_ids.update(match['ids_contabil'])
        
        # Tabela 1: Presente no bancário mas não no contábil
        extrato_nao_match = extrato_df[~extrato_df['id'].isin(extrato_match_ids)]
        tabela_bancario_sem_contabil = _criar_tabela_bancario_sem_contabil(extrato_nao_match)
        
        # Tabela 2: Presente no contábil mas não no bancário
        contabil_nao_match = contabil_df[~contabil_df['id'].isin(contabil_match_ids)]
        tabela_contabil_sem_bancario = _criar_tabela_contabil_sem_bancario(contabil_nao_match)
        
        # Tabela 3: Possíveis correspondências por similaridade
        tabela_similaridades = _criar_tabela_similaridades(extrato_nao_match, contabil_nao_match)
        
        return {
            'bancario_sem_contabil': tabela_bancario_sem_contabil,
            'contabil_sem_bancario': tabela_contabil_sem_bancario,
            'possiveis_similaridades': tabela_similaridades
        }

    def _criar_tabela_bancario_sem_contabil(extrato_nao_match):
        """Cria tabela para valores presentes no bancário mas não no contábil - TERMINOLOGIA MELHORADA"""
        tabela = []
        
        for _, transacao in extrato_nao_match.iterrows():
            data_str = transacao['data'].strftime('%d/%m/%Y') if hasattr(transacao['data'], 'strftime') else str(transacao['data'])
            
            tabela.append({
                'Tipo_Divergência': '🔴 Mov. Bancária sem Lançamento',
                'Data': data_str,
                'Valor_Bancário': f"R$ {transacao['valor']:,.2f}",
                'Descrição_Bancário': transacao.get('descricao', 'N/A'),
                'Origem': '🏦 Extrato Bancário',
                'Status': 'Não conciliado',
                'Recomendação': 'Verificar se é despesa não lançada, receita não identificada ou lançamento em período diferente',
                'Ação_Sugerida': 'Incluir no sistema contábil ou identificar natureza da transação'
            })
        
        return pd.DataFrame(tabela)

    def _criar_tabela_contabil_sem_bancario(contabil_nao_match):
        """Cria tabela para valores presentes no contábil mas não no bancário - TERMINOLOGIA MELHORADA"""
        tabela = []
        
        for _, lancamento in contabil_nao_match.iterrows():
            data_str = lancamento['data'].strftime('%d/%m/%Y') if hasattr(lancamento['data'], 'strftime') else str(lancamento['data'])
            
            tabela.append({
                'Tipo_Divergência': '🔴 Lançamento sem Mov. Bancária',
                'Data': data_str,
                'Valor_Contábil': f"R$ {lancamento['valor']:,.2f}",
                'Descrição_Contábil': lancamento.get('descricao', 'N/A'),
                'Origem': '📊 Sistema Contábil',
                'Status': 'Não conciliado',
                'Recomendação': 'Verificar se é provisionamento, lançamento futuro, ajuste contábil ou erro de lançamento',
                'Ação_Sugerida': 'Aguardar compensação, corrigir lançamento ou verificar periodicidade'
            })
        
        return pd.DataFrame(tabela)

    def _criar_tabela_similaridades(extrato_nao_match, contabil_nao_match):
        """Identifica possíveis correspondências por similaridade - TERMINOLOGIA MELHORADA"""
        tabela = []
        
        for _, extrato_row in extrato_nao_match.iterrows():
            valor_extrato = abs(extrato_row['valor'])
            data_extrato = extrato_row['data']
            
            for _, contabil_row in contabil_nao_match.iterrows():
                valor_contabil = abs(contabil_row['valor'])
                data_contabil = contabil_row['data']
                
                diff_valor_percent = abs(valor_extrato - valor_contabil) / valor_extrato * 100 if valor_extrato > 0 else 100
                diff_dias = abs((data_extrato - data_contabil).days) if hasattr(data_extrato, 'strftime') and hasattr(data_contabil, 'strftime') else 30
                
                if diff_valor_percent <= 10 and diff_dias <= 5:
                    similaridade = _calcular_similaridade_texto(
                        extrato_row.get('descricao', ''),
                        contabil_row.get('descricao', '')
                    )
                    
                    if similaridade >= 40:
                        confianca_ajuste = (100 - diff_valor_percent) * (100 - diff_dias * 2) * similaridade / 10000
                        
                        tabela.append({
                            'Tipo_Analise': '🟡 Possível Correspondência',
                            'Similaridade_Detectada': f"{similaridade:.1f}%",
                            'Data_Bancário': data_extrato.strftime('%d/%m/%Y') if hasattr(data_extrato, 'strftime') else str(data_extrato),
                            'Data_Contábil': data_contabil.strftime('%d/%m/%Y') if hasattr(data_contabil, 'strftime') else str(data_contabil),
                            'Valor_Bancário': f"R$ {extrato_row['valor']:,.2f}",
                            'Valor_Contábil': f"R$ {contabil_row['valor']:,.2f}",
                            'Descrição_Bancário': extrato_row.get('descricao', '')[:50] + "..." if len(extrato_row.get('descricao', '')) > 50 else extrato_row.get('descricao', ''),
                            'Descrição_Contábil': contabil_row.get('descricao', '')[:50] + "..." if len(contabil_row.get('descricao', '')) > 50 else contabil_row.get('descricao', ''),
                            'Diferença_Valor': f"R$ {abs(extrato_row['valor'] - contabil_row['valor']):,.2f}",
                            'Diferença_Dias': diff_dias,
                            'Confiança_Ajuste': f"{confianca_ajuste:.1f}%",
                            'Recomendação': 'Analisar manualmente - possível correspondência que precisa de validação'
                        })
        
        return pd.DataFrame(tabela)

    def _calcular_similaridade_texto(texto1, texto2):
        """Calcula similaridade entre textos"""
        if not texto1 or not texto2:
            return 0.0
        return SequenceMatcher(None, texto1.lower(), texto2.lower()).ratio() * 100

    # --- FIM DAS FUNÇÕES PARA TABELAS MELHORADAS ---

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
        
        1. **Correspondências Exatas**
            - Mesmo valor + mesma data 
            - Identificadores únicos (PIX, NSU, etc.) 
        
        2. **Correspondências por Similaridade** 
            - Valores próximos + datas próximas 
            - Descrições semelhantes 
        
        3. **Análise de Padrões Complexos** 
            - Parcelamentos (1 transação → N lançamentos) 
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
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            status_text.text("Preparando dados...")
            progress_bar.progress(20)
            
            # Aplicar filtros (código existente)
            if valor_minimo > 0:
                extrato_filtrado = extrato_df[extrato_df['valor_matching'] >= valor_minimo].copy()
                contabil_filtrado = contabil_df[contabil_df['valor_matching'] >= valor_minimo].copy()
            
            progress_bar.progress(40)
            status_text.text("Executando análise...")
            
            # Executar análise em camadas (código existente)
            resultados_exato = analyzer.matching_exato(extrato_filtrado, contabil_filtrado)
            progress_bar.progress(60)
            
            resultados_heurístico = analyzer.matching_heuristico(
                extrato_filtrado, contabil_filtrado, 
                resultados_exato['nao_matchados_extrato'],
                resultados_exato['nao_matchados_contabil'],
                tolerancia_data, tolerancia_valor, similaridade_minima
            )
            progress_bar.progress(80)
            
            resultados_ia = analyzer.matching_ia(
                extrato_filtrado, contabil_filtrado,
                resultados_heurístico['nao_matchados_extrato'],
                resultados_heurístico['nao_matchados_contabil']
            )
            
            progress_bar.progress(100)
            status_text.text("✅ Análise concluída!")
            
            # Consolidar resultados
            resultados_finais = analyzer.consolidar_resultados(
                resultados_exato, resultados_heurístico, resultados_ia
            )
            
            # Salvar na sessão
            st.session_state['resultados_analise'] = resultados_finais
            st.session_state['extrato_filtrado'] = extrato_filtrado
            st.session_state['contabil_filtrado'] = contabil_filtrado
            
            st.success("🎉 Análise de correspondências concluída!")
            st.rerun()
            
        except Exception as e:
            st.error(f"Erro na análise: {str(e)}")
            progress_bar.progress(0)
            
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
        aba1, aba2, aba3, aba4, aba5 = st.tabs([
            "🔍 Correspondências", 
            "⚠️ Divergências", 
            "📊 Estatísticas", 
            "📈 Dashboard Interativo",
            "🔧 Detalhes Técnicos"
        ])

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
            st.subheader("🔍 Análise Detalhada das Divergências")
            
            if resultados_finais.get('excecoes'):
                # Gerar tabelas melhoradas
                tabelas_divergencias = gerar_tabelas_divergencias_melhoradas(
                    resultados_finais, extrato_filtrado, contabil_filtrado
                )
                
                # Abas para cada tipo de divergência
                tab1, tab2, tab3 = st.tabs([
                    "🏦 Bancário sem Contábil", 
                    "📊 Contábil sem Bancário", 
                    "🔍 Similaridades"
                ])
                
                with tab1:
                    st.markdown("**Valores Presentes no Extrato mas Não na Contabilidade**")
                    if not tabelas_divergencias['bancario_sem_contabil'].empty:
                        st.dataframe(tabelas_divergencias['bancario_sem_contabil'], width='stretch')
                        
                        # Botão de exportação
                        csv_bancario = tabelas_divergencias['bancario_sem_contabil'].to_csv(index=False)
                        st.download_button(
                            label="📥 Exportar Divergências Bancárias",
                            data=csv_bancario,
                            file_name="divergencias_bancario_sem_contabil.csv",
                            mime="text/csv"
                        )
                    else:
                        st.success("✅ Nenhuma divergência")
                
                with tab2:
                    st.markdown("**Lançamentos Contábeis sem Movimentação Bancária**")
                    if not tabelas_divergencias['contabil_sem_bancario'].empty:
                        st.dataframe(tabelas_divergencias['contabil_sem_bancario'], width='stretch')
                        
                        csv_contabil = tabelas_divergencias['contabil_sem_bancario'].to_csv(index=False)
                        st.download_button(
                            label="📥 Exportar Divergências Contábeis",
                            data=csv_contabil,
                            file_name="divergencias_contabil_sem_bancario.csv",
                            mime="text/csv"
                        )
                    else:
                        st.success("✅ Nenhuma divergência")
                
                with tab3:
                    st.markdown("**Possíveis Correspondências por Similaridade**")
                    if not tabelas_divergencias['possiveis_similaridades'].empty:
                        st.dataframe(tabelas_divergencias['possiveis_similaridades'], width='stretch')
                        
                        csv_similaridades = tabelas_divergencias['possiveis_similaridades'].to_csv(index=False)
                        st.download_button(
                            label="📥 Exportar Similaridades",
                            data=csv_similaridades,
                            file_name="possiveis_correspondencias_similaridade.csv",
                            mime="text/csv"
                        )
                    else:
                        st.info("ℹ️ Nenhuma similaridade identificada")
            
            else:
                st.success("✅ Nenhuma divergência crítica identificada")
        
        
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
            
            # NOVA SEÇÃO: ESTATÍSTICAS DA IA - COM VERIFICAÇÃO DE EXISTÊNCIA
            if 'estatisticas_ia' in resultados_finais and resultados_finais['estatisticas_ia']:
                st.markdown("**🤖 Estatísticas da IA Avançada**")
                stats_ia = resultados_finais['estatisticas_ia']
                
                # Verificar se as chaves existem antes de acessar
                matches_semanticos = stats_ia.get('matches_semanticos', 0)
                matches_temporais = stats_ia.get('matches_temporais', 0)
                matches_agrupados = stats_ia.get('matches_agrupados', 0)
                matches_entidades = stats_ia.get('matches_entidades', 0)
                
                # Só mostrar se houver dados da IA
                if any([matches_semanticos, matches_temporais, matches_agrupados, matches_entidades]):
                    col_ia1, col_ia2, col_ia3, col_ia4 = st.columns(4)
                    
                    with col_ia1:
                        st.metric("Matches Semânticos", matches_semanticos)
                    
                    with col_ia2:
                        st.metric("Matches Temporais", matches_temporais)
                    
                    with col_ia3:
                        st.metric("Matches Agrupados", matches_agrupados)
                    
                    with col_ia4:
                        st.metric("Matches por Entidades", matches_entidades)
        
        with aba4:
            st.header("📈 Dashboard Interativo de Análise")
            
            if 'resultados_analise' in st.session_state:
                dashboard = get_dashboard()
                
                # Controles do dashboard
                col_controls1, col_controls2, col_controls3 = st.columns(3)
                
                with col_controls1:
                    show_overview = st.checkbox("Visão Geral", value=True)
                with col_controls2:
                    show_timeline = st.checkbox("Análise Temporal", value=True)
                with col_controls3:
                    show_distribution = st.checkbox("Distribuição de Valores", value=True)
                
                # Visão Geral
                if show_overview:
                    st.subheader("📊 Visão Geral da Conciliação")
                    overview_fig = dashboard.create_reconciliation_overview(
                        st.session_state.resultados_analise,
                        st.session_state.extrato_filtrado,
                        st.session_state.contabil_filtrado
                    )
                    st.plotly_chart(overview_fig, use_container_width=True)
                
                # Análise Temporal
                if show_timeline:
                    st.subheader("📈 Análise Temporal")
                    timeline_fig = dashboard.create_timeline_analysis(
                        st.session_state.extrato_filtrado,
                        st.session_state.contabil_filtrado
                    )
                    st.plotly_chart(timeline_fig, use_container_width=True)
                
                # Distribuição de Valores
                if show_distribution:
                    st.subheader("📦 Distribuição de Valores")
                    distribution_fig = dashboard.create_value_distribution(
                        st.session_state.extrato_filtrado,
                        st.session_state.contabil_filtrado
                    )
                    st.plotly_chart(distribution_fig, use_container_width=True)
                
                # Análise de Confiança (apenas se houver matches)
                if st.session_state.resultados_analise.get('matches'):
                    st.subheader("🎯 Análise de Confiança")
                    confidence_fig = dashboard.create_confidence_analysis(st.session_state.resultados_analise)
                    st.plotly_chart(confidence_fig, use_container_width=True)
                
                # Métricas Comparativas
                st.subheader("📋 Métricas Comparativas")
                metrics_fig = dashboard.create_comparison_metrics(
                    st.session_state.extrato_filtrado,
                    st.session_state.contabil_filtrado
                )
                st.plotly_chart(metrics_fig, use_container_width=True)
                # Estatísticas Rápidas
                col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
                
                with col_stat1:
                    total_extrato = len(st.session_state.extrato_filtrado)
                    st.metric("Transações Bancárias", total_extrato)
                
                with col_stat2:
                    total_contabil = len(st.session_state.contabil_filtrado)
                    st.metric("Lançamentos Contábeis", total_contabil)
                
                with col_stat3:
                    total_matches = len(st.session_state.resultados_analise.get('matches', []))
                    st.metric("Correspondências", total_matches)
                
                with col_stat4:
                    taxa_conciliação = (total_matches / total_extrato * 100) if total_extrato > 0 else 0
                    st.metric("Taxa de Conciliação", f"{taxa_conciliação:.1f}%")
            
            else:
                st.info("💡 Execute a análise de correspondências primeiro para visualizar o dashboard.")
                if st.button("🔍 Executar Análise", key="btn_analise_dashboard"):
                    st.switch_page("pages/analise_dados.py")
        
        
        
        
        with aba5:
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
                keys_to_clear = ['resultados_analise', 'extrato_filtrado', 'contabil_filtrado', 'tabelas_divergencias_melhoradas']
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


if __name__ == "__main__":
    main()