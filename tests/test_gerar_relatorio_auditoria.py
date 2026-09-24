"""
Teste de regressão de ponta a ponta para a integração de auditoria da
geração de relatório (issue XCRE-42, CT-AUD-01): log_report_generation
já existia em modules/audit_logger.py, mas pages/gerar_relatorio.py
nunca o chamava — a geração de relatório (sucesso OU falha) não deixava
nenhum rastro na auditoria.

Roda a página real (main()) em modo bare do Streamlit, simulando o
clique no botão "Gerar Relatório de Análise" via monkeypatch de
st.button, e inspeciona o audit_log.db resultante. Segue o mesmo padrão
de tests/test_logout_revocation.py / tests/test_importacao_limites.py
para lidar com o guard de autenticação (@require_auth em main()).

Dados 100% sintéticos.
"""
import sqlite3
from unittest import mock

import pandas as pd
import pytest
import streamlit as st


@pytest.fixture
def sessao_autenticada(tmp_path, monkeypatch):
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
        ("qa_user", "qa@example.com", password_hash, salt, "QA User"),
    )
    conn.commit()
    init_security_tables(conn)
    conn.close()

    import modules.audit_logger as audit_logger_module
    audit_logger_module._audit_logger = None

    import app
    success, user_info, token = app.login_user("qa_user", "SenhaNova1")
    assert success is True

    st.session_state["token"] = token
    st.session_state["user"] = user_info
    st.session_state["resultados_analise"] = {"matches": [], "excecoes": [{}]}
    st.session_state["extrato_df"] = pd.DataFrame({
        "id": [1], "data": pd.to_datetime(["2025-06-15"]), "valor": [60.50], "descricao": ["A"],
    })
    st.session_state["contabil_df"] = pd.DataFrame({
        "id": [1], "data": pd.to_datetime(["2025-06-20"]), "valor": [500.0], "descricao": ["C"],
    })

    return audit_path


def _clicar_gerar_relatorio(label, *args, **kwargs):
    return kwargs.get("key") == "btn_gerar_relatorio_analise"


def test_geracao_com_sucesso_registra_evento_de_auditoria(sessao_autenticada):
    audit_path = sessao_autenticada

    with mock.patch.object(st, "button", side_effect=_clicar_gerar_relatorio):
        import pages.gerar_relatorio as pagina
        pagina.main()

    conn = sqlite3.connect(audit_path)
    row = conn.execute(
        "SELECT user, details FROM audit_log WHERE action = 'REPORT_GENERATION'"
    ).fetchone()
    conn.close()

    assert row is not None
    user, details_json = row
    assert user == "qa_user"

    import json
    details = json.loads(details_json)
    assert details["success"] is True
    assert details["formato"] == "completo"
    # "lote" combina conta + período; o período vem de calcular_periodo_real
    # (item 1 desta issue) a partir das datas reais do extrato/contábil
    # fixados no fixture (15/06/2025 a 20/06/2025), não da data de geração.
    assert details["lote"] == "Não identificada | 15/06/2025 a 20/06/2025"
    assert details["included_exceptions"] == 1


def test_geracao_com_falha_registra_evento_de_auditoria_com_erro(sessao_autenticada):
    audit_path = sessao_autenticada

    with mock.patch.object(st, "button", side_effect=_clicar_gerar_relatorio), \
         mock.patch("modules.report_generator.gerar_relatorio_analise", side_effect=RuntimeError("falha sintética de geração")):
        import pages.gerar_relatorio as pagina
        import importlib
        importlib.reload(pagina)  # garante que pagina.report_gen aponte para o módulo já mockado
        pagina.main()

    conn = sqlite3.connect(audit_path)
    row = conn.execute(
        "SELECT severity, details FROM audit_log WHERE action = 'REPORT_GENERATION'"
    ).fetchone()
    conn.close()

    assert row is not None
    severity, details_json = row
    assert severity == "ERROR"

    import json
    details = json.loads(details_json)
    assert details["success"] is False
    assert "falha sintética de geração" in details["error_message"]
