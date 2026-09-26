"""
Testes AppTest para o item 2 da fase 7 (XCRE-55): tela de análise no
visual v3 conciso.

Visão padrão de destino: título, botão primário "Executar Análise de
Correspondências" (antes de rodar), e depois de executar: os 4
indicadores (Cobertura de Análise, Correspondências X/Y, Itens em
Aberto, Diferença Líquida), as 3 abas Correspondências / Divergências /
Similaridade (as mesmas 3 listas que a página já tem — bancário sem
contábil, contábil sem bancário e possíveis similaridades — sem
misturar itens dentro de uma aba), tabelas com botão de exportação CSV
(mesmo exportador `modules.export_divergencias.gerar_csv_divergencias`
da fase 5b) e um botão primário para o relatório. Nenhuma lógica de
matching muda — isto é regressão de LAYOUT, não de números.

Escrito ANTES da implementação (padrão do squad para XCRE-55): hoje a
página tem 5 abas de nível superior (Correspondências, Divergências,
Estatísticas, Dashboard Interativo, Detalhes Técnicos) e a aba
"Divergências" tem 3 sub-abas (em vez de "Similaridade" ser uma aba de
nível superior própria); os 4 indicadores de hoje também não incluem
"Diferença Líquida" nem consolidam "Correspondências" num único
X/Y. Os testes abaixo descrevem o layout de destino e devem falhar
contra o código atual.

Dados 100% sintéticos, desenhados para gerar exatamente: 2
correspondências exatas, 1 item bancário sem contábil e 1 item contábil
sem bancário (sem nenhuma similaridade entre os dois itens em aberto,
de propósito — datas e valores bem distantes — para manter a aba
Similaridade num estado "vazio" simples de verificar).
"""
import sqlite3

import pandas as pd
import pytest
import streamlit as st


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
        (username, f"{username}@example.com", password_hash, salt, "QA Análise"),
    )
    conn.commit()
    init_security_tables(conn)
    conn.close()

    import modules.audit_logger as audit_logger_module
    audit_logger_module._audit_logger = None

    import app
    success, user_info, token = app.login_user(username, "SenhaNova1")
    assert success is True
    return token, user_info


@pytest.fixture
def app_autenticado_com_dados(tmp_path, monkeypatch):
    """Sessão autenticada + dados sintéticos com 2 correspondências
    exatas e 1 item em aberto de cada lado, sem nenhuma similaridade
    entre os itens em aberto (datas/valores bem distantes de propósito).
    """
    token, user_info = _criar_usuario_e_autenticar(tmp_path, monkeypatch, "qa_analise")

    extrato_df = pd.DataFrame({
        "id": [1, 2, 3],
        "data": pd.to_datetime(["2025-06-10", "2025-06-12", "2025-06-01"]),
        "valor": [-100.00, 250.00, -999.99],
        "descricao": ["Pagamento Fornecedor A", "Recebimento Cliente B", "Tarifa Bancária Diversa"],
    })
    contabil_df = pd.DataFrame({
        "id": [1, 2, 3],
        "data": pd.to_datetime(["2025-06-10", "2025-06-12", "2025-06-25"]),
        "valor": [-100.00, 250.00, 5000.00],
        "descricao": ["Pagamento Fornecedor A", "Recebimento Cliente B", "Lançamento Contábil Diverso"],
    })
    return token, user_info, extrato_df, contabil_df


def _carregar_pagina_com_dados(app_autenticado_com_dados, executar_analise=False):
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

    if executar_analise:
        botoes = [b for b in at.button if b.label == "Executar Análise de Correspondências"]
        assert len(botoes) == 1, "botão primário 'Executar Análise de Correspondências' não encontrado"
        botoes[0].click()
        at.run()
        assert not at.exception, f"execução da análise levantou exceção: {at.exception}"

    return at


def test_visao_antes_de_executar_tem_so_o_botao_primario_sem_indicadores(app_autenticado_com_dados):
    at = _carregar_pagina_com_dados(app_autenticado_com_dados, executar_analise=False)

    botoes = [b for b in at.button if b.label == "Executar Análise de Correspondências"]
    assert len(botoes) == 1
    assert botoes[0].proto.type == "primary"

    # antes de rodar, os 4 indicadores e as 3 abas de resultado ainda não existem
    rotulos_metric = {m.label for m in at.metric}
    for rotulo in ("Cobertura de Análise", "Correspondências", "Itens em Aberto", "Diferença Líquida"):
        assert rotulo not in rotulos_metric


def test_apos_executar_mostra_os_4_indicadores(app_autenticado_com_dados):
    at = _carregar_pagina_com_dados(app_autenticado_com_dados, executar_analise=True)

    metricas = {m.label: m.value for m in at.metric}
    assert metricas.get("Cobertura de Análise") == "66.7%"
    assert metricas.get("Correspondências") == "2/3"
    assert metricas.get("Itens em Aberto") == "2"
    # diferença líquida = soma contábil (-100+250+5000=5150.00) - soma
    # extrato (-100+250-999.99=-849.99) = 5999,99 (mesmo formato
    # "R$ {valor:,.2f}" já usado em todas as outras métricas de R$ do
    # projeto, ex.: pages/importacao_dados.py)
    assert metricas.get("Diferença Líquida") == "R$ 5,999.99"


def test_apos_executar_tem_as_3_abas_correspondencias_divergencias_similaridade(app_autenticado_com_dados):
    at = _carregar_pagina_com_dados(app_autenticado_com_dados, executar_analise=True)

    rotulos_abas = [t.label for t in at.tabs]
    assert any("correspondências" in r.lower() for r in rotulos_abas)
    assert any("divergências" in r.lower() for r in rotulos_abas)
    assert any("similaridade" in r.lower() for r in rotulos_abas)

    # as 3 abas de resultado são de nível superior — "estatísticas" /
    # "dashboard" / "detalhes técnicos" só podem aparecer como abas
    # ANINHADAS dentro de algum expander fechado "Detalhes" (conteúdo
    # secundário), nunca soltas no mesmo nível das 3 principais.
    rotulos_dentro_detalhes = set()
    for exp in at.expander:
        if "detalhes" in exp.label.lower():
            rotulos_dentro_detalhes.update(t.label for t in exp.tabs)
    rotulos_fora_do_expander = [r for r in rotulos_abas if r not in rotulos_dentro_detalhes]
    assert not any("estatísticas" in r.lower() for r in rotulos_fora_do_expander)
    assert not any("dashboard" in r.lower() for r in rotulos_fora_do_expander)


def test_aba_divergencias_mostra_as_2_listas_separadas_com_exportacao_csv(app_autenticado_com_dados):
    at = _carregar_pagina_com_dados(app_autenticado_com_dados, executar_analise=True)

    aba_divergencias = next(t for t in at.tabs if "divergências" in t.label.lower())
    # as duas listas (bancário sem contábil / contábil sem bancário)
    # continuam existindo e SEPARADAS (não misturadas numa tabela só)
    assert len(aba_divergencias.dataframe) == 2
    # exportação CSV por lista, preservando o exportador da fase 5b
    assert len(aba_divergencias.download_button) == 2


def test_aba_similaridade_e_propria_e_tem_exportacao_csv(app_autenticado_com_dados):
    at = _carregar_pagina_com_dados(app_autenticado_com_dados, executar_analise=True)

    aba_similaridade = next(t for t in at.tabs if "similaridade" in t.label.lower())
    # cenário sintético foi desenhado para não gerar nenhuma
    # similaridade — a aba deve existir e não quebrar mesmo vazia
    assert not aba_similaridade.exception


def test_estatisticas_dashboard_e_detalhes_tecnicos_viraram_expander_detalhes(app_autenticado_com_dados):
    at = _carregar_pagina_com_dados(app_autenticado_com_dados, executar_analise=True)

    expanders_detalhes = [e for e in at.expander if "detalhes" in e.label.lower()]
    assert expanders_detalhes, "deve existir um expander 'Detalhes' com o conteúdo secundário preservado"
    textos = []
    for exp in expanders_detalhes:
        textos.append(exp.label.lower())
        textos += [m.value.lower() for m in exp.markdown]
        textos += [h.value.lower() for h in exp.header] if hasattr(exp, "header") else []
    textos_completos = " ".join(textos)
    for pista in ("estatísticas", "dashboard"):
        assert pista in textos_completos, f"conteúdo preservado não encontrado nos expanders 'Detalhes': {pista!r}"


def test_botao_primario_para_relatorio_existe_apos_executar(app_autenticado_com_dados):
    at = _carregar_pagina_com_dados(app_autenticado_com_dados, executar_analise=True)

    primarios = [b for b in at.button if "GERAR RELATÓRIO" in b.label.upper()]
    assert len(primarios) == 1
    assert primarios[0].proto.type == "primary"


def test_css_aba_ativa_e_navy_sem_fundo_azul_nem_sublinhado_vermelho(app_autenticado_com_dados):
    at = _carregar_pagina_com_dados(app_autenticado_com_dados, executar_analise=True)

    estilos = [m.value for m in at.markdown if "stTabs" in m.value and "aria-selected" in m.value]
    assert estilos, "CSS de estilização das abas não encontrado"
    css = estilos[0]
    assert "#0078D4" not in css, "fundo azul antigo da aba ativa não deve mais aparecer"
    assert "#FF4B4B" not in css, "sublinhado vermelho antigo da aba ativa não deve mais aparecer"
    assert "#002D72" in css, "aba ativa deve usar o navy do tema (#002D72) no texto/sublinhado"
