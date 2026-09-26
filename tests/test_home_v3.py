"""
Testes de regressão para a Home v3 (fase 6, XCRE-54 item 5): a área
principal de app.py (após login) precisa ter SOMENTE os 3 cartões de
etapa — "Importação de Dados", "Análise de Divergências", "Relatório
Final" — cada um com ícone SVG inline, número da etapa e um rótulo
curto, clicável (st.switch_page). Login, sidebar de navegação e o botão
"Sair" continuam funcionando; nenhum dos blocos antigos (boas-vindas
longas, blocos de funcionalidades, "Sobre o Sistema", status/resumo da
sessão, atalho "Nova Análise") pode sobrar.

Usa streamlit.testing.v1.AppTest (mesmo padrão de
tests/test_smoke_import_app.py) para rodar app.py de ponta a ponta com
uma sessão autenticada sintética.

Dados 100% sintéticos.
"""
import os
import sqlite3
import tempfile

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_APP_PY = os.path.join(REPO_ROOT, "app.py")

_ROTULOS_ETAPAS = ("Importação de Dados", "Análise de Divergências", "Relatório Final")


@pytest.fixture
def home_autenticada():
    """Roda app.py via AppTest com uma sessão autenticada sintética e
    devolve o AppTest já executado, posicionado na Home."""
    from streamlit.testing.v1 import AppTest

    db_path_original = os.environ.get("CONCILIACAO_DB_PATH")
    audit_path_original = os.environ.get("CONCILIACAO_AUDIT_DB_PATH")
    tmp = tempfile.mkdtemp()
    os.environ["CONCILIACAO_DB_PATH"] = os.path.join(tmp, "users.db")
    os.environ["CONCILIACAO_AUDIT_DB_PATH"] = os.path.join(tmp, "audit.db")
    try:
        from modules.auth_middleware import hash_password, init_security_tables
        password_hash, salt = hash_password("SenhaNova1")

        conn = sqlite3.connect(os.environ["CONCILIACAO_DB_PATH"])
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
            ("qa_home", "qa_home@example.com", password_hash, salt, "QA Home"),
        )
        conn.commit()
        init_security_tables(conn)
        conn.close()

        import modules.audit_logger as audit_logger_module
        audit_logger_module._audit_logger = None

        import app
        success, user_info, token = app.login_user("qa_home", "SenhaNova1")
        assert success is True

        at = AppTest.from_file(_APP_PY)
        at.session_state["token"] = token
        at.session_state["user"] = user_info
        at.run()
        assert not at.exception, f"app.py levantou exceção: {at.exception}"
        yield at
    finally:
        if db_path_original is None:
            os.environ.pop("CONCILIACAO_DB_PATH", None)
        else:
            os.environ["CONCILIACAO_DB_PATH"] = db_path_original
        if audit_path_original is None:
            os.environ.pop("CONCILIACAO_AUDIT_DB_PATH", None)
        else:
            os.environ["CONCILIACAO_AUDIT_DB_PATH"] = audit_path_original


def _labels_botoes_area_principal(at) -> list:
    """Botões que NÃO estão na sidebar (área principal da Home)."""
    labels_sidebar = {b.label for b in at.sidebar.button}
    return [b.label for b in at.button if b.label not in labels_sidebar]


# --- Exatamente 3 opções de etapa, com os rótulos exatos pedidos ---

def test_home_tem_exatamente_3_opcoes_de_etapa_com_rotulos_exatos(home_autenticada):
    at = home_autenticada
    labels_area_principal = _labels_botoes_area_principal(at)
    assert len(labels_area_principal) == 3
    assert set(labels_area_principal) == set(_ROTULOS_ETAPAS)


def test_home_mostra_numero_da_etapa_e_icone_svg_inline_para_cada_cartao(home_autenticada):
    at = home_autenticada
    corpo_markdown = "\n".join(m.value for m in at.markdown)
    for numero in (1, 2, 3):
        assert f"Etapa {numero}" in corpo_markdown
    # Ícone SVG inline (não emoji/imagem externa) para cada um dos 3 cartões.
    assert corpo_markdown.count("<svg") >= 3
    assert "step-card" in corpo_markdown


def test_rotulos_das_etapas_tem_no_maximo_6_palavras(home_autenticada):
    for rotulo in _ROTULOS_ETAPAS:
        assert len(rotulo.split()) <= 6


# --- Blocos antigos removidos da Home ---

def test_home_nao_tem_mais_boas_vindas_longas_nem_blocos_de_funcionalidades(home_autenticada):
    at = home_autenticada
    corpo_markdown = "\n".join(m.value for m in at.markdown)
    for trecho_removido in (
        "Funcionalidades principais",
        "Fluxo recomendado",
        "Sistema para análise e conciliação de extratos",
    ):
        assert trecho_removido not in corpo_markdown


def test_home_nao_tem_mais_sobre_o_sistema_nem_status_da_sessao(home_autenticada):
    at = home_autenticada
    corpo_markdown = "\n".join(m.value for m in at.markdown)
    corpo_headers = "\n".join(h.value for h in at.header)
    corpo_subheaders = "\n".join(s.value for s in at.subheader)
    texto_completo = corpo_markdown + corpo_headers + corpo_subheaders
    for trecho_removido in ("Sobre o Sistema", "Status da Sessão", "Desenvolvido por"):
        assert trecho_removido not in texto_completo


def test_home_nao_tem_mais_atalho_de_nova_analise(home_autenticada):
    at = home_autenticada
    labels = [b.label for b in at.button]
    assert not any("Nova Análise" in (label or "") for label in labels)


# --- Não inventa nome de produto ---

def test_titulo_da_pagina_continua_sistema_de_conciliacao_bancaria(home_autenticada):
    at = home_autenticada
    titulos = [t.value for t in at.title]
    assert any("Sistema de Conciliação Bancária" in t for t in titulos)


# --- Login, sidebar de navegação e Sair continuam funcionando ---

def test_sidebar_de_navegacao_e_botao_sair_continuam_presentes(home_autenticada):
    at = home_autenticada
    page_links_sidebar = [pl.label for pl in at.sidebar.get("page_link")] if at.sidebar.get("page_link") else []
    # Fallback: procura o texto de navegação no markdown da sidebar caso
    # a API de page_link não seja enumerável nesta versão do AppTest.
    sidebar_markdown = "\n".join(m.value for m in at.sidebar.markdown)
    assert "Navegação Principal" in sidebar_markdown

    labels_sidebar_botoes = [b.label for b in at.sidebar.button]
    assert "🚪 Sair" in labels_sidebar_botoes


def test_login_continua_funcionando_para_sessao_nao_autenticada():
    """Regressão rápida: sem sessão autenticada, a Home não aparece — o
    formulário de login continua sendo a primeira tela (mesmo teste de
    tests/test_smoke_import_app.py, verificado aqui de novo porque a
    Home v3 mexeu na mesma função de nível de módulo)."""
    from streamlit.testing.v1 import AppTest

    db_path_original = os.environ.get("CONCILIACAO_DB_PATH")
    audit_path_original = os.environ.get("CONCILIACAO_AUDIT_DB_PATH")
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["CONCILIACAO_DB_PATH"] = os.path.join(tmp, "users.db")
        os.environ["CONCILIACAO_AUDIT_DB_PATH"] = os.path.join(tmp, "audit.db")
        try:
            at = AppTest.from_file(_APP_PY)
            at.run()
            assert not at.exception
            labels = [ti.label for ti in at.text_input]
            assert "Username ou Email" in labels
            assert "Senha" in labels
        finally:
            if db_path_original is None:
                os.environ.pop("CONCILIACAO_DB_PATH", None)
            else:
                os.environ["CONCILIACAO_DB_PATH"] = db_path_original
            if audit_path_original is None:
                os.environ.pop("CONCILIACAO_AUDIT_DB_PATH", None)
            else:
                os.environ["CONCILIACAO_AUDIT_DB_PATH"] = audit_path_original


# --- Cada cartão navega para a página correspondente ---

@pytest.mark.parametrize("rotulo,pagina_esperada,titulo_esperado", [
    ("Importação de Dados", "pages/importacao_dados.py", "Importação de Dados"),
    ("Análise de Divergências", "pages/analise_dados.py", "Análise de Correspondências"),
    ("Relatório Final", "pages/gerar_relatorio.py", "Relatório de Análise"),
])
def test_cartao_navega_para_a_pagina_correspondente(home_autenticada, rotulo, pagina_esperada, titulo_esperado):
    at = home_autenticada
    botao = next(b for b in at.button if b.label == rotulo)
    botao.click().run()
    assert not at.exception, f"navegação para {pagina_esperada} levantou exceção: {at.exception}"
    titulos = [t.value for t in at.title]
    assert any(titulo_esperado in t for t in titulos), (
        f"esperava título contendo {titulo_esperado!r} após clicar em {rotulo!r}, "
        f"títulos encontrados: {titulos}"
    )
