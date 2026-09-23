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
from difflib import SequenceMatcher
from modules.auth_middleware import require_auth


def parse_valor_moeda(valor_str) -> float:
    """Converte uma string de valor monetário (prefixo 'R$' opcional, sinal
    negativo opcional) para float, aceitando tanto a convenção BRL (milhar
    '.', decimal ',') quanto a convenção usada pelo próprio f"{valor:,.2f}"
    do Python (milhar ',', decimal '.').

    Bug corrigido (E2E real, ver issue): o código anterior assumia sempre
    convenção BRL (`.replace('.', '').replace(',', '.')`), mas as tabelas de
    divergência desta página são montadas com `f"R$ {valor:,.2f}"`
    (`_criar_tabela_transacoes_sem_correspondencia` /
    `_criar_tabela_lancamentos_sem_correspondencia`), que produz milhar ','
    e decimal '.' — ex.: "R$ 1,300.00". O parser antigo removia o ÚNICO
    ponto (tratando-o como milhar) e não encontrava vírgula, resultando em
    "1300" → 1300 interpretado como "13,00" após a lógica ficar invertida
    (na prática: "R$ 1,300.00" virava 1.3), inflando o "Total em
    divergência" somado a partir dessas strings.

    Estratégia: o ÚLTIMO separador (',' ou '.') que aparece na string é
    tratado como decimal; qualquer separador do outro tipo é tratado como
    milhar e removido. Isso decide corretamente entre as duas convenções
    sem precisar adivinhar qual foi usada para gerar a string, e funciona
    tanto para "R$ 60,50"/"R$ 1.300,00" (BRL) quanto para "R$ 60.50"/
    "R$ 1,300.00" (a convenção real usada por este arquivo).
    """
    if valor_str is None:
        raise ValueError("valor monetário vazio")

    s = str(valor_str).strip().replace('R$', '').strip()

    negativo = False
    if s.startswith('-'):
        negativo = True
        s = s[1:].strip()
    elif s.startswith('(') and s.endswith(')'):
        negativo = True
        s = s[1:-1].strip()

    if not s:
        raise ValueError(f"valor monetário vazio: {valor_str!r}")

    ultima_virgula = s.rfind(',')
    ultimo_ponto = s.rfind('.')

    if ultima_virgula > ultimo_ponto:
        # vírgula é o separador decimal (convenção BRL); ponto(s) = milhar
        numero = s.replace('.', '').replace(',', '.')
    else:
        # ponto é o separador decimal (ou não há separador nenhum);
        # vírgula(s), se houver, são milhar
        numero = s.replace(',', '')

    valor = float(numero)
    return -valor if negativo else valor


@require_auth
def main():
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

    # --- NOVAS FUNÇÕES PARA TABELAS MELHORADAS ---
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
        
        # Tabela 1: Transações bancárias sem correspondência
        extrato_nao_match = extrato_df[~extrato_df['id'].isin(extrato_match_ids)]
        tabela_transacoes_sem_correspondencia = _criar_tabela_transacoes_sem_correspondencia(extrato_nao_match)
        
        # Tabela 2: Lançamentos contábeis sem correspondência
        contabil_nao_match = contabil_df[~contabil_df['id'].isin(contabil_match_ids)]
        tabela_lancamentos_sem_correspondencia = _criar_tabela_lancamentos_sem_correspondencia(contabil_nao_match)
        
        # Tabela 3: Possíveis correspondências por similaridade
        tabela_similaridades = _criar_tabela_similaridades(extrato_nao_match, contabil_nao_match)
        
        return {
            'transacoes_sem_correspondencia': tabela_transacoes_sem_correspondencia,
            'lancamentos_sem_correspondencia': tabela_lancamentos_sem_correspondencia,
            'possiveis_similaridades': tabela_similaridades
        }

    def _criar_tabela_transacoes_sem_correspondencia(extrato_nao_match):
        """Cria tabela para transações bancárias sem correspondência"""
        tabela = []
        
        for _, transacao in extrato_nao_match.iterrows():
            # Garantir que temos os dados corretos
            data_str = transacao['data'].strftime('%d/%m/%Y') if hasattr(transacao['data'], 'strftime') else str(transacao.get('data', 'N/A'))
            valor = transacao.get('valor_original', transacao.get('valor', 0))
            descricao = transacao.get('descricao', 'Descrição não disponível')
            
            tabela.append({
                'Data': data_str,
                'Valor': f"R$ {valor:,.2f}",
                'Descrição': descricao[:80] + "..." if len(descricao) > 80 else descricao,
                'Origem': 'Extrato Bancário',
                'Status': 'Não conciliado',
                'Recomendação': 'Verificar se é despesa não lançada ou receita não identificada'
            })
        
        return pd.DataFrame(tabela)

    def _criar_tabela_lancamentos_sem_correspondencia(contabil_nao_match):
        """Cria tabela para lançamentos contábeis sem correspondência"""
        tabela = []
        
        for _, lancamento in contabil_nao_match.iterrows():
            # Garantir que temos os dados corretos
            data_str = lancamento['data'].strftime('%d/%m/%Y') if hasattr(lancamento['data'], 'strftime') else str(lancamento.get('data', 'N/A'))
            valor = lancamento.get('valor_original', lancamento.get('valor', 0))
            descricao = lancamento.get('descricao', 'Descrição não disponível')
            
            tabela.append({
                'Data': data_str,
                'Valor': f"R$ {valor:,.2f}",
                'Descrição': descricao[:80] + "..." if len(descricao) > 80 else descricao,
                'Origem': 'Sistema Contábil',
                'Status': 'Não conciliado',
                'Recomendação': 'Verificar se é provisionamento, lançamento futuro ou erro'
            })
        
        return pd.DataFrame(tabela)

    def _criar_tabela_similaridades(extrato_nao_match, contabil_nao_match):
        """Identifica possíveis correspondências por similaridade"""
        tabela = []
        
        # Analisar possíveis matches por similaridade de valor e data
        for _, extrato_row in extrato_nao_match.iterrows():
            valor_extrato = abs(extrato_row.get('valor_original', extrato_row.get('valor', 0)))
            data_extrato = extrato_row.get('data', None)
            
            # Buscar lançamentos com valores similares (±10%) e datas próximas (±5 dias)
            for _, contabil_row in contabil_nao_match.iterrows():
                valor_contabil = abs(contabil_row.get('valor_original', contabil_row.get('valor', 0)))
                data_contabil = contabil_row.get('data', None)
                
                # Calcular similaridade
                if valor_extrato > 0:
                    diff_valor_percent = abs(valor_extrato - valor_contabil) / valor_extrato * 100
                else:
                    diff_valor_percent = 100
                    
                if hasattr(data_extrato, 'strftime') and hasattr(data_contabil, 'strftime'):
                    diff_dias = abs((data_extrato - data_contabil).days)
                else:
                    diff_dias = 30
                
                if diff_valor_percent <= 10 and diff_dias <= 5:
                    similaridade = _calcular_similaridade_texto(
                        extrato_row.get('descricao', ''),
                        contabil_row.get('descricao', '')
                    )
                    
                    if similaridade >= 40:  # Similaridade mínima de 40%
                        confianca_ajuste = (100 - diff_valor_percent) * (100 - diff_dias * 2) * similaridade / 10000
                        
                        data_extrato_str = data_extrato.strftime('%d/%m/%Y') if hasattr(data_extrato, 'strftime') else str(data_extrato)
                        data_contabil_str = data_contabil.strftime('%d/%m/%Y') if hasattr(data_contabil, 'strftime') else str(data_contabil)
                        
                        tabela.append({
                            'Similaridade': f"{similaridade:.1f}%",
                            'Data_Bancário': data_extrato_str,
                            'Data_Contábil': data_contabil_str,
                            'Valor_Bancário': f"R$ {extrato_row.get('valor_original', extrato_row.get('valor', 0)):,.2f}",
                            'Valor_Contábil': f"R$ {contabil_row.get('valor_original', contabil_row.get('valor', 0)):,.2f}",
                            'Descrição_Bancário': extrato_row.get('descricao', '')[:50] + "..." if len(extrato_row.get('descricao', '')) > 50 else extrato_row.get('descricao', ''),
                            'Descrição_Contábil': contabil_row.get('descricao', '')[:50] + "..." if len(contabil_row.get('descricao', '')) > 50 else contabil_row.get('descricao', ''),
                            'Diferença_Valor': f"R$ {abs(extrato_row.get('valor_original', extrato_row.get('valor', 0)) - contabil_row.get('valor_original', contabil_row.get('valor', 0))):,.2f}",
                            'Diferença_Dias': diff_dias,
                            'Confiança': f"{confianca_ajuste:.1f}%",
                            'Recomendação': 'Analisar possível correspondência manual'
                        })
        
        return pd.DataFrame(tabela)

    def _calcular_similaridade_texto(texto1, texto2):
        """Calcula similaridade entre textos"""
        if not texto1 or not texto2:
            return 0.0
        return SequenceMatcher(None, texto1.lower(), texto2.lower()).ratio() * 100

    # --- FIM DAS NOVAS FUNÇÕES ---

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
            st.subheader("📊 Análise Detalhada das Divergências")
            
            # Gerar tabelas melhoradas
            tabelas_divergencias = gerar_tabelas_divergencias_melhoradas(
                resultados_analise, extrato_filtrado, contabil_filtrado
            )
            
            # Tabela 1: Transações Bancárias sem Correspondência
            if not tabelas_divergencias['transacoes_sem_correspondencia'].empty:
                st.markdown("### 🏦 Transações Bancárias sem Correspondência Contábil")
                st.dataframe(
                    tabelas_divergencias['transacoes_sem_correspondencia'],
                    width='stretch',
                    hide_index=True
                )
                
                # Estatísticas
                total_valor = 0
                for valor_str in tabelas_divergencias['transacoes_sem_correspondencia']['Valor']:
                    try:
                        valor_clean = parse_valor_moeda(valor_str)
                        total_valor += abs(valor_clean)
                    except:
                        continue
                        
                st.info(f"**Total em divergência:** R$ {total_valor:,.2f} | **Itens:** {len(tabelas_divergencias['transacoes_sem_correspondencia'])}")
                
                # Botão de exportação
                csv_transacoes = tabelas_divergencias['transacoes_sem_correspondencia'].to_csv(index=False)
                st.download_button(
                    label="📥 Exportar Transações sem Correspondência",
                    data=csv_transacoes,
                    file_name="transacoes_bancarias_sem_correspondencia.csv",
                    mime="text/csv"
                )
            
            # Tabela 2: Lançamentos Contábeis sem Correspondência
            if not tabelas_divergencias['lancamentos_sem_correspondencia'].empty:
                if not tabelas_divergencias['transacoes_sem_correspondencia'].empty:
                    st.divider()
                    
                st.markdown("### 📊 Lançamentos Contábeis sem Movimentação Bancária")
                st.dataframe(
                    tabelas_divergencias['lancamentos_sem_correspondencia'],
                    width='stretch',
                    hide_index=True
                )
                
                # Estatísticas
                total_valor = 0
                for valor_str in tabelas_divergencias['lancamentos_sem_correspondencia']['Valor']:
                    try:
                        valor_clean = parse_valor_moeda(valor_str)
                        total_valor += abs(valor_clean)
                    except:
                        continue
                        
                st.info(f"**Total em divergência:** R$ {total_valor:,.2f} | **Itens:** {len(tabelas_divergencias['lancamentos_sem_correspondencia'])}")
                
                # Botão de exportação
                csv_lancamentos = tabelas_divergencias['lancamentos_sem_correspondencia'].to_csv(index=False)
                st.download_button(
                    label="📥 Exportar Lançamentos sem Correspondência",
                    data=csv_lancamentos,
                    file_name="lancamentos_contabeis_sem_correspondencia.csv",
                    mime="text/csv"
                )
            
            # Tabela 3: Possíveis Similaridades
            if not tabelas_divergencias['possiveis_similaridades'].empty:
                if not tabelas_divergencias['transacoes_sem_correspondencia'].empty or not tabelas_divergencias['lancamentos_sem_correspondencia'].empty:
                    st.divider()
                    
                st.markdown("### 🔍 Possíveis Correspondências por Similaridade")
                st.dataframe(
                    tabelas_divergencias['possiveis_similaridades'],
                    width='stretch',
                    hide_index=True
                )
                
                st.info(f"**{len(tabelas_divergencias['possiveis_similaridades'])} possíveis correspondências identificadas**")
                st.warning("💡 **Recomendação:** Analisar estas correspondências manualmente - podem ser matches válidos que o sistema não identificou com confiança suficiente")
                
                # Botão de exportação
                csv_similaridades = tabelas_divergencias['possiveis_similaridades'].to_csv(index=False)
                st.download_button(
                    label="📥 Exportar Possíveis Correspondências",
                    data=csv_similaridades,
                    file_name="possiveis_correspondencias_similaridade.csv",
                    mime="text/csv"
                )
            
            # Verificar se não há nenhuma divergência
            if (tabelas_divergencias['transacoes_sem_correspondencia'].empty and 
                tabelas_divergencias['lancamentos_sem_correspondencia'].empty and 
                tabelas_divergencias['possiveis_similaridades'].empty):
                st.success("✅ Nenhuma divergência identificada")
            
            # Salvar no session state para uso no relatório PDF
            st.session_state['tabelas_divergencias_melhoradas'] = tabelas_divergencias
            
        else:
            st.success("✅ Nenhuma divergência crítica identificada")

    # Geração do PDF
    st.divider()
    st.header("📄 Gerar Relatório PDF")

    col_gerar1, col_gerar2 = st.columns([2, 1])

    with col_gerar1:
        st.subheader("Configurações Finais")
        
        # MOSTRAR INFORMAÇÃO DA CONTA ANALISADA
        if 'conta_analisada' in st.session_state and st.session_state.conta_analisada:
            st.info(f"📋 **Conta analisada:** {st.session_state.conta_analisada}")
        else:
            st.warning("⚠️ **Conta não identificada** - Use o sistema de validação na importação")
        
        observacoes = st.text_area(
            "Observações e Contexto para o Relatório:",
            placeholder="Ex: Contexto específico da análise, considerações importantes, períodos atípicos...",
            height=100
        )
        
        formato_relatorio = st.selectbox(
            "Formato do Relatório",
            ["Completo", "Resumido"],
            help="Completo: Inclui todos os detalhes e tabelas completas | Resumido: Apenas sumário executivo e estatísticas principais"
        )

    with col_gerar2:
        st.subheader("Gerar PDF")
        
        if st.button("🔄 Gerar Relatório de Análise", type="primary", width='stretch', key="btn_gerar_relatorio_analise"):
            with st.spinner("Gerando relatório PDF..."):
                try:
                    # Obter as tabelas de divergências melhoradas se existirem
                    divergencias_tabela = None
                    if 'tabelas_divergencias_melhoradas' in st.session_state:
                        todas_divergencias = pd.concat([
                            st.session_state['tabelas_divergencias_melhoradas']['transacoes_sem_correspondencia'],
                            st.session_state['tabelas_divergencias_melhoradas']['lancamentos_sem_correspondencia'],
                            st.session_state['tabelas_divergencias_melhoradas']['possiveis_similaridades']
                        ], ignore_index=True)
                        divergencias_tabela = todas_divergencias
                    
                    # OBTER A CONTA ANALISADA DO SESSION STATE
                    conta_analisada = st.session_state.get('conta_analisada', 'Não identificada')
                    
                    # PASSAR A CONTA PARA A FUNÇÃO DE GERAR RELATÓRIO
                    pdf_path = report_gen.gerar_relatorio_analise(
                        resultados_analise=resultados_analise,
                        extrato_df=extrato_filtrado,
                        contabil_df=contabil_filtrado,
                        empresa_nome=empresa_nome,
                        contador_nome=contador_nome,
                        periodo=periodo_relatorio,
                        observacoes=observacoes,
                        formato=formato_relatorio.lower(),
                        divergencias_tabela=divergencias_tabela,
                        conta_analisada=conta_analisada  # ✅ NOVO PARÂMETRO
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
                    nome_arquivo = f"relatorio_{formato_relatorio.lower()}_{conta_analisada}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
                    href = f'<a href="data:application/pdf;base64,{b64_pdf}" download="{nome_arquivo}" style="background-color: #4CAF50; color: white; padding: 14px 20px; text-align: center; text-decoration: none; display: inline-block; border-radius: 5px; font-size: 16px;">📥 Baixar Relatório {formato_relatorio}</a>'
                    
                    st.markdown(href, unsafe_allow_html=True)
                    st.success(f"✅ Relatório {formato_relatorio} gerado com sucesso!")
                    st.info(f"📋 Conta incluída no relatório: **{conta_analisada}**")
                    
                    # Pré-visualização embutida
                    st.subheader("👁️ Pré-visualização do PDF")
                    base64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
                    pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="600" type="application/pdf"></iframe>'
                    st.markdown(pdf_display, unsafe_allow_html=True)
                    
                except Exception as e:
                    st.error(f"❌ Erro ao gerar relatório: {str(e)}")

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
            keys_to_clear = ['resultados_analise', 'extrato_filtrado', 'contabil_filtrado', 'tabelas_divergencias_melhoradas']
            for key in keys_to_clear:
                if key in st.session_state:
                    del st.session_state[key]
            st.switch_page("pages/importacao_dados.py")

    with col_acao3:
        if st.button("🏠 Início", key="btn_inicio"):
            st.switch_page("app.py")

if __name__ == "__main__":
    main()