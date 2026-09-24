# modules/report_executivo.py
"""Novo relatório "Executivo" em PDF (fase 3, XCRE-43): substitui o
FPDF célula-a-célula do relatório legado (modules/report_generator.py,
mantido como "Completo") por um template HTML renderizado com
WeasyPrint. Todo texto interpretativo (síntese, alertas, recomendações)
vem de REGRAS DETERMINÍSTICAS sobre os dados já calculados pelo app —
nada é gerado por IA nesta fase, então não há dado enviado a terceiros.

Contrato de dados de entrada (reaproveitado, sem duplicar cálculo):
- resultados_analise: dict com 'matches' (lista de dicts com
  'ids_extrato', 'ids_contabil', 'camada' em {'exata','heuristica','ia'},
  'confianca', 'valor_total', 'explicacao' — ver modules/data_analyzer.py)
  e 'excecoes'.
- extrato_df / contabil_df: DataFrames com colunas 'id', 'data', 'valor'
  (float, sinal preservado) e 'descricao'.
"""
import base64
import os
import re
import tempfile
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML, URLFetcher

from modules.report_generator import formatar_valor_brl

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
FONTS_DIR = os.path.join(BASE_DIR, "assets", "fonts")

# --- Limiares de alertas e recomendações (documentados; único lugar a
# ajustar caso o usuário valide outros valores) ---
ALERTA_PERIODO_TOLERANCIA_DIAS = 7
ALERTA_DIVERGENCIA_VALOR_MINIMA = 500.00
ALERTA_RECORRENCIA_MINIMA = 2
RECOMENDACAO_IMPACTO_ALTA = 500.00
RECOMENDACAO_IMPACTO_MEDIA = 10.00
RESIDUO_TOLERANCIA = 0.01


# Bloqueia qualquer busca de recurso remoto pelo WeasyPrint (requisito de
# segurança da fase 3): só permite 'data:' URIs, usadas para embutir a
# fonte Inter em base64 — nenhuma outra URL (http/https/file) é buscada.
_url_fetcher_seguro = URLFetcher(allowed_protocols=["data"])


_env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    autoescape=select_autoescape(["html", "j2"]),
)


def _carregar_fontes_base64() -> Dict[str, str]:
    pesos = {
        "400": "inter-latin-400-normal.woff2",
        "500": "inter-latin-500-normal.woff2",
        "600": "inter-latin-600-normal.woff2",
        "700": "inter-latin-700-normal.woff2",
    }
    fontes = {}
    for peso, arquivo in pesos.items():
        caminho = os.path.join(FONTS_DIR, arquivo)
        with open(caminho, "rb") as f:
            fontes[peso] = base64.b64encode(f.read()).decode("ascii")
    return fontes


def _fmt_data(valor) -> str:
    if valor is None:
        return "Não informado"
    ts = pd.to_datetime(valor, errors="coerce")
    if pd.isna(ts):
        return "Não informado"
    return ts.strftime("%d/%m/%Y")


def _fmt_valor(valor: float) -> str:
    return formatar_valor_brl(float(valor or 0.0))


def _fmt_pct(valor: float) -> str:
    """Formata um percentual com 1 casa decimal na convenção BRL
    (vírgula): 77.777...  -> '77,8'."""
    return f"{valor:.1f}".replace(".", ",")


def _normalizar_descricao(descricao) -> str:
    return re.sub(r"\s+", " ", str(descricao or "")).strip().lower()


def _linha_match_exato(match: Dict, extrato_df: pd.DataFrame, contabil_df: pd.DataFrame) -> Dict:
    ext = extrato_df[extrato_df["id"].isin(match.get("ids_extrato", []))]
    cont = contabil_df[contabil_df["id"].isin(match.get("ids_contabil", []))]
    descricao = str(ext.iloc[0].get("descricao", "")) if len(ext) else (
        str(cont.iloc[0].get("descricao", "")) if len(cont) else ""
    )
    data = ext.iloc[0]["data"] if len(ext) and "data" in ext.columns else (
        cont.iloc[0]["data"] if len(cont) and "data" in cont.columns else None
    )
    valor_extrato = float(ext["valor"].sum()) if len(ext) else 0.0
    valor_contabil = float(cont["valor"].sum()) if len(cont) else 0.0
    return {
        "descricao": descricao,
        "data": _fmt_data(data),
        "valor_extrato": valor_extrato,
        "valor_contabil": valor_contabil,
        "valor_extrato_fmt": _fmt_valor(valor_extrato),
        "valor_contabil_fmt": _fmt_valor(valor_contabil),
        "confianca": match.get("confianca", 0),
    }


def _linha_match_similaridade(match: Dict, extrato_df: pd.DataFrame, contabil_df: pd.DataFrame) -> Dict:
    ext = extrato_df[extrato_df["id"].isin(match.get("ids_extrato", []))]
    cont = contabil_df[contabil_df["id"].isin(match.get("ids_contabil", []))]
    descricao = str(ext.iloc[0].get("descricao", "")) if len(ext) else (
        str(cont.iloc[0].get("descricao", "")) if len(cont) else ""
    )
    data_extrato = ext.iloc[0]["data"] if len(ext) and "data" in ext.columns else None
    data_contabil = cont.iloc[0]["data"] if len(cont) and "data" in cont.columns else None
    valor_extrato = float(ext["valor"].sum()) if len(ext) else 0.0
    valor_contabil = float(cont["valor"].sum()) if len(cont) else 0.0
    diferenca = round(valor_contabil - valor_extrato, 2)
    if diferenca > 0:
        rotulo_diferenca = f"{_fmt_valor(abs(diferenca))} a mais no contábil"
    elif diferenca < 0:
        rotulo_diferenca = f"{_fmt_valor(abs(diferenca))} a menos no contábil"
    else:
        rotulo_diferenca = "Sem diferença de valor"
    return {
        "descricao": descricao,
        "data_extrato": _fmt_data(data_extrato),
        "data_contabil": _fmt_data(data_contabil),
        "valor_extrato": valor_extrato,
        "valor_contabil": valor_contabil,
        "valor_extrato_fmt": _fmt_valor(valor_extrato),
        "valor_contabil_fmt": _fmt_valor(valor_contabil),
        "diferenca": diferenca,
        "diferenca_fmt": _fmt_valor(diferenca),
        "rotulo_diferenca": rotulo_diferenca,
        "confianca": match.get("confianca", 0),
    }


def _linhas_abertas(df: pd.DataFrame) -> List[Dict]:
    linhas = []
    if df is None or len(df) == 0:
        return linhas
    for _, row in df.iterrows():
        linhas.append({
            "data": _fmt_data(row.get("data")),
            "descricao": str(row.get("descricao", "")),
            "valor": float(row.get("valor", 0.0)),
            "valor_fmt": _fmt_valor(row.get("valor", 0.0)),
        })
    return linhas


def calcular_ponte(
    saldo_extrato: float,
    saldo_contabil: float,
    liquido_extrato_aberto: float,
    liquido_contabil_aberto: float,
    soma_diferencas_similaridade: float,
) -> Dict[str, Any]:
    """Ponte determinística (sem pareamento) da issue XCRE-43:
    saldo contábil - saldo extrato = líquido em aberto (contábil) -
    líquido em aberto (extrato) + soma das diferenças de valor dos
    matches por similaridade.

    O resíduo é sempre CALCULADO (alvo - valor da ponte), nunca
    hard-coded como "fecha sem resíduo" — se a decomposição não bater
    (dado inconsistente), o relatório precisa mostrar isso (CT-F3-07)."""
    valor_calculado = round(
        liquido_contabil_aberto - liquido_extrato_aberto + soma_diferencas_similaridade, 2
    )
    alvo = round(saldo_contabil - saldo_extrato, 2)
    residuo = round(alvo - valor_calculado, 2)
    return {
        "liquido_extrato_aberto": liquido_extrato_aberto,
        "liquido_extrato_aberto_fmt": _fmt_valor(liquido_extrato_aberto),
        "liquido_contabil_aberto": liquido_contabil_aberto,
        "liquido_contabil_aberto_fmt": _fmt_valor(liquido_contabil_aberto),
        "soma_diferencas_similaridade": soma_diferencas_similaridade,
        "soma_diferencas_similaridade_fmt": _fmt_valor(soma_diferencas_similaridade),
        "valor_calculado": valor_calculado,
        "valor_calculado_fmt": _fmt_valor(valor_calculado),
        "alvo": alvo,
        "alvo_fmt": _fmt_valor(alvo),
        "residuo": residuo,
        "residuo_fmt": _fmt_valor(residuo),
        "fecha": abs(residuo) < RESIDUO_TOLERANCIA,
    }


def _calcular_alertas(
    *,
    extrato_df: pd.DataFrame,
    contabil_df: pd.DataFrame,
    cobertura_sistema: float,
    cobertura_efetiva: float,
    empresa_nome: str,
    analista_nome: str,
    extrato_aberto: pd.DataFrame,
    contabil_aberto: pd.DataFrame,
) -> List[Dict[str, str]]:
    alertas = []

    # 1. Período inconsistente entre as duas fontes.
    if len(extrato_df) and len(contabil_df) and "data" in extrato_df.columns and "data" in contabil_df.columns:
        datas_extrato = pd.to_datetime(extrato_df["data"], errors="coerce").dropna()
        datas_contabil = pd.to_datetime(contabil_df["data"], errors="coerce").dropna()
        if len(datas_extrato) and len(datas_contabil):
            diff_inicio = abs((datas_extrato.min() - datas_contabil.min()).days)
            diff_fim = abs((datas_extrato.max() - datas_contabil.max()).days)
            if diff_inicio > ALERTA_PERIODO_TOLERANCIA_DIAS or diff_fim > ALERTA_PERIODO_TOLERANCIA_DIAS:
                alertas.append({
                    "severidade": "atencao",
                    "titulo": "Período inconsistente entre as fontes",
                    "texto": (
                        f"O extrato cobre {_fmt_data(datas_extrato.min())} a {_fmt_data(datas_extrato.max())} "
                        f"e o contábil cobre {_fmt_data(datas_contabil.min())} a {_fmt_data(datas_contabil.max())} "
                        f"— divergência maior que {ALERTA_PERIODO_TOLERANCIA_DIAS} dias. Confirme a competência "
                        "antes de arquivar."
                    ),
                })

    # 2. Cobertura efetiva menor que a cobertura informada pelo sistema.
    if cobertura_efetiva < cobertura_sistema:
        alertas.append({
            "severidade": "atencao",
            "titulo": "Cobertura efetiva menor que a cobertura do sistema",
            "texto": (
                f"A cobertura do sistema é {_fmt_pct(cobertura_sistema)}%, mas considerando apenas as correspondências "
                f"exatas (valor e data idênticos) a cobertura efetiva é de {_fmt_pct(cobertura_efetiva)}%. As demais "
                "correspondências foram aceitas por similaridade e exigem conferência."
            ),
        })

    # 3. Campos de governança vazios.
    if not (empresa_nome or "").strip() or not (analista_nome or "").strip():
        faltando = []
        if not (empresa_nome or "").strip():
            faltando.append("empresa")
        if not (analista_nome or "").strip():
            faltando.append("analista")
        alertas.append({
            "severidade": "atencao",
            "titulo": "Campos de governança em branco",
            "texto": (
                f"Campo(s) não informado(s): {', '.join(faltando)}. Neste estado, o documento não está apto "
                "para arquivo de auditoria sem revisão."
            ),
        })

    # 4. Maior divergência de valor em aberto acima do limiar monetário.
    candidatos = []
    for linha in _linhas_abertas(extrato_aberto):
        candidatos.append((abs(linha["valor"]), linha["valor"], linha["descricao"], "extrato"))
    for linha in _linhas_abertas(contabil_aberto):
        candidatos.append((abs(linha["valor"]), linha["valor"], linha["descricao"], "contábil"))
    if candidatos:
        candidatos.sort(key=lambda item: item[0], reverse=True)
        abs_valor, valor, descricao, origem = candidatos[0]
        if abs_valor >= ALERTA_DIVERGENCIA_VALOR_MINIMA:
            alertas.append({
                "severidade": "critico",
                "titulo": f"Maior divergência em aberto: {_fmt_valor(valor)} ({origem})",
                "texto": (
                    f"O item '{descricao}' ({origem}) soma {_fmt_valor(valor)}, acima do limiar de "
                    f"{_fmt_valor(ALERTA_DIVERGENCIA_VALOR_MINIMA)} configurado para este alerta."
                ),
            })

    # 5. Itens em aberto recorrentes pela mesma descrição.
    descricoes = [
        _normalizar_descricao(linha["descricao"])
        for linha in _linhas_abertas(extrato_aberto) + _linhas_abertas(contabil_aberto)
        if linha["descricao"]
    ]
    if descricoes:
        contagem = Counter(descricoes)
        descricao_normalizada, qtd = contagem.most_common(1)[0]
        if qtd >= ALERTA_RECORRENCIA_MINIMA:
            alertas.append({
                "severidade": "informativo",
                "titulo": "Itens em aberto com descrição recorrente",
                "texto": (
                    f"A descrição '{descricao_normalizada}' aparece {qtd} vezes entre os itens em aberto "
                    "(extrato e contábil). Vale checar se extrato e contábil registram a mesma despesa/receita "
                    "por fontes diferentes."
                ),
            })

    return alertas


def _calcular_recomendacoes(
    *,
    alertas: List[Dict[str, str]],
    matches_similaridade_linhas: List[Dict],
    extrato_aberto: pd.DataFrame,
    contabil_aberto: pd.DataFrame,
) -> (List[Dict[str, Any]], List[str]):
    recomendacoes = []
    checklist = []

    candidatos = []
    for linha in _linhas_abertas(extrato_aberto):
        candidatos.append((abs(linha["valor"]), linha, "extrato"))
    for linha in _linhas_abertas(contabil_aberto):
        candidatos.append((abs(linha["valor"]), linha, "contábil"))
    candidatos.sort(key=lambda item: item[0], reverse=True)

    if candidatos and candidatos[0][0] >= RECOMENDACAO_IMPACTO_ALTA:
        abs_valor, linha, origem = candidatos[0]
        recomendacoes.append({
            "prioridade": "alta",
            "titulo": f"Investigar a maior divergência em aberto ({origem})",
            "texto": (
                f"'{linha['descricao']}' soma {linha['valor_fmt']} sem correspondência automática no "
                f"{origem}. Confirmar comprovantes e lançar o ajuste ou registrar a exceção."
            ),
            "impacto": linha["valor_fmt"],
        })
        checklist.append(f"Investigar '{linha['descricao']}' ({origem}, {linha['valor_fmt']}).")

    if any(a["titulo"].startswith("Período inconsistente") for a in alertas):
        recomendacoes.append({
            "prioridade": "alta",
            "titulo": "Confirmar a competência do período",
            "texto": "Alinhar o período informado às datas reais dos dados antes de arquivar o relatório.",
            "impacto": "Integridade",
        })
        checklist.append("Confirmar o período (competência) informado na capa.")

    if matches_similaridade_linhas:
        soma_diffs = sum(abs(linha["diferenca"]) for linha in matches_similaridade_linhas)
        if soma_diffs > 0:
            recomendacoes.append({
                "prioridade": "media",
                "titulo": "Corrigir valores dos lançamentos por similaridade",
                "texto": (
                    "Ajustar os "
                    f"{len(matches_similaridade_linhas)} lançamento(s) casados por similaridade cuja diferença "
                    "de valor está detalhada na seção 4, se confirmados com os comprovantes."
                ),
                "impacto": _fmt_valor(soma_diffs),
            })
            checklist.append("Conferir os lançamentos por similaridade da seção 4 com os comprovantes.")
        apenas_data = [l for l in matches_similaridade_linhas if abs(l["diferenca"]) < 0.005]
        if apenas_data:
            recomendacoes.append({
                "prioridade": "baixa",
                "titulo": "Padronizar datas dos casamentos por similaridade sem diferença de valor",
                "texto": (
                    f"{len(apenas_data)} par(es) têm apenas defasagem de data, sem efeito no valor. "
                    "Padronizar a data do extrato no lançamento melhora o casamento automático futuro."
                ),
                "impacto": "Sem efeito financeiro",
            })

    if any(a["titulo"] == "Itens em aberto com descrição recorrente" for a in alertas):
        recomendacoes.append({
            "prioridade": "media",
            "titulo": "Investigar itens em aberto recorrentes",
            "texto": "Verificar se a descrição recorrente indica lançamentos duplicados, parciais ou de fontes diferentes.",
            "impacto": "A confirmar",
        })
        checklist.append("Investigar a descrição recorrente apontada nos alertas.")

    checklist.append("Validar manualmente as correspondências por similaridade.")
    checklist.append("Reprocessar a conciliação após os ajustes para confirmar o fechamento da ponte.")

    return recomendacoes, checklist


def montar_contexto_executivo(
    resultados_analise: Dict,
    extrato_df: pd.DataFrame,
    contabil_df: pd.DataFrame,
    empresa_nome: str,
    analista_nome: str,
    classificacao_documento: str,
    periodo: str,
    conta_analisada: Optional[str],
    observacoes: str = "",
    meta_cobertura: Optional[str] = None,
    data_emissao: Optional[datetime] = None,
) -> Dict[str, Any]:
    data_emissao = data_emissao or datetime.now()
    matches = resultados_analise.get("matches", []) or []
    excecoes = resultados_analise.get("excecoes", []) or []

    ids_extrato_matched, ids_contabil_matched = set(), set()
    for m in matches:
        ids_extrato_matched.update(m.get("ids_extrato", []))
        ids_contabil_matched.update(m.get("ids_contabil", []))

    matches_exatos = [m for m in matches if m.get("camada") == "exata"]
    matches_similaridade = [m for m in matches if m.get("camada") != "exata"]

    total_extrato = len(extrato_df) if extrato_df is not None else 0
    total_contabil = len(contabil_df) if contabil_df is not None else 0

    cobertura_sistema = (len(matches) / total_extrato * 100) if total_extrato else 0.0
    cobertura_efetiva = (len(matches_exatos) / total_extrato * 100) if total_extrato else 0.0

    saldo_extrato = float(extrato_df["valor"].sum()) if total_extrato and "valor" in extrato_df.columns else 0.0
    saldo_contabil = float(contabil_df["valor"].sum()) if total_contabil and "valor" in contabil_df.columns else 0.0
    diferenca_liquida = round(saldo_contabil - saldo_extrato, 2)

    extrato_aberto = (
        extrato_df[~extrato_df["id"].isin(ids_extrato_matched)] if total_extrato else pd.DataFrame(columns=["data", "descricao", "valor"])
    )
    contabil_aberto = (
        contabil_df[~contabil_df["id"].isin(ids_contabil_matched)] if total_contabil else pd.DataFrame(columns=["data", "descricao", "valor"])
    )

    liquido_extrato_aberto = float(extrato_aberto["valor"].sum()) if len(extrato_aberto) else 0.0
    liquido_contabil_aberto = float(contabil_aberto["valor"].sum()) if len(contabil_aberto) else 0.0

    matches_exatos_linhas = [_linha_match_exato(m, extrato_df, contabil_df) for m in matches_exatos]
    matches_similaridade_linhas = [_linha_match_similaridade(m, extrato_df, contabil_df) for m in matches_similaridade]
    soma_diferencas_similaridade = round(sum(l["diferenca"] for l in matches_similaridade_linhas), 2)

    subtotal_exato_extrato = round(sum(l["valor_extrato"] for l in matches_exatos_linhas), 2)
    subtotal_exato_contabil = round(sum(l["valor_contabil"] for l in matches_exatos_linhas), 2)

    ponte = calcular_ponte(
        saldo_extrato, saldo_contabil, liquido_extrato_aberto, liquido_contabil_aberto, soma_diferencas_similaridade
    )

    alertas = _calcular_alertas(
        extrato_df=extrato_df if extrato_df is not None else pd.DataFrame(),
        contabil_df=contabil_df if contabil_df is not None else pd.DataFrame(),
        cobertura_sistema=cobertura_sistema,
        cobertura_efetiva=cobertura_efetiva,
        empresa_nome=empresa_nome,
        analista_nome=analista_nome,
        extrato_aberto=extrato_aberto,
        contabil_aberto=contabil_aberto,
    )
    recomendacoes, checklist = _calcular_recomendacoes(
        alertas=alertas,
        matches_similaridade_linhas=matches_similaridade_linhas,
        extrato_aberto=extrato_aberto,
        contabil_aberto=contabil_aberto,
    )

    headline = (
        f"O sistema casou {len(matches)} das {total_extrato} transações, mas só {len(matches_exatos)} "
        f"casamento(s) são exatos. {len(matches_similaridade)} diferem em valor ou data, e "
        f"{len(extrato_aberto) + len(contabil_aberto)} item(ns) seguem sem par."
    )
    takeaways = [
        {
            "titulo": f"Cobertura informada de {_fmt_pct(cobertura_sistema)}%",
            "texto": f"{len(matches)} de {total_extrato} transações do extrato têm par no contábil.",
            "classe": "",
        },
        {
            "titulo": f"A cobertura efetiva é de {_fmt_pct(cobertura_efetiva)}%",
            "texto": (
                f"Apenas {len(matches_exatos)} casamento(s) coincidem em valor e data. Os demais "
                f"{len(matches_similaridade)} foram aceitos por similaridade."
            ),
            "classe": "watch",
        },
        {
            "titulo": f"{len(extrato_aberto) + len(contabil_aberto)} item(ns) seguem sem correspondência",
            "texto": (
                f"{len(extrato_aberto)} no extrato e {len(contabil_aberto)} no contábil — ver seção 5 "
                "para a ponte de reconciliação."
            ),
            "classe": "risk",
        },
        {
            "titulo": f"Diferença líquida de {_fmt_valor(diferenca_liquida)}",
            "texto": (
                f"O extrato soma {_fmt_valor(saldo_extrato)} e o contábil {_fmt_valor(saldo_contabil)}. "
                + ("A ponte da seção 5 fecha sem resíduo." if ponte["fecha"] else
                   f"A ponte da seção 5 aponta resíduo de {ponte['residuo_fmt']} — requer investigação.")
            ),
            "classe": "",
        },
    ]

    empresa_display = (empresa_nome or "").strip() or "Não informado"
    analista_display = (analista_nome or "").strip() or "Não informado"
    classificacao_display = (classificacao_documento or "").strip() or "Documento interno"
    meta_cobertura_display = (meta_cobertura or "").strip() or None
    conta_display = (conta_analisada or "").strip() or "Não identificada"
    conta_footer = conta_display.replace('"', "'").replace("\\", "/").replace("\n", " ")

    contexto = {
        "conta_analisada": conta_display,
        "conta_footer": conta_footer,
        "periodo": periodo,
        "data_emissao_str": data_emissao.strftime("%d/%m/%Y, %H:%M"),
        "empresa_nome": empresa_display,
        "analista_nome": analista_display,
        "classificacao_documento": classificacao_display,
        "meta_cobertura": meta_cobertura_display,
        "observacoes": (observacoes or "").strip(),
        "total_extrato": total_extrato,
        "total_contabil": total_contabil,
        "total_matches": len(matches),
        "total_exatos": len(matches_exatos),
        "total_similaridade": len(matches_similaridade),
        "total_extrato_aberto": len(extrato_aberto),
        "total_contabil_aberto": len(contabil_aberto),
        "total_aberto": len(extrato_aberto) + len(contabil_aberto),
        "total_excecoes": len(excecoes),
        "cobertura_sistema": cobertura_sistema,
        "cobertura_efetiva": cobertura_efetiva,
        "saldo_extrato": saldo_extrato,
        "saldo_extrato_fmt": _fmt_valor(saldo_extrato),
        "saldo_contabil": saldo_contabil,
        "saldo_contabil_fmt": _fmt_valor(saldo_contabil),
        "diferenca_liquida": diferenca_liquida,
        "diferenca_liquida_fmt": _fmt_valor(diferenca_liquida),
        "matches_exatos_linhas": matches_exatos_linhas,
        "subtotal_exato_extrato_fmt": _fmt_valor(subtotal_exato_extrato),
        "subtotal_exato_contabil_fmt": _fmt_valor(subtotal_exato_contabil),
        "matches_similaridade_linhas": matches_similaridade_linhas,
        "extrato_aberto_linhas": _linhas_abertas(extrato_aberto),
        "contabil_aberto_linhas": _linhas_abertas(contabil_aberto),
        "ponte": ponte,
        "alertas": alertas,
        "recomendacoes": recomendacoes,
        "checklist": checklist,
        "headline": headline,
        "takeaways": takeaways,
        "fontes": _carregar_fontes_base64(),
    }
    return contexto


def gerar_relatorio_executivo(
    resultados_analise: Dict,
    extrato_df: pd.DataFrame,
    contabil_df: pd.DataFrame,
    empresa_nome: str = "",
    analista_nome: str = "",
    classificacao_documento: str = "Documento interno",
    periodo: str = "",
    observacoes: str = "",
    conta_analisada: Optional[str] = None,
    meta_cobertura: Optional[str] = None,
    **kwargs,
) -> str:
    """Gera o relatório Executivo em PDF e retorna o caminho do arquivo
    gerado. Levanta ValueError para pré-condições ausentes (sem análise,
    DataFrame vazio) — quem chama (pages/gerar_relatorio.py) trata isso
    como falha, sem oferecer um PDF parcial."""
    if resultados_analise is None:
        raise ValueError("Resultados da análise não fornecidos")
    if extrato_df is None or len(extrato_df) == 0:
        raise ValueError("DataFrame do extrato está vazio ou não fornecido")
    if contabil_df is None or len(contabil_df) == 0:
        raise ValueError("DataFrame contábil está vazio ou não fornecido")

    contexto = montar_contexto_executivo(
        resultados_analise=resultados_analise,
        extrato_df=extrato_df,
        contabil_df=contabil_df,
        empresa_nome=empresa_nome,
        analista_nome=analista_nome,
        classificacao_documento=classificacao_documento,
        periodo=periodo,
        conta_analisada=conta_analisada,
        observacoes=observacoes,
        meta_cobertura=meta_cobertura,
    )

    template = _env.get_template("relatorio_executivo.html.j2")
    html_renderizado = template.render(**contexto)

    temp_dir = tempfile.gettempdir()
    pdf_path = os.path.join(
        temp_dir, f"relatorio_executivo_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.pdf"
    )
    HTML(string=html_renderizado, base_url=None, url_fetcher=_url_fetcher_seguro).write_pdf(pdf_path)
    return pdf_path
