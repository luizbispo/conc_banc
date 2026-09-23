"""
Teste de regressão de ponta a ponta (sem Streamlit real, mesmo padrão de
tests/test_login_legacy_migration.py) para a revogação de token no
logout (issue XCRE-42, Parte A, item 5a).

Antes, app.logout_user() só limpava st.session_state: o JWT emitido no
login continuava criptograficamente válido no servidor por até 24h
(JWT_EXPIRATION_HOURS), então um token copiado antes do logout podia ser
reutilizado em outra sessão/contexto. Agora o logout revoga o token
(lista de revogação por jti em SQLite) e app.check_authentication() /
modules.auth_middleware.enforce_auth() passam a rejeitar tokens
revogados mesmo que ainda estejam dentro do prazo de expiração.

Dados 100% sintéticos.
"""
import sqlite3

import pytest
import streamlit as st


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "users.db")
    audit_path = str(tmp_path / "audit.db")
    monkeypatch.setenv("CONCILIACAO_DB_PATH", db_path)
    monkeypatch.setenv("CONCILIACAO_AUDIT_DB_PATH", audit_path)

    from modules.auth_middleware import hash_password
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
        ("usuario_teste", "teste@example.com", password_hash, salt, "Usuário Teste"),
    )
    conn.commit()

    from modules.auth_middleware import init_security_tables
    init_security_tables(conn)
    conn.close()

    import modules.audit_logger as audit_logger_module
    audit_logger_module._audit_logger = None

    return db_path


def _import_app_fresh(monkeypatch):
    import app
    return app


def test_token_funciona_antes_do_logout(fresh_db, monkeypatch):
    app = _import_app_fresh(monkeypatch)
    success, user_info, token = app.login_user("usuario_teste", "SenhaNova1")
    assert success is True

    is_valid, payload = app.verify_token(token)
    assert is_valid is True
    assert payload["username"] == "usuario_teste"


def test_logout_revoga_token_e_check_authentication_passa_a_rejeitar(fresh_db, monkeypatch):
    app = _import_app_fresh(monkeypatch)
    success, user_info, token = app.login_user("usuario_teste", "SenhaNova1")
    assert success is True

    st.session_state["token"] = token
    st.session_state["user"] = user_info

    app.logout_user()

    # O JWT ainda não expirou (24h) e continua criptograficamente válido
    # isoladamente — mas o servidor deve recusá-lo por estar revogado.
    from modules.auth_middleware import is_token_revoked
    is_valid, payload = app.verify_token(token)
    assert is_valid is True  # a assinatura/exp continuam OK...
    assert is_token_revoked(payload.get("jti")) is True  # ...mas está revogado

    # Simula reapresentar o mesmo token após o logout (ex.: token copiado
    # antes do logout): check_authentication() deve recusar.
    st.session_state["token"] = token
    st.session_state["user"] = user_info
    assert app.check_authentication() is False
    assert "token" not in st.session_state


def test_novo_login_apos_logout_gera_sessao_valida_e_distinta(fresh_db, monkeypatch):
    app = _import_app_fresh(monkeypatch)
    success, user_info, token_antigo = app.login_user("usuario_teste", "SenhaNova1")
    assert success is True

    st.session_state["token"] = token_antigo
    st.session_state["user"] = user_info
    app.logout_user()

    success2, user_info2, token_novo = app.login_user("usuario_teste", "SenhaNova1")
    assert success2 is True
    assert token_novo != token_antigo

    st.session_state["token"] = token_novo
    st.session_state["user"] = user_info2
    assert app.check_authentication() is True
