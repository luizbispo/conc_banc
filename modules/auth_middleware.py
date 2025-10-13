# modules/auth_middleware.py
import streamlit as st
import jwt
import os
from datetime import datetime
from typing import Optional, Callable
import hashlib

def hash_password(password: str) -> str:
    """Cria hash da senha usando SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

# Configurações de segurança
SECRET_KEY = os.getenv("CONCILIACAO_SECRET_KEY", "chave_secreta_padrao_mudar_em_producao")
JWT_ALGORITHM = "HS256"

def require_auth(page_function: Callable) -> Callable:
    """
    Decorator para exigir autenticação em páginas
    """
    def wrapper(*args, **kwargs):
        # Verificar se usuário está autenticado
        if 'token' not in st.session_state or 'user' not in st.session_state:
            st.error("🔐 Acesso não autorizado. Faça login para acessar esta página.")
            if st.button("🔄 Ir para Login"):
                st.switch_page("app.py")
            st.stop()
        
        # Verificar validade do token
        token = st.session_state.token
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
            
            # Adicionar informações do usuário ao contexto
            st.session_state.user_id = payload['user_id']
            st.session_state.user_role = payload['role']
            st.session_state.username = payload['username']
            
        except jwt.ExpiredSignatureError:
            st.error("⏰ Sessão expirada. Faça login novamente.")
            st.session_state.pop('token', None)
            st.session_state.pop('user', None)
            if st.button("🔄 Fazer Login"):
                st.switch_page("app.py")
            st.stop()
        except jwt.InvalidTokenError:
            st.error("❌ Token inválido. Faça login novamente.")
            st.session_state.pop('token', None)
            st.session_state.pop('user', None)
            if st.button("🔄 Fazer Login"):
                st.switch_page("app.py")
            st.stop()
        
        # Executar a função da página
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
    """
    Decorator para exigir role específico
    """
    def decorator(page_function: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            # Primeiro verificar autenticação
            require_auth(page_function)(*args, **kwargs)
            
            # Depois verificar role
            user_role = get_user_role()
            if user_role != required_role and user_role != 'admin':
                st.error("🚫 Acesso negado. Permissões insuficientes.")
                st.stop()
            
            return page_function(*args, **kwargs)
        return wrapper
    return decorator

def log_user_action(action: str, details: str = ""):
    """Registra ação do usuário para auditoria"""
    user = get_current_user()
    if user:
        print(f"AUDIT [{datetime.now()}] User: {user['username']} | Action: {action} | Details: {details}")