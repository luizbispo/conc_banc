"""
Testes AppTest para o item 4 da fase 7 (XCRE-55): login e polimento
visual v3 (app.py + assets/custom.css).

Conforme mockup-login (anexo da issue): tela de login com um cartão
centralizado, título "Sistema de Conciliação Bancária", campos de
usuário/senha e botão "Entrar"; a aba "Registrar" continua existindo.
NENHUM comportamento novo: login, logout e cadastro continuam
funcionando exatamente como antes — só a apresentação muda.

Não havia, antes desta issue, nenhum teste dirigindo a UI real de
login/registrar/sair via `streamlit.testing.v1.AppTest` (os testes
existentes — tests/test_logout_revocation.py,
tests/test_login_legacy_migration.py — chamam
app.login_user/register_user/logout_user diretamente como funções
Python, sem passar pelos formulários renderizados). Os testes abaixo
preenchem essa lacuna antes da mudança visual, então servem tanto de
regressão funcional quanto de verificação do layout novo.

Dados 100% sintéticos.
"""
import os
import sqlite3

import pytest

APP_PY = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")


@pytest.fixture
def banco_com_usuario(tmp_path, monkeypatch):
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
        ("usuario_teste", "teste@example.com", password_hash, salt, "Usuário Teste"),
    )
    conn.commit()
    init_security_tables(conn)
    conn.close()

    import modules.audit_logger as audit_logger_module
    audit_logger_module._audit_logger = None

    return db_path


def _carregar_app():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(APP_PY, default_timeout=30)
    at.run()
    assert not at.exception, f"app.py levantou exceção ao carregar: {at.exception}"
    return at


def test_tela_de_login_tem_titulo_cartao_tabs_e_campos(banco_com_usuario):
    at = _carregar_app()

    titulos = [t.value for t in at.title]
    assert any("Sistema de Conciliação Bancária" in t for t in titulos)

    # cartão: título + abas ficam dentro de pelo menos um container COM
    # BORDA (st.container(border=True)), não soltos na largura toda da
    # página nem só dentro das colunas de centralização (que também são
    # "flex_container", mas sem borda).
    containers_com_borda = [
        n for n in at.main
        if getattr(n, "type", None) == "flex_container" and n.proto.flex_container.border
    ]
    assert containers_com_borda, "o formulário de login deve estar dentro de um container com borda (cartão)"

    rotulos_abas = [t.label for t in at.tabs]
    assert "Login" in rotulos_abas
    assert "Registrar" in rotulos_abas

    rotulos_campos = [ti.label for ti in at.text_input]
    assert "Username ou Email" in rotulos_campos
    assert "Senha" in rotulos_campos

    # form_submit_button aparece em at.button no AppTest
    assert any(b.label == "Entrar" for b in at.button)


def test_login_com_sucesso_via_formulario_autentica_e_mostra_home(banco_com_usuario):
    at = _carregar_app()

    aba_login = next(t for t in at.tabs if t.label == "Login")

    campo_usuario = next(ti for ti in aba_login.text_input if ti.label == "Username ou Email")
    campo_senha = next(ti for ti in aba_login.text_input if ti.label == "Senha")
    campo_usuario.set_value("usuario_teste")
    campo_senha.set_value("SenhaNova1")

    botao_entrar = next(b for b in aba_login.button if b.label == "Entrar")
    botao_entrar.click()
    at.run()

    assert not at.exception, f"login via formulário levantou exceção: {at.exception}"
    assert at.session_state.get("user", {}).get("username") == "usuario_teste"
    assert at.session_state.get("token")

    # depois de logado, a Home v3 aparece (título do sistema + os 3 cartões de etapa)
    titulos = [t.value for t in at.title]
    assert any("Sistema de Conciliação Bancária" in t for t in titulos)
    rotulos_botoes_home = [b.label for b in at.button]
    assert "Importação de Dados" in rotulos_botoes_home


def test_logout_via_sidebar_volta_para_tela_de_login(banco_com_usuario):
    at = _carregar_app()
    from modules.auth_middleware import hash_password
    import app
    success, user_info, token = app.login_user("usuario_teste", "SenhaNova1")
    assert success is True

    at.session_state["token"] = token
    at.session_state["user"] = user_info
    at.run()
    assert not at.exception

    botao_sair = next(b for b in at.sidebar.button if "Sair" in b.label)
    botao_sair.click()
    at.run()

    assert not at.exception, f"logout levantou exceção: {at.exception}"
    assert "token" not in at.session_state
    assert "user" not in at.session_state
    rotulos_abas = [t.label for t in at.tabs]
    assert "Login" in rotulos_abas and "Registrar" in rotulos_abas


def test_cadastro_via_formulario_cria_usuario_que_consegue_logar(banco_com_usuario):
    at = _carregar_app()

    aba_registrar = next(t for t in at.tabs if t.label == "Registrar")
    campos = {ti.label: ti for ti in aba_registrar.text_input}
    campos["Nome Completo"].set_value("Pessoa Nova QA")
    campos["Username"].set_value("pessoa_nova_qa")
    campos["Email"].set_value("pessoa.nova.qa@example.com")
    campos["Senha"].set_value("SenhaValida1")
    campos["Confirmar Senha"].set_value("SenhaValida1")

    botao_registrar = next(b for b in aba_registrar.button if b.label == "Registrar")
    botao_registrar.click()
    at.run()

    assert not at.exception, f"cadastro via formulário levantou exceção: {at.exception}"
    mensagens_sucesso = [s.value for s in at.success]
    assert any("sucesso" in m.lower() for m in mensagens_sucesso)

    import app
    success, user_info, _token = app.login_user("pessoa_nova_qa", "SenhaValida1")
    assert success is True
    assert user_info["username"] == "pessoa_nova_qa"
