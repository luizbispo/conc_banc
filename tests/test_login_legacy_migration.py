"""
Testes de regressão de ponta a ponta (sem Streamlit) para app.login_user
contra bancos de dados sintéticos LEGADOS (SHA-256 sem salt, esquema de
antes do commit 1f4c03f) e NOVOS (PBKDF2 salgado, esquema atual).

Motivação: a revisão de segurança do commit 1f4c03f identificou que
bancos legados ficavam permanentemente impedidos de autenticar, porque
verify_password() passou a exigir password_salt. Estes testes travam a
regressão: login legado precisa continuar funcionando (com migração
transparente do hash) e login em banco já migrado precisa continuar
funcionando sem alteração de comportamento.

Todos os dados (usuários, senhas, e-mails) são sintéticos, criados no
próprio teste.
"""
import hashlib
import sqlite3

import pytest


@pytest.fixture
def legacy_db(tmp_path, monkeypatch):
    """Banco no esquema LEGADO: password_hash = SHA-256 puro,
    password_salt NULL — como um users.db criado antes desta migração."""
    db_path = str(tmp_path / "legacy_users.db")
    audit_path = str(tmp_path / "legacy_audit.db")
    monkeypatch.setenv("CONCILIACAO_DB_PATH", db_path)
    monkeypatch.setenv("CONCILIACAO_AUDIT_DB_PATH", audit_path)

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
    legacy_hash = hashlib.sha256("SenhaLegada1".encode()).hexdigest()
    conn.execute(
        "INSERT INTO users (username, email, password_hash, password_salt, full_name, role, is_active) "
        "VALUES (?, ?, ?, NULL, ?, 'user', 1)",
        ("usuario_legado", "legado@example.com", legacy_hash, "Usuário Legado"),
    )
    conn.commit()

    from modules.auth_middleware import init_security_tables
    init_security_tables(conn)  # tabela login_attempts, como um banco real passaria a ter
    conn.close()

    import modules.audit_logger as audit_logger_module
    audit_logger_module._audit_logger = None  # força singleton novo apontando para audit_path

    return db_path


def _import_app_fresh(monkeypatch):
    """app.py roda st.set_page_config() e outras chamadas de módulo no
    import; como os testes já podem ter importado 'app' antes de setar
    as env vars de DB, usamos importlib.reload para garantir que as
    funções peguem os caminhos corretos via os.getenv() (lidos a cada
    chamada, não fixados no import)."""
    import app
    return app


def test_legacy_account_can_still_login(legacy_db, monkeypatch):
    app = _import_app_fresh(monkeypatch)

    success, user_info, token = app.login_user("usuario_legado", "SenhaLegada1")

    assert success is True
    assert user_info["username"] == "usuario_legado"


def test_legacy_account_wrong_password_still_fails(legacy_db, monkeypatch):
    app = _import_app_fresh(monkeypatch)

    success, _, msg = app.login_user("usuario_legado", "SenhaErrada9")

    assert success is False
    assert msg == "Usuário ou senha incorretos"


def test_legacy_account_hash_is_migrated_to_pbkdf2_after_successful_login(legacy_db, monkeypatch):
    app = _import_app_fresh(monkeypatch)

    success, _, _ = app.login_user("usuario_legado", "SenhaLegada1")
    assert success is True

    conn = sqlite3.connect(legacy_db)
    password_hash, password_salt = conn.execute(
        "SELECT password_hash, password_salt FROM users WHERE username = 'usuario_legado'"
    ).fetchone()
    conn.close()

    assert password_salt not in (None, "")  # antes: permanecia NULL para sempre
    legacy_hash = hashlib.sha256("SenhaLegada1".encode()).hexdigest()
    assert password_hash != legacy_hash  # não é mais o hash SHA-256 puro


def test_migrated_account_logs_in_again_with_new_scheme(legacy_db, monkeypatch):
    """Login duas vezes seguidas: a primeira migra, a segunda já deve
    usar o caminho PBKDF2 normal (sem regressão pós-migração)."""
    app = _import_app_fresh(monkeypatch)

    success1, _, _ = app.login_user("usuario_legado", "SenhaLegada1")
    assert success1 is True

    success2, user_info2, _ = app.login_user("usuario_legado", "SenhaLegada1")
    assert success2 is True
    assert user_info2["username"] == "usuario_legado"


def test_wrong_password_on_legacy_account_does_not_migrate_hash(legacy_db, monkeypatch):
    """Uma tentativa com senha ERRADA contra uma conta legada não pode
    reescrever o hash — só uma autenticação bem-sucedida migra."""
    app = _import_app_fresh(monkeypatch)

    success, _, _ = app.login_user("usuario_legado", "SenhaErrada9")
    assert success is False

    conn = sqlite3.connect(legacy_db)
    password_hash, password_salt = conn.execute(
        "SELECT password_hash, password_salt FROM users WHERE username = 'usuario_legado'"
    ).fetchone()
    conn.close()

    assert password_salt in (None, "")
    legacy_hash = hashlib.sha256("SenhaErrada9".encode()).hexdigest()
    original_hash = hashlib.sha256("SenhaLegada1".encode()).hexdigest()
    assert password_hash == original_hash


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    """Banco já criado no esquema ATUAL (PBKDF2 salgado), simulando uma
    instalação nova — deve continuar funcionando sem qualquer mudança de
    comportamento (não pode haver regressão para o caso não-legado)."""
    db_path = str(tmp_path / "fresh_users.db")
    audit_path = str(tmp_path / "fresh_audit.db")
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
        ("usuario_novo", "novo@example.com", password_hash, salt, "Usuário Novo"),
    )
    conn.commit()

    from modules.auth_middleware import init_security_tables
    init_security_tables(conn)
    conn.close()

    import modules.audit_logger as audit_logger_module
    audit_logger_module._audit_logger = None

    return db_path


def test_already_migrated_account_logs_in_normally(fresh_db, monkeypatch):
    app = _import_app_fresh(monkeypatch)

    success, user_info, _ = app.login_user("usuario_novo", "SenhaNova1")

    assert success is True
    assert user_info["username"] == "usuario_novo"


def test_already_migrated_account_hash_is_not_rewritten_unnecessarily(fresh_db, monkeypatch):
    app = _import_app_fresh(monkeypatch)

    conn = sqlite3.connect(fresh_db)
    hash_before, salt_before = conn.execute(
        "SELECT password_hash, password_salt FROM users WHERE username = 'usuario_novo'"
    ).fetchone()
    conn.close()

    success, _, _ = app.login_user("usuario_novo", "SenhaNova1")
    assert success is True

    conn = sqlite3.connect(fresh_db)
    hash_after, salt_after = conn.execute(
        "SELECT password_hash, password_salt FROM users WHERE username = 'usuario_novo'"
    ).fetchone()
    conn.close()

    assert hash_after == hash_before
    assert salt_after == salt_before
