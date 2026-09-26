"""
Testes de regressão para a integração do helper de tema v3 em app.py e
nas páginas (fase 6, XCRE-54 item 4): `modules.tema.aplicar_tema()`
precisa ser chamado uma vez por execução de cada uma das quatro telas
(app.py + as três páginas em pages/), SEM alterar nada do comportamento
funcional já existente.

Este arquivo só verifica a integração em si (o helper É chamado, uma
única vez, cedo o bastante para não depender de nenhum dado de negócio).
Os comportamentos funcionais que precisam continuar intactos (login,
navegação, logout, mensagens de erro) já têm suíte própria — rodada à
parte como regressão, não duplicada aqui:
tests/test_smoke_import_app.py, tests/test_logout_revocation.py,
tests/test_gerar_relatorio_auditoria.py, tests/test_importacao_limites.py,
tests/test_analise_dados_auditoria.py.

Dados 100% sintéticos.
"""
import importlib
import os
import sqlite3
import tempfile
from unittest import mock

import pandas as pd
import pytest
import streamlit as st

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_APP_PY = os.path.join(REPO_ROOT, "app.py")
_CSS_PATH = os.path.join(REPO_ROOT, "assets", "custom.css")


def _criar_usuario_e_autenticar(tmp_path, monkeypatch, username: str):
    """Mesmo padrão de tests/test_gerar_relatorio_auditoria.py: cria um
    usuário sintético num banco descartável e autentica a sessão via
    app.login_user, sem tocar em nenhum dado real."""
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
        (username, f"{username}@example.com", password_hash, salt, "QA Tema"),
    )
    conn.commit()
    init_security_tables(conn)
    conn.close()

    import modules.audit_logger as audit_logger_module
    audit_logger_module._audit_logger = None

    import app
    success, user_info, token = app.login_user(username, "SenhaNova1")
    assert success is True

    st.session_state["token"] = token
    st.session_state["user"] = user_info


@pytest.fixture
def sessao_autenticada(tmp_path, monkeypatch):
    """Sessão autenticada + dados sintéticos mínimos (mesmo padrão de
    tests/test_gerar_relatorio_auditoria.py), suficientes para chegar ao
    ponto de injeção do tema (logo após st.set_page_config) em
    gerar_relatorio.py e analise_dados.py."""
    _criar_usuario_e_autenticar(tmp_path, monkeypatch, "qa_tema")
    st.session_state["resultados_analise"] = {"matches": [], "excecoes": [{}]}
    st.session_state["extrato_df"] = pd.DataFrame({
        "id": [1], "data": pd.to_datetime(["2025-06-15"]), "valor": [60.50], "descricao": ["A"],
    })
    st.session_state["contabil_df"] = pd.DataFrame({
        "id": [1], "data": pd.to_datetime(["2025-06-20"]), "valor": [500.0], "descricao": ["C"],
    })
    st.session_state["dados_carregados"] = True


# --- app.py ---

def test_app_py_injeta_tema_v3_e_preserva_tela_de_login():
    from streamlit.testing.v1 import AppTest

    db_path_original = os.environ.get("CONCILIACAO_DB_PATH")
    audit_path_original = os.environ.get("CONCILIACAO_AUDIT_DB_PATH")
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["CONCILIACAO_DB_PATH"] = os.path.join(tmp, "users.db")
        os.environ["CONCILIACAO_AUDIT_DB_PATH"] = os.path.join(tmp, "audit.db")
        try:
            at = AppTest.from_file(_APP_PY)
            at.run()
            assert not at.exception, f"app.py levantou exceção ao carregar: {at.exception}"

            with open(_CSS_PATH, "r", encoding="utf-8") as f:
                css_real = f.read()
            estilos = [m.value for m in at.markdown if "<style" in m.value]
            assert len(estilos) == 1, "o tema deve ser injetado exatamente uma vez por execução"
            assert css_real in estilos[0]

            # Login preservado: o formulário de usuário/senha continua lá.
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


# --- pages/gerar_relatorio.py ---

def test_gerar_relatorio_chama_aplicar_tema_uma_vez_por_execucao(sessao_autenticada):
    import pages.gerar_relatorio as pagina

    with mock.patch.object(pagina, "aplicar_tema") as tema_mock:
        try:
            pagina.main()
        except Exception:
            # Dados sintéticos mínimos não cobrem todo o fluxo de geração
            # de PDF (fora do escopo deste teste, já coberto por
            # tests/test_gerar_relatorio_auditoria.py) — só precisamos
            # confirmar que aplicar_tema() já rodou antes de qualquer
            # ponto de falha possível.
            pass

    tema_mock.assert_called_once_with()


# --- pages/analise_dados.py ---

def test_analise_dados_chama_aplicar_tema_uma_vez_por_execucao(sessao_autenticada):
    import pages.analise_dados as pagina

    with mock.patch.object(pagina, "aplicar_tema") as tema_mock:
        try:
            pagina.main()
        except Exception:
            # Dados sintéticos mínimos não cobrem todo o pipeline de
            # matching (fora do escopo deste teste, já coberto por
            # tests/test_analise_dados_auditoria.py) — só precisamos
            # confirmar que aplicar_tema() já rodou antes de qualquer
            # ponto de falha possível.
            pass

    tema_mock.assert_called_once_with()


# --- pages/importacao_dados.py ---

def test_importacao_dados_chama_aplicar_tema_ao_carregar_a_pagina(tmp_path, monkeypatch):
    _criar_usuario_e_autenticar(tmp_path, monkeypatch, "qa_importacao")

    # Garante que o módulo já está em sys.modules ANTES de mockar: se este
    # for o primeiro import do processo, o próprio `import` (não só o
    # reload logo abaixo) executaria o módulo do zero e contaria como uma
    # chamada extra a aplicar_tema().
    import pages.importacao_dados as pg

    with mock.patch("modules.tema.aplicar_tema") as tema_mock:
        importlib.reload(pg)  # roda o módulo (e a chamada a aplicar_tema()) de novo

    tema_mock.assert_called_once_with()
