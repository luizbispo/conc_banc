"""
Testes AppTest para o item 3 da fase 7 (XCRE-55): tela de relatório no
visual v3 conciso.

Visão padrão de destino: título "Relatório Final", formulário no CORPO
da página (não na sidebar) com Nome da Empresa, Nome do Contador
(Analista), Classificação do documento e Observações; o período
aparece só como TEXTO informativo somente-leitura ("Período: ... ,
calculado dos arquivos" — nenhum widget editável); botão primário para
gerar o relatório e, depois de gerado, um jeito de baixar o PDF mais a
mensagem de sucesso. Os gráficos/resumo/abas que duplicavam a tela de
análise saem desta tela (continuam no PDF e em pages/analise_dados.py).
Sem meta de cobertura, sem período editável, sem pré-visualização/
iframe. Auditoria e log continuam sendo chamados como antes.

Escrito ANTES da implementação (padrão do squad para XCRE-55): hoje o
formulário fica na sidebar, o período nunca é mostrado ao usuário, e há
uma seção "Resumo da Análise" + "Sumário Executivo" com gráficos e 3
abas que duplicam pages/analise_dados.py — os testes abaixo devem
falhar contra o código atual.

Mesmo padrão de mock de `st.button` (via key) e de
`modules.report_executivo.gerar_relatorio_executivo` de
tests/test_gerar_relatorio_auditoria.py, mas dirigindo a página via
`streamlit.testing.v1.AppTest` (permite inspecionar o layout renderizado
— texto_input, tabs, markdown — em vez de só o banco de auditoria).

Dados 100% sintéticos.
"""
import os
import re
import sqlite3
from unittest import mock

import pandas as pd
import pytest


def _criar_usuario_e_autenticar(tmp_path, monkeypatch, username: str):
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
        (username, f"{username}@example.com", password_hash, salt, "QA Relatório"),
    )
    conn.commit()
    init_security_tables(conn)
    conn.close()

    import modules.audit_logger as audit_logger_module
    audit_logger_module._audit_logger = None

    import app
    success, user_info, token = app.login_user(username, "SenhaNova1")
    assert success is True
    return token, user_info, audit_path


@pytest.fixture
def app_autenticado_com_analise(tmp_path, monkeypatch):
    token, user_info, audit_path = _criar_usuario_e_autenticar(tmp_path, monkeypatch, "qa_relatorio")

    extrato_df = pd.DataFrame({
        "id": [1, 2],
        "data": pd.to_datetime(["2025-06-10", "2025-06-12"]),
        "valor": [-100.00, 250.00],
        "descricao": ["Pagamento Fornecedor A", "Recebimento Cliente B"],
    })
    contabil_df = pd.DataFrame({
        "id": [1, 2],
        "data": pd.to_datetime(["2025-06-10", "2025-06-12"]),
        "valor": [-100.00, 250.00],
        "descricao": ["Pagamento Fornecedor A", "Recebimento Cliente B"],
    })
    resultados_analise = {
        "matches": [
            {
                "tipo_match": "1:1", "camada": "exata",
                "ids_extrato": [1], "ids_contabil": [1],
                "valor_total": 100.0, "confianca": 100, "explicacao": "match exato",
                "chave_match": "EXATO_1_1",
            },
        ],
        "excecoes": [{"ids_envolvidos": [2]}],
    }
    return token, user_info, extrato_df, contabil_df, resultados_analise, audit_path


def _carregar_pagina(app_autenticado_com_analise):
    from streamlit.testing.v1 import AppTest

    token, user_info, extrato_df, contabil_df, resultados_analise, _audit_path = app_autenticado_com_analise
    app_py = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")

    at = AppTest.from_file(app_py, default_timeout=30)
    at.session_state["token"] = token
    at.session_state["user"] = user_info
    at.session_state["extrato_df"] = extrato_df
    at.session_state["contabil_df"] = contabil_df
    at.session_state["resultados_analise"] = resultados_analise
    at.session_state["conta_analisada"] = "12345678"
    at.switch_page("pages/gerar_relatorio.py")
    at.run()
    assert not at.exception, f"página levantou exceção só ao carregar: {at.exception}"
    return at


def test_titulo_e_formulario_no_corpo_no_sidebar(app_autenticado_com_analise):
    at = _carregar_pagina(app_autenticado_com_analise)

    titulos = [t.value for t in at.title]
    assert any("Relatório Final" in t for t in titulos)

    # formulário no CORPO da página: os 3 campos de texto curtos + a
    # observação continuam existindo, mas fora da sidebar.
    rotulos_corpo = {ti.label for ti in at.text_input} | {ta.label for ta in at.text_area}
    assert "Nome da Empresa" in rotulos_corpo
    assert "Nome do Contador (Analista)" in rotulos_corpo
    assert "Classificação do documento" in rotulos_corpo
    assert any("observações" in r.lower() for r in rotulos_corpo)

    assert len(at.sidebar.text_input) == 0, "o formulário não deve mais estar na sidebar"
    assert len(at.sidebar.text_area) == 0


def test_periodo_e_texto_somente_leitura_sem_campo_editavel(app_autenticado_com_analise):
    at = _carregar_pagina(app_autenticado_com_analise)

    textos = " ".join(m.value for m in at.markdown) + " ".join(c.value for c in at.caption)
    assert "período" in textos.lower()
    assert "calculado dos arquivos" in textos.lower()
    # as datas sintéticas do fixture (10/06 e 12/06/2025) devem aparecer
    # no texto do período calculado automaticamente
    assert "10/06/2025" in textos and "12/06/2025" in textos

    # nenhum widget de período editável (nem text_input, nem date_input)
    rotulos_editaveis = [ti.label for ti in at.text_input] + [di.label for di in at.date_input]
    assert not any("período" in r.lower() for r in rotulos_editaveis)


def test_sem_meta_de_cobertura_sem_preview_sem_iframe(app_autenticado_com_analise):
    at = _carregar_pagina(app_autenticado_com_analise)

    corpo_markdown = " ".join(m.value for m in at.markdown).lower()
    assert "meta" not in corpo_markdown or "meta de cobertura" not in corpo_markdown
    assert "<iframe" not in corpo_markdown


def test_graficos_resumo_e_abas_duplicados_da_analise_foram_removidos(app_autenticado_com_analise):
    at = _carregar_pagina(app_autenticado_com_analise)

    # "Resumo da Análise" (4 métricas) e "Sumário Executivo" (abas Visão
    # Geral/Correspondências/Divergências com gráficos) duplicavam
    # pages/analise_dados.py — devem ter saído desta tela.
    assert len(at.tabs) == 0, "as abas de resumo/gráficos duplicados da análise não devem mais existir aqui"
    rotulos_metric = {m.label for m in at.metric}
    for rotulo in ("Transações Analisadas", "Lançamentos Analisados", "Cobertura de Análise", "Divergências Identificadas"):
        assert rotulo not in rotulos_metric


def test_botao_primario_gerar_relatorio_existe_com_a_mesma_key(app_autenticado_com_analise):
    at = _carregar_pagina(app_autenticado_com_analise)

    botoes = [b for b in at.button if b.key == "btn_gerar_relatorio_analise"]
    assert len(botoes) == 1, "a key do botão de gerar relatório precisa continuar 'btn_gerar_relatorio_analise' (usada por outros testes de auditoria)"
    assert botoes[0].proto.type == "primary"


def test_apos_gerar_mostra_link_de_download_e_sucesso_sem_iframe(app_autenticado_com_analise):
    at = _carregar_pagina(app_autenticado_com_analise)

    with mock.patch("modules.report_executivo.gerar_relatorio_executivo", return_value=b"%PDF-1.4 conteudo sintetico"):
        botao = next(b for b in at.button if b.key == "btn_gerar_relatorio_analise")
        botao.click()
        at.run()

    assert not at.exception, f"geração do relatório levantou exceção: {at.exception}"

    corpo_markdown = " ".join(m.value for m in at.markdown)
    assert "download=" in corpo_markdown, "link/botão para baixar o PDF não encontrado"
    assert "<iframe" not in corpo_markdown.lower(), "não pode haver pré-visualização em iframe"
    assert any("sucesso" in s.value.lower() for s in at.success), "mensagem de sucesso não encontrada"


def _contraste_wcag(hex_fundo: str, hex_texto: str) -> float:
    """Razão de contraste WCAG 2.x entre duas cores hex (#RRGGBB)."""
    def luminancia(hex_cor: str) -> float:
        hex_cor = hex_cor.lstrip("#")
        r, g, b = (int(hex_cor[i:i + 2], 16) / 255 for i in (0, 2, 4))

        def linearizar(c: float) -> float:
            return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

        r, g, b = linearizar(r), linearizar(g), linearizar(b)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    l1, l2 = luminancia(hex_fundo), luminancia(hex_texto)
    mais_claro, mais_escuro = max(l1, l2), min(l1, l2)
    return (mais_claro + 0.05) / (mais_escuro + 0.05)


def test_link_baixar_pdf_tem_contraste_aa_sem_mudar_o_link(app_autenticado_com_analise):
    """Achado da verificação integrada (CT-F7-VIS-11): o link "Baixar
    PDF" tinha 2,7796:1 (branco sobre #4CAF50) — abaixo do mínimo AA de
    4,5:1 para texto normal. O download em si (href com o PDF em
    base64, atributo `download`) não pode mudar, só as cores."""
    at = _carregar_pagina(app_autenticado_com_analise)

    with mock.patch("modules.report_executivo.gerar_relatorio_executivo", return_value=b"%PDF-1.4 conteudo sintetico"):
        botao = next(b for b in at.button if b.key == "btn_gerar_relatorio_analise")
        botao.click()
        at.run()

    assert not at.exception, f"geração do relatório levantou exceção: {at.exception}"

    corpo_markdown = " ".join(m.value for m in at.markdown)
    link_match = re.search(r'<a href="data:application/pdf;base64,[^"]+" download="[^"]+"[^>]*>', corpo_markdown)
    assert link_match, "link de download do PDF (com o href base64 e o atributo download) não encontrado"
    link_html = link_match.group(0)

    cor_fundo = re.search(r'background-color:\s*(#[0-9A-Fa-f]{6})', link_html)
    cor_texto = re.search(r'(?<!background-)color:\s*(#[0-9A-Fa-f]{6}|white)', link_html)
    assert cor_fundo, "background-color do link de download não encontrado"
    assert cor_texto, "color do link de download não encontrado"

    hex_texto = "#FFFFFF" if cor_texto.group(1).lower() == "white" else cor_texto.group(1)
    razao = _contraste_wcag(cor_fundo.group(1), hex_texto)
    assert razao >= 4.5, f"contraste do link 'Baixar PDF' abaixo do mínimo AA (4.5:1): {razao:.4f}:1"
