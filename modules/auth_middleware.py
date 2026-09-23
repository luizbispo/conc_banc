# modules/auth_middleware.py
"""
Módulo central de autenticação/autorização.

Este módulo é a ÚNICA fonte de verdade para chave JWT, hashing de senha,
verificação de sessão e limitação de tentativas de login. app.py e as
páginas do Streamlit devem importar daqui em vez de reimplementar a lógica
(antes havia duas implementações divergentes de SECRET_KEY/hash, o que é
uma fonte real de bugs de segurança).
"""
import streamlit as st
import jwt
import os
import sqlite3
import secrets
import hmac
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Optional, Callable

logger = logging.getLogger(__name__)

# --- CONFIGURAÇÃO DE BANCO DE DADOS ---
def get_db_path() -> str:
    return os.getenv("CONCILIACAO_DB_PATH", "users.db")

def get_db_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    return sqlite3.connect(db_path or get_db_path())

# --- CHAVE JWT ---
# Nunca embutir uma chave padrão fixa e conhecida no código-fonte: qualquer
# pessoa com acesso ao repositório poderia forjar tokens válidos. Se a
# variável de ambiente não estiver definida, gera-se uma chave aleatória em
# memória para esta execução (todas as sessões são invalidadas a cada
# reinício do processo — limitação aceitável para o escopo atual; em
# produção, defina CONCILIACAO_SECRET_KEY para permitir múltiplos processos
# e reinícios sem derrubar sessões).
_env_secret = os.getenv("CONCILIACAO_SECRET_KEY")
if _env_secret:
    SECRET_KEY = _env_secret
else:
    SECRET_KEY = secrets.token_hex(32)
    logger.warning(
        "CONCILIACAO_SECRET_KEY não definido: usando uma chave aleatória gerada "
        "em memória apenas para esta execução. Defina a variável de ambiente "
        "em produção para manter sessões válidas entre reinícios e múltiplos "
        "processos."
    )

JWT_ALGORITHM = "HS256"

# --- HASHING DE SENHA ---
# SHA-256 puro é rápido demais e sem salt, o que facilita ataques de força
# bruta/rainbow table. PBKDF2-HMAC-SHA256 com salt por usuário e alta
# contagem de iterações é usado em vez disso (biblioteca padrão do Python,
# sem nova dependência).
PBKDF2_ITERATIONS = 260_000

def hash_password(password: str, salt: Optional[str] = None) -> tuple[str, str]:
    """Gera hash PBKDF2-HMAC-SHA256 da senha. Retorna (hash_hex, salt_hex)."""
    if salt is None:
        salt = secrets.token_hex(16)
    derived = hashlib.pbkdf2_hmac(
        'sha256', password.encode('utf-8'), bytes.fromhex(salt), PBKDF2_ITERATIONS
    )
    return derived.hex(), salt

def verify_password(password: str, password_hash: str, salt: Optional[str]) -> bool:
    """Verifica senha em tempo constante. Retorna False se não houver salt
    (conta legada incompatível com o esquema atual — ver
    verify_password_with_migration para o caminho de migração)."""
    if not salt or not password_hash:
        return False
    candidate, _ = hash_password(password, salt)
    return hmac.compare_digest(candidate, password_hash)

def verify_legacy_sha256(password: str, password_hash: str) -> bool:
    """Verifica a senha contra o esquema LEGADO (SHA-256 puro, sem salt),
    usado por este projeto antes da migração para PBKDF2. Existe só para
    permitir a migração transparente de contas antigas na primeira
    autenticação — nunca deve ser usado como esquema de verificação
    contínuo (SHA-256 puro é rápido demais e sem salt, vulnerável a
    força bruta/rainbow table)."""
    if not password_hash:
        return False
    legacy_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()
    return hmac.compare_digest(legacy_hash, password_hash)

def verify_password_with_migration(password: str, password_hash: str, salt: Optional[str]) -> tuple[bool, bool]:
    """Verifica a senha aceitando tanto o esquema atual (PBKDF2 + salt)
    quanto o esquema legado (SHA-256 sem salt), para que contas de bancos
    criados antes desta migração continuem autenticando sem exigir reset
    de senha.

    Retorna (senha_valida, precisa_migrar):
    - precisa_migrar é True quando a senha bateu no esquema LEGADO — o
      chamador deve, na mesma requisição de login bem-sucedida, gerar um
      novo hash_password(password) e regravar password_hash/password_salt
      no banco, para que a conta nunca mais dependa de SHA-256 sem salt.
    - Quando salt já existe (conta já no esquema atual), o caminho é
      idêntico a verify_password() e precisa_migrar é sempre False.

    Nota de canal lateral: o caminho legado é computacionalmente muito
    mais barato que PBKDF2 (260k iterações). Para não introduzir uma
    diferença de tempo observável que distinga "conta legada" de "conta
    já migrada" a partir de fora, este caminho também executa (e
    descarta) um hash_password() completo, equalizando o custo com o
    caminho salgado.
    """
    if salt:
        return verify_password(password, password_hash, salt), False

    senha_valida = verify_legacy_sha256(password, password_hash)
    hash_password(password)  # trabalho descartado, só para equalizar tempo
    return senha_valida, senha_valida

# --- LIMITAÇÃO DE TENTATIVAS DE LOGIN (RATE LIMITING) ---
LOGIN_MAX_ATTEMPTS = 5
LOGIN_WINDOW_MINUTES = 15
LOGIN_LOCKOUT_MINUTES = 15

def init_security_tables(conn: Optional[sqlite3.Connection] = None) -> None:
    """Cria as tabelas de suporte à segurança (idempotente)."""
    owns_conn = conn is None
    conn = conn or get_db_connection()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS login_attempts (
            identifier TEXT PRIMARY KEY,
            failed_count INTEGER DEFAULT 0,
            window_started_at TIMESTAMP,
            locked_until TIMESTAMP
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS revoked_tokens (
            jti TEXT PRIMARY KEY,
            revoked_at TIMESTAMP NOT NULL,
            expires_at TIMESTAMP NOT NULL
        )
    ''')
    conn.commit()
    if owns_conn:
        conn.close()

# --- REVOGAÇÃO DE TOKEN NO SERVIDOR ---
# O JWT tem validade de 24h (JWT_EXPIRATION_HOURS em app.py) e, até aqui,
# "logout" só limpava o st.session_state local: o token continuava
# criptograficamente válido no servidor até expirar sozinho — quem
# copiasse o token antes do logout podia reutilizá-lo por até 24h. Uma
# lista de revogação por jti (JWT ID único por token, ver
# generate_jti/app.py) fecha essa janela sem precisar de estado de sessão
# no servidor para todo login (só para os tokens efetivamente
# revogados).

def generate_jti() -> str:
    """Gera um identificador único e imprevisível para um novo token JWT."""
    return secrets.token_hex(16)

def revoke_token(jti: str, expires_at) -> None:
    """Marca um token (pelo jti) como revogado até sua própria expiração
    natural. Também remove entradas já expiradas da tabela, para que ela
    não cresça indefinidamente com tokens que já seriam recusados de
    qualquer forma pela expiração do JWT."""
    if not jti:
        return
    now = datetime.now()
    expires_at_str = expires_at.isoformat() if hasattr(expires_at, 'isoformat') else str(expires_at)
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('DELETE FROM revoked_tokens WHERE expires_at <= ?', (now.isoformat(),))
    c.execute('''
        INSERT OR REPLACE INTO revoked_tokens (jti, revoked_at, expires_at)
        VALUES (?, ?, ?)
    ''', (jti, now.isoformat(), expires_at_str))
    conn.commit()
    conn.close()

def is_token_revoked(jti: Optional[str]) -> bool:
    """Verifica se um token (pelo jti) está na lista de revogação."""
    if not jti:
        return False
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT 1 FROM revoked_tokens WHERE jti = ?', (jti,))
    row = c.fetchone()
    conn.close()
    return row is not None

def _normalize_identifier(identifier: str) -> str:
    return (identifier or "").strip().lower()

def check_login_rate_limit(identifier: str) -> tuple[bool, int]:
    """Retorna (permitido, segundos_restantes_de_bloqueio).

    A limitação é aplicada pelo identificador digitado (username/email),
    independente de o usuário existir de fato, para não criar um oráculo
    de enumeração de contas via presença/ausência de bloqueio."""
    identifier = _normalize_identifier(identifier)
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT locked_until FROM login_attempts WHERE identifier = ?', (identifier,))
    row = c.fetchone()
    conn.close()
    if row and row[0]:
        locked_until = datetime.fromisoformat(row[0])
        if datetime.now() < locked_until:
            return False, int((locked_until - datetime.now()).total_seconds())
    return True, 0

def record_login_failure(identifier: str) -> None:
    identifier = _normalize_identifier(identifier)
    now = datetime.now()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT failed_count, window_started_at FROM login_attempts WHERE identifier = ?', (identifier,))
    row = c.fetchone()
    if row:
        failed_count, window_started_at = row
        window_start = datetime.fromisoformat(window_started_at) if window_started_at else now
        if (now - window_start).total_seconds() > LOGIN_WINDOW_MINUTES * 60:
            failed_count = 0
            window_start = now
        failed_count += 1
        locked_until = None
        if failed_count >= LOGIN_MAX_ATTEMPTS:
            locked_until = (now + timedelta(minutes=LOGIN_LOCKOUT_MINUTES)).isoformat()
        c.execute('''
            UPDATE login_attempts SET failed_count = ?, window_started_at = ?, locked_until = ?
            WHERE identifier = ?
        ''', (failed_count, window_start.isoformat(), locked_until, identifier))
    else:
        c.execute('''
            INSERT INTO login_attempts (identifier, failed_count, window_started_at, locked_until)
            VALUES (?, 1, ?, NULL)
        ''', (identifier, now.isoformat()))
    conn.commit()
    conn.close()

def record_login_success(identifier: str) -> None:
    identifier = _normalize_identifier(identifier)
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('DELETE FROM login_attempts WHERE identifier = ?', (identifier,))
    conn.commit()
    conn.close()

# --- REVALIDAÇÃO DE USUÁRIO ---
def revalidate_user(user_id: int) -> Optional[dict]:
    """Busca o estado ATUAL do usuário no banco. Usado para não confiar
    apenas no payload do JWT (que pode ficar obsoleto se o usuário for
    desativado ou tiver a role alterada depois do login)."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT id, username, full_name, role, is_active FROM users WHERE id = ?', (user_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    return {
        'id': row[0],
        'username': row[1],
        'full_name': row[2],
        'role': row[3],
        'is_active': bool(row[4]),
    }

def _clear_session() -> None:
    st.session_state.pop('token', None)
    st.session_state.pop('user', None)
    st.session_state.pop('user_id', None)
    st.session_state.pop('user_role', None)
    st.session_state.pop('username', None)

# --- VERIFICAÇÃO DE AUTENTICAÇÃO ---
def enforce_auth() -> None:
    """Bloqueia a execução do script (st.stop()) se o usuário não estiver
    autenticado, com sessão expirada/inválida, ou tiver sido desativado
    desde o login. Pode ser chamada diretamente no topo de uma página
    (não apenas via decorator), o que é necessário para páginas que não
    encapsulam o conteúdo em uma função (ex.: importação de dados, que
    antes não tinha NENHUM guard de autenticação)."""
    if 'token' not in st.session_state or 'user' not in st.session_state:
        st.error("🔐 Acesso não autorizado. Faça login para acessar esta página.")
        if st.button("🔄 Ir para Login"):
            st.switch_page("app.py")
        st.stop()

    token = st.session_state.token
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        st.error("⏰ Sessão expirada. Faça login novamente.")
        _clear_session()
        if st.button("🔄 Fazer Login"):
            st.switch_page("app.py")
        st.stop()
    except jwt.InvalidTokenError:
        st.error("❌ Token inválido. Faça login novamente.")
        _clear_session()
        if st.button("🔄 Fazer Login"):
            st.switch_page("app.py")
        st.stop()

    if is_token_revoked(payload.get('jti')):
        st.error("🔒 Sessão encerrada (logout). Faça login novamente.")
        _clear_session()
        if st.button("🔄 Fazer Login"):
            st.switch_page("app.py")
        st.stop()

    current = revalidate_user(payload['user_id'])
    if current is None or not current['is_active']:
        st.error("🔐 Sua conta foi desativada ou removida. Faça login novamente.")
        _clear_session()
        if st.button("🔄 Fazer Login"):
            st.switch_page("app.py")
        st.stop()

    # Auto-corrige role/username em relação ao JWT (que pode estar
    # obsoleto): a fonte de verdade é sempre o banco, nunca o payload.
    st.session_state.user_id = current['id']
    st.session_state.user_role = current['role']
    st.session_state.username = current['username']
    st.session_state.user['role'] = current['role']
    st.session_state.user['username'] = current['username']
    st.session_state.user['full_name'] = current['full_name']

def require_auth(page_function: Callable) -> Callable:
    """Decorator para exigir autenticação em páginas."""
    def wrapper(*args, **kwargs):
        enforce_auth()
        return page_function(*args, **kwargs)
    return wrapper

def get_current_user() -> Optional[dict]:
    """Retorna informações do usuário atual"""
    if 'user' in st.session_state:
        return st.session_state.user
    return None

def get_user_role() -> Optional[str]:
    """Retorna o role do usuário atual"""
    user = get_current_user()
    return user.get('role') if user else None

def require_role(required_role: str) -> Callable:
    """Decorator para exigir role específico.

    Correção: a versão anterior chamava require_auth(page_function)(*args,
    **kwargs) — o que já EXECUTA a página — e depois, se a role fosse
    válida, chamava page_function(*args, **kwargs) de novo, rodando a
    página duas vezes antes/durante a decisão de autorização. Agora a
    checagem de autenticação/revalidação roda sem executar a página."""
    def decorator(page_function: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            enforce_auth()

            user_role = get_user_role()
            if user_role != required_role and user_role != 'admin':
                st.error("🚫 Acesso negado. Permissões insuficientes.")
                st.stop()

            return page_function(*args, **kwargs)
        return wrapper
    return decorator

def log_user_action(action: str, details: str = "") -> None:
    """Registra ação do usuário para auditoria (trilha persistente real,
    não apenas print). Ver modules/audit_logger.py."""
    from modules.audit_logger import get_audit_logger, AuditAction
    user = get_current_user()
    username = user['username'] if user else "Sistema"
    get_audit_logger().log_action(
        action=AuditAction.USER_ACTION,
        user=username,
        description=action,
        details={'details': details},
    )
