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

from modules.data_analyzer import identificar_pares_provaveis_similaridade
from modules.report_generator import formatar_valor_brl

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
FONTS_DIR = os.path.join(BASE_DIR, "assets", "fonts")

# --- Limiares de alertas e recomendações (documentados; único lugar a
# ajustar caso o usuário valide outros valores) ---
ALERTA_PERIODO_TOLERANCIA_DIAS = 7
# Revisado na issue XCRE-44 (item A2c): antes se aplicava ao maior item
# BRUTO em aberto isoladamente; agora se aplica à exposição já agrupada
# por natureza (recebimentos/pagamentos) calculada por
# _calcular_exposicao_agrupada — um patamar de materialidade sobre um
# número mais preciso, já que pares identificados na ponte detalhada não
# representam mais o valor bruto das duas pontas, só a diferença real
# entre elas. R$500,00 permanece um patamar razoável nesta fase; não há
# indicação de que precise mudar de valor, só de base de cálculo.
ALERTA_DIVERGENCIA_VALOR_MINIMA = 500.00
ALERTA_RECORRENCIA_MINIMA = 2
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


def pluralizar(quantidade: int, singular: str, plural: Optional[str] = None) -> str:
    """Helper único de pluralização (issue XCRE-44, item A3), usado no
    módulo e no template: 1 casamento / N casamentos; 1 item / N itens.
    `plural` é obrigatório para formas irregulares (ex.: item -> itens);
    quando omitido, usa a forma regular (singular + 's')."""
    if quantidade == 1:
        return singular
    return plural if plural is not None else f"{singular}s"


def _fmt_contagem(quantidade: int, singular: str, plural: Optional[str] = None) -> str:
    """'{quantidade} {palavra no plural correto}', ex.: '1 item' / '8 itens'."""
    return f"{quantidade} {pluralizar(quantidade, singular, plural)}"


_env.globals["pluralizar"] = pluralizar


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


def _rotulo_diferenca_por_magnitude(valor_contabil: float, valor_extrato: float) -> "tuple[str, float]":
    """Rótulo de diferença de valor por MAGNITUDE (issue XCRE-44, item A1):
    compara |contábil| com |extrato|, não o sinal algébrico
    (contábil - extrato). Um débito maior no contábil (ex.: -43,30 contra
    -40,30 no extrato) é "a mais no contábil", nunca "a menos" — o sinal
    algébrico sozinho inverte esse resultado para despesas. Vale para
    débitos e créditos. A diferença de DATA é sempre mostrada à parte,
    nunca misturada a este rótulo."""
    diferenca_magnitude = round(abs(valor_contabil) - abs(valor_extrato), 2)
    if diferenca_magnitude > 0:
        rotulo = f"{_fmt_valor(diferenca_magnitude)} a mais no contábil"
    elif diferenca_magnitude < 0:
        rotulo = f"{_fmt_valor(abs(diferenca_magnitude))} a menos no contábil"
    else:
        rotulo = "Sem diferença de valor"
    return rotulo, diferenca_magnitude


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
    rotulo_diferenca, diferenca_magnitude = _rotulo_diferenca_por_magnitude(valor_contabil, valor_extrato)
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
        "diferenca_magnitude": diferenca_magnitude,
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
    # Passagem explícita da ponte DETALHADA (soma dos itens em aberto, sem
    # o ajuste por similaridade) para a ponte COMPACTA acima (issue
    # XCRE-48, item 1): mesmo `soma_diferencas_similaridade`, mas exibido
    # como operação de sinal único ("148,55 - 1,00 = 147,55") em vez do
    # valor com sinal embutido ("+ R$ -1,00"), que confunde quem não é
    # da área.
    ajuste_similaridade_operador = "-" if soma_diferencas_similaridade < 0 else "+"
    return {
        "liquido_extrato_aberto": liquido_extrato_aberto,
        "liquido_extrato_aberto_fmt": _fmt_valor(liquido_extrato_aberto),
        "liquido_contabil_aberto": liquido_contabil_aberto,
        "liquido_contabil_aberto_fmt": _fmt_valor(liquido_contabil_aberto),
        "soma_diferencas_similaridade": soma_diferencas_similaridade,
        "soma_diferencas_similaridade_fmt": _fmt_valor(soma_diferencas_similaridade),
        "ajuste_similaridade_abs_fmt": _fmt_valor(abs(soma_diferencas_similaridade)),
        "ajuste_similaridade_operador": ajuste_similaridade_operador,
        "valor_calculado": valor_calculado,
        "valor_calculado_fmt": _fmt_valor(valor_calculado),
        "alvo": alvo,
        "alvo_fmt": _fmt_valor(alvo),
        "residuo": residuo,
        "residuo_fmt": _fmt_valor(residuo),
        "fecha": abs(residuo) < RESIDUO_TOLERANCIA,
    }


NATUREZA_RECEBIMENTOS = "recebimentos"
NATUREZA_PAGAMENTOS = "pagamentos"


def _natureza(valor: float) -> str:
    """Recebimento (crédito, valor >= 0) ou pagamento (débito, valor < 0)."""
    return NATUREZA_RECEBIMENTOS if valor >= 0 else NATUREZA_PAGAMENTOS


def _data_apenas(valor):
    ts = pd.to_datetime(valor, errors="coerce")
    return None if pd.isna(ts) else ts.date()


def _linha_pares_provaveis(par: Dict) -> Dict:
    """Formata um par candidato de modules.data_analyzer.identificar_pares_provaveis_similaridade
    para exibição na seção 5(a) 'Pares prováveis apontados pelo sistema'."""
    descricao = par["descricao_extrato"] or par["descricao_contabil"]
    return {
        "descricao": descricao,
        "data_extrato": _fmt_data(par["data_extrato"]),
        "data_contabil": _fmt_data(par["data_contabil"]),
        "valor_extrato_fmt": _fmt_valor(par["valor_extrato"]),
        "valor_contabil_fmt": _fmt_valor(par["valor_contabil"]),
        "diferenca_valor_fmt": _fmt_valor(par["diferenca_valor"]),
        "diferenca_dias": par["diferenca_dias"],
        "similaridade": par["similaridade"],
        "confianca": par["confianca"],
    }


def _linha_ponte_par(par: Dict, origem: str) -> Dict:
    """Uma linha pareada da ponte DETALHADA (issue XCRE-44, item A2b):
    reaproveita o mesmo rótulo por magnitude do item A1. `origem` é
    'sistema' (o par também está entre os 'pares prováveis apontados
    pelo sistema' da seção 5a) ou 'hipotese' (encontrado só pela regra
    objetiva — mesma descrição normalizada + mesma data — sem respaldo
    do sistema; rotulado 'Hipótese do analista')."""
    valor_extrato = par["valor_extrato"]
    valor_contabil = par["valor_contabil"]
    diferenca = round(valor_contabil - valor_extrato, 2)
    rotulo_diferenca, diferenca_magnitude = _rotulo_diferenca_por_magnitude(valor_contabil, valor_extrato)
    return {
        "descricao": par["descricao_extrato"] or par["descricao_contabil"],
        "data_extrato": _fmt_data(par["data_extrato"]),
        "data_contabil": _fmt_data(par["data_contabil"]),
        "valor_extrato": valor_extrato,
        "valor_contabil": valor_contabil,
        "valor_extrato_fmt": _fmt_valor(valor_extrato),
        "valor_contabil_fmt": _fmt_valor(valor_contabil),
        "diferenca": diferenca,
        "diferenca_fmt": _fmt_valor(diferenca),
        "rotulo_diferenca": rotulo_diferenca,
        "diferenca_magnitude": diferenca_magnitude,
        "origem": origem,
        "origem_label": "Hipótese do analista" if origem == "hipotese" else "Par apontado pelo sistema",
        "natureza": _natureza(valor_contabil),
    }


def _construir_ponte_detalhada(
    extrato_aberto: pd.DataFrame,
    contabil_aberto: pd.DataFrame,
    pares_provaveis: List[Dict],
) -> "tuple[List[Dict], pd.DataFrame, pd.DataFrame]":
    """Ponte DETALHADA linha a linha (issue XCRE-44, item A2b), visão
    ADICIONAL à ponte determinística compacta (que continua como
    padrão): decompõe os itens em aberto em pares (mesma descrição
    normalizada + mesma data + valor diferente) + itens que seguem
    totalmente sem par. Pareamento é EXCLUSIVO — cada id é usado no
    máximo uma vez — priorizando, em ordem:
    1) os pares que o sistema já aponta (seção 5a), maior confiança
       primeiro;
    2) pares adicionais encontrados só pela regra objetiva entre os
       itens restantes, rotulados 'hipótese do analista' (não vieram da
       lista do sistema).
    """
    usados_extrato: set = set()
    usados_contabil: set = set()
    linhas_pares: List[Dict] = []

    for par in sorted(pares_provaveis, key=lambda p: -p["confianca"]):
        if par["id_extrato"] in usados_extrato or par["id_contabil"] in usados_contabil:
            continue
        usados_extrato.add(par["id_extrato"])
        usados_contabil.add(par["id_contabil"])
        linhas_pares.append(_linha_ponte_par(par, origem="sistema"))

    for _, ext in extrato_aberto.iterrows():
        if ext["id"] in usados_extrato:
            continue
        chave_ext = (_normalizar_descricao(ext.get("descricao")), _data_apenas(ext.get("data")))
        for _, cont in contabil_aberto.iterrows():
            if cont["id"] in usados_contabil:
                continue
            chave_cont = (_normalizar_descricao(cont.get("descricao")), _data_apenas(cont.get("data")))
            if chave_ext != chave_cont:
                continue
            if round(float(ext["valor"]) - float(cont["valor"]), 2) == 0:
                continue  # mesmo valor: não é uma divergência a explicar na ponte
            usados_extrato.add(ext["id"])
            usados_contabil.add(cont["id"])
            par = {
                "data_extrato": ext.get("data"), "data_contabil": cont.get("data"),
                "valor_extrato": float(ext["valor"]), "valor_contabil": float(cont["valor"]),
                "descricao_extrato": str(ext.get("descricao", "") or ""),
                "descricao_contabil": str(cont.get("descricao", "") or ""),
            }
            linhas_pares.append(_linha_ponte_par(par, origem="hipotese"))
            break

    nao_pareados_extrato = extrato_aberto[~extrato_aberto["id"].isin(usados_extrato)]
    nao_pareados_contabil = contabil_aberto[~contabil_aberto["id"].isin(usados_contabil)]
    return linhas_pares, nao_pareados_extrato, nao_pareados_contabil


def _montar_ponte_detalhada(
    linhas_pares: List[Dict],
    nao_pareados_extrato: pd.DataFrame,
    nao_pareados_contabil: pd.DataFrame,
    liquido_contabil_aberto: float,
    liquido_extrato_aberto: float,
) -> Dict[str, Any]:
    linhas_sem_par = _linhas_abertas(nao_pareados_extrato)
    for linha in linhas_sem_par:
        linha["lado"] = "extrato"
    linhas_sem_par_contabil = _linhas_abertas(nao_pareados_contabil)
    for linha in linhas_sem_par_contabil:
        linha["lado"] = "contábil"
    linhas_sem_par += linhas_sem_par_contabil

    soma_pares = round(sum(l["diferenca"] for l in linhas_pares), 2)
    soma_sem_par_contabil = round(sum(float(v) for v in nao_pareados_contabil["valor"]), 2) if len(nao_pareados_contabil) else 0.0
    soma_sem_par_extrato = round(sum(float(v) for v in nao_pareados_extrato["valor"]), 2) if len(nao_pareados_extrato) else 0.0
    total_detalhado = round(soma_pares + soma_sem_par_contabil - soma_sem_par_extrato, 2)
    alvo_aberto = round(liquido_contabil_aberto - liquido_extrato_aberto, 2)
    residuo = round(alvo_aberto - total_detalhado, 2)

    return {
        "linhas_pares": linhas_pares,
        "linhas_sem_par": linhas_sem_par,
        "total_pares": len(linhas_pares),
        "total_sem_par": len(linhas_sem_par),
        "soma_pares_fmt": _fmt_valor(soma_pares),
        "alvo_aberto_fmt": _fmt_valor(alvo_aberto),
        "total_detalhado_fmt": _fmt_valor(total_detalhado),
        "residuo": residuo,
        "residuo_fmt": _fmt_valor(residuo),
        "fecha": abs(residuo) < RESIDUO_TOLERANCIA,
    }


def _resumo_itens_abertos(linhas_pares: List[Dict], total_sem_par: int) -> Dict[str, Any]:
    """Resumo do início da seção 5 (issue XCRE-48, item 3): quantos dos
    itens em aberto estão em pares prováveis apontados pelo sistema,
    quantos em pares por hipótese do analista, e quantos seguem sem par
    nenhum — derivado da MESMA saída de `_construir_ponte_detalhada`
    usada na tabela abaixo, nunca recalculado ou codificado à parte.
    Cada par conta os DOIS lados (extrato + contábil) como itens
    individuais em aberto, para a soma bater com o total de itens em
    aberto (não com o número de pares)."""
    pares_provaveis = sum(1 for l in linhas_pares if l["origem"] == "sistema") * 2
    pares_hipotese = sum(1 for l in linhas_pares if l["origem"] == "hipotese") * 2
    return {
        "pares_provaveis": pares_provaveis,
        "pares_hipotese": pares_hipotese,
        "sem_par": total_sem_par,
        "total": pares_provaveis + pares_hipotese + total_sem_par,
    }


def _juntar_valores_fmt(valores_fmt: List[str]) -> str:
    if not valores_fmt:
        return ""
    if len(valores_fmt) == 1:
        return valores_fmt[0]
    return ", ".join(valores_fmt[:-1]) + " e " + valores_fmt[-1]


def _calcular_exposicao_agrupada(
    linhas_pares: List[Dict],
    nao_pareados_extrato: pd.DataFrame,
    nao_pareados_contabil: pd.DataFrame,
) -> Dict[str, Any]:
    """Exposição agrupada por natureza (issue XCRE-44, item A2c): soma
    das |diferenças| dos pares identificados na ponte detalhada + itens
    em aberto sem par nenhum, separada em recebimentos (créditos) e
    pagamentos (débitos). Usada por alertas, manchete/takeaways e
    recomendações em vez do maior item bruto isolado, porque um par já
    identificado (ex.: 1.400,00 contábil x 1.300,00 extrato) representa
    uma exposição real de só R$100,00 — não R$1.400,00."""
    buckets: Dict[str, List[Dict[str, Any]]] = {NATUREZA_RECEBIMENTOS: [], NATUREZA_PAGAMENTOS: []}

    for linha in linhas_pares:
        valor_diferenca = abs(linha["diferenca"])
        if valor_diferenca <= 0:
            continue
        valor_referencia = (
            linha["valor_contabil"] if abs(linha["valor_contabil"]) >= abs(linha["valor_extrato"])
            else linha["valor_extrato"]
        )
        buckets[linha["natureza"]].append({
            "descricao": linha["descricao"],
            "valor_diferenca": valor_diferenca,
            "valor_referencia_fmt": _fmt_valor(abs(valor_referencia)),
            "origem": "par",
        })

    for df in (nao_pareados_extrato, nao_pareados_contabil):
        for _, row in df.iterrows():
            valor = float(row["valor"])
            if valor == 0:
                continue
            buckets[_natureza(valor)].append({
                "descricao": str(row.get("descricao", "") or ""),
                "valor_diferenca": abs(valor),
                "valor_referencia_fmt": _fmt_valor(abs(valor)),
                "origem": "sem_par",
            })

    totais = {natureza: round(sum(i["valor_diferenca"] for i in itens), 2) for natureza, itens in buckets.items()}
    natureza_principal = max(totais, key=lambda n: totais[n]) if any(totais.values()) else None
    total_principal = totais.get(natureza_principal, 0.0) if natureza_principal else 0.0

    return {
        "buckets": buckets,
        "totais": totais,
        "totais_fmt": {natureza: _fmt_valor(valor) for natureza, valor in totais.items()},
        "natureza_principal": natureza_principal,
        "total_principal": total_principal,
        "total_principal_fmt": _fmt_valor(total_principal),
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
    exposicao: Dict[str, Any],
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
                f"{pluralizar(len(faltando), 'Campo não informado', 'Campos não informados')}: "
                f"{', '.join(faltando)}. Neste estado, o documento não está apto "
                "para arquivo de auditoria sem revisão."
            ),
        })

    # 4. Maior exposição agrupada por natureza acima do limiar monetário
    # (issue XCRE-44, item A2c). Substitui o alerta anterior, que
    # apontava o maior ITEM BRUTO em aberto isoladamente — um par já
    # identificado na ponte detalhada (ex.: 1.400,00 contábil x 1.300,00
    # extrato) tem uma exposição real de só R$100,00, não R$1.400,00;
    # alertar pelo valor bruto do item superestimava o risco. O limiar
    # (R$500,00, ALERTA_DIVERGENCIA_VALOR_MINIMA) foi revisado e mantido:
    # segue sendo um patamar de materialidade razoável, agora aplicado à
    # exposição JÁ AGRUPADA (mais precisa) em vez de a uma linha bruta.
    natureza_principal = exposicao.get("natureza_principal")
    if natureza_principal:
        total_principal = exposicao["totais"][natureza_principal]
        if total_principal >= ALERTA_DIVERGENCIA_VALOR_MINIMA:
            alertas.append({
                "severidade": "critico",
                "titulo": f"Maior exposição em aberto: {natureza_principal}, {exposicao['total_principal_fmt']}",
                "texto": (
                    f"A soma das divergências identificadas em {natureza_principal} (pares com diferença de "
                    f"valor + itens sem par nenhum) é {exposicao['total_principal_fmt']}, acima do limiar de "
                    f"{_fmt_valor(ALERTA_DIVERGENCIA_VALOR_MINIMA)} configurado para este alerta. Ver seção 5 "
                    "para o detalhamento linha a linha."
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
    exposicao: Dict[str, Any],
) -> (List[Dict[str, Any]], List[str]):
    recomendacoes = []
    checklist = []

    # Investigar a maior exposição agrupada por natureza (issue XCRE-44,
    # item A2c) — substitui a recomendação anterior baseada no maior item
    # BRUTO isolado. É sempre a recomendação de prioridade mais alta do
    # relatório (o principal ponto de ação financeira), independente do
    # valor: mesmo uma exposição pequena em termos absolutos é o maior
    # risco financeiro remanescente desta conciliação depois que os pares
    # já identificados na ponte detalhada explicam o resto da divergência.
    natureza_principal = exposicao.get("natureza_principal")
    if natureza_principal:
        itens_principais = exposicao["buckets"][natureza_principal]
        valores_fmt = _juntar_valores_fmt([item["valor_referencia_fmt"] for item in itens_principais])
        total_fmt = exposicao["total_principal_fmt"]
        recomendacoes.append({
            "prioridade": "alta",
            "titulo": f"Investigar os {natureza_principal} de {valores_fmt}",
            "texto": (
                f"Soma das divergências identificadas em {natureza_principal} (pares com diferença de valor "
                f"entre extrato e contábil, e itens em aberto sem par nenhum — ver seção 5): {total_fmt}. "
                "Confirmar comprovantes e lançar o ajuste ou registrar a exceção."
            ),
            "impacto": total_fmt,
        })
        checklist.append(f"Investigar os {natureza_principal} de {valores_fmt} (impacto {total_fmt}).")

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
            n_similaridade = len(matches_similaridade_linhas)
            alvo_texto = (
                "o lançamento casado por similaridade" if n_similaridade == 1
                else f"os {n_similaridade} lançamentos casados por similaridade"
            )
            recomendacoes.append({
                "prioridade": "media",
                "titulo": "Corrigir valores dos lançamentos por similaridade",
                "texto": (
                    f"Ajustar {alvo_texto} cuja diferença de valor está detalhada na seção 4, se confirmados com "
                    "os comprovantes."
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
                    f"{_fmt_contagem(len(apenas_data), 'par', 'pares')} "
                    f"{pluralizar(len(apenas_data), 'tem', 'têm')} apenas defasagem de data, sem efeito no valor. "
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

    # Pares prováveis apontados pelo sistema (seção 5a) + ponte detalhada
    # linha a linha (seção 5b) + exposição agrupada por natureza — issue
    # XCRE-44, item A2. Reaproveita o MESMO cálculo que
    # pages/analise_dados.py já usa e expõe na UI/CSV (fonte única em
    # modules.data_analyzer.identificar_pares_provaveis_similaridade),
    # em vez de recalcular de forma divergente aqui.
    pares_provaveis = identificar_pares_provaveis_similaridade(extrato_aberto, contabil_aberto)
    pares_provaveis_linhas = [_linha_pares_provaveis(p) for p in pares_provaveis]
    linhas_ponte_pares, nao_pareados_extrato, nao_pareados_contabil = _construir_ponte_detalhada(
        extrato_aberto, contabil_aberto, pares_provaveis
    )
    ponte_detalhada = _montar_ponte_detalhada(
        linhas_ponte_pares, nao_pareados_extrato, nao_pareados_contabil,
        liquido_contabil_aberto, liquido_extrato_aberto,
    )
    resumo_itens_abertos = _resumo_itens_abertos(linhas_ponte_pares, ponte_detalhada["total_sem_par"])
    exposicao = _calcular_exposicao_agrupada(linhas_ponte_pares, nao_pareados_extrato, nao_pareados_contabil)

    alertas = _calcular_alertas(
        extrato_df=extrato_df if extrato_df is not None else pd.DataFrame(),
        contabil_df=contabil_df if contabil_df is not None else pd.DataFrame(),
        cobertura_sistema=cobertura_sistema,
        cobertura_efetiva=cobertura_efetiva,
        empresa_nome=empresa_nome,
        analista_nome=analista_nome,
        extrato_aberto=extrato_aberto,
        contabil_aberto=contabil_aberto,
        exposicao=exposicao,
    )
    recomendacoes, checklist = _calcular_recomendacoes(
        alertas=alertas,
        matches_similaridade_linhas=matches_similaridade_linhas,
        extrato_aberto=extrato_aberto,
        contabil_aberto=contabil_aberto,
        exposicao=exposicao,
    )

    total_aberto_headline = len(extrato_aberto) + len(contabil_aberto)
    headline = (
        f"O sistema casou {len(matches)} das {total_extrato} transações, mas só "
        f"{_fmt_contagem(len(matches_exatos), 'casamento', 'casamentos')} "
        f"{pluralizar(len(matches_exatos), 'é exato', 'são exatos')}. {len(matches_similaridade)} diferem em "
        f"valor ou data, e {_fmt_contagem(total_aberto_headline, 'item', 'itens')} "
        f"{pluralizar(total_aberto_headline, 'segue sem par', 'seguem sem par')}."
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
                f"Apenas {_fmt_contagem(len(matches_exatos), 'casamento', 'casamentos')} "
                f"{pluralizar(len(matches_exatos), 'coincide', 'coincidem')} em valor e data. Os demais "
                f"{len(matches_similaridade)} foram aceitos por similaridade."
            ),
            "classe": "watch",
        },
        {
            "titulo": (
                f"{_fmt_contagem(total_aberto_headline, 'item', 'itens')} "
                f"{pluralizar(total_aberto_headline, 'segue', 'seguem')} sem correspondência"
            ),
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
    if exposicao["natureza_principal"]:
        # Exposição agrupada por natureza (issue XCRE-44, item A2c): o
        # takeaway financeiro mais acionável do relatório — soma das
        # divergências já explicadas por pares (seção 5b) + itens que
        # seguem totalmente sem par, separada em recebimentos/pagamentos.
        takeaways.append({
            "titulo": f"Principal exposição: {exposicao['natureza_principal']}, {exposicao['total_principal_fmt']}",
            "texto": (
                f"Soma das divergências (pares com diferença de valor + itens sem par nenhum) em "
                f"{exposicao['natureza_principal']} — ver a ponte detalhada na seção 5."
            ),
            "classe": "risk",
        })

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
        "pares_provaveis_linhas": pares_provaveis_linhas,
        "ponte_detalhada": ponte_detalhada,
        "resumo_itens_abertos": resumo_itens_abertos,
        "exposicao": exposicao,
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
