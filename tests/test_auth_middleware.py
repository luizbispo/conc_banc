"""
Testes de regressão para modules/auth_middleware.py.

Cobrem as correções implementadas na revisão real do repositório
(issue XCRE-41): hashing de senha salgado, limitação de tentativas de
login (rate limiting), revalidação do usuário contra o banco (para não
confiar apenas no payload do JWT quando a conta é desativada/rebaixada) e
a migração transparente de contas legadas (SHA-256 sem salt) para PBKDF2
salgado, apontada na revisão de segurança do commit 1f4c03f como bloqueio
funcional (bancos legados ficavam impossibilitados de logar).

Usa dados 100% sintéticos gerados no próprio teste — nenhum dado real.
"""
import hashlib
import sqlite3

import pytest

from modules import auth_middleware as am


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = str(tmp_path / "test_users.db")
    monkeypatch.setenv("CONCILIACAO_DB_PATH", path)

    conn = sqlite3.connect(path)
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
    conn.commit()
    conn.close()

    am.init_security_tables()
    return path


def _insert_user(db_path, username="qauser", role="user", is_active=1, password="Teste123"):
    password_hash, salt = am.hash_password(password)
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO users (username, email, password_hash, password_salt, full_name, role, is_active) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (username, f"{username}@example.com", password_hash, salt, "Usuário QA", role, is_active),
    )
    conn.commit()
    user_id = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()[0]
    conn.close()
    return user_id


# --- Hashing de senha ---

def test_hash_password_roundtrip():
    password_hash, salt = am.hash_password("SenhaForte1")
    assert am.verify_password("SenhaForte1", password_hash, salt) is True


def test_hash_password_wrong_password_fails():
    password_hash, salt = am.hash_password("SenhaForte1")
    assert am.verify_password("SenhaErrada9", password_hash, salt) is False


def test_hash_password_generates_unique_salt_per_call():
    hash1, salt1 = am.hash_password("SenhaForte1")
    hash2, salt2 = am.hash_password("SenhaForte1")
    assert salt1 != salt2
    assert hash1 != hash2


def test_verify_password_without_salt_is_rejected():
    # verify_password() "puro" (sem migração) continua rejeitando contas
    # sem salt — o caminho de migração é uma função separada e explícita
    # (verify_password_with_migration), nunca implícito aqui.
    assert am.verify_password("qualquer", "algumhash", None) is False
    assert am.verify_password("qualquer", "algumhash", "") is False


# --- Migração de contas legadas (SHA-256 sem salt -> PBKDF2 salgado) ---
# Regressão apontada na revisão de segurança do commit 1f4c03f: bancos
# criados antes desta migração têm password_salt nulo e password_hash em
# SHA-256 puro; sem tratamento explícito, verify_password() passou a
# rejeitar essas contas incondicionalmente (bloqueio funcional real).

def _legacy_sha256_hash(password: str) -> str:
    """Reproduz o esquema de hash usado pelo código ANTES da migração
    para PBKDF2 (SHA-256 puro, sem salt), para simular um users.db
    legado nos testes."""
    return hashlib.sha256(password.encode()).hexdigest()


def test_verify_legacy_sha256_accepts_correct_password():
    legacy_hash = _legacy_sha256_hash("SenhaAntiga1")
    assert am.verify_legacy_sha256("SenhaAntiga1", legacy_hash) is True


def test_verify_legacy_sha256_rejects_wrong_password():
    legacy_hash = _legacy_sha256_hash("SenhaAntiga1")
    assert am.verify_legacy_sha256("SenhaErrada9", legacy_hash) is False


def test_verify_legacy_sha256_rejects_empty_hash():
    assert am.verify_legacy_sha256("qualquer", "") is False
    assert am.verify_legacy_sha256("qualquer", None) is False


def test_migration_path_accepts_legacy_account_and_flags_migration():
    """Conta legada (sem salt): senha correta deve autenticar E sinalizar
    que o chamador precisa regravar o hash."""
    legacy_hash = _legacy_sha256_hash("SenhaAntiga1")

    senha_valida, precisa_migrar = am.verify_password_with_migration(
        "SenhaAntiga1", legacy_hash, salt=None
    )

    assert senha_valida is True
    assert precisa_migrar is True


def test_migration_path_rejects_wrong_password_without_flagging_migration():
    legacy_hash = _legacy_sha256_hash("SenhaAntiga1")

    senha_valida, precisa_migrar = am.verify_password_with_migration(
        "SenhaErrada9", legacy_hash, salt=None
    )

    assert senha_valida is False
    assert precisa_migrar is False


def test_migration_path_does_not_flag_migration_for_already_migrated_account():
    """Conta já no esquema atual (com salt): deve se comportar
    exatamente como verify_password() e NUNCA sinalizar migração — a
    migração só se aplica ao caminho legado sem salt."""
    password_hash, salt = am.hash_password("SenhaNova1")

    senha_valida, precisa_migrar = am.verify_password_with_migration(
        "SenhaNova1", password_hash, salt
    )

    assert senha_valida is True
    assert precisa_migrar is False


def test_migration_path_new_scheme_rejects_wrong_password():
    password_hash, salt = am.hash_password("SenhaNova1")

    senha_valida, precisa_migrar = am.verify_password_with_migration(
        "SenhaErrada9", password_hash, salt
    )

    assert senha_valida is False
    assert precisa_migrar is False


def test_migration_path_empty_salt_string_is_treated_as_legacy():
    """password_salt pode vir como string vazia (não só NULL/None)
    dependendo de como a linha foi inserida — o caminho de migração deve
    tratar ambos os casos como 'sem salt'."""
    legacy_hash = _legacy_sha256_hash("SenhaAntiga1")

    senha_valida, precisa_migrar = am.verify_password_with_migration(
        "SenhaAntiga1", legacy_hash, salt=""
    )

    assert senha_valida is True
    assert precisa_migrar is True


# --- Limitação de tentativas de login ---

def test_rate_limit_allows_before_threshold(db_path):
    allowed, _ = am.check_login_rate_limit("usuario_teste")
    assert allowed is True

    for _ in range(am.LOGIN_MAX_ATTEMPTS - 1):
        am.record_login_failure("usuario_teste")

    allowed, retry_after = am.check_login_rate_limit("usuario_teste")
    assert allowed is True


def test_rate_limit_locks_after_max_attempts(db_path):
    for _ in range(am.LOGIN_MAX_ATTEMPTS):
        am.record_login_failure("usuario_bloqueado")

    allowed, retry_after = am.check_login_rate_limit("usuario_bloqueado")
    assert allowed is False
    assert retry_after > 0


def test_rate_limit_is_keyed_by_identifier_not_by_account_existence(db_path):
    """A limitação deve valer igualmente para identificadores que
    correspondem ou não a uma conta real, para não vazar (via
    presença/ausência de bloqueio) se um username existe."""
    for _ in range(am.LOGIN_MAX_ATTEMPTS):
        am.record_login_failure("conta_que_nao_existe")

    allowed, _ = am.check_login_rate_limit("conta_que_nao_existe")
    assert allowed is False


def test_rate_limit_reset_on_success(db_path):
    for _ in range(am.LOGIN_MAX_ATTEMPTS - 1):
        am.record_login_failure("usuario_recupera")
    am.record_login_success("usuario_recupera")

    for _ in range(am.LOGIN_MAX_ATTEMPTS - 1):
        am.record_login_failure("usuario_recupera")
    allowed, _ = am.check_login_rate_limit("usuario_recupera")
    assert allowed is True  # ainda não atingiu o limite de novo após o reset


def test_rate_limit_case_insensitive_identifier(db_path):
    for _ in range(am.LOGIN_MAX_ATTEMPTS):
        am.record_login_failure("UsuarioMisto")

    allowed, _ = am.check_login_rate_limit("usuariomisto")
    assert allowed is False


# --- Revalidação de usuário contra o banco ---

def test_revalidate_user_returns_current_state(db_path):
    user_id = _insert_user(db_path, username="ana", role="user")
    current = am.revalidate_user(user_id)
    assert current is not None
    assert current["username"] == "ana"
    assert current["role"] == "user"
    assert current["is_active"] is True


def test_revalidate_user_reflects_role_change_without_new_login(db_path):
    """Fecha o gap relatado na avaliação arquitetural: um usuário
    promovido/rebaixado depois do login não deve continuar com a role
    antiga só porque o JWT foi emitido antes da mudança."""
    user_id = _insert_user(db_path, username="bruno", role="user")

    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE users SET role = 'admin' WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()

    current = am.revalidate_user(user_id)
    assert current["role"] == "admin"


def test_revalidate_user_reflects_deactivation(db_path):
    user_id = _insert_user(db_path, username="carla", is_active=1)

    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE users SET is_active = 0 WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()

    current = am.revalidate_user(user_id)
    assert current["is_active"] is False


def test_revalidate_user_returns_none_for_deleted_user(db_path):
    user_id = _insert_user(db_path, username="deletado")

    conn = sqlite3.connect(db_path)
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()

    assert am.revalidate_user(user_id) is None
