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
        # Cabeçalho do relatório
        self.set_font('Arial', 'B', 16)
        self.cell(0, 10, 'RELATORIO DE CONCILIACAO BANCARIA', 0, 1, 'C')
        self.set_font('Arial', 'I', 10)
        self.cell(0, 5, f'Gerado em: {datetime.now().strftime("%d/%m/%Y %H:%M")}', 0, 1, 'C')
        self.ln(5)
    
    def footer(self):
        # Rodapé do relatório
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Pagina {self.page_no()}', 0, 0, 'C')
    
    def chapter_title(self, title):
        # Título de capítulo
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, self.clean_text(title), 0, 1, 'L')
        self.ln(2)
    
    def chapter_body(self, body):
        # Corpo do texto
        self.set_font('Arial', '', 10)
        cleaned_body = self.clean_text(body)
        self.multi_cell(0, 6, cleaned_body)
        self.ln()
    
    def clean_text(self, text):
        """Remove TODOS os caracteres especiais e Unicode"""
        if not text:
            return ""
        
        # Substituir TODOS os caracteres problemáticos
        text = str(text)
        
        # Remover ou substituir caracteres Unicode específicos
        replacements = {
            '✅': '[OK]', '✔': '[OK]', '✓': '[OK]', '☑': '[OK]',
            '❌': '[ERRO]', '✖': '[ERRO]', '❎': '[ERRO]',
            '⚠': '[ATENCAO]', '⚡': '[RAPIDO]', '🎯': '[FOCO]',
            '📊': '[METRICAS]', '📋': '[RELATORIO]', '🔍': '[ANALISE]',
            '💡': '[DICA]', '🚀': '[RAPIDO]', '⭐': '[DESTAQUE]',
            '•': '-', '·': '-', '–': '-', '—': '-', '‣': '-', '⁃': '-',
            '“': '"', '”': '"', '‘': "'", '’': "'", '´': "'", '`': "'",
            'á': 'a', 'à': 'a', 'ã': 'a', 'â': 'a', 'ä': 'a',
            'é': 'e', 'è': 'e', 'ê': 'e', 'ë': 'e',
            'í': 'i', 'ì': 'i', 'î': 'i', 'ï': 'i',
            'ó': 'o', 'ò': 'o', 'õ': 'o', 'ô': 'o', 'ö': 'o',
            'ú': 'u', 'ù': 'u', 'û': 'u', 'ü': 'u',
            'ç': 'c', 'ñ': 'n',
            'Á': 'A', 'À': 'A', 'Ã': 'A', 'Â': 'A', 'Ä': 'A',
            'É': 'E', 'È': 'E', 'Ê': 'E', 'Ë': 'E',
            'Í': 'I', 'Ì': 'I', 'Î': 'I', 'Ï': 'I',
            'Ó': 'O', 'Ò': 'O', 'Õ': 'O', 'Ô': 'O', 'Ö': 'O',
            'Ú': 'U', 'Ù': 'U', 'Û': 'U', 'Ü': 'U',
            'Ç': 'C', 'Ñ': 'N'
        }
        
        # Aplicar substituições
        for old_char, new_char in replacements.items():
            text = text.replace(old_char, new_char)
        
        # Remover qualquer outro caractere não-ASCII
        text = text.encode('ascii', 'ignore').decode('ascii')
        
        return text
    
    def add_table(self, data, headers):
        # Adicionar tabela simples
        self.set_font('Arial', 'B', 10)
        
        # Larguras das colunas ajustadas
        col_widths = [15, 20, 25, 25, 30, 25, 25]
        
        # Cabeçalho
        for i, header in enumerate(headers):
            self.cell(col_widths[i], 10, self.clean_text(header), 1, 0, 'C')
        self.ln()
        
        # Dados
        self.set_font('Arial', '', 8)
        for row in data:
            for i, item in enumerate(row):
                self.cell(col_widths[i], 8, self.clean_text(str(item)), 1, 0, 'C')
            self.ln()

def gerar_relatorio_completo(matches_aprovados: List[Dict],
                           matches_rejeitados: List[Dict],
                           excecoes: List[Dict],
                           extrato_df: pd.DataFrame,
                           contabil_df: pd.DataFrame,
                           empresa_nome: str = "Empresa",
                           contador_nome: str = "Contador",
                           periodo: str = "",
                           observacoes: str = "",
                           formato: str = "completo") -> str:
    """
    Gera relatório PDF completo da conciliação
    """
    
    pdf = PDFReport()
    
    # Página 1: Capa e Sumário Executivo
    pdf.add_page()
    
    # Capa
    pdf.set_font('Arial', 'B', 20)
    pdf.cell(0, 40, 'RELATORIO DE CONCILIACAO - COMPLETO', 0, 1, 'C')
    pdf.set_font('Arial', 'B', 16)
    pdf.cell(0, 20, pdf.clean_text(empresa_nome), 0, 1, 'C')
    pdf.set_font('Arial', '', 12)
    pdf.cell(0, 10, f'Periodo: {periodo}', 0, 1, 'C')
    pdf.cell(0, 10, f'Responsavel: {pdf.clean_text(contador_nome)}', 0, 1, 'C')
    pdf.cell(0, 10, f'Data de geracao: {datetime.now().strftime("%d/%m/%Y")}', 0, 1, 'C')
    
    pdf.ln(20)
    
    # Sumário Executivo
    pdf.chapter_title('SUMARIO EXECUTIVO - COMPLETO')
    
    total_transacoes = len(extrato_df)
    total_lancamentos = len(contabil_df)
    total_conciliado = len(matches_aprovados)
    valor_total_conciliado = sum(match['valor_total'] for match in matches_aprovados)
    
    resumo_texto = f"""
    Este relatorio apresenta os resultados completos do processo de conciliacao bancaria referente ao periodo {periodo}.

    RESUMO ESTATISTICO COMPLETO:
    - Transacoes bancarias analisadas: {total_transacoes}
    - Lancamentos contabeis analisados: {total_lancamentos}
    - Conciliações validadas: {total_conciliado}
    - Valor total conciliado: R$ {valor_total_conciliado:,.2f}
    - Taxa de sucesso: {(total_conciliado/max(total_transacoes, 1)*100):.1f}%
    - Excecoes identificadas: {len(excecoes)}
    - Matches rejeitados: {len(matches_rejeitados)}

    METODOLOGIA DETALHADA:
    O processo utilizou uma abordagem em tres camadas:
    1. Matching Exato: Identificadores unicos (TXID, NSU, Nosso Numero)
    2. Matching Heuristico: Tolerancias de data e valor + similaridade textual
    3. Inteligencia Artificial: Casos complexos e analise semantica
    """
    
    pdf.chapter_body(resumo_texto)
    
    # Página 2: Detalhes das Conciliações
    pdf.add_page()
    pdf.chapter_title('CONCILIACOES APROVADAS - DETALHADAS')
    
    if matches_aprovados:
        # Tabela de conciliações
        headers = ['ID', 'Tipo', 'Camada', 'Confianca', 'Valor', 'Trans Bank', 'Lanc Cont']
        
        # Calcular larguras dinamicamente
        col_widths = [15, 20, 25, 25, 30, 25, 25]
        
        # Cabeçalho
        pdf.set_font('Arial', 'B', 9)
        for i, header in enumerate(headers):
            pdf.cell(col_widths[i], 8, header, 1, 0, 'C')
        pdf.ln()
        
        # Dados
        pdf.set_font('Arial', '', 8)
        for i, match in enumerate(matches_aprovados):
            pdf.cell(col_widths[0], 6, str(i + 1), 1, 0, 'C')
            pdf.cell(col_widths[1], 6, match['tipo_match'], 1, 0, 'C')
            pdf.cell(col_widths[2], 6, match['camada'], 1, 0, 'C')
            pdf.cell(col_widths[3], 6, f"{match['confianca']}%", 1, 0, 'C')
            pdf.cell(col_widths[4], 6, f"R$ {match['valor_total']:.2f}", 1, 0, 'C')
            pdf.cell(col_widths[5], 6, str(len(match['ids_extrato'])), 1, 0, 'C')
            pdf.cell(col_widths[6], 6, str(len(match['ids_contabil'])), 1, 0, 'C')
            pdf.ln()
        
        # Detalhes das conciliações mais relevantes
        pdf.ln(10)
        pdf.chapter_title('DETALHES DAS PRINCIPAIS CONCILIACOES')
        
        for i, match in enumerate(matches_aprovados[:10]):
            pdf.set_font('Arial', 'B', 10)
            pdf.cell(0, 8, f'Conciliação {i + 1}: {match["tipo_match"]} - {match["camada"]}', 0, 1)
            pdf.set_font('Arial', '', 9)
            pdf.multi_cell(0, 5, f'Explicacao: {pdf.clean_text(match["explicacao"])}')
            pdf.multi_cell(0, 5, f'Valor: R$ {match["valor_total"]:.2f} | Confianca: {match["confianca"]}%')
            pdf.ln(3)
    else:
        pdf.chapter_body('Nenhuma conciliacao aprovada para o periodo.')
    
    # Página 3: Exceções e Recomendações
    if excecoes:
        pdf.add_page()
        pdf.chapter_title('EXCECOES E DIVERGENCIAS - DETALHES')
        
        for i, excecao in enumerate(excecoes):
            pdf.set_font('Arial', 'B', 10)
            pdf.cell(0, 8, f'Excecao {i + 1}: {excecao["tipo"]} - {excecao["severidade"]}', 0, 1)
            pdf.set_font('Arial', '', 9)
            pdf.multi_cell(0, 5, f'Descricao: {pdf.clean_text(excecao["descricao"])}')
            pdf.multi_cell(0, 5, f'Acao Sugerida: {pdf.clean_text(excecao["acao_sugerida"])}')
            pdf.multi_cell(0, 5, f'Transacoes envolvidas: {len(excecao["ids_envolvidos"])}')
            pdf.ln(5)
    
    # Página 4: Matches Rejeitados
    if matches_rejeitados:
        pdf.add_page()
        pdf.chapter_title('MATCHES REJEITADOS - ANALISE')
        
        pdf.set_font('Arial', '', 10)
        pdf.multi_cell(0, 6, f'Total de matches rejeitados: {len(matches_rejeitados)}')
        pdf.ln(5)
        
        for i, match in enumerate(matches_rejeitados[:5]):
            pdf.set_font('Arial', 'B', 9)
            pdf.cell(0, 8, f'Match Rejeitado {i + 1}: {match["tipo_match"]}', 0, 1)
            pdf.set_font('Arial', '', 8)
            pdf.multi_cell(0, 5, f'Razao: {pdf.clean_text(match.get("explicacao", "Nao especificada"))}')
            pdf.multi_cell(0, 5, f'Valor: R$ {match["valor_total"]:.2f} | Confianca: {match["confianca"]}%')
            pdf.ln(3)
    
    # Página 5: Observações e Assinatura
    pdf.add_page()
    pdf.chapter_title('OBSERVACOES E RECOMENDACOES COMPLETAS')
    
    if observacoes:
        pdf.chapter_body(f'OBSERVACOES:\n{pdf.clean_text(observacoes)}')
    else:
        pdf.chapter_body('Nenhuma observacao adicional fornecida.')
    
    pdf.ln(10)
    pdf.chapter_title('RECOMENDACOES DETALHADAS')
    
    recomendacoes = """
    1. Implementar as conciliacoes aprovadas no sistema contabil
    2. Investigar e resolver as excecoes identificadas
    3. Revisar processos para reduzir divergencias futuras
    4. Manter documentacao adequada para auditoria
    5. Realizar conciliacao mensalmente para melhor controle
    6. Analisar os matches rejeitados para melhorar o processo
    7. Documentar as lições aprendidas com as excecoes
    """
    
    pdf.chapter_body(recomendacoes)
    
    # Assinatura
    pdf.ln(20)
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 8, '_________________________', 0, 1, 'C')
    pdf.cell(0, 8, pdf.clean_text(contador_nome), 0, 1, 'C')
    pdf.cell(0, 8, 'Contador Responsavel', 0, 1, 'C')
    
    # Salvar PDF
    temp_dir = tempfile.gettempdir()
    pdf_path = os.path.join(temp_dir, f'relatorio_completo_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf')
    pdf.output(pdf_path)
    
    return pdf_path

def gerar_relatorio_resumido(matches_aprovados: List[Dict],
                           matches_rejeitados: List[Dict],
                           excecoes: List[Dict],
                           extrato_df: pd.DataFrame,
                           contabil_df: pd.DataFrame,
                           empresa_nome: str = "Empresa",
                           contador_nome: str = "Contador",
                           periodo: str = "",
                           observacoes: str = "") -> str:
    """Gera versão resumida do relatório - apenas informações essenciais"""
    
    pdf = PDFReport()
    
    # Página 1: Capa e Sumário Executivo
    pdf.add_page()
    
    # Capa
    pdf.set_font('Arial', 'B', 20)
    pdf.cell(0, 40, 'RELATORIO DE CONCILIACAO - RESUMIDO', 0, 1, 'C')
    pdf.set_font('Arial', 'B', 16)
    pdf.cell(0, 20, pdf.clean_text(empresa_nome), 0, 1, 'C')
    pdf.set_font('Arial', '', 12)
    pdf.cell(0, 10, f'Periodo: {periodo}', 0, 1, 'C')
    pdf.cell(0, 10, f'Responsavel: {pdf.clean_text(contador_nome)}', 0, 1, 'C')
    
    pdf.ln(20)
    
    # Sumário Executivo RESUMIDO
    pdf.chapter_title('SUMARIO EXECUTIVO RESUMIDO')
    
    total_conciliado = len(matches_aprovados)
    valor_total_conciliado = sum(match['valor_total'] for match in matches_aprovados)
    total_analisado = len(matches_aprovados) + len(matches_rejeitados)
    taxa_sucesso = (total_conciliado / total_analisado * 100) if total_analisado > 0 else 0
    
    resumo_texto = f"""
    RESUMO ESTATISTICO:
    - Conciliações validadas: {total_conciliado}
    - Valor total conciliado: R$ {valor_total_conciliado:,.2f}
    - Taxa de sucesso: {taxa_sucesso:.1f}%
    - Excecoes identificadas: {len(excecoes)}
    
    STATUS: CONCILIACAO REALIZADA COM SUCESSO
    
    PRINCIPAIS RESULTADOS:
    A conciliacao foi concluida com {total_conciliado} matches validados,
    totalizando R$ {valor_total_conciliado:,.2f} em transacoes conciliadas.
    """
    
    pdf.chapter_body(resumo_texto)
    
    # Apenas tabela resumida
    if matches_aprovados:
        pdf.ln(10)
        pdf.chapter_title('CONCILIACOES APROVADAS (RESUMO)')
        
        headers = ['ID', 'Tipo', 'Valor', 'Confianca']
        col_widths = [15, 25, 40, 30]
        
        # Cabeçalho
        pdf.set_font('Arial', 'B', 9)
        for i, header in enumerate(headers):
            pdf.cell(col_widths[i], 8, header, 1, 0, 'C')
        pdf.ln()
        
        # Dados
        pdf.set_font('Arial', '', 8)
        for i, match in enumerate(matches_aprovados):
            pdf.cell(col_widths[0], 6, str(i + 1), 1, 0, 'C')
            pdf.cell(col_widths[1], 6, match['tipo_match'], 1, 0, 'C')
            pdf.cell(col_widths[2], 6, f"R$ {match['valor_total']:.2f}", 1, 0, 'C')
            pdf.cell(col_widths[3], 6, f"{match['confianca']}%", 1, 0, 'C')
            pdf.ln()
    
    # Recomendações básicas
    pdf.ln(10)
    pdf.chapter_title('RECOMENDACOES BASICAS')
    
    recomendacoes = """
    1. Implementar conciliacoes aprovadas
    2. Verificar excecoes identificadas
    3. Manter documentacao
    """
    
    pdf.chapter_body(recomendacoes)
    
    # Assinatura simplificada
    pdf.ln(15)
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 8, '_________________________', 0, 1, 'C')
    pdf.cell(0, 8, pdf.clean_text(contador_nome), 0, 1, 'C')
    
    # Salvar PDF
    temp_dir = tempfile.gettempdir()
    pdf_path = os.path.join(temp_dir, f'relatorio_resumido_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf')
    pdf.output(pdf_path)
    
    return pdf_path

def gerar_relatorio_executivo(matches_aprovados: List[Dict],
                            matches_rejeitados: List[Dict],
                            excecoes: List[Dict],
                            extrato_df: pd.DataFrame,
                            contabil_df: pd.DataFrame,
                            empresa_nome: str = "Empresa",
                            contador_nome: str = "Contador",
                            periodo: str = "",
                            observacoes: str = "") -> str:
    """Gera versão executiva do relatório - foco em métricas e tomada de decisão"""
    
    pdf = PDFReport()
    
    # Página 1: Capa e Sumário Executivo
    pdf.add_page()
    
    # Capa
    pdf.set_font('Arial', 'B', 20)
    pdf.cell(0, 40, 'RELATORIO EXECUTIVO DE CONCILIACAO', 0, 1, 'C')
    pdf.set_font('Arial', 'B', 16)
    pdf.cell(0, 20, pdf.clean_text(empresa_nome), 0, 1, 'C')
    pdf.set_font('Arial', '', 12)
    pdf.cell(0, 10, f'Periodo: {periodo}', 0, 1, 'C')
    
    pdf.ln(20)
    
    # Sumário Executivo EXECUTIVO
    pdf.chapter_title('RELATORIO EXECUTIVO - VISAO GERAL')
    
    total_conciliado = len(matches_aprovados)
    valor_total_conciliado = sum(match['valor_total'] for match in matches_aprovados)
    total_analisado = len(matches_aprovados) + len(matches_rejeitados)
    taxa_sucesso = (total_conciliado / total_analisado * 100) if total_analisado > 0 else 0
    excecoes_criticas = len([e for e in excecoes if e.get('severidade') == 'ALTA'])
    
    resumo_texto = f"""
    METRICAS CHAVE PARA DECISAO:
    
    PERFORMANCE DA CONCILIACAO:
    - Taxa de sucesso: {taxa_sucesso:.1f}%
    - Valor financeiro conciliado: R$ {valor_total_conciliado:,.2f}
    - Volume de transacoes validadas: {total_conciliado}
    
    PONTOS DE ATENCAO:
    - Excecoes criticas: {excecoes_criticas}
    - Matches rejeitados: {len(matches_rejeitados)}
    
    STATUS EXECUTIVO:
    [OK] CONCILIACAO BEM-SUCEDIDA
    
    A operacao foi concluida com indicadores positivos,
    demonstrando eficacia no processo de conciliacao.
    """
    
    pdf.chapter_body(resumo_texto)
    
    # Apenas métricas principais e top conciliações
    if matches_aprovados:
        pdf.ln(10)
        pdf.chapter_title('PRINCIPAIS CONCILIACOES POR VALOR')
        
        # Apenas as 5 maiores conciliações
        maiores_matches = sorted(matches_aprovados, key=lambda x: x['valor_total'], reverse=True)[:5]
        
        for i, match in enumerate(maiores_matches):
            pdf.set_font('Arial', 'B', 10)
            pdf.cell(0, 8, f'Top {i + 1}: R$ {match["valor_total"]:,.2f}', 0, 1)
            pdf.set_font('Arial', '', 9)
            pdf.multi_cell(0, 5, f'Tipo: {match["tipo_match"]} | Confianca: {match["confianca"]}% | Camada: {match["camada"]}')
            pdf.ln(3)
    
    # Recomendações executivas
    pdf.ln(10)
    pdf.chapter_title('RECOMENDACOES EXECUTIVAS')
    
    recomendacoes = """
    1. APROVAR implementacao das conciliacoes validadas
    2. DESTINAR recursos para analise das excecoes criticas
    3. MANTER a periodicidade mensal do processo
    4. CONSIDERAR a automacao para ganhos de eficiencia
    """
    
    pdf.chapter_body(recomendacoes)
    
    # Assinatura executiva
    pdf.ln(20)
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 8, '_________________________', 0, 1, 'C')
    pdf.cell(0, 8, pdf.clean_text(contador_nome), 0, 1, 'C')
    pdf.cell(0, 8, 'Contador Responsavel', 0, 1, 'C')
    pdf.cell(0, 8, pdf.clean_text(empresa_nome), 0, 1, 'C')
    
    # Salvar PDF
    temp_dir = tempfile.gettempdir()
    pdf_path = os.path.join(temp_dir, f'relatorio_executivo_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf')
    pdf.output(pdf_path)
    
    return pdf_path