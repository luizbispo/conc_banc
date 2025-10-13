# modules/user_manager.py
import streamlit as st
import sqlite3
from modules.auth_middleware import require_role, get_current_user

@require_role('admin')

def show_user_management():
    """Interface de gerenciamento de usuários (apenas admin)"""
    st.title("👥 Gerenciamento de Usuários")
    
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
                    if st.button("🔧 Editar", key=f"edit_{id}"):
                        st.session_state.editing_user = id
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
                    if id != 1:  # Não permitir excluir admin principal
                        if st.button("🗑️ Excluir", key=f"delete_{id}"):
                            c.execute('DELETE FROM users WHERE id = ?', (id,))
                            conn.commit()
                            st.rerun()
    
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
                # Implementar criação de usuário
                st.success(f"Usuário {new_username} adicionado com sucesso!")
            else:
                st.error("Preencha todos os campos")
    
    conn.close()

# Adicionar esta página ao app.py se desejar gerenciamento de usuários