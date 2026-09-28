"""
Regressão para o achado da revisão pós-fase 7 (XCRE-55): a página de
Análise tinha uma seção "Debug - Similaridades" com dados reais de
transações sempre visível na barra lateral, apesar de estar dentro de
dois níveis de contêiner fechado (expander "Detalhes" > aba "Dashboard
Interativo" > expander "Debug Similaridades"). Causa: a função
`debug_matching_similaridades` escrevia direto em `st.sidebar.*` em vez
de no contêiner que a chamava, então o conteúdo "vazava" para a barra
lateral de verdade independente do estado dos expanders/abas ao redor.

Achado relacionado: 4 caixinhas em "⚙️ Configurações de Análise" >
"📋 Regras de Correspondência" / "🎯 Filtros de Análise" (parcelamentos
1:N, consolidações N:1, priorizar matches exatos, analisar apenas mês
corrente) nunca eram lidas em nenhum lugar do código — marcar ou
desmarcar não mudava o resultado da análise.

Correção: remover a função de debug (a mesma informação já aparece
corretamente na aba "Similaridade") e as 4 caixinhas decorativas.
`valor_minimo`, que É lido pelo filtro de itens em aberto, foi mantido.

Dados 100% sintéticos.
"""
import sqlite3

import pandas as pd
import pytest


def _criar_usuario_e_autenticar(tmp_path, monkeypatch, username: str):
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
        (username, f"{username}@example.com", password_hash, salt, "QA Debug Sidebar"),
    )
    conn.commit()
    init_security_tables(conn)
    conn.close()

    from modules.auth_middleware import get_db_connection
    conn = get_db_connection(db_path)
    row = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    user_id = row[0]

    import jwt
    from app import SECRET_KEY, JWT_ALGORITHM
    from datetime import datetime, timedelta
    payload = {
        "user_id": user_id, "username": username, "role": "user",
        "exp": datetime.utcnow() + timedelta(hours=1),
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)
    return token, {"id": user_id, "username": username, "role": "user"}


@pytest.fixture
def app_autenticado_com_dados(tmp_path, monkeypatch):
    token, user_info = _criar_usuario_e_autenticar(tmp_path, monkeypatch, "qa_debug_sidebar")
    extrato_df = pd.DataFrame({
        "id": [1, 2],
        "data": pd.to_datetime(["2025-06-10", "2025-06-01"]),
        "valor": [-100.00, -999.99],
        "descricao": ["Pagamento Fornecedor A", "Tarifa Bancária Diversa"],
    })
    contabil_df = pd.DataFrame({
        "id": [1, 2],
        "data": pd.to_datetime(["2025-06-10", "2025-06-25"]),
        "valor": [-100.00, 5000.00],
        "descricao": ["Pagamento Fornecedor A", "Lançamento Contábil Diverso"],
    })
    return token, user_info, extrato_df, contabil_df


def _carregar_e_executar(app_autenticado_com_dados):
    import os
    from streamlit.testing.v1 import AppTest

    token, user_info, extrato_df, contabil_df = app_autenticado_com_dados
    app_py = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")

    at = AppTest.from_file(app_py, default_timeout=30)
    at.session_state["token"] = token
    at.session_state["user"] = user_info
    at.session_state["extrato_df"] = extrato_df
    at.session_state["contabil_df"] = contabil_df
    at.session_state["dados_carregados"] = True
    at.switch_page("pages/analise_dados.py")
    at.run()
    assert not at.exception, f"página levantou exceção só ao carregar: {at.exception}"

    botoes = [b for b in at.button if b.label == "Executar Análise de Correspondências"]
    assert len(botoes) == 1
    botoes[0].click()
    at.run()
    assert not at.exception, f"execução da análise levantou exceção: {at.exception}"
    return at


def _todo_texto_da_sidebar(at):
    return "\n".join(str(getattr(el, "value", "") or "") for el in at.sidebar)


def test_sidebar_nao_tem_secao_debug_similaridades(app_autenticado_com_dados):
    at = _carregar_e_executar(app_autenticado_com_dados)
    texto = _todo_texto_da_sidebar(at)
    assert "Debug" not in texto
    assert "Similaridades" not in texto or "Debug - Similaridades" not in texto


def test_sidebar_nao_expoe_descricoes_de_transacao_do_debug(app_autenticado_com_dados):
    """A função removida escrevia a descrição e o valor de cada transação
    do exemplo direto na sidebar; nenhuma delas deve aparecer lá."""
    at = _carregar_e_executar(app_autenticado_com_dados)
    texto = _todo_texto_da_sidebar(at)
    assert "Pagamento Fornecedor A" not in texto
    assert "Lançamento Contábil Diverso" not in texto


def test_sidebar_nao_tem_caixinhas_decorativas_sem_efeito(app_autenticado_com_dados):
    at = _carregar_e_executar(app_autenticado_com_dados)
    rotulos = {c.label for c in at.sidebar.checkbox}
    for rotulo in (
        "Identificar parcelamentos (1:N)",
        "Identificar consolidações (N:1)",
        "Priorizar matches exatos",
        "Analisar apenas mês corrente",
    ):
        assert rotulo not in rotulos


def test_filtro_valor_minimo_continua_funcionando(app_autenticado_com_dados):
    """valor_minimo É lido pelo filtro (diferente das caixinhas removidas);
    o campo continua na sidebar."""
    at = _carregar_e_executar(app_autenticado_com_dados)
    rotulos = {n.label for n in at.sidebar.number_input}
    assert "Valor mínimo (R$)" in rotulos


def test_aba_similaridade_continua_existindo_como_alternativa_ao_debug_removido(app_autenticado_com_dados):
    at = _carregar_e_executar(app_autenticado_com_dados)
    rotulos_abas = [t.label for t in at.tabs]
    assert any("Similaridade" in r for r in rotulos_abas)
