# pages/4_📄_gerar_relatorio.py
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import tempfile
import os
import base64
import modules.report_generator as report_gen

st.set_page_config(page_title="Gerar Relatório", page_icon="📄", layout="wide")

st.title("📄 Gerar Relatório de Conciliação")
st.markdown("Gere o relatório PDF final com todas as conciliações aprovadas")

# Verificar se há dados para relatório
if 'matches_aprovados' not in st.session_state or len(st.session_state['matches_aprovados']) == 0:
    st.error("❌ Nenhuma conciliação aprovada para gerar relatório.")
    st.info("Volte para a página de revisão para aprovar conciliações.")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📋 Voltar para Revisão"):
            st.switch_page("pages/revisao_resultados.py")
    with col2:
        if st.button("🔍 Fazer Nova Análise"):
            st.switch_page("pages/analise_dados.py")
    st.stop()

# Dados para o relatório
matches_aprovados = st.session_state['matches_aprovados']
matches_rejeitados = st.session_state.get('matches_rejeitados', [])
excecoes = st.session_state.get('resultados_analise', {}).get('excecoes', [])
extrato_df = st.session_state['extrato_df']
contabil_df = st.session_state['contabil_df']

# Configurações do relatório
st.sidebar.header("⚙️ Configurações do Relatório")

empresa_nome = st.sidebar.text_input("Nome da Empresa", "Empresa Exemplo Ltda")
contador_nome = st.sidebar.text_input("Nome do Contador", "Contador Responsavel")
periodo_relatorio = st.sidebar.text_input("Período do Relatório", 
                                         f"{datetime.now().strftime('%B/%Y')}")

incluir_rejeitados = st.sidebar.checkbox("Incluir matches rejeitados no apêndice", True)
incluir_excecoes = st.sidebar.checkbox("Incluir análise de exceções", True)

# Pré-visualização do relatório
st.header("📋 Pré-visualização do Relatório")

# Métricas do relatório
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Conciliações Aprovadas", len(matches_aprovados))

with col2:
    valor_total = sum(match['valor_total'] for match in matches_aprovados)
    st.metric("Valor Total Conciliado", f"R$ {valor_total:,.2f}")

with col3:
    total_analisado = len(matches_aprovados) + len(matches_rejeitados)
    taxa_aprovacao = (len(matches_aprovados) / total_analisado * 100) if total_analisado > 0 else 0
    st.metric("Taxa de Aprovação", f"{taxa_aprovacao:.1f}%")

with col4:
    st.metric("Exceções Identificadas", len(excecoes))

# Sumário executivo
st.subheader("📊 Sumário Executivo")

aba_sumario, aba_detalhes, aba_excecoes = st.tabs(["📈 Visão Geral", "🔍 Detalhes", "⚠️ Exceções"])

with aba_sumario:
    col_a, col_b = st.columns(2)
    
    with col_a:
        st.markdown("**Distribuição por Camada de Matching**")
        camadas_data = {
            'Camada': ['Exata', 'Heurística', 'IA'],
            'Quantidade': [
                len([m for m in matches_aprovados if m['camada'] == 'exata']),
                len([m for m in matches_aprovados if m['camada'] == 'heuristica']),
                len([m for m in matches_aprovados if m['camada'] == 'ia'])
            ]
        }
        st.bar_chart(pd.DataFrame(camadas_data).set_index('Camada'))
    
    with col_b:
        st.markdown("**Tipos de Conciliação**")
        tipos_data = {
            'Tipo': ['1:1', '1:N', 'N:1'],
            'Quantidade': [
                len([m for m in matches_aprovados if m['tipo_match'] == '1:1']),
                len([m for m in matches_aprovados if m['tipo_match'] == '1:N']),
                len([m for m in matches_aprovados if m['tipo_match'] == 'N:1'])
            ]
        }
        st.bar_chart(pd.DataFrame(tipos_data).set_index('Tipo'))

with aba_detalhes:
    # Tabela de conciliações aprovadas
    st.markdown("**Conciliações Aprovadas**")
    
    dados_tabela = []
    for i, match in enumerate(matches_aprovados):
        transacoes_extrato = extrato_df[extrato_df['id'].isin(match['ids_extrato'])]
        transacoes_contabil = contabil_df[contabil_df['id'].isin(match['ids_contabil'])]
        
        dados_tabela.append({
            'ID': i + 1,
            'Tipo': match['tipo_match'],
            'Camada': match['camada'],
            'Confiança': f"{match['confianca']}%",
            'Valor Total': f"R$ {match['valor_total']:,.2f}",
            'Transações Banco': len(match['ids_extrato']),
            'Lançamentos': len(match['ids_contabil']),
            'Explicação': match['explicacao'][:80] + "..." if len(match['explicacao']) > 80 else match['explicacao']
        })
    
    if dados_tabela:
        st.dataframe(pd.DataFrame(dados_tabela), use_container_width=True)
    else:
        st.info("Nenhuma conciliação aprovada para mostrar.")

with aba_excecoes:
    if excecoes:
        st.markdown("**Exceções e Divergências**")
        
        for excecao in excecoes:
            with st.expander(f"{excecao['tipo']} - {excecao['severidade']}"):
                st.write(f"**Descrição:** {excecao['descricao']}")
                st.write(f"**Ação Sugerida:** {excecao['acao_sugerida']}")
                st.write(f"**Transações Envolvidas:** {len(excecao['ids_envolvidos'])}")
    else:
        st.success("✅ Nenhuma exceção crítica identificada.")

# Geração do PDF
st.divider()
st.header("🎯 Gerar Relatório PDF")

col_gerar1, col_gerar2 = st.columns([2, 1])

with col_gerar1:
    st.subheader("Configurações Finais")
    
    observacoes = st.text_area(
        "Observações Adicionais para o Relatório:",
        placeholder="Ex: Considerações especiais, ressalvas, recomendações...",
        height=100
    )
    
    formato_relatorio = st.selectbox(
        "Formato do Relatório",
        ["Completo", "Resumido", "Executivo"],
        index=0  # Padrão: Completo
    )
    
    # Descrição dos formatos
    with st.expander("ℹ️ Sobre os Formatos de Relatório"):
        st.markdown("""
        **📄 COMPLETO:** 
        - Todas as conciliações detalhadas
        - Análise completa de exceções
        - Matches rejeitados
        - Recomendações detalhadas
        - 4-5 páginas
        
        **📋 RESUMIDO:**
        - Apenas informações essenciais
        - Tabela resumida de conciliações
        - Recomendações básicas
        - 2-3 páginas
        
        **🎯 EXECUTIVO:**
        - Foco em métricas e KPIs
        - Visão para tomada de decisão
        - Principais conciliações por valor
        - Recomendações estratégicas
        - 2 páginas
        """)

with col_gerar2:
    st.subheader("Gerar PDF")
    
    if st.button("📄 Gerar Relatório PDF", type="primary", use_container_width=True):
        with st.spinner("Gerando relatório PDF..."):
            try:
                # Mostrar qual formato está sendo gerado
                st.info(f"🔄 Gerando relatório no formato: **{formato_relatorio}**")
                
                # Preparar dados com base nas configurações
                matches_rejeitados_final = matches_rejeitados if incluir_rejeitados else []
                excecoes_final = excecoes if incluir_excecoes else []
                
                # Chamar a função correta baseada no formato selecionado
                if formato_relatorio == "Resumido":
                    pdf_path = report_gen.gerar_relatorio_resumido(
                        matches_aprovados=matches_aprovados,
                        matches_rejeitados=matches_rejeitados_final,
                        excecoes=excecoes_final,
                        extrato_df=extrato_df,
                        contabil_df=contabil_df,
                        empresa_nome=empresa_nome,
                        contador_nome=contador_nome,
                        periodo=periodo_relatorio,
                        observacoes=observacoes
                    )
                    success_message = "✅ Relatório **RESUMIDO** gerado com sucesso!"
                    
                elif formato_relatorio == "Executivo":
                    pdf_path = report_gen.gerar_relatorio_executivo(
                        matches_aprovados=matches_aprovados,
                        matches_rejeitados=matches_rejeitados_final,
                        excecoes=excecoes_final,
                        extrato_df=extrato_df,
                        contabil_df=contabil_df,
                        empresa_nome=empresa_nome,
                        contador_nome=contador_nome,
                        periodo=periodo_relatorio,
                        observacoes=observacoes
                    )
                    success_message = "✅ Relatório **EXECUTIVO** gerado com sucesso!"
                    
                else:  # Completo (padrão)
                    pdf_path = report_gen.gerar_relatorio_completo(
                        matches_aprovados=matches_aprovados,
                        matches_rejeitados=matches_rejeitados_final,
                        excecoes=excecoes_final,
                        extrato_df=extrato_df,
                        contabil_df=contabil_df,
                        empresa_nome=empresa_nome,
                        contador_nome=contador_nome,
                        periodo=periodo_relatorio,
                        observacoes=observacoes,
                        formato="completo"
                    )
                    success_message = "✅ Relatório **COMPLETO** gerado com sucesso!"
                
                # Ler o PDF gerado
                with open(pdf_path, "rb") as pdf_file:
                    pdf_bytes = pdf_file.read()
                
                # Criar download link
                b64_pdf = base64.b64encode(pdf_bytes).decode()
                href = f'<a href="data:application/pdf;base64,{b64_pdf}" download="relatorio_conciliacao_{formato_relatorio.lower()}_{datetime.now().strftime("%Y%m%d_%H%M")}.pdf" style="background-color: #4CAF50; color: white; padding: 14px 20px; text-align: center; text-decoration: none; display: inline-block; border-radius: 5px; font-size: 16px;">📥 Baixar Relatório {formato_relatorio.upper()}</a>'
                
                st.markdown(href, unsafe_allow_html=True)
                st.success(success_message)
                
                # Pré-visualização embutida
                st.subheader("👁️ Pré-visualização do PDF")
                base64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
                pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="600" type="application/pdf"></iframe>'
                st.markdown(pdf_display, unsafe_allow_html=True)
                
            except Exception as e:
                st.error(f"❌ Erro ao gerar relatório: {str(e)}")
                st.info("💡 **Dica:** Verifique se há caracteres especiais problemáticos nos dados.")

# Navegação e ações finais
st.divider()
st.header("🚪 Próximas Ações")

col_acao1, col_acao2, col_acao3 = st.columns(3)

with col_acao1:
    if st.button("📋 Revisar Novamente", use_container_width=True):
        st.switch_page("pages/revisao_resultados.py")

with col_acao2:
    if st.button("🔄 Nova Análise", use_container_width=True):
        # Limpar session state para nova análise
        keys_to_clear = ['matches_aprovados', 'matches_rejeitados', 'matches_pendentes', 
                        'resultados_analise']
        for key in keys_to_clear:
            if key in st.session_state:
                del st.session_state[key]
        st.switch_page("pages/importacao_dados.py")

with col_acao3:
    if st.button("🏠 Início", use_container_width=True):
        st.switch_page("app.py")

# Resumo do processo
with st.expander("📋 Resumo do Processo Concluído"):
    st.markdown(f"""
    **Processo de Conciliação Finalizado**
    
    - ✅ **Arquivos Importados:** {len(extrato_df)} transações bancárias + {len(contabil_df)} lançamentos
    - ✅ **Análise Realizada:** {len(matches_aprovados)} conciliações aprovadas
    - ✅ **Revisão Concluída:** {len(matches_rejeitados)} conciliações rejeitadas
    - ✅ **Relatório Gerado:** PDF profissional disponível para download
    
    **Próximos passos recomendados:**
    1. Salve o relatório PDF nos arquivos da empresa
    2. Encaminhe para o departamento contábil
    3. Execute as ações recomendadas para as exceções
    4. Agende a próxima conciliação
    """)