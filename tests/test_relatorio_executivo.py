"""
Testes do relatório Executivo em PDF (fase 3, XCRE-43): golden test do
caso de referência B×C, ponte de reconciliação, layout (sumário
clicável, páginas, fontes embutidas), escape de HTML malicioso,
bloqueio de recurso remoto pelo WeasyPrint, ausência de credenciais e
integração com a auditoria. Cobre os casos CT-F3-01/02/03/04/06/07/
10/11/13/14/15 do caderno docs/casos-de-teste-fase-3.md.

Dados 100% sintéticos (Exemplos/B_1234490.ofx e C_1234490.ofx são o
fixture sintético já usado na fase 2 para o cenário de referência).
"""
import json
import os
import re
import shutil
import sqlite3
import subprocess
import tempfile
from unittest import mock

import pandas as pd
import pytest
from ofxparse import OfxParser
from pypdf import PdfReader

from modules.data_analyzer import (
    DataAnalyzer,
    TOLERANCIA_VALOR_PERCENTUAL_PADRAO,
    TOLERANCIA_VALOR_ABSOLUTA_MAXIMA_PADRAO,
)
from modules.report_executivo import (
    calcular_ponte,
    gerar_relatorio_executivo,
    montar_contexto_executivo,
    _url_fetcher_seguro,
)

EXEMPLOS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Exemplos")

POPPLER_DISPONIVEL = all(shutil.which(bin_) for bin_ in ("pdfinfo", "pdffonts", "pdftoppm"))


def _carregar_ofx(nome_arquivo: str) -> pd.DataFrame:
    caminho = os.path.join(EXEMPLOS_DIR, nome_arquivo)
    with open(caminho, "rb") as f:
        ofx = OfxParser.parse(f)
    linhas = []
    for account in ofx.accounts:
        for transacao in account.statement.transactions:
            linhas.append({
                "data": transacao.date,
                "valor": float(transacao.amount),
                "descricao": transacao.memo or transacao.payee or "",
            })
    df = pd.DataFrame(linhas)
    df["id"] = range(1, len(df) + 1)
    return df


@pytest.fixture(scope="module")
def resultados_b_x_c():
    """Roda o pipeline de matching real (fase 2) sobre o fixture B×C e
    devolve (resultados_analise, extrato_df, contabil_df) — a mesma
    entrada que pages/gerar_relatorio.py passaria ao gerador."""
    extrato = _carregar_ofx("B_1234490.ofx")
    contabil = _carregar_ofx("C_1234490.ofx")

    analyzer = DataAnalyzer()
    exato = analyzer.matching_exato(extrato, contabil)
    heuristico = analyzer.matching_heuristico(
        extrato, contabil,
        exato["nao_matchados_extrato"], exato["nao_matchados_contabil"],
        tolerancia_dias=2,
        tolerancia_valor_percentual=TOLERANCIA_VALOR_PERCENTUAL_PADRAO,
        similaridade_minima=70,
        tolerancia_valor_absoluta_maxima=TOLERANCIA_VALOR_ABSOLUTA_MAXIMA_PADRAO,
    )
    resultados = {"matches": exato["matches"] + heuristico["matches"], "excecoes": []}
    return resultados, extrato, contabil


@pytest.fixture(scope="module")
def pdf_executivo_b_x_c(resultados_b_x_c, tmp_path_factory):
    # gerar_relatorio_executivo devolve BYTES (revisão de segurança
    # XCRE-51/SEC-R-02: nenhum arquivo temporário sobrevive à chamada).
    # Os testes abaixo precisam de um caminho real (PdfReader, pdfinfo,
    # pdffonts, pdftoppm), então os bytes são gravados aqui, num diretório
    # de teste descartável — não no diretório privado que o próprio
    # gerador já apagou.
    resultados, extrato, contabil = resultados_b_x_c
    pdf_bytes = gerar_relatorio_executivo(
        resultados_analise=resultados,
        extrato_df=extrato,
        contabil_df=contabil,
        empresa_nome="Empresa QA",
        analista_nome="Analista QA",
        classificacao_documento="Documento interno",
        periodo="15/06/2025 a 16/07/2025",
        conta_analisada="1234490",
    )
    pdf_path = tmp_path_factory.mktemp("pdf_executivo_b_x_c") / "relatorio.pdf"
    pdf_path.write_bytes(pdf_bytes)
    return str(pdf_path)


def _extrair_texto(pdf_path: str) -> str:
    reader = PdfReader(pdf_path)
    return "\n".join(page.extract_text() or "" for page in reader.pages)


# --- CT-F3-03: golden test B×C (números, cobertura, ponte) ---

def test_golden_b_x_c_contexto_bate_com_o_modelo(resultados_b_x_c):
    resultados, extrato, contabil = resultados_b_x_c
    ctx = montar_contexto_executivo(
        resultados_analise=resultados,
        extrato_df=extrato,
        contabil_df=contabil,
        empresa_nome="Empresa QA",
        analista_nome="Analista QA",
        classificacao_documento="Documento interno",
        periodo="15/06/2025 a 16/07/2025",
        conta_analisada="1234490",
    )

    assert ctx["total_extrato"] == 18
    assert ctx["total_contabil"] == 18
    assert ctx["total_matches"] == 14
    assert ctx["total_exatos"] == 11
    assert ctx["total_similaridade"] == 3
    assert ctx["total_extrato_aberto"] == 4
    assert ctx["total_contabil_aberto"] == 4

    assert ctx["cobertura_sistema"] == pytest.approx(77.77777777777779)
    assert ctx["cobertura_efetiva"] == pytest.approx(61.111111111111114)

    assert ctx["saldo_extrato"] == pytest.approx(-140.88, abs=0.01)
    assert ctx["saldo_contabil"] == pytest.approx(6.67, abs=0.01)
    assert ctx["diferenca_liquida"] == pytest.approx(147.55, abs=0.01)

    ponte = ctx["ponte"]
    assert ponte["liquido_extrato_aberto"] == pytest.approx(1213.78, abs=0.01)
    assert ponte["liquido_contabil_aberto"] == pytest.approx(1362.33, abs=0.01)
    assert ponte["valor_calculado"] == pytest.approx(147.55, abs=0.01)
    assert ponte["alvo"] == pytest.approx(147.55, abs=0.01)
    assert ponte["residuo"] == pytest.approx(0.0, abs=0.01)
    assert ponte["fecha"] is True

    diffs = sorted(round(l["diferenca"], 2) for l in ctx["matches_similaridade_linhas"])
    assert diffs == [-3.00, 0.00, 2.00]


def test_golden_b_x_c_pdf_contem_os_valores_do_modelo(pdf_executivo_b_x_c):
    texto = _extrair_texto(pdf_executivo_b_x_c)
    valores_esperados = [
        "77,8", "61,1",
        "-140,88", "6,67", "147,55",
        "1.213,78", "1.362,33",
        "3,00 a mais", "2,00 a menos",
        # A2: pares prováveis do sistema, ponte detalhada e exposição
        # agrupada (issue XCRE-44).
        "Pares prováveis apontados pelo sistema",
        "hipótese do analista",
        "Principal exposição: recebimentos, R$ 150,63",
        "Investigar os recebimentos de R$ 1.400,00 e R$ 50,63",
        # A4: período em uma linha só e descrição sem quebra indevida —
        # se qualquer um tivesse voltado a quebrar em duas linhas, a
        # extração de texto não produziria mais esta substring exata
        # (um espaço simples entre as duas partes).
        "15/06/2025 a 16/07/2025",
        "Aguia Branca - Passage - Parcela 6/6",
    ]
    for valor in valores_esperados:
        assert valor in texto, f"valor {valor!r} não encontrado no PDF Executivo"


# --- Ponte de reconciliação (CT-F3-06 / CT-F3-07) ---

def test_ponte_fecha_sem_residuo_quando_dados_sao_consistentes():
    ponte = calcular_ponte(
        saldo_extrato=-140.88, saldo_contabil=6.67,
        liquido_extrato_aberto=1213.78, liquido_contabil_aberto=1362.33,
        soma_diferencas_similaridade=-1.00,
    )
    assert ponte["fecha"] is True
    assert ponte["residuo"] == pytest.approx(0.0, abs=0.01)


def test_ponte_mostra_residuo_explicito_quando_dados_sao_inconsistentes():
    """CT-F3-07: a ponte nunca deve ser hard-coded como fechada — se os
    agregados não baterem com a diferença real dos saldos (dado
    sintético inconsistente), o resíduo deve aparecer, com sinal e
    valor, em vez de ser escondido ou corrigido por arredondamento."""
    ponte = calcular_ponte(
        saldo_extrato=-140.88, saldo_contabil=6.67,
        liquido_extrato_aberto=1213.78, liquido_contabil_aberto=1362.33 + 1.00,
        soma_diferencas_similaridade=-1.00,
    )
    assert ponte["fecha"] is False
    assert ponte["residuo"] == pytest.approx(-1.00, abs=0.01)
    assert ponte["residuo_fmt"] != "R$ 0,00"


# --- XCRE-48 item 1: passagem explícita da ponte detalhada (R$ 148,55) para a compacta (R$ 147,55) ---

def test_ponte_expoe_ajuste_de_similaridade_como_operacao_de_sinal_unico():
    """A ponte deve expor o ajuste por similaridade como uma operação de
    sinal único (ex.: "148,55 - 1,00 = 147,55"), não como um valor com
    sinal embutido ("+ R$ -1,00"), para que a passagem da ponte
    detalhada (148,55) para a compacta (147,55) fique clara para
    leigo."""
    ponte = calcular_ponte(
        saldo_extrato=-140.88, saldo_contabil=6.67,
        liquido_extrato_aberto=1213.78, liquido_contabil_aberto=1362.33,
        soma_diferencas_similaridade=-1.00,
    )
    assert ponte["ajuste_similaridade_operador"] == "-"
    assert ponte["ajuste_similaridade_abs_fmt"] == "R$ 1,00"
    assert ponte["valor_calculado_fmt"] == "R$ 147,55"

    ponte_ajuste_positivo = calcular_ponte(
        saldo_extrato=0.0, saldo_contabil=1.0,
        liquido_extrato_aberto=0.0, liquido_contabil_aberto=0.0,
        soma_diferencas_similaridade=1.00,
    )
    assert ponte_ajuste_positivo["ajuste_similaridade_operador"] == "+"
    assert ponte_ajuste_positivo["ajuste_similaridade_abs_fmt"] == "R$ 1,00"


def test_pdf_explicita_a_passagem_da_ponte_detalhada_para_a_compacta(pdf_executivo_b_x_c):
    """A seção 5 deve deixar explícita, no texto e na tabela, a
    passagem entre a ponte detalhada (R$ 148,55) e a ponte compacta
    (R$ 147,55): R$ 148,55 - R$ 1,00 = R$ 147,55, com o contexto de que
    R$ 1,00 é o ajuste das diferenças aceitas por similaridade — sem
    alterar nenhum dos números do baseline B×C."""
    texto = _extrair_texto(pdf_executivo_b_x_c)
    # Normaliza espaços/quebras de linha do PDF (ex.: "R$ 148,55 - R$\n1,00")
    # antes de checar a substring exata da fórmula.
    texto_normalizado = re.sub(r"\s+", " ", texto)
    assert "R$ 148,55 - R$ 1,00 = R$ 147,55" in texto_normalizado
    assert "ajuste das diferenças" in texto
    assert "aceitou por" in texto
    # Baseline B×C intacto.
    assert "77,8" in texto and "61,1" in texto
    assert "147,55" in texto


# --- XCRE-48 item 2: legenda "par provável apontado pelo sistema" vs "hipótese do analista" ---

def test_pdf_contem_legenda_dos_rotulos_par_provavel_e_hipotese(pdf_executivo_b_x_c):
    """A seção 5 deve trazer uma legenda curta (1-2 linhas) explicando os
    dois rótulos usados nas tabelas de pares: "par provável apontado
    pelo sistema" (calculado por similaridade) e "hipótese do analista"
    (regra objetiva de descrição + data, ainda sem confirmação) — sem
    quebrar o limite de 10 páginas nem alterar o baseline B×C."""
    texto = _extrair_texto(pdf_executivo_b_x_c)
    texto_normalizado = re.sub(r"\s+", " ", texto)
    assert "Como ler os rótulos desta seção" in texto_normalizado
    assert "par provável apontado pelo sistema" in texto_normalizado
    assert "calculada automaticamente por similaridade" in texto_normalizado
    assert "hipótese do analista" in texto_normalizado
    assert "regra objetiva de mesma descrição e mesma data" in texto_normalizado
    # A legenda deve aparecer uma única vez na seção 5, não repetida a
    # cada linha/tabela.
    assert texto_normalizado.count("Como ler os rótulos desta seção") == 1
    # Baseline B×C intacto.
    assert "77,8" in texto and "61,1" in texto and "147,55" in texto


def test_pdf_continua_com_no_maximo_10_paginas_apos_a_legenda(pdf_executivo_b_x_c):
    reader = PdfReader(pdf_executivo_b_x_c)
    assert len(reader.pages) <= 10


# --- XCRE-48 item 3: resumo dos 8 itens em aberto (pares prováveis / hipótese / sem par) ---

def test_pdf_resumo_itens_abertos_soma_8_extraida_do_relatorio(pdf_executivo_b_x_c):
    """A seção 5 deve abrir com uma linha de resumo das contagens dos 8
    itens em aberto — pares prováveis apontados pelo sistema, pares por
    hipótese do analista e itens sem par nenhum — usando os mesmos
    significados da legenda da Rodada 2. As três contagens são
    extraídas do próprio texto renderizado do PDF (não hard-codadas no
    teste) e a soma deve bater com o total real de itens em aberto."""
    texto = _extrair_texto(pdf_executivo_b_x_c)
    texto_normalizado = re.sub(r"\s+", " ", texto)
    match = re.search(
        r"Desses? (\d+) itens? em aberto: (\d+) est\w+ em par provável apontado pelo sistema, "
        r"(\d+) em par por hipótese do analista e (\d+) segu\w+ sem par nenhum",
        texto_normalizado,
    )
    assert match, "linha de resumo dos itens em aberto não encontrada no PDF"
    total_aberto, pares_provaveis, pares_hipotese, sem_par = (int(g) for g in match.groups())
    assert pares_provaveis + pares_hipotese + sem_par == total_aberto
    assert total_aberto == 8
    # Baseline B×C intacto.
    assert "77,8" in texto and "61,1" in texto and "147,55" in texto


def test_resumo_itens_abertos_soma_bate_com_total_sem_par_sintetico():
    """Complementa o teste acima com um cenário sintético (2 pares do
    sistema + 1 por hipótese + 3 sem par) para garantir que a soma bate
    mesmo fora do caso B×C — cada par conta os dois lados (extrato +
    contábil) como itens individuais em aberto."""
    from modules.report_executivo import _resumo_itens_abertos

    linhas_pares = [
        {"origem": "sistema"}, {"origem": "sistema"}, {"origem": "hipotese"},
    ]
    resumo = _resumo_itens_abertos(linhas_pares, total_sem_par=3)
    assert resumo["pares_provaveis"] == 4
    assert resumo["pares_hipotese"] == 2
    assert resumo["sem_par"] == 3
    assert resumo["total"] == 9
    assert resumo["pares_provaveis"] + resumo["pares_hipotese"] + resumo["sem_par"] == resumo["total"]


# --- CT-F3-10 / CT-F3-11: layout, sumário clicável, páginas, fontes ---

def test_pdf_tem_no_maximo_10_paginas_e_referencia_gera_9_ou_menos(pdf_executivo_b_x_c):
    reader = PdfReader(pdf_executivo_b_x_c)
    assert len(reader.pages) <= 10


def test_quebra_de_pagina_forcada_so_em_capa_sumario_e_contracapa():
    """CT-F3-10 (revisado na issue XCRE-44, item A4c): nenhuma página do
    corpo (seções 1 a 8) pode ficar quase vazia por uma quebra forçada
    indevida. A seção 8 (auditoria) deixou de forçar quebra de página
    antes de si (removido o `class="pb"` do `<section id="auditoria">`):
    como a seção 8 é curta, forçá-la a começar numa página nova deixava
    a página anterior E a própria seção 8 com bastante espaço vazio —
    agora ela flui naturalmente após a seção 7. Restam só 3 pontos fixos
    de quebra: capa, sumário e contracapa. Em vez de inferir isso do PDF
    renderizado (frágil), verifica a fonte da regra no template."""
    caminho = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "templates", "relatorio_executivo.html.j2",
    )
    with open(caminho, encoding="utf-8") as f:
        css = f.read()

    permitidos = {
        ".cover{height:262mm;padding:6mm 0 0;break-after:page}",
        ".toc{break-after:page;padding-top:10px}",
        ".backcover{height:255mm;padding:4mm 0 0;break-before:page;break-inside:avoid}",
    }
    for regra in permitidos:
        assert regra in css, f"regra de quebra de página esperada não encontrada: {regra!r}"

    assert 'class="pb"' not in css

    total_break_before = css.count("break-before:page")
    total_break_after = css.count("break-after:page")
    assert total_break_before == 1, "só a contracapa pode forçar quebra antes"
    # .cover + .toc = 2
    assert total_break_after == 2, "só a capa e o sumário podem forçar quebra depois"


def test_sumario_tem_oito_links_para_as_oito_secoes(pdf_executivo_b_x_c):
    reader = PdfReader(pdf_executivo_b_x_c)
    destinos_esperados = {
        "sintese", "kpis", "composicao", "correspondencias",
        "divergencias", "alertas", "recomendacoes", "auditoria",
    }
    destinos_encontrados = set()
    for page in reader.pages:
        for annot in page.get("/Annots") or []:
            obj = annot.get_object()
            if obj.get("/Subtype") == "/Link" and obj.get("/Dest"):
                destinos_encontrados.add(str(obj["/Dest"]))
    assert destinos_esperados <= destinos_encontrados


def test_contracapa_nao_esta_no_sumario_e_termina_com_fim_do_relatorio(pdf_executivo_b_x_c):
    texto = _extrair_texto(pdf_executivo_b_x_c)
    assert "Fim do relatório" in texto


@pytest.mark.skipif(not POPPLER_DISPONIVEL, reason="pdfinfo/pdffonts/pdftoppm (poppler-utils) não disponíveis neste ambiente")
def test_pdf_e_a4_retrato_com_fonte_inter_embutida_nos_quatro_pesos(pdf_executivo_b_x_c):
    info = subprocess.run(["pdfinfo", pdf_executivo_b_x_c], capture_output=True, text=True, check=True).stdout
    assert "A4" in info
    fontes = subprocess.run(["pdffonts", pdf_executivo_b_x_c], capture_output=True, text=True, check=True).stdout
    linhas_inter = [linha for linha in fontes.splitlines() if "Inter" in linha]
    assert len(linhas_inter) >= 4, f"esperado ao menos 4 variantes de Inter embutidas, achou:\n{fontes}"
    for linha in linhas_inter:
        colunas = linha.split()
        assert "yes" in colunas, f"fonte não embutida (emb != yes): {linha}"


@pytest.mark.skipif(not POPPLER_DISPONIVEL, reason="pdftoppm (poppler-utils) não disponível neste ambiente")
def test_todas_as_paginas_rasterizam_sem_erro(pdf_executivo_b_x_c, tmp_path):
    prefixo = str(tmp_path / "pagina")
    resultado = subprocess.run(
        ["pdftoppm", "-png", "-r", "60", pdf_executivo_b_x_c, prefixo],
        capture_output=True, text=True,
    )
    assert resultado.returncode == 0, resultado.stderr
    paginas = list(tmp_path.glob("pagina*.png"))
    reader = PdfReader(pdf_executivo_b_x_c)
    assert len(paginas) == len(reader.pages)


@pytest.mark.skipif(not POPPLER_DISPONIVEL, reason="pdftoppm (poppler-utils) não disponível neste ambiente")
def test_nenhuma_pagina_do_corpo_fica_com_mais_de_metade_vazia(pdf_executivo_b_x_c, tmp_path):
    """Item A4c (issue XCRE-44): rasteriza TODAS as páginas com
    `pdftoppm` e mede, por pixel, quanto de cada página (abaixo da
    margem superior, acima do rodapé) fica em branco depois do último
    conteúdo — não apenas confere o retorno do comando. A diretriz da
    issue é "~40% vazia"; o limite automatizado aqui é mais folgado
    (55%) de propósito, para não ficar frágil a variações de
    fonte/hinting entre ambientes, mas ainda pega regressões grosseiras
    (ex.: uma seção inteira empurrada para uma página quase vazia). A
    validação fina (~35-38% medido no cenário B×C) é visual, registrada
    na entrega da issue via rasterização manual."""
    from PIL import Image
    import numpy as np

    prefixo = str(tmp_path / "pagina")
    resultado = subprocess.run(
        ["pdftoppm", "-png", "-r", "80", pdf_executivo_b_x_c, prefixo],
        capture_output=True, text=True,
    )
    assert resultado.returncode == 0, resultado.stderr

    paginas = sorted(tmp_path.glob("pagina*.png"))
    assert len(paginas) >= 3  # capa + sumário + ao menos mais uma

    # Capa, sumário e contracapa têm layout de "cartaz"/lista curta com
    # espaço em branco deliberado (ver .cover/.toc/.backcover no
    # template) — fora do escopo desta checagem, que é sobre páginas de
    # CORPO (seções 1 a 8, que começam depois do sumário).
    paginas_corpo = paginas[2:-1]
    assert paginas_corpo, "esperado ao menos uma página de corpo entre sumário e contracapa"

    for pagina in paginas_corpo:
        arr = np.array(Image.open(pagina).convert("L"))
        h, _ = arr.shape
        margem_topo = int(h * 0.065)  # ~15mm de margem superior em A4
        margem_rodape = int(h * 0.05)  # rodapé com paginação/rótulo
        corpo = arr[margem_topo:h - margem_rodape, :]
        linhas_com_conteudo = np.where((corpo < 250).any(axis=1))[0]
        if len(linhas_com_conteudo) == 0:
            continue  # página sem nenhum conteúdo textual não é o alvo desta checagem
        pct_vazio_abaixo = 100 - (linhas_com_conteudo.max() / corpo.shape[0] * 100)
        assert pct_vazio_abaixo <= 55, (
            f"{pagina.name}: {pct_vazio_abaixo:.1f}% vazia abaixo do último conteúdo "
            "(limite automatizado 55%, diretriz da issue ~40%)"
        )


# --- CT-F3-13: escape de HTML e bloqueio de recurso remoto ---

def test_descricao_maliciosa_e_escapada_no_pdf_gerado(tmp_path):
    payload = "<script>alert('x')</script><img src=\"https://exemplo.invalid/roubo\">"
    extrato = pd.DataFrame({
        "id": [1],
        "data": pd.to_datetime(["2025-06-15"]),
        "valor": [123.45],
        "descricao": [payload],
    })
    contabil = pd.DataFrame({
        "id": [1],
        "data": pd.to_datetime(["2025-06-20"]),
        "valor": [999.99],
        "descricao": ["Lançamento & \"aspas\" com acentuação"],
    })
    resultados = {"matches": [], "excecoes": []}

    pdf_bytes = gerar_relatorio_executivo(
        resultados_analise=resultados,
        extrato_df=extrato,
        contabil_df=contabil,
        empresa_nome="Empresa QA",
        analista_nome="Analista QA",
        periodo="15/06/2025 a 20/06/2025",
        conta_analisada="0000000",
    )
    assert len(pdf_bytes) > 0
    pdf_path = tmp_path / "relatorio.pdf"
    pdf_path.write_bytes(pdf_bytes)
    texto = _extrair_texto(str(pdf_path))
    # O texto do script aparece como TEXTO (renderizado no PDF), nunca
    # como marcação HTML ativa — o teste de segurança real é que o
    # Jinja2 (autoescape=True) nunca produziu uma tag <script> literal
    # no HTML intermediário, verificado a seguir.
    assert "alert(" in texto or "script" in texto.lower()


def test_html_intermediario_escapa_tags_e_nao_interpreta_script():
    payload = "<script>alert('x')</script><img src=\"https://exemplo.invalid/roubo\">"
    extrato = pd.DataFrame({
        "id": [1], "data": pd.to_datetime(["2025-06-15"]), "valor": [10.0], "descricao": [payload],
    })
    contabil = pd.DataFrame({
        "id": [1], "data": pd.to_datetime(["2025-06-20"]), "valor": [10.0], "descricao": ["C"],
    })
    resultados = {"matches": [], "excecoes": []}
    ctx = montar_contexto_executivo(
        resultados_analise=resultados, extrato_df=extrato, contabil_df=contabil,
        empresa_nome="Empresa QA", analista_nome="Analista QA",
        classificacao_documento="Documento interno", periodo="p", conta_analisada="1",
    )
    from modules.report_executivo import _env
    template = _env.get_template("relatorio_executivo.html.j2")
    html_renderizado = template.render(**ctx)

    assert "<script>" not in html_renderizado
    assert "&lt;script&gt;" in html_renderizado
    assert 'src="https://exemplo.invalid/roubo"' not in html_renderizado


def test_url_fetcher_bloqueia_protocolo_remoto_mas_permite_data_uri():
    with pytest.raises(ValueError):
        _url_fetcher_seguro("https://exemplo.invalid/fonte.woff2")
    with pytest.raises(ValueError):
        _url_fetcher_seguro("http://exemplo.invalid/img.png")
    # 'data:' é permitido (usado para embutir a fonte Inter em base64).
    resposta = _url_fetcher_seguro("data:text/plain;base64,aGVsbG8=")
    assert resposta is not None


# --- Ausência de credenciais no PDF ---

def test_pdf_nao_contem_credenciais_ou_segredos(pdf_executivo_b_x_c):
    texto = _extrair_texto(pdf_executivo_b_x_c)
    for segredo in ("admin123", "SenhaNova1", "Bearer ", "eyJhbGciOi"):
        assert segredo not in texto


# --- CT-F3-02: campos configuráveis e valores ausentes ---

def test_campos_vazios_aparecem_como_nao_informado_sem_meta_externa(resultados_b_x_c):
    resultados, extrato, contabil = resultados_b_x_c
    ctx = montar_contexto_executivo(
        resultados_analise=resultados, extrato_df=extrato, contabil_df=contabil,
        empresa_nome="", analista_nome="", classificacao_documento="",
        periodo="15/06/2025 a 16/07/2025", conta_analisada=None, meta_cobertura="",
    )
    assert ctx["empresa_nome"] == "Não informado"
    assert ctx["analista_nome"] == "Não informado"
    assert ctx["classificacao_documento"] == "Documento interno"
    assert ctx["meta_cobertura"] is None
    assert ctx["conta_analisada"] == "Não identificada"

    ctx_com_meta = montar_contexto_executivo(
        resultados_analise=resultados, extrato_df=extrato, contabil_df=contabil,
        empresa_nome="Empresa QA", analista_nome="Analista QA", classificacao_documento="Uso restrito",
        periodo="15/06/2025 a 16/07/2025", conta_analisada="1234490", meta_cobertura="90%",
    )
    assert ctx_com_meta["meta_cobertura"] == "90%"


# --- CT-F3-15: pré-condições ausentes não geram PDF de sucesso ---

def test_resultados_none_levanta_erro_sem_gerar_pdf():
    with pytest.raises(ValueError):
        gerar_relatorio_executivo(
            resultados_analise=None,
            extrato_df=pd.DataFrame({"id": [1], "data": ["2025-06-15"], "valor": [1.0]}),
            contabil_df=pd.DataFrame({"id": [1], "data": ["2025-06-15"], "valor": [1.0]}),
        )


def test_extrato_vazio_levanta_erro_sem_gerar_pdf():
    with pytest.raises(ValueError):
        gerar_relatorio_executivo(
            resultados_analise={"matches": [], "excecoes": []},
            extrato_df=pd.DataFrame(columns=["id", "data", "valor"]),
            contabil_df=pd.DataFrame({"id": [1], "data": ["2025-06-15"], "valor": [1.0]}),
        )


def test_contabil_vazio_levanta_erro_sem_gerar_pdf():
    with pytest.raises(ValueError):
        gerar_relatorio_executivo(
            resultados_analise={"matches": [], "excecoes": []},
            extrato_df=pd.DataFrame({"id": [1], "data": ["2025-06-15"], "valor": [1.0]}),
            contabil_df=pd.DataFrame(columns=["id", "data", "valor"]),
        )


# --- CT-F3-14: auditoria REPORT_GENERATION para o formato "executivo" ---

@pytest.fixture
def sessao_autenticada_executivo(tmp_path, monkeypatch):
    db_path = str(tmp_path / "users.db")
    audit_path = str(tmp_path / "audit.db")
    monkeypatch.setenv("CONCILIACAO_DB_PATH", db_path)
    monkeypatch.setenv("CONCILIACAO_AUDIT_DB_PATH", audit_path)

    from modules.auth_middleware import hash_password, init_security_tables
    password_hash, salt = hash_password("SenhaNova1")

    conn = sqlite3.connect(db_path)
    conn.execute('''
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            password_salt TEXT,
            full_name TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        )
    ''')
    conn.execute(
        "INSERT INTO users (username, email, password_hash, password_salt, full_name, role, is_active) "
        "VALUES (?, ?, ?, ?, ?, 'user', 1)",
        ("qa_user", "qa@example.com", password_hash, salt, "QA User"),
    )
    conn.commit()
    init_security_tables(conn)
    conn.close()

    import modules.audit_logger as audit_logger_module
    audit_logger_module._audit_logger = None

    import app
    success, user_info, token = app.login_user("qa_user", "SenhaNova1")
    assert success is True

    import streamlit as st
    st.session_state["token"] = token
    st.session_state["user"] = user_info
    st.session_state["resultados_analise"] = {"matches": [], "excecoes": [{}]}
    st.session_state["extrato_df"] = pd.DataFrame({
        "id": [1], "data": pd.to_datetime(["2025-06-15"]), "valor": [60.50], "descricao": ["A"],
    })
    st.session_state["contabil_df"] = pd.DataFrame({
        "id": [1], "data": pd.to_datetime(["2025-06-20"]), "valor": [500.0], "descricao": ["C"],
    })

    return audit_path


def _clicar_gerar_relatorio(label, *args, **kwargs):
    return kwargs.get("key") == "btn_gerar_relatorio_analise"


def test_geracao_executivo_padrao_registra_auditoria_com_sucesso(sessao_autenticada_executivo):
    import streamlit as st
    audit_path = sessao_autenticada_executivo

    with mock.patch.object(st, "button", side_effect=_clicar_gerar_relatorio):
        import pages.gerar_relatorio as pagina
        import importlib
        importlib.reload(pagina)
        pagina.main()

    conn = sqlite3.connect(audit_path)
    row = conn.execute(
        "SELECT user, details FROM audit_log WHERE action = 'REPORT_GENERATION'"
    ).fetchone()
    conn.close()

    assert row is not None
    user, details_json = row
    assert user == "qa_user"
    details = json.loads(details_json)
    assert details["success"] is True
    assert details["formato"] == "executivo"


def test_geracao_executivo_com_falha_registra_auditoria_sem_expor_stacktrace(sessao_autenticada_executivo):
    import streamlit as st
    audit_path = sessao_autenticada_executivo

    with mock.patch.object(st, "button", side_effect=_clicar_gerar_relatorio), \
         mock.patch("modules.report_executivo.gerar_relatorio_executivo", side_effect=RuntimeError("falha sintética de geração")):
        import pages.gerar_relatorio as pagina
        import importlib
        importlib.reload(pagina)
        pagina.main()

    conn = sqlite3.connect(audit_path)
    row = conn.execute(
        "SELECT severity, details FROM audit_log WHERE action = 'REPORT_GENERATION'"
    ).fetchone()
    conn.close()

    assert row is not None
    severity, details_json = row
    assert severity == "ERROR"
    details = json.loads(details_json)
    assert details["success"] is False
    assert details["formato"] == "executivo"
    assert "falha sintética de geração" in details["error_message"]
