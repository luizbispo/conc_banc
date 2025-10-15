# modules/report_generator.py
import pandas as pd
import numpy as np
from datetime import datetime
from fpdf import FPDF
import tempfile
import os
from typing import List, Dict, Any
import traceback

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
        if not text: return ""
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
        except: pass
        return text

def _gerar_relatorio_fallback(empresa_nome: str, contador_nome: str, erro: str) -> str:
    """Gera um relatório minimalista em caso de erro crítico"""
    try:
        pdf = PDFReport()
        pdf.add_page()
        pdf.set_font('Arial', 'B', 16)
        pdf.cell(0, 40, 'RELATÓRIO DE CONCILIAÇÃO - ERRO', 0, 1, 'C')
        pdf.set_font('Arial', '', 12)
        pdf.multi_cell(0, 10, f"Empresa: {pdf.clean_text(empresa_nome)}")
        pdf.multi_cell(0, 10, f"Contador: {pdf.clean_text(contador_nome)}")
        pdf.multi_cell(0, 10, f"Data: {datetime.now().strftime('%d/%m/%Y')}")
        pdf.ln(10)
        pdf.set_font('Arial', 'B', 14)
        pdf.multi_cell(0, 10, "OCORREU UM ERRO DURANTE A GERAÇÃO DO RELATÓRIO:")
        pdf.set_font('Arial', '', 10)
        pdf.multi_cell(0, 8, f"Erro: {pdf.clean_text(erro)}")
        pdf.multi_cell(0, 8, "Por favor, tente novamente ou entre em contato com o suporte.")
        pdf.ln(10)
        pdf.multi_cell(0, 8, "Informações técnicas para o suporte:")
        pdf.set_font('Arial', 'I', 8)
        pdf.multi_cell(0, 6, f"Timestamp: {datetime.now().isoformat()}")
        
        temp_dir = tempfile.gettempdir()
        pdf_path = os.path.join(temp_dir, f'relatorio_erro_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf')
        pdf.output(pdf_path)
        return pdf_path
    except Exception as e:
        # Fallback extremo - criar arquivo de texto simples
        temp_dir = tempfile.gettempdir()
        txt_path = os.path.join(temp_dir, f'relatorio_erro_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt')
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(f"RELATÓRIO DE CONCILIAÇÃO - ERRO\n")
            f.write(f"Empresa: {empresa_nome}\n")
            f.write(f"Contador: {contador_nome}\n")
            f.write(f"Data: {datetime.now().strftime('%d/%m/%Y')}\n")
            f.write(f"Erro original: {erro}\n")
            f.write(f"Erro no fallback: {str(e)}\n")
        return txt_path

def gerar_relatorio_analise(resultados_analise: Dict,
                          extrato_df: pd.DataFrame,
                          contabil_df: pd.DataFrame,
                          empresa_nome: str = "Empresa",
                          contador_nome: str = "Contador",
                          periodo: str = "",
                          observacoes: str = "",
                          formato: str = "completo",
                          divergencias_tabela: pd.DataFrame = None,
                          conta_analisada: str = None,
                          **kwargs) -> str:
    """
    Gera relatório de análise (não de conciliação)
    formato: 'completo' ou 'resumido'
    conta_analisada: Número da conta bancária analisada
    """
    try:
        print(f"🔧 INICIANDO GERAÇÃO DE RELATÓRIO - Formato: {formato}")
        print(f"   Empresa: {empresa_nome}")
        print(f"   Conta: {conta_analisada}")
        print(f"   Resultados: {len(resultados_analise.get('matches', []))} matches")
        print(f"   Observações: {observacoes[:100]}{'...' if len(observacoes) > 100 else ''}")
        
        # VALIDAÇÃO DE DADOS CRÍTICOS
        if resultados_analise is None:
            raise ValueError("Resultados da análise não fornecidos")
        
        if extrato_df is None or len(extrato_df) == 0:
            raise ValueError("DataFrame do extrato está vazio ou não fornecido")
            
        if contabil_df is None or len(contabil_df) == 0:
            raise ValueError("DataFrame contábil está vazio ou não fornecido")
        
        pdf = PDFReport()
        
        # Página 1: Capa (comum para ambos os formatos)
        pdf.add_page()
        pdf.set_font('Arial', 'B', 20)
        pdf.cell(0, 40, 'RELATÓRIO DE ANÁLISE DE CORRESPONDÊNCIAS', 0, 1, 'C')
        pdf.set_font('Arial', 'B', 16)
        pdf.cell(0, 20, pdf.clean_text(empresa_nome), 0, 1, 'C')
        
        # INCLUIR INFORMAÇÃO DA CONTA NA CAPA
        pdf.set_font('Arial', 'B', 14)
        if conta_analisada and conta_analisada != "Não identificada":
            pdf.cell(0, 10, f'Conta Analisada: {conta_analisada}', 0, 1, 'C')
        
        pdf.set_font('Arial', '', 12)
        pdf.cell(0, 10, f'Período: {periodo}', 0, 1, 'C')
        pdf.cell(0, 10, f'Analista: {pdf.clean_text(contador_nome)}', 0, 1, 'C')
        pdf.cell(0, 10, f'Data de geração: {datetime.now().strftime("%d/%m/%Y")}', 0, 1, 'C')
        pdf.cell(0, 10, f'Formato: {formato.upper()}', 0, 1, 'C')
        
        pdf.ln(20)
        pdf.add_page()
        
        # Sumário Executivo (comum para ambos os formatos)
        pdf.chapter_title('RELATÓRIO DE ANÁLISE - CORRESPONDÊNCIAS IDENTIFICADAS')
        
        total_matches = len(resultados_analise.get('matches', []))
        total_excecoes = len(resultados_analise.get('excecoes', []))
        total_extrato = len(extrato_df) if extrato_df is not None else 0
        total_contabil = len(contabil_df) if contabil_df is not None else 0
        
        # INCLUIR CONTA NO SUMÁRIO EXECUTIVO
        resumo_texto = f"""
        ESTE É UM RELATÓRIO DE ANÁLISE E IDENTIFICAÇÃO DE CORRESPONDÊNCIAS
        
        CONTA ANALISADA: {conta_analisada if conta_analisada else "Não especificada"}
        
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
        """
        
        pdf.chapter_body(resumo_texto)
        
        # NOVA SEÇÃO: OBSERVAÇÕES DO USUÁRIO
        if observacoes and observacoes.strip():
            pdf.ln(5)
            pdf.set_font('Arial', 'B', 12)
            pdf.cell(0, 10, 'OBSERVAÇÕES E CONTEXTO ADICIONAL:', 0, 1)
            pdf.set_font('Arial', '', 10)
            
            # FORMATAR OBSERVAÇÕES COM MESMA FORMATAÇÃO DO RESTO DO RELATÓRIO
            observacoes_formatadas = pdf.clean_text(observacoes)
            
            # Usar a mesma abordagem do chapter_body para consistência
            linhas = observacoes_formatadas.split('\n')
            for linha in linhas:
                if linha.strip():
                    # Adicionar indentação igual às outras seções
                    pdf.cell(10)  # Indentação de 10 unidades
                    pdf.multi_cell(0, 6, linha.strip())
                else:
                    pdf.ln(3)  # Espaço menor entre parágrafos
            
            pdf.ln(5)
        
        resumo_final = """
        ATENÇÃO: Este relatório apresenta CORRESPONDÊNCIAS IDENTIFICADAS que devem ser validadas 
        manualmente pelo contador antes da conciliação final.
        """
        
        pdf.chapter_body(resumo_final)
        
        # Página 2: Estatísticas (comum para ambos os formatos)
        pdf.add_page()
        pdf.chapter_title('ESTATÍSTICAS DETALHADAS')
        
        # INCLUIR CONTA NAS ESTATÍSTICAS
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, f'CONTA: {conta_analisada if conta_analisada else "Não especificada"}', 0, 1)
        pdf.set_font('Arial', '', 10)
        
        # Métricas principais
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, 'MÉTRICAS PRINCIPAIS:', 0, 1)
        pdf.set_font('Arial', '', 10)
        
        taxa_cobertura = (total_matches / total_extrato * 100) if total_extrato > 0 else 0
        
        # CÁLCULOS SEGUROS DE VALORES
        try:
            valor_total_extrato_absoluto = extrato_df['valor'].abs().sum() if 'valor' in extrato_df.columns else 0
            valor_total_extrato = extrato_df['valor'].sum() if 'valor' in extrato_df.columns else 0
            valor_total_contabil = contabil_df['valor'].sum() if 'valor' in contabil_df.columns else 0
        except Exception as e:
            print(f"⚠️ Erro no cálculo de valores: {e}")
            valor_total_extrato_absoluto = 0
            valor_total_extrato = 0
            valor_total_contabil = 0
        
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
        - Correspondências 1:1: {len([m for m in resultados_analise.get('matches', []) if m.get('tipo_match') == '1:1'])}
        - Correspondências 1:N: {len([m for m in resultados_analise.get('matches', []) if m.get('tipo_match') == '1:N'])}
        - Correspondências N:1: {len([m for m in resultados_analise.get('matches', []) if m.get('tipo_match') == 'N:1'])}
        
        EFETIVIDADE POR CAMADA:
        - Correspondências exatas: {len([m for m in resultados_analise.get('matches', []) if m.get('camada') == 'exata'])}
        - Correspondências por similaridade: {len([m for m in resultados_analise.get('matches', []) if m.get('camada') == 'heuristica'])}
        - Correspondências complexas: {len([m for m in resultados_analise.get('matches', []) if m.get('camada') == 'ia'])}
        """
        
        pdf.chapter_body(estatisticas_texto)
        
        # CONTEÚDO ESPECÍFICO PARA RELATÓRIO COMPLETO
        if formato == 'completo':
            # Página 3: Correspondências Identificadas (apenas no completo)
            if resultados_analise.get('matches'):
                pdf.add_page()
                pdf.chapter_title('CORRESPONDÊNCIAS IDENTIFICADAS - DETALHES COMPLETOS')
                
                headers = ['ID', 'Tipo', 'Camada', 'Confiança', 'Valor Total', 'Transação Bancária', 'Lançamento Contábil']
                col_widths = [10, 20, 25, 20, 30, 30, 30]
                
                pdf.set_font('Arial', 'B', 8)
                for i, header in enumerate(headers):
                    pdf.cell(col_widths[i], 8, header, 1, 0, 'C')
                pdf.ln()
                
                pdf.set_font('Arial', '', 7)
                for i, match in enumerate(resultados_analise['matches']):
                    pdf.cell(col_widths[0], 6, str(i + 1), 1, 0, 'C')
                    pdf.cell(col_widths[1], 6, match.get('tipo_match', 'N/A'), 1, 0, 'C')
                    pdf.cell(col_widths[2], 6, match.get('camada', 'N/A'), 1, 0, 'C')
                    pdf.cell(col_widths[3], 6, f"{match.get('confianca', 0)}%", 1, 0, 'C')
                    pdf.cell(col_widths[4], 6, f"R$ {match.get('valor_total', 0):.2f}", 1, 0, 'C')
                    pdf.cell(col_widths[5], 6, str(len(match.get('ids_extrato', []))), 1, 0, 'C')
                    pdf.cell(col_widths[6], 6, str(len(match.get('ids_contabil', []))), 1, 0, 'C')
                    pdf.ln()
                
                pdf.ln(10)
                pdf.chapter_title('PRINCIPAIS CORRESPONDÊNCIAS - DETALHES')
                
                for i, match in enumerate(resultados_analise['matches']):
                    pdf.set_font('Arial', 'B', 9)
                    pdf.cell(0, 8, f'Correspondência {i + 1}: {match.get("tipo_match", "N/A")} - {match.get("camada", "N/A")}', 0, 1)
                    pdf.set_font('Arial', '', 8)
                    pdf.multi_cell(0, 4, f'Justificativa: {pdf.clean_text(match.get("explicacao", "Sem explicação"))}')
                    pdf.multi_cell(0, 4, f'Valor: R$ {match.get("valor_total", 0):.2f} | Confiança: {match.get("confianca", 0)}%')       
                    
                    # TENTAR OBTER TRANSAÇÕES COM TRATAMENTO DE ERRO
                    try:
                        if extrato_df is not None and 'id' in extrato_df.columns:
                            transacoes_extrato = extrato_df[extrato_df['id'].isin(match.get('ids_extrato', []))]
                            pdf.multi_cell(0, 4, f'Transações bancárias: {len(transacoes_extrato)}')
                            for _, trans in transacoes_extrato.iterrows():
                                data_str = trans['data'].strftime('%d/%m') if hasattr(trans.get('data'), 'strftime') else str(trans.get('data', 'N/A'))
                                valor_original = trans.get('valor_original', trans.get('valor', 0))
                                pdf.multi_cell(0, 3, f'  - R$ {valor_original:,.2f} | {data_str} | {pdf.clean_text(trans.get("descricao", "N/A")[:30])}')
                        
                        if contabil_df is not None and 'id' in contabil_df.columns:
                            transacoes_contabil = contabil_df[contabil_df['id'].isin(match.get('ids_contabil', []))]
                            pdf.multi_cell(0, 4, f'Lançamentos contábeis: {len(transacoes_contabil)}')
                            for _, lanc in transacoes_contabil.iterrows():
                                data_str = lanc['data'].strftime('%d/%m') if hasattr(lanc.get('data'), 'strftime') else str(lanc.get('data', 'N/A'))
                                valor_original = lanc.get('valor_original', lanc.get('valor', 0))
                                pdf.multi_cell(0, 3, f'  - R$ {valor_original:,.2f} | {data_str} | {pdf.clean_text(lanc.get("descricao", "N/A")[:30])}')
                    except Exception as e:
                        pdf.multi_cell(0, 4, f'Erro ao carregar detalhes: {str(e)}')
                    
                    pdf.ln(5)

        else:  # RELATÓRIO RESUMIDO
            # Página 3: Correspondências Resumidas
            if resultados_analise.get('matches'):
                pdf.add_page()
                pdf.chapter_title('CORRESPONDÊNCIAS IDENTIFICADAS - VISÃO RESUMIDA')
                
                pdf.set_font('Arial', '', 9)
                pdf.multi_cell(0, 5, f'Total de correspondências identificadas: {len(resultados_analise["matches"])}')
                
                # Apenas estatísticas resumidas no relatório resumido
                tipos_match = {
                    '1:1': len([m for m in resultados_analise['matches'] if m.get('tipo_match') == '1:1']),
                    '1:N': len([m for m in resultados_analise['matches'] if m.get('tipo_match') == '1:N']),
                    'N:1': len([m for m in resultados_analise['matches'] if m.get('tipo_match') == 'N:1'])
                }
                
                pdf.multi_cell(0, 5, f'Distribuição: 1:1 ({tipos_match["1:1"]}), 1:N ({tipos_match["1:N"]}), N:1 ({tipos_match["N:1"]})')                
                
                if resultados_analise['matches']:
                    pdf.ln(5)
                    pdf.set_font('Arial', 'B', 10)
                    pdf.cell(0, 8, 'TODAS AS CORRESPONDÊNCIAS IDENTIFICADAS:', 0, 1)
                    
                    for i, match in enumerate(resultados_analise['matches']):
                        pdf.set_font('Arial', 'B', 9)
                        pdf.cell(0, 6, f'{i+1}. {match.get("tipo_match", "N/A")} - Confiança: {match.get("confianca", 0)}% - Valor: R$ {match.get("valor_total", 0):.2f}', 0, 1)
                        pdf.set_font('Arial', '', 8)
                        pdf.multi_cell(0, 4, f'   {pdf.clean_text(match.get("explicacao", "Sem explicação")[:100])}...')
                        pdf.ln(2)

                
        
        # Página de Divergências
        if divergencias_tabela is not None and not divergencias_tabela.empty:
            try:
                pdf.add_page()
                
                if formato == 'completo':
                    pdf.chapter_title('DIVERGÊNCIAS IDENTIFICADAS - ANÁLISE COMPLETA')
                else:
                    pdf.chapter_title('DIVERGÊNCIAS IDENTIFICADAS - RESUMO')
                
                # Separar as divergências por tipo com tratamento seguro
                transacoes_sem_correspondencia = pd.DataFrame()
                lancamentos_sem_correspondencia = pd.DataFrame()
                similaridades = pd.DataFrame()
                
                if 'Origem' in divergencias_tabela.columns:
                    transacoes_sem_correspondencia = divergencias_tabela[
                        divergencias_tabela['Origem'] == 'Extrato Bancário'
                    ]
                    lancamentos_sem_correspondencia = divergencias_tabela[
                        divergencias_tabela['Origem'] == 'Sistema Contábil'
                    ]
                
                if 'Similaridade' in divergencias_tabela.columns:
                    similaridades = divergencias_tabela[
                        divergencias_tabela['Similaridade'].notna()
                    ]
                
                # Tabela 1: Transações Bancárias sem Correspondência
                if not transacoes_sem_correspondencia.empty:
                    pdf.set_font('Arial', 'B', 12)
                    pdf.cell(0, 10, 'TRANSAÇÕES BANCÁRIAS SEM CORRESPONDÊNCIA:', 0, 1)
                    
                    headers = ['Data', 'Valor', 'Descrição', 'Status']
                    col_widths = [25, 25, 80, 30]
                    
                    pdf.set_font('Arial', 'B', 8)
                    for i, header in enumerate(headers):
                        pdf.cell(col_widths[i], 8, header, 1, 0, 'C')
                    pdf.ln()
                    
                    pdf.set_font('Arial', '', 7)
                    for _, row in transacoes_sem_correspondencia.head(20).iterrows():  # Limitar a 20 itens
                        pdf.cell(col_widths[0], 6, str(row.get('Data', '')), 1, 0, 'C')
                        pdf.cell(col_widths[1], 6, str(row.get('Valor', '')), 1, 0, 'C')
                        pdf.cell(col_widths[2], 6, pdf.clean_text(str(row.get('Descrição', ''))[:40]), 1, 0, 'L')
                        pdf.cell(col_widths[3], 6, str(row.get('Status', '')), 1, 0, 'C')
                        pdf.ln()
                    
                    pdf.ln(5)
                    pdf.set_font('Arial', 'I', 8)
                    pdf.cell(0, 6, f'Total de transações sem correspondência: {len(transacoes_sem_correspondencia)}', 0, 1)
                    pdf.ln(5)
                
                # Tabela 2: Lançamentos Contábeis sem Correspondência
                if not lancamentos_sem_correspondencia.empty:
                    pdf.set_font('Arial', 'B', 12)
                    pdf.cell(0, 10, 'LANÇAMENTOS CONTÁBEIS SEM MOVIMENTAÇÃO BANCÁRIA:', 0, 1)
                    
                    headers = ['Data', 'Valor', 'Descrição', 'Status']
                    col_widths = [25, 25, 80, 30]
                    
                    pdf.set_font('Arial', 'B', 8)
                    for i, header in enumerate(headers):
                        pdf.cell(col_widths[i], 8, header, 1, 0, 'C')
                    pdf.ln()
                    
                    pdf.set_font('Arial', '', 7)
                    for _, row in lancamentos_sem_correspondencia.head(20).iterrows():  # Limitar a 20 itens
                        pdf.cell(col_widths[0], 6, str(row.get('Data', '')), 1, 0, 'C')
                        pdf.cell(col_widths[1], 6, str(row.get('Valor', '')), 1, 0, 'C')
                        pdf.cell(col_widths[2], 6, pdf.clean_text(str(row.get('Descrição', ''))[:40]), 1, 0, 'L')
                        pdf.cell(col_widths[3], 6, str(row.get('Status', '')), 1, 0, 'C')
                        pdf.ln()
                    
                    pdf.ln(5)
                    pdf.set_font('Arial', 'I', 8)
                    pdf.cell(0, 6, f'Total de lançamentos sem correspondência: {len(lancamentos_sem_correspondencia)}', 0, 1)
                    pdf.ln(5)
                
                # Tabela 3: Similaridades
                if not similaridades.empty:
                    pdf.set_font('Arial', 'B', 12)
                    pdf.cell(0, 10, 'POSSÍVEIS CORRESPONDÊNCIAS POR SIMILARIDADE:', 0, 1)
                    
                    # Layout otimizado para texto completo
                    headers = ['Similaridade', 'Valor Bancário', 'Descrição Bancária', 'Valor Contábil', 'Descrição Contábil', 'Diferença']
                    col_widths = [18, 24, 50, 24, 50, 16]
                    
                    pdf.set_font('Arial', 'B', 8)
                    for i, header in enumerate(headers):
                        pdf.cell(col_widths[i], 8, header, 1, 0, 'C')
                    pdf.ln()
                    
                    pdf.set_font('Arial', '', 7)
                    for _, row in similaridades.head(10).iterrows():  # Reduzir para 10 itens para caber texto completo
                        # Similaridade
                        pdf.cell(col_widths[0], 6, str(row.get('Similaridade', '')), 1, 0, 'C')
                        
                        # Valor Bancário
                        pdf.cell(col_widths[1], 6, str(row.get('Valor_Bancário', '')), 1, 0, 'C')
                        
                        # Descrição Bancária COMPLETA
                        desc_bancario = pdf.clean_text(str(row.get('Descrição_Bancário', '')))
                        # Não truncar - deixar texto completo
                        pdf.cell(col_widths[2], 6, desc_bancario, 1, 0, 'L')
                        
                        # Valor Contábil
                        pdf.cell(col_widths[3], 6, str(row.get('Valor_Contábil', '')), 1, 0, 'C')
                        
                        # Descrição Contábil COMPLETA
                        desc_contabil = pdf.clean_text(str(row.get('Descrição_Contábil', '')))
                        # Não truncar - deixar texto completo
                        pdf.cell(col_widths[4], 6, desc_contabil, 1, 0, 'L')
                        
                        # Diferença
                        pdf.cell(col_widths[5], 6, str(row.get('Diferença_Valor', '')), 1, 0, 'C')
                        pdf.ln()
                    
                    pdf.ln(5)
                    pdf.set_font('Arial', 'I', 8)
                    pdf.cell(0, 6, f'Total de possíveis correspondências: {len(similaridades)} (mostrando 10 principais)', 0, 1)
                                    

            except Exception as e:
                print(f"⚠️ Erro na seção de divergências: {e}")
                pdf.add_page()
                pdf.chapter_title('ERRO NA GERAÇÃO DE DIVERGÊNCIAS')
                pdf.multi_cell(0, 8, f"Não foi possível gerar a seção de divergências: {str(e)}")
        
        # Página: Recomendações (comum para ambos)
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
               - Analisar transações sem correspondência
               - Verificar lançamentos sem movimento bancário
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
        
        # INCLUIR OBSERVAÇÕES NAS RECOMENDAÇÕES SE HOUVER
        if observacoes and observacoes.strip():
            recomendacoes_texto += f"""
            
            OBSERVAÇÕES E CONTEXTO INFORMADO:
            {observacoes}
            """
        
        recomendacoes_texto += """
        
        OBSERVAÇÕES IMPORTANTES:
        - Este relatório é uma FERRAMENTA DE AUXÍLIO
        - Todas as correspondências devem ser VALIDADAS MANUALMENTE
        - A responsabilidade final pela conciliação é do contador
        - Mantenha documentação adequada para auditoria
        """
        
        pdf.chapter_body(recomendacoes_texto)

        # Na página final: Incluir conta nas informações de auditoria
        pdf.add_page()
        pdf.chapter_title('INFORMAÇÕES DE AUDITORIA')
        
        auditoria_texto = f"""
        INFORMAÇÕES PARA AUDITORIA:
        
        - Conta analisada: {conta_analisada if conta_analisada else "Não especificada"}
        - Empresa: {empresa_nome}
        - Período: {periodo}
        - Analista: {contador_nome}
        - Data de geração: {datetime.now().strftime("%d/%m/%Y %H:%M")}
        - Total de transações: {total_extrato}
        - Total de lançamentos: {total_contabil}
        - Correspondências identificadas: {total_matches}
        - Divergências: {total_excecoes}
        """
        
        # INCLUIR OBSERVAÇÕES NA AUDITORIA SE HOUVER
        if observacoes and observacoes.strip():
            auditoria_texto += f"""
        - Observações: {observacoes[:200]}{'...' if len(observacoes) > 200 else ''}
            """
        
        auditoria_texto += """
        
        Este relatório foi gerado automaticamente pelo Sistema de Conciliação Bancária e deve ser arquivado junto
        com a documentação contábil do período.
        """
        
        pdf.chapter_body(auditoria_texto)
        
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
            print(f"✅ RELATÓRIO GERADO COM SUCESSO: {pdf_path}")
            return pdf_path
            
        except Exception as e:
            print(f"❌ ERRO CRÍTICO ao salvar PDF: {str(e)}")
            print(f"🔍 Stack trace: {traceback.format_exc()}")
            
            # Tentar fallback
            return _gerar_relatorio_fallback(empresa_nome, contador_nome, str(e))
            
    except Exception as e:
        # Log de erro mais detalhado
        print(f"❌ ERRO CRÍTICO ao gerar relatório: {str(e)}")
        print(f"🔍 Stack trace: {traceback.format_exc()}")
        
        # Criar relatório de fallback
        return _gerar_relatorio_fallback(empresa_nome, contador_nome, str(e))

def _abreviar_tipo_divergencia(tipo_original):
    """Abrevia tipos longos de divergência para melhor visualização na tabela - TERMINOLOGIA MELHORADA"""
    abreviacoes = {
        'MOVIMENTAÇÃO_BANCÁRIA_SEM_LANÇAMENTO': 'Mov. Bancária s/Lançamento',
        'LANÇAMENTO_CONTÁBIL_SEM_MOVIMENTAÇÃO': 'Lançamento s/Mov. Bancária',
        'DIFERENÇA_DE_SALDO': 'Dif. Saldo',
        'TRANSAÇÃO_SEM_CORRESPONDÊNCIA': 'Transação s/Correspondência',
        'LANÇAMENTO_SEM_CORRESPONDÊNCIA': 'Lançamento s/Correspondência'
    }
    return abreviacoes.get(tipo_original, tipo_original)