# app.py - Aplicação Principal Streamlit com Sistema de Login
import streamlit as st
import hashlib
import sqlite3
import re
from datetime import datetime, timedelta
import jwt
import os
from typing import Optional

# Configuração da página
st.set_page_config(
    page_title="Sistema de Conciliação Bancária",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CONFIGURAÇÕES DE SEGURANÇA ---
SECRET_KEY = os.getenv("CONCILIACAO_SECRET_KEY", "chave_secreta_padrao_mudar_em_producao")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

# --- BANCO DE DADOS DE USUÁRIOS ---
def init_db():
    """Inicializa o banco de dados de usuários"""
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    # Tabela de usuários
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        )
    ''')
    
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
    
    # Inserir usuário admin padrão se não existir
    c.execute("SELECT COUNT(*) FROM users WHERE username = 'admin'")
    if c.fetchone()[0] == 0:
        password_hash = hash_password("admin123")
        c.execute('''
            INSERT INTO users (username, email, password_hash, full_name, role)
            VALUES (?, ?, ?, ?, ?)
        ''', ('admin', 'admin@sistema.com', password_hash, 'Administrador', 'admin'))
    
    conn.commit()
    conn.close()

def hash_password(password: str) -> str:
    """Cria hash da senha usando SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, password_hash: str) -> bool:
    """Verifica se a senha corresponde ao hash"""
    return hash_password(password) == password_hash

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
    """Autentica usuário e retorna token JWT"""
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    c.execute('''
        SELECT id, username, email, full_name, role, password_hash, is_active
        FROM users WHERE username = ? OR email = ?
    ''', (username, username))
    
    user = c.fetchone()
    
    if not user:
        conn.close()
        return False, None, "Usuário não encontrado"
    
    user_id, username, email, full_name, role, password_hash, is_active = user
    
    if not is_active:
        conn.close()
        return False, None, "Usuário desativado"
    
    if not verify_password(password, password_hash):
        conn.close()
        return False, None, "Senha incorreta"
    
    # Atualizar último login
    c.execute('UPDATE users SET last_login = ? WHERE id = ?', (datetime.now(), user_id))
    
    # Criar token JWT
    payload = {
        'user_id': user_id,
        'username': username,
        'role': role,
        'exp': datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)
    }
    
    token = jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)
    
    conn.commit()
    conn.close()
    
    user_info = {
        'user_id': user_id,
        'username': username,
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
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    # Verificar se username ou email já existem
    c.execute('SELECT id FROM users WHERE username = ? OR email = ?', (username, email))
    if c.fetchone():
        conn.close()
        return False, "Username ou email já cadastrados"
    
    # Inserir novo usuário
    password_hash = hash_password(password)
    try:
        c.execute('''
            INSERT INTO users (username, email, password_hash, full_name, role)
            VALUES (?, ?, ?, ?, 'user')
        ''', (username, email, password_hash, full_name))
        
        conn.commit()
        conn.close()
        return True, "Usuário registrado com sucesso"
    except Exception as e:
        conn.close()
        return False, f"Erro ao registrar usuário: {str(e)}"

def logout_user():
    """Realiza logout do usuário"""
    st.session_state.pop('token', None)
    st.session_state.pop('user', None)
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
    """Verifica se usuário está autenticado"""
    if 'token' not in st.session_state or 'user' not in st.session_state:
        return False
    
    token = st.session_state.token
    is_valid, payload = verify_token(token)
    
    if not is_valid:
        st.session_state.pop('token', None)
        st.session_state.pop('user', None)
        return False
    
    return True

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

    # Conteúdo principal
    st.title("🏦 Sistema de Conciliação Bancária")
    st.markdown(f"""
    ### Olá, {st.session_state.user['full_name']}!
    
    Sistema para análise e conciliação de extratos bancários e lançamentos contábeis

    **Funcionalidades principais:**
    - **Importação** de extratos bancários e lançamentos contábeis
    - **Análise inteligente** com matching em múltiplas camadas  
    - **Relatórios em PDF** para documentação

    **Fluxo recomendado:**
    1. **Importação** → Carregue os arquivos bancários e contábeis
    2. **Análise** → Sistema identifica correspondências automaticamente
    3. **Relatório** → Gere PDF para documentação e auditoria
    """)

    # Navegação entre páginas
    st.divider()
    st.subheader("Iniciar Conciliação")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("Importação de Dados", width='stretch'):
            st.switch_page("pages/importacao_dados.py")

    with col2:
        if st.button("Análise de Dados", width='stretch'):
            st.switch_page("pages/analise_dados.py")

    with col3:
        if st.button(" Gerar Relatório", width='stretch'):
            st.switch_page("pages/gerar_relatorio.py")

    # Informações do sistema
    with st.sidebar:
        st.header("ℹ️ Sobre o Sistema")
        st.markdown("""
        **Versão:** 2.4.0     
        **Desenvolvido para:** Empresas e contadores  
        **Desenvolvido por:** Luiz Bispo (X-Testing)
                    
        **Funcionalidades:**
        - Sistema de autenticação seguro
        - Suporte a OFX, CSV, CNAB
        - Matching inteligente
        - Auditoria completa
        - Relatórios em PDF
        """)
        
        # Status da sessão atual
        st.divider()
        st.subheader("📊 Status da Sessão")
        
        if 'extrato_carregado' in st.session_state:
            st.success("✅ Extrato carregado")
        else:
            st.warning("📥 Aguardando extrato")
        
        if 'contabil_carregado' in st.session_state:
            st.success("✅ Lançamentos carregados")
        else:
            st.warning("📥 Aguardando lançamentos")
        
        if 'resultados_analise' in st.session_state:
            st.success("✅ Análise concluída")
        
        if 'matches_aprovados' in st.session_state:
            st.success(f"✅ {len(st.session_state.matches_aprovados)} conciliações aprovadas")

    # Limpar sessão
    st.sidebar.divider()
    if st.sidebar.button("🔄 Nova Análise", width='stretch'):
        keys_to_clear = [
            'extrato_carregado', 'contabil_carregado', 'caminho_extrato', 
            'caminho_contabil', 'resultados_analise', 'extrato_df', 
            'contabil_df', 'matches_aprovados', 'matches_rejeitados', 
            'matches_pendentes', 'conta_analisada'
        ]
        for key in keys_to_clear:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()

def show_user_management_section():
    """Mostra a interface de gerenciamento de usuários"""
    st.title("👥 Gerenciamento de Usuários")
    
    # Botão para voltar
    if st.button("← Voltar para o Sistema"):
        st.session_state.show_user_management = False
        st.rerun()
    
    import sqlite3
    from modules.auth_middleware import hash_password
    
    conn = sqlite3.connect('users.db')
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
                        st.rerun()
                with col_act2:
                    if is_active:
                        if st.button("🚫 Desativar", key=f"deactivate_{id}"):
                            c.execute('UPDATE users SET is_active = 0 WHERE id = ?', (id,))
                            conn.commit()
                            st.rerun()
                    else:
                        if st.button("✅ Ativar", key=f"activate_{id}"):
                            c.execute('UPDATE users SET is_active = 1 WHERE id = ?', (id,))
                            conn.commit()
                            st.rerun()
                with col_act3:
                    if id != 1 and id != st.session_state.user['user_id']:  # Não permitir excluir admin principal ou a si mesmo
                        if st.button("🗑️ Excluir", key=f"delete_{id}"):
                            c.execute('DELETE FROM users WHERE id = ?', (id,))
                            conn.commit()
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
                    password_hash = hash_password(new_password)
                    c.execute('''
                        INSERT INTO users (username, email, password_hash, full_name, role)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (new_username, new_email, password_hash, new_full_name, new_role))
                    conn.commit()
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