"""
Testes AppTest para o item 1 da fase 7 (XCRE-55): tela de importação no
visual v3 conciso.

Visão padrão de destino: título, os 2 uploaders (Extrato Bancário e
Lançamentos Contábeis) lado a lado, e o botão primário para seguir à
análise quando os dados estiverem prontos. Os recursos secundários que
hoje ficam soltos na sidebar e no corpo da página (rádio de "Método de
Importação" com Link de Pastas na Nuvem / Links Diretos, checkbox do
"Novo Sistema de Validação por nome de arquivo", checkbox "Permitir OFX
no lado contábil", o expander "Guia Completo de Importação", o expander
"Modo Desenvolvedor" e o expander "Ajuda - Sistema de Validação por
Nome", além das Instruções Gerais da sidebar) NÃO podem ser apagados
(regra de não perder funcionalidade da issue) — só relocados para
dentro de UM único expander fechado "Opções avançadas" no fim da
página. A sidebar da página deve sobrar só com a navegação.

Escrito ANTES da implementação (padrão do squad para XCRE-55): hoje
esses recursos ainda estão soltos na sidebar/corpo da página, então os
dois primeiros testes abaixo devem falhar contra o código atual e
passar depois da implementação do item 1.

Mesmo padrão de fixture/AppTest de
tests/test_importacao_mensagem_unica_limite.py (guard de autenticação
em nível de módulo desta página). Dados 100% sintéticos.
"""
import os
import sqlite3

import pytest

APP_PY = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")


@pytest.fixture
def app_autenticado(tmp_path, monkeypatch):
    """Mesmo setup de autenticação de
    tests/test_importacao_mensagem_unica_limite.py::app_autenticado — a
    página completa roda isolada por instância de AppTest, então precisa
    da própria sessão pré-carregada, não da global `st`."""
    db_path = str(tmp_path / "users.db")
    audit_path = str(tmp_path / "audit.db")
    structured_log_path = str(tmp_path / "eventos_estruturados.jsonl")
    monkeypatch.setenv("CONCILIACAO_DB_PATH", db_path)
    monkeypatch.setenv("CONCILIACAO_AUDIT_DB_PATH", audit_path)
    monkeypatch.setenv("CONCILIACAO_STRUCTURED_LOG_PATH", structured_log_path)

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
    import modules.structured_logger as structured_logger_module
    structured_logger_module._structured_logger = None

    import app
    success, user_info, token = app.login_user("usuario_teste", "SenhaNova1")
    assert success is True

    return token, user_info


def _carregar_pagina(app_autenticado):
    from streamlit.testing.v1 import AppTest

    token, user_info = app_autenticado
    at = AppTest.from_file(APP_PY, default_timeout=30)
    at.session_state["token"] = token
    at.session_state["user"] = user_info
    at.switch_page("pages/importacao_dados.py")
    at.run()
    assert not at.exception, f"página levantou exceção só ao carregar: {at.exception}"
    return at


def test_visao_padrao_tem_os_2_uploaders_e_sidebar_so_com_navegacao(app_autenticado):
    at = _carregar_pagina(app_autenticado)

    # os 2 uploaders da visão padrão continuam com as mesmas keys já
    # usadas por tests/test_importacao_mensagem_unica_limite.py
    assert at.get_by_key("extrato_upload") is not None
    assert at.get_by_key("contabil_upload") is not None

    # a sidebar da página fica só com a navegação: nenhum widget de
    # configuração (rádio de método, checkboxes) deve sobrar lá.
    assert len(at.sidebar.radio) == 0, "rádio de método não deveria mais estar na sidebar"
    assert len(at.sidebar.checkbox) == 0, "checkboxes de configuração não deveriam mais estar na sidebar"


def test_opcoes_avancadas_existe_fechado_e_concentra_os_recursos_secundarios(app_autenticado):
    at = _carregar_pagina(app_autenticado)

    expanders = [e for e in at.expander if "opções avançadas" in e.label.lower()]
    assert len(expanders) == 1, "deve existir exatamente um expander 'Opções avançadas'"
    avancadas = expanders[0]
    assert avancadas.proto.expanded is False, "o expander 'Opções avançadas' deve começar fechado"

    # nenhum rádio/checkbox de configuração sobra fora deste único
    # expander (tudo o que era da sidebar/corpo foi para dentro dele)
    assert len(at.radio) == len(avancadas.radio)
    assert len(at.checkbox) == len(avancadas.checkbox)
    assert len(avancadas.checkbox) >= 2, "checkboxes de validação por nome e de OFX no contábil preservados"

    textos = " ".join(m.value for m in avancadas.markdown).lower()
    textos += " ".join(r.label for r in avancadas.radio).lower()
    textos += " ".join(" ".join(r.options) for r in avancadas.radio).lower()
    textos += " ".join(c.label for c in avancadas.checkbox).lower()
    for pista in (
        "link de pastas na nuvem",
        "links diretos",
        "validação por nome",
        "modo desenvolvedor",
        "guia completo",
        "ajuda",
        "instruções gerais",
    ):
        assert pista in textos, f"recurso preservado não encontrado no expander 'Opções avançadas': {pista!r}"


def test_botao_primario_para_analise_aparece_quando_dados_estao_prontos(app_autenticado):
    at = _carregar_pagina(app_autenticado)

    primarios_antes = [b for b in at.button if b.label == "Ir para Análise de Dados"]
    assert len(primarios_antes) == 0, "sem dados carregados, o botão para análise não deve aparecer"

    at.session_state["dados_carregados"] = True
    at.run()

    primarios = [b for b in at.button if b.label == "Ir para Análise de Dados"]
    assert len(primarios) == 1
    assert primarios[0].proto.type == "primary"


def test_cartoes_extrato_e_contabil_tem_a_mesma_estrutura_alinhada(app_autenticado):
    """Achado do E2E da verificação integrada (CT-F7-VIS): o título
    "Lançamentos Contábeis" ficava FORA do `st.container(border=True)`
    da coluna 2, enquanto "Extrato Bancário" ficava DENTRO do da coluna
    1 — ~61px de diferença visível entre os cartões. Os dois títulos
    precisam morar dentro do mesmo container com borda que envolve o
    respectivo uploader, os dois cartões com a mesma estrutura."""
    at = _carregar_pagina(app_autenticado)

    containers_com_borda = [
        n for n in at.main
        if getattr(n, "type", None) == "flex_container" and n.proto.flex_container.border
    ]
    assert len(containers_com_borda) == 2, "os 2 cartões de upload devem ser containers com borda"

    container_extrato = next(
        c for c in containers_com_borda if any(fu.key == "extrato_upload" for fu in c.file_uploader)
    )
    container_contabil = next(
        c for c in containers_com_borda if any(fu.key == "contabil_upload" for fu in c.file_uploader)
    )

    assert any(sh.value == "🏦 Extrato Bancário" for sh in container_extrato.subheader), (
        "título 'Extrato Bancário' deve estar dentro do mesmo cartão do uploader"
    )
    assert any(sh.value == "📊 Lançamentos Contábeis" for sh in container_contabil.subheader), (
        "título 'Lançamentos Contábeis' deve estar dentro do mesmo cartão do uploader (achado do E2E)"
    )

    # nenhum dos dois títulos pode sobrar solto FORA de todos os cartões
    subheaders_fora = [
        sh.value for sh in at.subheader
        if not any(sh in c.subheader for c in containers_com_borda)
    ]
    assert "🏦 Extrato Bancário" not in subheaders_fora
    assert "📊 Lançamentos Contábeis" not in subheaders_fora
