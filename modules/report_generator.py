# modules/report_generator.py
import pandas as pd
import numpy as np
from datetime import datetime
from fpdf import FPDF
import tempfile
import os
from typing import List, Dict, Any

class PDFReport(FPDF):
    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=15)
        self.add_page()
        
    def header(self):
        self.set_font('Arial', 'B', 16)
        self.cell(0, 40, 'RELATÓRIO DE CONCILIAÇÃO BANCÁRIA', 0, 1, 'C')
        self.set_font('Arial', 'I', 10)
        self.cell(0, 5, f'Gerado em: {datetime.now().strftime("%d/%m/%Y %H:%M")}', 0, 1, 'C')
        self.ln(5)
    
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')
    
    def chapter_title(self, title):
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, self.clean_text(title), 0, 1, 'L')
        self.ln(2)

    def chapter_body(self, body):
        self.set_font('Arial', '', 10)
        cleaned_body = self.clean_text(body)
        self.multi_cell(0, 6, cleaned_body)
        self.ln()
    
    def clean_text(self, text):
        if not text:
            return ""
        
        text = str(text)
        
        replacements = {
            '✅': '[OK]', '✔': '[OK]', '✓': '[OK]', '☑': '[OK]',
            '❌': '[ERRO]', '✖': '[ERRO]', '❎': '[ERRO]',
            '⚠': '[ATENCAO]', '⚡': '[RAPIDO]', '🎯': '[FOCO]',
            '📊': '[METRICAS]', '📋': '[RELATORIO]', '🔍': '[ANALISE]',
            '💡': '[DICA]', '🚀': '[RAPIDO]', '⭐': '[DESTAQUE]',
            '•': '-', '·': '-', '–': '-', '—': '-', '‣': '-', '⁃': '-',
            '“': '"', '”': '"', '‘': "'", '’': "'", '´': "'", '`': "'",
        }
        
        for old_char, new_char in replacements.items():
            text = text.replace(old_char, new_char)
        
        try:
            text = text.encode('latin-1', 'replace').decode('latin-1')
        except:
            pass
        
        return text
    
def gerar_relatorio_analise(resultados_analise: Dict,
                          extrato_df: pd.DataFrame,
                          contabil_df: pd.DataFrame,
                          empresa_nome: str = "Empresa",
                          contador_nome: str = "Contador",
                          periodo: str = "",
                          observacoes: str = "",
                          formato: str = "completo",
                          divergencias_tabela: pd.DataFrame = None,
                          **kwargs) -> str:
    """
    Gera relatório de análise (não de conciliação)
    formato: 'completo' ou 'resumido'
    """
    pdf = PDFReport()
    
    # Página 1: Capa (comum para ambos os formatos)
    pdf.add_page()
    pdf.set_font('Arial', 'B', 20)
    pdf.cell(0, 40, 'RELATÓRIO DE ANÁLISE DE CORRESPONDÊNCIAS', 0, 1, 'C')
    pdf.set_font('Arial', 'B', 16)
    pdf.cell(0, 20, pdf.clean_text(empresa_nome), 0, 1, 'C')
    pdf.set_font('Arial', '', 12)
    pdf.cell(0, 10, f'Período: {periodo}', 0, 1, 'C')
    pdf.cell(0, 10, f'Analista: {pdf.clean_text(contador_nome)}', 0, 1, 'C')
    pdf.cell(0, 10, f'Data de geração: {datetime.now().strftime("%d/%m/%Y")}', 0, 1, 'C')
    pdf.cell(0, 10, f'Formato: {formato.upper()}', 0, 1, 'C')
    
    pdf.ln(20)
    
    # Sumário Executivo (comum para ambos os formatos)
    pdf.chapter_title('RELATÓRIO DE ANÁLISE - CORRESPONDÊNCIAS IDENTIFICADAS')
    
    total_matches = len(resultados_analise['matches'])
    total_excecoes = len(resultados_analise.get('excecoes', []))
    total_extrato = len(extrato_df)
    total_contabil = len(contabil_df)
    
    resumo_texto = f"""
    ESTE É UM RELATÓRIO DE ANÁLISE E IDENTIFICAÇÃO DE CORRESPONDÊNCIAS
    
    OBJETIVO:
    Identificar automaticamente relações entre transações bancárias e lançamentos contábeis
    para auxiliar no processo de conciliação manual.
    
    RESULTADOS DA ANÁLISE:
    - Transações bancárias analisadas: {total_extrato}
    - Lançamentos contábeis analisados: {total_contabil}
    - Correspondências identificadas: {total_matches}
    - Divergências encontradas: {total_excecoes}
    - Período analisado: {periodo}
    
    METODOLOGIA:
    Análise em três camadas:
    1. CORRESPONDÊNCIAS EXATAS: Valores e datas idênticos, identificadores únicos
    2. CORRESPONDÊNCIAS POR SIMILARIDADE: Valores e datas próximos, textos similares  
    3. ANÁLISE DE PADRÕES: Parcelamentos, consolidações, padrões temporais
    
    OBSERVAÇÕES:
    {observacoes if observacoes else 'Nenhuma observação adicional'}
    
    ATENÇÃO: Este relatório apresenta CORRESPONDÊNCIAS IDENTIFICADAS que devem ser validadas 
    manualmente pelo contador antes da conciliação final.
    """
    
    pdf.chapter_body(resumo_texto)
    
    # Página 2: Estatísticas (comum para ambos os formatos)
    pdf.add_page()
    pdf.chapter_title('ESTATÍSTICAS DETALHADAS')
    
    # Métricas principais
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'MÉTRICAS PRINCIPAIS:', 0, 1)
    pdf.set_font('Arial', '', 10)
    
    taxa_cobertura = (total_matches / total_extrato * 100) if total_extrato > 0 else 0
    valor_total_extrato_absoluto = extrato_df['valor'].abs().sum()
    valor_total_extrato = extrato_df['valor'].sum()
    valor_total_contabil = contabil_df['valor'].sum()
    
    estatisticas_texto = f"""
    VOLUME DE DADOS:
    - Transações bancárias: {total_extrato}
    - Lançamentos contábeis: {total_contabil}
    - Valor total extrato (absoluto): R$ {valor_total_extrato_absoluto:,.2f}
    - Valor total extrato: R$ {valor_total_extrato:,.2f}
    - Valor total contábil: R$ {valor_total_contabil:,.2f}
    
    RESULTADOS DA IDENTIFICAÇÃO:
    - Correspondências identificadas: {total_matches}
    - Taxa de cobertura: {taxa_cobertura:.1f}%
    - Divergências: {total_excecoes}
    
    DISTRIBUIÇÃO POR TIPO:
    - Correspondências 1:1: {len([m for m in resultados_analise['matches'] if m['tipo_match'] == '1:1'])}
    - Correspondências 1:N: {len([m for m in resultados_analise['matches'] if m['tipo_match'] == '1:N'])}
    - Correspondências N:1: {len([m for m in resultados_analise['matches'] if m['tipo_match'] == 'N:1'])}
    
    EFETIVIDADE POR CAMADA:
    - Correspondências exatas: {len([m for m in resultados_analise['matches'] if m['camada'] == 'exata'])}
    - Correspondências por similaridade: {len([m for m in resultados_analise['matches'] if m['camada'] == 'heuristica'])}
    - Correspondências complexas: {len([m for m in resultados_analise['matches'] if m['camada'] == 'ia'])}
    """
    
    pdf.chapter_body(estatisticas_texto)
    
    # CONTEÚDO ESPECÍFICO PARA RELATÓRIO COMPLETO
    if formato == 'completo':
        # Página 3: Correspondências Identificadas (apenas no completo)
        if resultados_analise['matches']:
            pdf.add_page()
            pdf.chapter_title('CORRESPONDÊNCIAS IDENTIFICADAS - DETALHES COMPLETOS')
            
            headers = ['ID', 'Tipo', 'Camada', 'Confiança', 'Valor Total', 'Trans Bank', 'Lanc Cont']
            col_widths = [10, 20, 25, 20, 30, 20, 20]
            
            pdf.set_font('Arial', 'B', 8)
            for i, header in enumerate(headers):
                pdf.cell(col_widths[i], 8, header, 1, 0, 'C')
            pdf.ln()
            
            pdf.set_font('Arial', '', 7)
            for i, match in enumerate(resultados_analise['matches']):
                pdf.cell(col_widths[0], 6, str(i + 1), 1, 0, 'C')
                pdf.cell(col_widths[1], 6, match['tipo_match'], 1, 0, 'C')
                pdf.cell(col_widths[2], 6, match['camada'], 1, 0, 'C')
                pdf.cell(col_widths[3], 6, f"{match['confianca']}%", 1, 0, 'C')
                pdf.cell(col_widths[4], 6, f"R$ {match['valor_total']:.2f}", 1, 0, 'C')
                pdf.cell(col_widths[5], 6, str(len(match['ids_extrato'])), 1, 0, 'C')
                pdf.cell(col_widths[6], 6, str(len(match['ids_contabil'])), 1, 0, 'C')
                pdf.ln()
            
            pdf.ln(10)
            pdf.chapter_title('PRINCIPAIS CORRESPONDÊNCIAS - DETALHES')
            
            for i, match in enumerate(resultados_analise['matches'][:10]):  # Limitar a 10 no completo
                pdf.set_font('Arial', 'B', 9)
                pdf.cell(0, 8, f'Correspondência {i + 1}: {match["tipo_match"]} - {match["camada"]}', 0, 1)
                pdf.set_font('Arial', '', 8)
                pdf.multi_cell(0, 4, f'Justificativa: {pdf.clean_text(match["explicacao"])}')
                pdf.multi_cell(0, 4, f'Valor: R$ {match["valor_total"]:.2f} | Confiança: {match["confianca"]}%')
                
                transacoes_extrato = extrato_df[extrato_df['id'].isin(match['ids_extrato'])]
                transacoes_contabil = contabil_df[contabil_df['id'].isin(match['ids_contabil'])]
                
                pdf.multi_cell(0, 4, f'Transações bancárias: {len(transacoes_extrato)}')
                for _, trans in transacoes_extrato.iterrows():
                    data_str = trans['data'].strftime('%d/%m') if hasattr(trans['data'], 'strftime') else str(trans['data'])
                    valor_original = trans.get('valor_original', trans['valor'])
                    pdf.multi_cell(0, 3, f'  - R$ {valor_original:,.2f} | {data_str} | {pdf.clean_text(trans["descricao"][:30])}')
                
                pdf.multi_cell(0, 4, f'Lançamentos contábeis: {len(transacoes_contabil)}')
                for _, lanc in transacoes_contabil.iterrows():
                    data_str = lanc['data'].strftime('%d/%m') if hasattr(lanc['data'], 'strftime') else str(lanc['data'])
                    valor_original = lanc.get('valor_original', lanc['valor'])
                    pdf.multi_cell(0, 3, f'  - R$ {valor_original:,.2f} | {data_str} | {pdf.clean_text(lanc["descricao"][:30])}')
                
                pdf.ln(5)
    
    else:  # RELATÓRIO RESUMIDO
        # Página 3: Correspondências Resumidas
        if resultados_analise['matches']:
            pdf.add_page()
            pdf.chapter_title('CORRESPONDÊNCIAS IDENTIFICADAS - VISÃO RESUMIDA')
            
            pdf.set_font('Arial', '', 9)
            pdf.multi_cell(0, 5, f'Total de correspondências identificadas: {len(resultados_analise["matches"])}')
            
            # Apenas estatísticas resumidas no relatório resumido
            tipos_match = {
                '1:1': len([m for m in resultados_analise['matches'] if m['tipo_match'] == '1:1']),
                '1:N': len([m for m in resultados_analise['matches'] if m['tipo_match'] == '1:N']),
                'N:1': len([m for m in resultados_analise['matches'] if m['tipo_match'] == 'N:1'])
            }
            
            pdf.multi_cell(0, 5, f'Distribuição: 1:1 ({tipos_match["1:1"]}), 1:N ({tipos_match["1:N"]}), N:1 ({tipos_match["N:1"]})')
            
            # Apenas as 3 principais correspondências por confiança
            matches_ordenados = sorted(resultados_analise['matches'], key=lambda x: x['confianca'], reverse=True)[:3]
            
            if matches_ordenados:
                pdf.ln(5)
                pdf.set_font('Arial', 'B', 10)
                pdf.cell(0, 8, 'PRINCIPAIS CORRESPONDÊNCIAS (TOP 3):', 0, 1)
                
                for i, match in enumerate(matches_ordenados):
                    pdf.set_font('Arial', 'B', 9)
                    pdf.cell(0, 6, f'{i+1}. {match["tipo_match"]} - Confiança: {match["confianca"]}% - Valor: R$ {match["valor_total"]:.2f}', 0, 1)
                    pdf.set_font('Arial', '', 8)
                    pdf.multi_cell(0, 4, f'   {pdf.clean_text(match["explicacao"][:100])}...')
                    pdf.ln(2)
    
    # Página de Divergências (comum mas com detalhamento diferente)
    if resultados_analise.get('excecoes'):
        pdf.add_page()
        
        if formato == 'completo':
            pdf.chapter_title('DIVERGÊNCIAS IDENTIFICADAS - ANÁLISE COMPLETA')
        else:
            pdf.chapter_title('DIVERGÊNCIAS IDENTIFICADAS - RESUMO')
        
        for i, excecao in enumerate(resultados_analise['excecoes']):
            pdf.set_font('Arial', 'B', 10)
            pdf.cell(0, 8, f'Divergência {i + 1}: {excecao["tipo"]} - {excecao["severidade"]}', 0, 1)
            pdf.set_font('Arial', '', 9)
            pdf.multi_cell(0, 5, f'Descrição: {pdf.clean_text(excecao["descricao"])}')
            pdf.multi_cell(0, 5, f'Recomendação: {pdf.clean_text(excecao["acao_sugerida"])}')
            pdf.multi_cell(0, 5, f'Itens envolvidos: {len(excecao["ids_envolvidos"])}')
            pdf.ln(5)
    
    # Tabela de Divergências Detalhadas (APENAS NO COMPLETO)
    if formato == 'completo' and divergencias_tabela is not None and not divergencias_tabela.empty:
        try:
            pdf.add_page()
            pdf.chapter_title('TABELA DETALHADA DE DIVERGÊNCIAS')
            
            headers = ['Tipo', 'Severidade', 'Data', 'Descrição', 'Valor', 'Origem']
            col_widths = [15, 20, 20, 60, 25, 20]
            
            pdf.set_font('Arial', 'B', 8)
            for i, header in enumerate(headers):
                pdf.cell(col_widths[i], 8, header, 1, 0, 'C')
            pdf.ln()
            
            def abreviar_tipo_divergencia(tipo_original):
                abreviacoes = {
                    'TRANSAÇÃO_SEM_CORRESPONDÊNCIA': 'TSC',
                    'LANÇAMENTO_SEM_CORRESPONDÊNCIA': 'LSC',
                    'TRANSAÇÃO_SEM_CORRESPONDENCIA': 'TSC',
                    'LANÇAMENTO_SEM_CORRESPONDENCIA': 'LSC'
                }
                return abreviacoes.get(tipo_original, tipo_original)
            
            pdf.set_font('Arial', '', 7)
            for _, row in divergencias_tabela.iterrows():
                descricao = str(row.get('Descrição', row.get('descricao', '')))[:50] + "..." if len(str(row.get('Descrição', row.get('descricao', '')))) > 50 else str(row.get('Descrição', row.get('descricao', '')))
                
                tipo_original = str(row.get('Tipo_Divergência', row.get('Tipo', '')))
                tipo = abreviar_tipo_divergencia(tipo_original)
                
                severidade = str(row.get('Severidade', ''))
                data = str(row.get('Data', ''))
                valor = str(row.get('Valor', ''))
                origem = str(row.get('Origem', ''))
                
                pdf.cell(col_widths[0], 6, pdf.clean_text(tipo), 1, 0, 'C')
                pdf.cell(col_widths[1], 6, pdf.clean_text(severidade), 1, 0, 'C')
                pdf.cell(col_widths[2], 6, pdf.clean_text(data), 1, 0, 'C')
                pdf.cell(col_widths[3], 6, pdf.clean_text(descricao), 1, 0, 'L')
                pdf.cell(col_widths[4], 6, pdf.clean_text(valor), 1, 0, 'C')
                pdf.cell(col_widths[5], 6, pdf.clean_text(origem), 1, 0, 'C')
                pdf.ln()
            
            pdf.ln(5)
            pdf.set_font('Arial', 'I', 8)
            pdf.cell(0, 6, f'Total de divergências detalhadas: {len(divergencias_tabela)}', 0, 1)
            
        except Exception as e:
            print(f"⚠️ Aviso: Não foi possível adicionar tabela de divergências: {e}")
    
    # Página final: Recomendações (comum para ambos)
    pdf.add_page()
    pdf.chapter_title('RECOMENDAÇÕES E PRÓXIMOS PASSOS')
    
    if formato == 'completo':
        recomendacoes_texto = """
        RECOMENDAÇÕES PARA CONCILIAÇÃO MANUAL:
        
        1. VALIDAR CORRESPONDÊNCIAS IDENTIFICADAS
           - Confirmar cada correspondência proposta
           - Verificar se as relações fazem sentido comercial
           - Validar valores e datas
        
        2. INVESTIGAR DIVERGÊNCIAS
           - Analisar transações sem correspondência (TSC)
           - Verificar lançamentos sem movimento bancário (LSC)
           - Identificar possíveis erros de lançamento
        
        3. AJUSTES NECESSÁRIOS
           - Corrigir lançamentos incorretos
           - Incluir transações omitidas
           - Ajustar classificações contábeis
        
        4. DOCUMENTAÇÃO
           - Manter registro das validações realizadas
           - Documentar ajustes feitos
           - Arquivar este relatório de análise
        """
    else:
        recomendacoes_texto = """
        PRÓXIMOS PASSOS RECOMENDADOS:
        
        • Validar correspondências identificadas
        • Investigar divergências críticas
        • Ajustar lançamentos conforme necessário
        • Documentar processo de conciliação
        
        PARA ANÁLISE DETALHADA:
        Consulte o relatório completo para:
        - Tabelas detalhadas de correspondências
        - Análise completa de divergências
        - Detalhes técnicos da análise
        """
    
    recomendacoes_texto += """
    
    OBSERVAÇÕES IMPORTANTES:
    - Este relatório é uma FERRAMENTA DE AUXÍLIO
    - Todas as correspondências devem ser VALIDADAS MANUALMENTE
    - A responsabilidade final pela conciliação é do contador
    - Mantenha documentação adequada para auditoria
    """
    
    pdf.chapter_body(recomendacoes_texto)
    pdf.add_page()
    
    # Assinatura
    pdf.ln(15)
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 8, '_________________________', 0, 1, 'C')
    pdf.cell(0, 8, pdf.clean_text(contador_nome), 0, 1, 'C')
    pdf.cell(0, 8, 'Contador Responsável', 0, 1, 'C')
    
    # Salvar PDF
    temp_dir = tempfile.gettempdir()
    pdf_path = os.path.join(temp_dir, f'relatorio_analise_{formato}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf')
    
    try:
        pdf.output(pdf_path)
        return pdf_path
    except Exception as e:
        print(f"Erro ao salvar PDF: {e}")
        pdf_path_fallback = os.path.join(temp_dir, f'relatorio_analise_fallback_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf')
        pdf.output(pdf_path_fallback)
        return pdf_path_fallback

def _abreviar_tipo_divergencia(self, tipo_original):
    """Abrevia tipos longos de divergência para melhor visualização na tabela"""
    abreviacoes = {
        'TRANSAÇÃO_SEM_CORRESPONDÊNCIA': 'TSC',
        'LANÇAMENTO_SEM_CORRESPONDÊNCIA': 'LSC',
        'TRANSAÇÃO_SEM_CORRESPONDENCIA': 'TSC',  # Fallback sem acento
        'LANÇAMENTO_SEM_CORRESPONDENCIA': 'LSC'  # Fallback sem acento
    }
    return abreviacoes.get(tipo_original, tipo_original)