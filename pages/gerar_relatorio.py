# pages/4_📄_gerar_relatorio.py
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import tempfile
import time
import base64
import modules.report_executivo as report_executivo
import locale
from modules.auth_middleware import require_auth, get_current_user
from modules.audit_logger import get_audit_logger
from modules.structured_logger import get_structured_logger
from modules.tema import aplicar_tema


# parse_valor_moeda mudou de casa para modules/report_generator.py (é
# reutilizada lá para somar as colunas 'Valor' das tabelas de divergência
# ao gerar o PDF); reexportada aqui para não quebrar o import existente
# (inclusive em tests/test_parse_valor_moeda.py).
from modules.report_generator import parse_valor_moeda


def calcular_periodo_real(extrato_df: pd.DataFrame, contabil_df: pd.DataFrame) -> str:
    """Calcula o período real coberto pelos dados analisados (menor e maior
    data entre extrato e contábil), formatado como 'dd/mm/aaaa a
    dd/mm/aaaa'. Anos diferentes entre extrato e contábil são tratados
    normalmente (min/max globais). Se um dos dois lados estiver vazio ou
    sem nenhuma data válida, usa só o outro lado, sem quebrar. Datas
    inválidas são ignoradas individualmente (`errors='coerce'`).

    Bug corrigido (E2E real, ver issue XCRE-42): o campo "Período" do
    relatório usava `datetime.now().strftime('%B/%Y')` como valor padrão
    — ou seja, o mês em que o PDF foi GERADO (ex.: "September/2026"), não
    o intervalo real das transações analisadas.

    XCRE-54 item 2: o campo manual da barra lateral que permitia ao
    usuário corrigir esse valor foi removido — este cálculo automático é
    agora a ÚNICA fonte do período exibido (capa, seção de auditoria e
    lote da auditoria). Por isso, sem nenhuma data válida em nenhum dos
    dois lados, não é mais aceitável cair de volta silenciosamente no mês
    de geração (pareceria um período real, mas não é): devolve uma
    mensagem clara em português.
    """
    datas = []
    for df in (extrato_df, contabil_df):
        if df is not None and 'data' in df.columns and len(df) > 0:
            serie = pd.to_datetime(df['data'], errors='coerce').dropna()
            if not serie.empty:
                datas.append(serie.min())
                datas.append(serie.max())

    if not datas:
        return "Período não determinado (nenhuma data válida nos arquivos carregados)"

    data_inicio = min(datas)
    data_fim = max(datas)
    return f"{data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}"


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
    aplicar_tema()

    audit = get_audit_logger()
    _usuario_logado = get_current_user()
    usuario_atual = _usuario_logado['username'] if _usuario_logado else 'desconhecido'

    # --- Menu Customizado ---
    with st.sidebar:
        st.markdown("### Navegação Principal") 
        st.page_link("app.py", label="Início (Home)", icon="🏠")
        
        st.page_link("pages/importacao_dados.py", label="📥 Importação de Dados", icon=None)
        st.page_link("pages/analise_dados.py", label="📊 Análise de Divergências", icon=None)
        st.page_link("pages/gerar_relatorio.py", label="📝 Relatório Final", icon=None)
    # --- Fim do Menu Customizado ---

    st.title("📄 Relatório Final")

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

    # Formulário no CORPO da página (fase 7, item 3): antes ficava na
    # sidebar. O período NUNCA é um campo editável — é sempre o
    # automático (calcular_periodo_real), calculado a partir das datas
    # reais dos arquivos carregados (XCRE-54 item 2), exibido abaixo só
    # como texto informativo.
    st.subheader("Dados do Relatório")
    col_form1, col_form2 = st.columns(2)
    with col_form1:
        empresa_nome = st.text_input("Nome da Empresa", "")
        classificacao_documento = st.text_input("Classificação do documento", "Documento interno")
    with col_form2:
        contador_nome = st.text_input("Nome do Contador (Analista)", "")
    observacoes = st.text_area(
        "Observações e Contexto para o Relatório:",
        placeholder="Ex: Contexto específico da análise, considerações importantes, períodos atípicos...",
        height=100
    )

    periodo_relatorio = calcular_periodo_real(extrato_filtrado, contabil_filtrado)
    st.caption(f"📅 Período: {periodo_relatorio}, calculado dos arquivos")

    # Formato único: relatório Executivo (o formato legado "Completo" foi
    # removido do seletor a pedido do usuário).
    formato_relatorio = "Executivo"

    # Geração do PDF
    st.divider()

    # MOSTRAR INFORMAÇÃO DA CONTA ANALISADA
    if 'conta_analisada' in st.session_state and st.session_state.conta_analisada:
        st.caption(f"📋 Conta analisada: {st.session_state.conta_analisada}")
    else:
        st.warning("⚠️ **Conta não identificada** - Use o sistema de validação na importação")

    if st.button("Gerar Relatório", type="primary", width='stretch', key="btn_gerar_relatorio_analise"):
        with st.spinner("Gerando relatório PDF..."):
            _inicio_relatorio = time.time()
            try:
                # OBTER A CONTA ANALISADA DO SESSION STATE
                conta_analisada = st.session_state.get('conta_analisada', 'Não identificada')
                # "Lote" identifica QUAL conciliação foi reportada na
                # auditoria (conta + período), sem incluir nenhum dado
                # sensível — nunca senha/token.
                lote_auditoria = f"{conta_analisada} | {periodo_relatorio}"

                # PASSAR A CONTA PARA A FUNÇÃO DE GERAR RELATÓRIO
                # Relatório Executivo (fase 3, XCRE-43): template HTML +
                # WeasyPrint, narrativa por regras determinísticas.
                # Devolve os BYTES do PDF diretamente (revisão de
                # segurança XCRE-51/SEC-R-02): o gerador já escreve o
                # PDF num diretório privado por execução e o apaga em
                # `finally`, então nenhum caminho local chega até aqui.
                pdf_bytes = report_executivo.gerar_relatorio_executivo(
                    resultados_analise=resultados_analise,
                    extrato_df=extrato_filtrado,
                    contabil_df=contabil_filtrado,
                    empresa_nome=empresa_nome,
                    analista_nome=contador_nome,
                    classificacao_documento=classificacao_documento,
                    periodo=periodo_relatorio,
                    observacoes=observacoes,
                    conta_analisada=conta_analisada,
                )

                # Verificar se o conteúdo foi lido
                if len(pdf_bytes) == 0:
                    motivo = "Arquivo PDF está vazio"
                    audit.log_report_generation(
                        formato=formato_relatorio.lower(), user=usuario_atual, lote=lote_auditoria,
                        success=False, error_message=motivo,
                    )
                    get_structured_logger().log_geracao_relatorio(
                        formato=formato_relatorio.lower(), sucesso=False, motivo='falha',
                        matches_incluidos=0, divergencias_incluidas=0,
                        duracao_segundos=time.time() - _inicio_relatorio,
                    )
                    st.error(f"❌ Erro: {motivo}")
                    st.stop()

                audit.log_report_generation(
                    formato=formato_relatorio.lower(),
                    user=usuario_atual,
                    lote=lote_auditoria,
                    success=True,
                    included_matches=len(resultados_analise.get('matches', [])),
                    included_exceptions=len(resultados_analise.get('excecoes', [])),
                )
                get_structured_logger().log_geracao_relatorio(
                    formato=formato_relatorio.lower(), sucesso=True, motivo='sucesso',
                    matches_incluidos=len(resultados_analise.get('matches', [])),
                    divergencias_incluidas=len(resultados_analise.get('excecoes', [])),
                    duracao_segundos=time.time() - _inicio_relatorio,
                )

                # Criar download link
                b64_pdf = base64.b64encode(pdf_bytes).decode()
                nome_arquivo = f"relatorio_{formato_relatorio.lower()}_{conta_analisada}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
                href = f'<a href="data:application/pdf;base64,{b64_pdf}" download="{nome_arquivo}" style="background-color: #4CAF50; color: white; padding: 14px 20px; text-align: center; text-decoration: none; display: inline-block; border-radius: 5px; font-size: 16px;">📥 Baixar PDF</a>'

                st.markdown(href, unsafe_allow_html=True)
                st.success("✅ Relatório gerado com sucesso!")

                # Sem pré-visualização embutida: o Chrome bloqueia PDF em iframe com data: URL
                # ("conteúdo bloqueado pelo Chrome"); o PDF é entregue pelo botão de download acima.
                
            except Exception as e:
                audit.log_report_generation(
                    formato=formato_relatorio.lower(),
                    user=usuario_atual,
                    lote=f"{st.session_state.get('conta_analisada', 'Não identificada')} | {periodo_relatorio}",
                    success=False,
                    error_message=str(e),
                )
                get_structured_logger().log_geracao_relatorio(
                    formato=formato_relatorio.lower(), sucesso=False, motivo='falha',
                    matches_incluidos=0, divergencias_incluidas=0,
                    duracao_segundos=time.time() - _inicio_relatorio,
                )
                st.error(f"❌ Erro ao gerar relatório: {str(e)}")

    # Navegação: "Voltar para Análise" e "Início" saíram por duplicar a
    # navegação já disponível na sidebar; "Nova Importação" continua
    # (não é só navegação — também limpa os resultados da sessão).
    st.divider()
    if st.button("🔄 Nova Importação", key="btn_nova_importacao"):
        # Limpar session state para nova análise
        keys_to_clear = ['resultados_analise', 'extrato_filtrado', 'contabil_filtrado', 'tabelas_divergencias_melhoradas']
        for key in keys_to_clear:
            if key in st.session_state:
                del st.session_state[key]
        st.switch_page("pages/importacao_dados.py")

if __name__ == "__main__":
    main()