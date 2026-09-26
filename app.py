# app.py - Aplicação Principal Streamlit com Sistema de Login
import streamlit as st
import sqlite3
import re
from datetime import datetime, timedelta
import jwt
import os
import time
from typing import Optional
from modules.auth_middleware import (
    SECRET_KEY,
    JWT_ALGORITHM,
    hash_password,
    verify_password,
    verify_password_with_migration,
    get_db_connection,
    init_security_tables,
    check_login_rate_limit,
    record_login_failure,
    record_login_success,
    revalidate_user,
    generate_jti,
    revoke_token,
    is_token_revoked,
)
from modules.audit_logger import get_audit_logger, AuditAction, AuditSeverity
from modules.structured_logger import get_structured_logger
from modules.tema import aplicar_tema

# Configuração da página
st.set_page_config(
    page_title="Sistema de Conciliação Bancária",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# XCRE-54 item 4: tema v3 (fase 6) aplicado uma vez por execução da
# página, logo após a configuração — antes de login ou home renderizar.
aplicar_tema()

# --- CONFIGURAÇÕES DE SEGURANÇA ---
# SECRET_KEY, hashing de senha e limitação de tentativas agora vêm de
# modules/auth_middleware.py (fonte única, ver comentários lá) — antes
# havia uma segunda cópia de SECRET_KEY/hash_password aqui, divergente da
# de modules/auth_middleware.py.
JWT_EXPIRATION_HOURS = 24

# --- BANCO DE DADOS DE USUÁRIOS ---
def init_db():
    """Inicializa o banco de dados de usuários"""
    conn = get_db_connection()
    c = conn.cursor()

    # Tabela de usuários
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
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

    # Migração leve para bancos criados antes da coluna password_salt existir
    c.execute("PRAGMA table_info(users)")
    existing_cols = {row[1] for row in c.fetchall()}
    if 'password_salt' not in existing_cols:
        c.execute("ALTER TABLE users ADD COLUMN password_salt TEXT")

    # Tabela de sessões
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            session_token TEXT UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    init_security_tables(conn)

    # Inserir usuário admin padrão se não existir
    c.execute("SELECT COUNT(*) FROM users WHERE username = 'admin'")
    if c.fetchone()[0] == 0:
        password_hash, password_salt = hash_password("admin123")
        c.execute('''
            INSERT INTO users (username, email, password_hash, password_salt, full_name, role)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', ('admin', 'admin@sistema.com', password_hash, password_salt, 'Administrador', 'admin'))

    conn.commit()
    conn.close()

def validate_email(email: str) -> bool:
    """Valida formato do email"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_password(password: str) -> tuple[bool, str]:
    """Valida força da senha"""
    if len(password) < 8:
        return False, "A senha deve ter pelo menos 8 caracteres"
    if not re.search(r"[A-Z]", password):
        return False, "A senha deve conter pelo menos uma letra maiúscula"
    if not re.search(r"[a-z]", password):
        return False, "A senha deve conter pelo menos uma letra minúscula"
    if not re.search(r"\d", password):
        return False, "A senha deve conter pelo menos um número"
    return True, "Senha válida"

# --- SISTEMA DE AUTENTICAÇÃO ---
def login_user(username: str, password: str) -> tuple[bool, Optional[dict], str]:
    """Autentica usuário e retorna token JWT.

    Correções de segurança em relação à versão anterior:
    - Limitação de tentativas (bloqueio temporário após 5 falhas em 15 min),
      aplicada pelo identificador digitado, antes de tocar o banco.
    - Mensagem de erro genérica e idêntica para usuário inexistente, senha
      incorreta e conta desativada (evita enumeração de contas válidas por
      diferença de mensagem).
    - Verificação de senha sempre executada, mesmo quando o usuário não
      existe (compara contra um hash "dummy"), para reduzir (não eliminar)
      diferença de tempo de resposta como sinal de enumeração.
    - Hash de senha salgado (PBKDF2), não mais SHA-256 puro sem salt.
    - Contas de bancos criados ANTES desta migração (password_salt nulo,
      hash SHA-256 puro) continuam autenticando: verify_password_with_migration
      aceita o hash legado na primeira tentativa e, se válido, regrava
      password_hash/password_salt em PBKDF2 imediatamente, sem exigir
      reset de senha nem expor ao usuário que houve migração.
    - Login bem-sucedido/malsucedido é registrado na trilha de auditoria.
    """
    audit = get_audit_logger()
    genericos = "Usuário ou senha incorretos"
    _inicio_login = time.time()

    allowed, retry_after_seconds = check_login_rate_limit(username)
    if not allowed:
        minutos = max(1, retry_after_seconds // 60)
        audit.log_action(
            action=AuditAction.USER_ACTION,
            user=username or "desconhecido",
            description="Login bloqueado por limite de tentativas",
            severity=AuditSeverity.WARNING,
        )
        get_structured_logger().log_login(
            sucesso=False, motivo="limite_de_tentativas",
            duracao_segundos=time.time() - _inicio_login,
        )
        return False, None, f"Muitas tentativas de login. Tente novamente em {minutos} min."

    conn = get_db_connection()
    c = conn.cursor()

    c.execute('''
        SELECT id, username, email, full_name, role, password_hash, password_salt, is_active
        FROM users WHERE username = ? OR email = ?
    ''', (username, username))

    user = c.fetchone()

    # Hash "dummy" para manter o custo de verificação semelhante ao caminho
    # de usuário existente, mesmo quando o usuário não é encontrado.
    _dummy_hash, _dummy_salt = hash_password("usuario-nao-existe-nesta-instancia")

    if not user:
        verify_password(password, _dummy_hash, _dummy_salt)
        conn.close()
        record_login_failure(username)
        audit.log_action(
            action=AuditAction.USER_ACTION,
            user=username or "desconhecido",
            description="Falha de login: usuário não encontrado",
            severity=AuditSeverity.WARNING,
        )
        get_structured_logger().log_login(
            sucesso=False, motivo="usuario_nao_encontrado",
            duracao_segundos=time.time() - _inicio_login,
        )
        return False, None, genericos

    user_id, username_db, email, full_name, role, password_hash, password_salt, is_active = user

    senha_valida, precisa_migrar = verify_password_with_migration(password, password_hash, password_salt)

    if senha_valida and precisa_migrar:
        # Conta legada autenticada com sucesso no hash SHA-256 sem salt:
        # regrava imediatamente em PBKDF2 + salt, para que esta conta
        # nunca mais dependa do esquema fraco. Isso é transparente para o
        # usuário — nenhuma mensagem ou comportamento visível muda.
        novo_hash, novo_salt = hash_password(password)
        c.execute(
            'UPDATE users SET password_hash = ?, password_salt = ? WHERE id = ?',
            (novo_hash, novo_salt, user_id),
        )
        # Commit imediato: independe do que acontece adiante (ex.: conta
        # desativada) — sem isso, um conn.close() sem commit em um branch
        # de erro descartaria a migração silenciosamente.
        conn.commit()
        audit.log_action(
            action=AuditAction.CONFIG_CHANGE,
            user=username_db,
            description="Senha migrada de SHA-256 legado para PBKDF2 salgado no login",
            severity=AuditSeverity.INFO,
        )

    if not senha_valida:
        conn.close()
        record_login_failure(username)
        audit.log_action(
            action=AuditAction.USER_ACTION,
            user=username_db,
            description="Falha de login: senha incorreta",
            severity=AuditSeverity.WARNING,
        )
        get_structured_logger().log_login(
            sucesso=False, motivo="senha_incorreta",
            duracao_segundos=time.time() - _inicio_login,
        )
        return False, None, genericos

    if not is_active:
        conn.close()
        record_login_failure(username)
        audit.log_action(
            action=AuditAction.USER_ACTION,
            user=username_db,
            description="Login negado: usuário desativado",
            severity=AuditSeverity.WARNING,
        )
        get_structured_logger().log_login(
            sucesso=False, motivo="usuario_inativo",
            duracao_segundos=time.time() - _inicio_login,
        )
        # Aqui já sabemos que a senha está correta, então revelar que a
        # conta está desativada não abre uma nova via de enumeração.
        return False, None, "Usuário desativado. Contate um administrador."

    # Atualizar último login
    c.execute('UPDATE users SET last_login = ? WHERE id = ?', (datetime.now(), user_id))

    # Criar token JWT
    payload = {
        'user_id': user_id,
        'username': username_db,
        'role': role,
        'jti': generate_jti(),  # necessário para revogar este token específico no logout
        'exp': datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)
    }

    token = jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)

    conn.commit()
    conn.close()

    record_login_success(username)
    audit.log_action(
        action=AuditAction.USER_ACTION,
        user=username_db,
        description="Login bem-sucedido",
        severity=AuditSeverity.INFO,
    )
    get_structured_logger().log_login(
        sucesso=True, motivo="sucesso", usuario=username_db,
        duracao_segundos=time.time() - _inicio_login,
    )

    user_info = {
        'user_id': user_id,
        'username': username_db,
        'email': email,
        'full_name': full_name,
        'role': role
    }

    return True, user_info, token

def verify_token(token: str) -> tuple[bool, Optional[dict]]:
    """Verifica e decodifica token JWT"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return True, payload
    except jwt.ExpiredSignatureError:
        return False, None
    except jwt.InvalidTokenError:
        return False, None

def register_user(username: str, email: str, password: str, full_name: str) -> tuple[bool, str]:
    """Registra novo usuário"""
    # Validar dados
    if not validate_email(email):
        return False, "Email inválido"
    
    is_valid, msg = validate_password(password)
    if not is_valid:
        return False, msg
    
    if len(username) < 3:
        return False, "Username deve ter pelo menos 3 caracteres"
    
    conn = get_db_connection()
    c = conn.cursor()

    # Verificar se username ou email já existem
    c.execute('SELECT id FROM users WHERE username = ? OR email = ?', (username, email))
    if c.fetchone():
        conn.close()
        return False, "Username ou email já cadastrados"

    # Inserir novo usuário
    password_hash, password_salt = hash_password(password)
    try:
        c.execute('''
            INSERT INTO users (username, email, password_hash, password_salt, full_name, role)
            VALUES (?, ?, ?, ?, ?, 'user')
        ''', (username, email, password_hash, password_salt, full_name))

        conn.commit()
        conn.close()
        get_audit_logger().log_action(
            action=AuditAction.USER_ACTION,
            user=username,
            description="Novo usuário registrado",
            severity=AuditSeverity.INFO,
        )
        return True, "Usuário registrado com sucesso"
    except Exception as e:
        conn.close()
        return False, f"Erro ao registrar usuário: {str(e)}"

def logout_user():
    """Realiza logout do usuário.

    Além de limpar a sessão local, revoga o token no servidor (lista de
    revogação por jti) para que ele não possa mais ser reutilizado antes
    de expirar naturalmente (até 24h) — antes, "logout" só apagava o
    st.session_state local; o token JWT continuava criptograficamente
    válido no servidor até o fim das 24h."""
    user = st.session_state.get('user')
    token = st.session_state.get('token')
    if token:
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
            exp_timestamp = payload.get('exp')
            if payload.get('jti') and exp_timestamp:
                revoke_token(payload['jti'], datetime.utcfromtimestamp(exp_timestamp))
        except jwt.InvalidTokenError:
            pass  # token já inválido/expirado: nada a revogar
    if user:
        get_audit_logger().log_action(
            action=AuditAction.USER_ACTION,
            user=user.get('username', 'desconhecido'),
            description="Logout",
            severity=AuditSeverity.INFO,
        )
    st.session_state.pop('token', None)
    st.session_state.pop('user', None)
    st.session_state.pop('user_id', None)
    st.session_state.pop('user_role', None)
    st.session_state.pop('username', None)
    st.rerun()

# --- PÁGINA DE LOGIN ---
def show_login_page():
    """Exibe página de login"""
    st.title("🔐 Sistema de Conciliação Bancária")
    st.markdown("### Faça login para acessar o sistema")
    
    tab1, tab2 = st.tabs(["Login", "Registrar"])
    
    with tab1:
        with st.form("login_form"):
            username = st.text_input("Username ou Email")
            password = st.text_input("Senha", type="password")
            submit = st.form_submit_button("Entrar")
            
            if submit:
                if not username or not password:
                    st.error("Preencha todos os campos")
                else:
                    success, user_info, token = login_user(username, password)
                    if success:
                        st.session_state.token = token
                        st.session_state.user = user_info
                        st.success(f"Bem-vindo, {user_info['full_name']}!")
                        st.rerun()
                    else:
                        st.error(f"Falha no login: {token}")  # 'token' aqui contém a mensagem de erro
    
    with tab2:
        st.info("Registre-se para acessar o sistema")
        with st.form("register_form"):
            col1, col2 = st.columns(2)
            with col1:
                full_name = st.text_input("Nome Completo")
                username = st.text_input("Username")
            with col2:
                email = st.text_input("Email")
                password = st.text_input("Senha", type="password")
                confirm_password = st.text_input("Confirmar Senha", type="password")
            
            submit = st.form_submit_button("Registrar")
            
            if submit:
                if not all([full_name, username, email, password, confirm_password]):
                    st.error("Preencha todos os campos")
                elif password != confirm_password:
                    st.error("Senhas não coincidem")
                else:
                    success, message = register_user(username, email, password, full_name)
                    if success:
                        st.success(message)
                        st.info("Agora faça login com suas credenciais")
                    else:
                        st.error(message)

# --- VERIFICAÇÃO DE AUTENTICAÇÃO ---
def check_authentication():
    """Verifica se usuário está autenticado.

    Além de validar o JWT, revalida o usuário no banco a cada checagem:
    um token continua criptograficamente válido mesmo depois que a conta é
    desativada ou tem a role alterada, então confiar só no payload permite
    acesso obsoleto. Ver modules.auth_middleware.revalidate_user."""
    if 'token' not in st.session_state or 'user' not in st.session_state:
        return False

    token = st.session_state.token
    is_valid, payload = verify_token(token)

    if not is_valid:
        st.session_state.pop('token', None)
        st.session_state.pop('user', None)
        return False

    if is_token_revoked(payload.get('jti')):
        st.session_state.pop('token', None)
        st.session_state.pop('user', None)
        return False

    current = revalidate_user(payload['user_id'])
    if current is None or not current['is_active']:
        st.session_state.pop('token', None)
        st.session_state.pop('user', None)
        return False

    # Sincroniza role/username com o estado atual do banco em vez de
    # confiar apenas no que foi assinado no momento do login.
    st.session_state.user['role'] = current['role']
    st.session_state.user['username'] = current['username']
    st.session_state.user['full_name'] = current['full_name']

    return True

# --- HOME v3 (fase 6, XCRE-54 item 5): 3 cartões de etapa ---
# Ícones SVG inline (thin line, viewBox 24x24) do anexo icones.svg.md da
# issue (design system v3) — conteúdo ESTÁTICO do repositório, nunca
# interpolado com dado do usuário.
_ICONE_UPLOAD = (
    '<svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>'
    '<polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>'
)
_ICONE_ANALISE = (
    '<svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
    '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>'
    '<path d="M11 8v6"/><path d="M8 11h6"/></svg>'
)
_ICONE_RELATORIO = (
    '<svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/>'
    '<polyline points="14 2 14 8 20 8"/><line x1="8" y1="13" x2="16" y2="13"/>'
    '<line x1="8" y1="17" x2="16" y2="17"/></svg>'
)

# Rótulos EXATOS pedidos pela issue (cada um com <= 6 palavras) — a Home
# não inventa nome de produto nem texto de etapa diferente deste.
_ETAPAS_HOME = (
    {"numero": 1, "rotulo": "Importação de Dados", "pagina": "pages/importacao_dados.py",
     "icone_svg": _ICONE_UPLOAD, "chave": "home_card_importacao"},
    {"numero": 2, "rotulo": "Análise de Divergências", "pagina": "pages/analise_dados.py",
     "icone_svg": _ICONE_ANALISE, "chave": "home_card_analise"},
    {"numero": 3, "rotulo": "Relatório Final", "pagina": "pages/gerar_relatorio.py",
     "icone_svg": _ICONE_RELATORIO, "chave": "home_card_relatorio"},
)


# --- LAYOUT PRINCIPAL APÓS LOGIN ---
def show_main_app():
    """Exibe a aplicação principal após login"""
    
    # Sidebar com informações do usuário
    with st.sidebar:
        st.success(f"👋 Bem-vindo, **{st.session_state.user['full_name']}**")
        st.caption(f"Username: {st.session_state.user['username']}")
        st.caption(f"Tipo: {st.session_state.user['role']}")
        
        # BOTÃO DE GERENCIAMENTO DE USUÁRIOS (apenas para admin)
        if st.session_state.user['role'] == 'admin':
            if st.button("👥 Gerenciar Usuários", use_container_width=True):
                st.session_state.show_user_management = True
        
        if st.button("🚪 Sair", use_container_width=True):
            logout_user()
        
        st.divider()
    
    # Seção de Gerenciamento de Usuários (apenas para admin)
    if st.session_state.get('show_user_management', False) and st.session_state.user['role'] == 'admin':
        show_user_management_section()
        return  # Para mostrar apenas o gerenciamento
    
    # Menu Customizado
    with st.sidebar:
        st.markdown("### Navegação Principal")
        st.page_link("app.py", label="Início (Home)", icon="🏠")
        
        # Use o nome do arquivo exato no primeiro parâmetro, e o que quiser no 'label'
        st.page_link("pages/importacao_dados.py", label="📥 Importação de Dados", icon=None)
        st.page_link("pages/analise_dados.py", label="📊 Análise de Divergências", icon=None)
        st.page_link("pages/gerar_relatorio.py", label="📝 Relatório Final", icon=None)

    # Conteúdo principal — Home v3 (fase 6, XCRE-54 item 5): SOMENTE as
    # opções das 3 etapas do fluxo, como 3 cartões iguais e clicáveis.
    # Tudo o mais que existia aqui (boas-vindas longas, blocos de
    # funcionalidades, "Sobre o Sistema", status/resumo da sessão,
    # atalho "Nova Análise") foi removido por decisão do usuário. Ícones
    # SVG inline vêm do anexo icones.svg.md (design system v3) — texto
    # estático do repositório, nunca dado do usuário.
    st.title("🏦 Sistema de Conciliação Bancária")

    for coluna, etapa in zip(st.columns(3), _ETAPAS_HOME):
        with coluna:
            st.markdown(
                '<div class="step-card">'
                f'<div>{etapa["icone_svg"]}</div>'
                f'<div class="step-number">Etapa {etapa["numero"]}</div>'
                f'<div class="step-label">{etapa["rotulo"]}</div>'
                '</div>',
                unsafe_allow_html=True,
            )
            if st.button(etapa["rotulo"], key=etapa["chave"], width='stretch'):
                st.switch_page(etapa["pagina"])

def show_user_management_section():
    """Mostra a interface de gerenciamento de usuários"""
    st.title("👥 Gerenciamento de Usuários")
    
    # Botão para voltar
    if st.button("← Voltar para o Sistema"):
        st.session_state.show_user_management = False
        st.rerun()
    
    admin_username = st.session_state.user['username']
    conn = get_db_connection()
    c = conn.cursor()
    
    # Listar usuários
    st.subheader("Usuários Cadastrados")
    c.execute('''
        SELECT id, username, email, full_name, role, is_active, created_at, last_login 
        FROM users ORDER BY created_at DESC
    ''')
    users = c.fetchall()
    
    if users:
        for user in users:
            id, username, email, full_name, role, is_active, created_at, last_login = user
            
            with st.expander(f"{full_name} ({username}) - {role}"):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Email:** {email}")
                    st.write(f"**Ativo:** {'✅' if is_active else '❌'}")
                with col2:
                    st.write(f"**Criado em:** {created_at}")
                    st.write(f"**Último login:** {last_login or 'Nunca'}")
                
                # Ações
                col_act1, col_act2, col_act3 = st.columns(3)
                with col_act1:
                    if st.button("🔧 Editar Role", key=f"edit_{id}"):
                        # Lógica para editar role
                        new_role = "admin" if role == "user" else "user"
                        c.execute('UPDATE users SET role = ? WHERE id = ?', (new_role, id))
                        conn.commit()
                        get_audit_logger().log_action(
                            action=AuditAction.CONFIG_CHANGE,
                            user=admin_username,
                            description=f"Role de '{username}' alterada",
                            details={'target_user': username, 'old_role': role, 'new_role': new_role},
                            severity=AuditSeverity.WARNING,
                        )
                        st.rerun()
                with col_act2:
                    if is_active:
                        if st.button("🚫 Desativar", key=f"deactivate_{id}"):
                            c.execute('UPDATE users SET is_active = 0 WHERE id = ?', (id,))
                            conn.commit()
                            get_audit_logger().log_action(
                                action=AuditAction.CONFIG_CHANGE,
                                user=admin_username,
                                description=f"Usuário '{username}' desativado",
                                details={'target_user': username},
                                severity=AuditSeverity.WARNING,
                            )
                            st.rerun()
                    else:
                        if st.button("✅ Ativar", key=f"activate_{id}"):
                            c.execute('UPDATE users SET is_active = 1 WHERE id = ?', (id,))
                            conn.commit()
                            get_audit_logger().log_action(
                                action=AuditAction.CONFIG_CHANGE,
                                user=admin_username,
                                description=f"Usuário '{username}' ativado",
                                details={'target_user': username},
                                severity=AuditSeverity.WARNING,
                            )
                            st.rerun()
                with col_act3:
                    if id != 1 and id != st.session_state.user['user_id']:  # Não permitir excluir admin principal ou a si mesmo
                        if st.button("🗑️ Excluir", key=f"delete_{id}"):
                            c.execute('DELETE FROM users WHERE id = ?', (id,))
                            conn.commit()
                            get_audit_logger().log_action(
                                action=AuditAction.CONFIG_CHANGE,
                                user=admin_username,
                                description=f"Usuário '{username}' excluído",
                                details={'target_user': username},
                                severity=AuditSeverity.CRITICAL,
                            )
                            st.rerun()
                    else:
                        st.write("🔒 Protegido")
    
    # Adicionar novo usuário
    st.subheader("Adicionar Novo Usuário")
    with st.form("add_user_form"):
        col1, col2 = st.columns(2)
        with col1:
            new_username = st.text_input("Username")
            new_full_name = st.text_input("Nome Completo")
        with col2:
            new_email = st.text_input("Email")
            new_role = st.selectbox("Tipo de Usuário", ["user", "admin"])
        
        new_password = st.text_input("Senha Temporária", type="password")
        
        if st.form_submit_button("Adicionar Usuário"):
            if all([new_username, new_email, new_full_name, new_password]):
                try:
                    password_hash, password_salt = hash_password(new_password)
                    c.execute('''
                        INSERT INTO users (username, email, password_hash, password_salt, full_name, role)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (new_username, new_email, password_hash, password_salt, new_full_name, new_role))
                    conn.commit()
                    get_audit_logger().log_action(
                        action=AuditAction.CONFIG_CHANGE,
                        user=admin_username,
                        description=f"Usuário '{new_username}' criado pelo administrador",
                        details={'target_user': new_username, 'role': new_role},
                        severity=AuditSeverity.WARNING,
                    )
                    st.success(f"Usuário {new_username} adicionado com sucesso!")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("Username ou email já existe")
            else:
                st.error("Preencha todos os campos")
    
    conn.close()


# --- INICIALIZAÇÃO ---
def main():
    """Função principal da aplicação"""
    # Inicializar banco de dados
    init_db()
    
    # Verificar autenticação
    if not check_authentication():
        show_login_page()
    else:
        show_main_app()

if __name__ == "__main__":
    main()