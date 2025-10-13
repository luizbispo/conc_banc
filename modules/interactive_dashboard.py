# modules/interactive_dashboard.py
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import plotly.figure_factory as ff
from plotly.subplots import make_subplots
import streamlit as st
from datetime import datetime
from typing import Dict, List, Any

class InteractiveDashboard:
    """Cria dashboards interativos para análise de dados de conciliação"""
    
    def __init__(self):
        self.color_palette = {
            'extrato': '#1f77b4',      # Azul
            'contabil': '#ff7f0e',     # Laranja
            'match': '#2ca02c',        # Verde
            'divergencia': '#d62728',  # Vermelho
            'texto': '#ffffff',        # BRANCO para texto no fundo escuro
            'fundo': '#0e1117',        # FUNDO ESCURO do Streamlit
            'grid': '#2a2a2a'          # Cinza escuro para grade
        }
    
    def create_reconciliation_overview(self, resultados_analise: Dict, extrato_df: pd.DataFrame, contabil_df: pd.DataFrame):
        """Cria visão geral da conciliação com múltiplos gráficos"""
        try:
            # Dados básicos
            total_extrato = len(extrato_df)
            total_contabil = len(contabil_df)
            total_matches = len(resultados_analise.get('matches', []))
            
            # Criar subplots
            fig = make_subplots(
                rows=2, cols=2,
                subplot_titles=(
                    '📊 Status da Conciliação', 
                    '🔍 Tipos de Correspondência',
                    '🎯 Distribuição de Confiança', 
                    '📈 Volume por Data'
                ),
                specs=[
                    [{"type": "pie"}, {"type": "bar"}],
                    [{"type": "histogram"}, {"type": "scatter"}]
                ],
                vertical_spacing=0.15,
                horizontal_spacing=0.1
            )
            
            # 1. Gráfico de Pizza - Status
            matched_extrato = total_matches
            unmatched_extrato = total_extrato - matched_extrato
            unmatched_contabil = total_contabil - matched_extrato
            
            fig.add_trace(
                go.Pie(
                    labels=['Correspondências', 'Divergências Extrato', 'Divergências Contábil'],
                    values=[matched_extrato, unmatched_extrato, unmatched_contabil],
                    marker=dict(colors=['#2ca02c', '#ff7f0e', '#d62728']),
                    name="Status Conciliação",
                    hole=0.4,
                    textinfo='percent+value',
                    textfont=dict(color='white', size=12)
                ),
                row=1, col=1
            )
            
            # 2. Gráfico de Barras - Tipos de Match
            if resultados_analise.get('matches'):
                tipos_match = {}
                for match in resultados_analise['matches']:
                    tipo = match.get('tipo_match', 'N/A')
                    tipos_match[tipo] = tipos_match.get(tipo, 0) + 1
                
                fig.add_trace(
                    go.Bar(
                        x=list(tipos_match.keys()),
                        y=list(tipos_match.values()),
                        marker_color='#17becf',
                        name="Tipos de Match",
                        text=list(tipos_match.values()),
                        textposition='auto',
                        textfont=dict(color='white')
                    ),
                    row=1, col=2
                )
            else:
                fig.add_trace(
                    go.Bar(x=['Nenhum'], y=[0], name="Sem matches"),
                    row=1, col=2
                )
            
            # 3. Histograma - Distribuição de Confiança
            if resultados_analise.get('matches'):
                confiancas = [match.get('confianca', 0) for match in resultados_analise['matches']]
                fig.add_trace(
                    go.Histogram(
                        x=confiancas,
                        nbinsx=10,
                        marker_color='#9467bd',
                        name="Confiança",
                        opacity=0.7
                    ),
                    row=2, col=1
                )
            
            # 4. Gráfico de Linhas - Volume por Data
            if 'data' in extrato_df.columns and not extrato_df.empty:
                try:
                    extrato_daily = extrato_df.groupby(extrato_df['data'].dt.date).agg({
                        'valor': ['count', 'sum']
                    }).reset_index()
                    
                    contabil_daily = contabil_df.groupby(contabil_df['data'].dt.date).agg({
                        'valor': ['count', 'sum']
                    }).reset_index()
                    
                    fig.add_trace(
                        go.Scatter(
                            x=extrato_daily['data'],
                            y=extrato_daily[('valor', 'count')],
                            mode='lines+markers',
                            name='Transações Extrato',
                            line=dict(color=self.color_palette['extrato'], width=3),
                            marker=dict(size=6)
                        ),
                        row=2, col=2
                    )
                    
                    fig.add_trace(
                        go.Scatter(
                            x=contabil_daily['data'],
                            y=contabil_daily[('valor', 'count')],
                            mode='lines+markers',
                            name='Lançamentos Contábil',
                            line=dict(color=self.color_palette['contabil'], width=3),
                            marker=dict(size=6)
                        ),
                        row=2, col=2
                    )
                except Exception as e:
                    st.warning(f"Não foi possível criar gráfico temporal: {e}")
            
            # Atualizar layout com fundo escuro
            fig.update_layout(
                height=700,
                title_text="📊 Dashboard de Conciliação - Visão Geral",
                title_font=dict(color='white', size=16),
                showlegend=True,
                template="plotly_dark",  # TEMA ESCURO
                font=dict(color='white', size=12),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)'
            )
            
            # Configurar cores dos eixos e títulos
            fig.update_xaxes(
                showgrid=True, 
                gridcolor='#2a2a2a', 
                color='white',
                title_font=dict(color='white')
            )
            fig.update_yaxes(
                showgrid=True, 
                gridcolor='#2a2a2a', 
                color='white',
                title_font=dict(color='white')
            )
            
            # Ajustar cores dos títulos dos subplots
            fig.update_annotations(
                font=dict(color='white', size=14)
            )
            
            return fig
            
        except Exception as e:
            st.error(f"Erro ao criar dashboard: {e}")
            return self._create_empty_figure("Erro ao gerar visualização")
    
    def create_timeline_analysis(self, extrato_df: pd.DataFrame, contabil_df: pd.DataFrame):
        """Cria análise temporal detalhada das transações"""
        try:
            fig = make_subplots(
                rows=2, cols=1,
                subplot_titles=(
                    '💰 Valor Diário (R$)',
                    '📦 Quantidade de Transações por Dia'
                ),
                vertical_spacing=0.25,  # ESPAÇAMENTO MÁXIMO
                row_heights=[0.5, 0.5]
            )
            
            # Preparar dados temporais
            extrato_daily = extrato_df.groupby(extrato_df['data'].dt.date).agg({
                'valor': ['sum', 'count', 'mean']
            }).reset_index()
            
            contabil_daily = contabil_df.groupby(contabil_df['data'].dt.date).agg({
                'valor': ['sum', 'count', 'mean']
            }).reset_index()
            
            # 1. Valor diário
            fig.add_trace(
                go.Scatter(
                    x=extrato_daily['data'],
                    y=extrato_daily[('valor', 'sum')].abs(),
                    mode='lines+markers',
                    name='Extrato Bancário',
                    line=dict(color=self.color_palette['extrato'], width=3),
                    marker=dict(size=6, color=self.color_palette['extrato'])
                ),
                row=1, col=1
            )
            
            fig.add_trace(
                go.Scatter(
                    x=contabil_daily['data'],
                    y=contabil_daily[('valor', 'sum')].abs(),
                    mode='lines+markers',
                    name='Lançamentos Contábeis',
                    line=dict(color=self.color_palette['contabil'], width=3),
                    marker=dict(size=6, color=self.color_palette['contabil'])
                ),
                row=1, col=1
            )
            
            # 2. Quantidade diária
            fig.add_trace(
                go.Bar(
                    x=extrato_daily['data'],
                    y=extrato_daily[('valor', 'count')],
                    name='Qtd. Extrato',
                    marker_color=self.color_palette['extrato'],
                    opacity=0.7,
                    text=extrato_daily[('valor', 'count')],
                    textposition='auto',
                    textfont=dict(color='white')
                ),
                row=2, col=1
            )
            
            fig.add_trace(
                go.Bar(
                    x=contabil_daily['data'],
                    y=contabil_daily[('valor', 'count')],
                    name='Qtd. Contábil',
                    marker_color=self.color_palette['contabil'],
                    opacity=0.7,
                    text=contabil_daily[('valor', 'count')],
                    textposition='auto',
                    textfont=dict(color='white')
                ),
                row=2, col=1
            )
            
            # Layout com fundo escuro e bom espaçamento
            fig.update_layout(
                height=750,  # ALTURA AUMENTADA
                title_text="📈 Análise Temporal Detalhada",
                title_font=dict(color='white', size=16),
                showlegend=True,
                template="plotly_dark",  # TEMA ESCURO
                font=dict(color='white', size=12),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                margin=dict(t=100, b=80, l=80, r=80, pad=30)  # MARGENS GENEROSAS
            )
            
            # Ajustar títulos dos subplots
            fig.update_annotations(
                font=dict(color='white', size=14),
                yshift=15  # Move os títulos para cima
            )
            
            # Configurar eixos com cores claras
            fig.update_xaxes(
                showgrid=True, 
                gridcolor='#2a2a2a', 
                color='white',
                title_font=dict(color='white')
            )
            fig.update_yaxes(
                showgrid=True, 
                gridcolor='#2a2a2a', 
                color='white',
                title_font=dict(color='white')
            )
            
            fig.update_yaxes(
                title_text="Valor (R$)", 
                row=1, col=1,
                title_font=dict(color='white')
            )
            fig.update_yaxes(
                title_text="Quantidade", 
                row=2, col=1,
                title_font=dict(color='white')
            )
            fig.update_xaxes(
                title_text="Data", 
                row=2, col=1,
                title_font=dict(color='white')
            )
            
            return fig
            
        except Exception as e:
            st.error(f"Erro na análise temporal: {e}")
            return self._create_empty_figure("Erro na análise temporal")
    
    def create_value_distribution(self, extrato_df: pd.DataFrame, contabil_df: pd.DataFrame):
        """Cria visualização da distribuição de valores"""
        try:
            fig = make_subplots(
                rows=1, cols=2,
                subplot_titles=(
                    '📊 Distribuição de Valores - Extrato',
                    '📊 Distribuição de Valores - Contábil'
                )
            )
            
            # Box plot para extrato
            fig.add_trace(
                go.Box(
                    y=extrato_df['valor'].abs(),
                    name='Extrato',
                    marker_color=self.color_palette['extrato'],
                    boxpoints='outliers'
                ),
                row=1, col=1
            )
            
            # Box plot para contábil
            fig.add_trace(
                go.Box(
                    y=contabil_df['valor'].abs(),
                    name='Contábil',
                    marker_color=self.color_palette['contabil'],
                    boxpoints='outliers'
                ),
                row=1, col=2
            )
            
            fig.update_layout(
                height=400,
                title_text="📦 Distribuição de Valores (Box Plot)",
                title_font=dict(color='white', size=16),
                showlegend=False,
                template="plotly_dark",  # TEMA ESCURO
                font=dict(color='white', size=12),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)'
            )
            
            # Configurar eixos
            fig.update_xaxes(
                color='white',
                title_font=dict(color='white')
            )
            fig.update_yaxes(
                title_text="Valor Absoluto (R$)", 
                type="log",
                color='white',
                title_font=dict(color='white')
            )
            
            # Ajustar cores dos títulos dos subplots
            fig.update_annotations(
                font=dict(color='white', size=14)
            )
            
            return fig
            
        except Exception as e:
            return self._create_empty_figure("Erro na distribuição de valores")
    
    def create_confidence_analysis(self, resultados_analise: Dict):
        """Análise detalhada das confianças dos matches"""
        try:
            if not resultados_analise.get('matches'):
                return self._create_empty_figure("Nenhuma correspondência para análise")
            
            matches_df = pd.DataFrame(resultados_analise['matches'])
            
            fig = make_subplots(
                rows=1, cols=2,
                subplot_titles=(
                    '🎯 Confiança por Camada de Análise',
                    '📈 Distribuição por Tipo de Match'
                )
            )
            
            # Box plot por camada
            camadas = matches_df.groupby('camada')['confianca'].apply(list)
            for i, (camada, valores) in enumerate(camadas.items()):
                fig.add_trace(
                    go.Box(
                        y=valores,
                        name=camada,
                        marker_color=px.colors.qualitative.Set3[i % len(px.colors.qualitative.Set3)]
                    ),
                    row=1, col=1
                )
            
            # Scatter plot por tipo
            for tipo in matches_df['tipo_match'].unique():
                tipo_data = matches_df[matches_df['tipo_match'] == tipo]
                fig.add_trace(
                    go.Scatter(
                        x=tipo_data['tipo_match'],
                        y=tipo_data['confianca'],
                        mode='markers',
                        name=tipo,
                        marker=dict(
                            size=8, 
                            opacity=0.6,
                            color=px.colors.qualitative.Set1[list(matches_df['tipo_match'].unique()).index(tipo) % len(px.colors.qualitative.Set1)]
                        )
                    ),
                    row=1, col=2
                )
            
            fig.update_layout(
                height=500,
                title_text="🔍 Análise de Confiança das Correspondências",
                title_font=dict(color='white', size=16),
                showlegend=True,
                template="plotly_dark",  # TEMA ESCURO
                font=dict(color='white', size=12),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)'
            )
            
            # Configurar eixos
            fig.update_xaxes(
                color='white',
                title_font=dict(color='white')
            )
            fig.update_yaxes(
                color='white',
                title_font=dict(color='white')
            )
            
            # Ajustar cores dos títulos dos subplots
            fig.update_annotations(
                font=dict(color='white', size=14)
            )
            
            return fig
            
        except Exception as e:
            return self._create_empty_figure("Erro na análise de confiança")
    
    def create_comparison_metrics(self, extrato_df: pd.DataFrame, contabil_df: pd.DataFrame):
        """Cria métricas comparativas entre extrato e contábil"""
        try:
            # Calcular métricas
            metrics_data = []
            
            # Métricas do extrato
            metrics_data.append({
                'Fonte': 'Extrato Bancário',
                'Total Transações': f"{len(extrato_df):,}",
                'Valor Total (R$)': f"R$ {extrato_df['valor'].sum():,.2f}",
                'Valor Médio (R$)': f"R$ {extrato_df['valor'].mean():,.2f}",
                'Maior Valor (R$)': f"R$ {extrato_df['valor'].max():,.2f}",
                'Menor Valor (R$)': f"R$ {extrato_df['valor'].min():,.2f}"
            })
            
            # Métricas do contábil
            metrics_data.append({
                'Fonte': 'Lançamentos Contábeis', 
                'Total Transações': f"{len(contabil_df):,}",
                'Valor Total (R$)': f"R$ {contabil_df['valor'].sum():,.2f}",
                'Valor Médio (R$)': f"R$ {contabil_df['valor'].mean():,.2f}",
                'Maior Valor (R$)': f"R$ {contabil_df['valor'].max():,.2f}",
                'Menor Valor (R$)': f"R$ {contabil_df['valor'].min():,.2f}"
            })
            
            metrics_df = pd.DataFrame(metrics_data)
            
            # Criar tabela visual com cores para fundo escuro
            fig = go.Figure(data=[go.Table(
                header=dict(
                    values=list(metrics_df.columns),
                    fill_color='#1f77b4',
                    align='center',
                    font=dict(size=12, color='white', family="Arial"),
                    height=40
                ),
                cells=dict(
                    values=[metrics_df[col] for col in metrics_df.columns],
                    fill_color=['#2a2a2a', '#1a1a1a'],  # Cores escuras alternadas
                    align='center',
                    font=dict(size=11, color='white', family="Arial"),  # Texto branco
                    height=30
                )
            )])
            
            fig.update_layout(
                height=200,
                margin=dict(l=0, r=0, t=0, b=0),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)'
            )
            
            return fig
            
        except Exception as e:
            return self._create_empty_figure("Erro nas métricas comparativas")
    
    def _create_empty_figure(self, message: str):
        """Cria uma figura vazia com mensagem de erro"""
        fig = go.Figure()
        fig.add_annotation(
            text=message,
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=16, color='white')
        )
        fig.update_layout(
            height=400,
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='white')
        )
        return fig

# Instância global para caching
@st.cache_resource
def get_dashboard():
    return InteractiveDashboard()