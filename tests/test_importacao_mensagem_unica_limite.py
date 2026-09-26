"""
Testes de reprodução/regressão para o achado do E2E publicado da fase
5c (issue XCRE-53, fase 5d, item 2): ao subir um OFX com 25.000
transações (acima do limite de 20.000), a página mostrava a mensagem
certa ("...tem 25000 transações, acima do limite de 20000 transações
por importação.") MAS TAMBÉM duas mensagens redundantes por cima:
"Erro ao processar OFX: motivo de carga de arquivo desconhecido:
'limite_transacoes_excedido'" e "Não foi possível extrair dados do
arquivo". O mesmo padrão acontece para os limites estruturais de CSV
(linhas, colunas, tamanho de campo) — mesma causa raiz.

Causa raiz (confirmada por leitura de código, não pela descrição
original da issue): `_categorizar_motivo_carga_arquivo`
(pages/importacao_dados.py) JÁ categoriza corretamente os 4 motivos de
limite ('limite_transacoes_excedido', 'limite_linhas_excedido',
'limite_colunas_excedido', 'limite_campo_excedido'), mas esses 4
códigos nunca foram cadastrados no `MOTIVOS_CARGA_ARQUIVO` (allowlist
de `modules/structured_logger.py`). `log_carga_arquivo` levanta
`ValueError("motivo de carga de arquivo desconhecido: ...")` para
qualquer motivo fora da allowlist — essa exceção é capturada pelo
`except Exception` de `processar_arquivo`, que then emite uma SEGUNDA
mensagem de erro (a mensagem da própria exceção) e devolve `None` em
vez de parar no primeiro `return` logo após a mensagem certa. A
chamada do fluxo de upload único ("SISTEMA ORIGINAL", mais abaixo no
mesmo módulo) então vê o retorno `None`/vazio e mostra uma TERCEIRA
mensagem genérica ("Não foi possível extrair dados do arquivo") por
cima — sem saber que uma mensagem específica já tinha sido exibida.

Segue o mesmo padrão estrutural de fixture/helpers de
tests/test_seguranca_limites_estruturais.py (mesmo guard de
autenticação em nível de módulo desta página). Os testes abaixo
reproduzem o problema em duas camadas:

1. Nível de `processar_arquivo` (mesmo padrão de
   tests/test_validacao_entrada_ofx_csv.py): confirma que a allowlist
   de motivos não derruba a função com uma exceção e uma segunda
   mensagem.
2. Nível de página completa via `streamlit.testing.v1.AppTest` (já
   usado em tests/test_smoke_import_app.py para SEC-R-07): dirige o
   `st.file_uploader` real do fluxo "SISTEMA ORIGINAL" e conta quantos
   elementos de erro aparecem na página renderizada — cobre a terceira
   mensagem, que só existe no código de nível de script da página, fora
   de `processar_arquivo`. Isto NÃO é E2E de navegador (não abre um
   servidor Streamlit nem um browser real); é o framework de teste
   oficial do próprio Streamlit, rodando em processo.

Dados 100% sintéticos.
"""
import importlib
import io
import os
import sqlite3
from unittest.mock import patch

import pytest
import streamlit as st

APP_PY = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")
IMPORTACAO_DADOS_PY = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pages", "importacao_dados.py"
)


@pytest.fixture
def pagina_importacao(tmp_path, monkeypatch):
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

    st.session_state["token"] = token
    st.session_state["user"] = user_info

    import pages.importacao_dados as pg
    importlib.reload(pg)  # roda enforce_auth() de novo com a sessão válida acima
    pg._parsear_csv_cacheado.clear()
    pg._parsear_ofx_cacheado.clear()

    return pg


class ArquivoFalso(io.BytesIO):
    def __init__(self, content: bytes, name: str):
        super().__init__(content)
        self.name = name
        self.size = len(content)


def _ofx_com_n_transacoes(n: int) -> bytes:
    transacoes = "".join(
        f"<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20240101<TRNAMT>1.00<FITID>{i}<MEMO>Transacao sintetica {i}</STMTTRN>\n"
        for i in range(n)
    )
    return (
        "OFXHEADER:100\n"
        "DATA:OFXSGML\n"
        "<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS>\n"
        "<BANKTRANLIST>\n"
        f"{transacoes}"
        "</BANKTRANLIST>\n"
        "</STMTRS></STMTRNRS></BANKMSGSRSV1></OFX>\n"
    ).encode("utf-8")


def _csv_com_n_linhas(n: int) -> bytes:
    linhas = "\n".join(f"2024-01-01,1.00,Transacao sintetica {i}" for i in range(n))
    return ("data,valor,descricao\n" + linhas + "\n").encode("utf-8")


def _csv_com_n_colunas(n: int) -> bytes:
    cabecalho = "data,valor," + ",".join(f"extra_{i}" for i in range(n - 2))
    linha = "2024-01-01,1.00," + ",".join(str(i) for i in range(n - 2))
    return (cabecalho + "\n" + linha + "\n").encode("utf-8")


def _csv_com_campo_de_n_caracteres(n: int) -> bytes:
    campo = "X" * n
    return (
        "data,valor,descricao\n"
        f"2024-01-01,1.00,{campo}\n"
    ).encode("utf-8")


def _mensagens(mock_error) -> list:
    return [chamada[0][0] for chamada in mock_error.call_args_list]


# --- Nível de processar_arquivo: exatamente UMA mensagem por rejeição de limite ---

def test_ofx_25_mil_transacoes_mostra_uma_unica_mensagem_de_erro(pagina_importacao):
    """Reproduz literalmente o cenário do achado E2E da 5c: 25.000
    transações OFX, limite padrão de 20.000."""
    pg = pagina_importacao
    assert pg.LIMITE_OFX_MAX_TRANSACOES == 20_000
    conteudo = _ofx_com_n_transacoes(25_000)
    arquivo = ArquivoFalso(conteudo, "extrato_25mil.ofx")

    with patch.object(pg.st, "error") as mock_error:
        resultado = pg.processar_arquivo(arquivo, "ofx")

    mensagens = _mensagens(mock_error)
    assert mock_error.call_count == 1, f"esperava 1 mensagem, veio {len(mensagens)}: {mensagens}"
    assert "25000 transações" in mensagens[0]
    assert "20000 transações" in mensagens[0]
    assert "motivo de carga de arquivo desconhecido" not in mensagens[0].lower()
    assert "não foi possível extrair" not in mensagens[0].lower()
    assert not (hasattr(resultado, "empty") and not resultado.empty)


def test_csv_acima_do_limite_de_linhas_mostra_uma_unica_mensagem_de_erro(pagina_importacao):
    pg = pagina_importacao
    pg.LIMITE_CSV_MAX_LINHAS = 100
    conteudo = _csv_com_n_linhas(150)
    arquivo = ArquivoFalso(conteudo, "extrato_muitas_linhas.csv")

    with patch.object(pg.st, "error") as mock_error:
        resultado = pg.processar_arquivo(arquivo, "csv")

    mensagens = _mensagens(mock_error)
    assert mock_error.call_count == 1, f"esperava 1 mensagem, veio {len(mensagens)}: {mensagens}"
    assert "linhas" in mensagens[0].lower()
    assert "motivo de carga de arquivo desconhecido" not in mensagens[0].lower()
    assert "não foi possível extrair" not in mensagens[0].lower()
    assert not (hasattr(resultado, "empty") and not resultado.empty)


def test_csv_acima_do_limite_de_colunas_mostra_uma_unica_mensagem_de_erro(pagina_importacao):
    pg = pagina_importacao
    pg.LIMITE_CSV_MAX_COLUNAS = 50
    conteudo = _csv_com_n_colunas(80)
    arquivo = ArquivoFalso(conteudo, "extrato_muitas_colunas.csv")

    with patch.object(pg.st, "error") as mock_error:
        resultado = pg.processar_arquivo(arquivo, "csv")

    mensagens = _mensagens(mock_error)
    assert mock_error.call_count == 1, f"esperava 1 mensagem, veio {len(mensagens)}: {mensagens}"
    assert "colunas" in mensagens[0].lower()
    assert "motivo de carga de arquivo desconhecido" not in mensagens[0].lower()
    assert "não foi possível extrair" not in mensagens[0].lower()
    assert not (hasattr(resultado, "empty") and not resultado.empty)


def test_csv_campo_acima_do_limite_de_caracteres_mostra_uma_unica_mensagem_de_erro(pagina_importacao):
    pg = pagina_importacao
    pg.LIMITE_CSV_MAX_CARACTERES_CAMPO = 1000
    conteudo = _csv_com_campo_de_n_caracteres(1500)
    arquivo = ArquivoFalso(conteudo, "extrato_campo_gigante.csv")

    with patch.object(pg.st, "error") as mock_error:
        resultado = pg.processar_arquivo(arquivo, "csv")

    mensagens = _mensagens(mock_error)
    assert mock_error.call_count == 1, f"esperava 1 mensagem, veio {len(mensagens)}: {mensagens}"
    assert "caracteres" in mensagens[0].lower()
    assert "motivo de carga de arquivo desconhecido" not in mensagens[0].lower()
    assert "não foi possível extrair" not in mensagens[0].lower()
    assert not (hasattr(resultado, "empty") and not resultado.empty)


# --- Nível de página completa (AppTest): a 3ª mensagem redundante só existe aqui ---

@pytest.fixture
def app_autenticado(tmp_path, monkeypatch):
    """Mesmo setup de autenticação da fixture `pagina_importacao`, mas
    devolvendo (token, user_info) para alimentar `AppTest.session_state`
    — a página completa (script inteiro, incluindo o fluxo "SISTEMA
    ORIGINAL" de upload único) roda isolada por instância de AppTest,
    então precisa da própria sessão pré-carregada, não da global `st`."""
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


def test_pagina_completa_ofx_25_mil_transacoes_mostra_uma_unica_mensagem(app_autenticado):
    """Dirige o `st.file_uploader` real do fluxo "SISTEMA ORIGINAL" (a
    tela padrão, sem o checkbox de validação por nome de arquivo) via
    `AppTest`, contando quantos elementos `st.error` aparecem na página
    renderizada depois do upload — a única forma de cobrir a 3ª
    mensagem redundante ("Não foi possível extrair dados do arquivo"),
    que vive no código de nível de script da página, fora de
    `processar_arquivo`."""
    from streamlit.testing.v1 import AppTest

    token, user_info = app_autenticado
    at = AppTest.from_file(APP_PY, default_timeout=30)
    at.session_state["token"] = token
    at.session_state["user"] = user_info
    at.switch_page("pages/importacao_dados.py")
    at.run()
    assert not at.exception, f"página levantou exceção só ao carregar: {at.exception}"

    conteudo = _ofx_com_n_transacoes(25_000)
    uploader = at.get_by_key("extrato_upload")
    uploader.set_value(("extrato_25mil.ofx", conteudo, "application/octet-stream"))
    at.run()

    assert not at.exception, f"upload rejeitado levantou exceção não tratada: {at.exception}"
    mensagens_erro = [e.value for e in at.error]
    assert len(mensagens_erro) == 1, f"esperava 1 st.error, vieram {len(mensagens_erro)}: {mensagens_erro}"
    assert "25000 transações" in mensagens_erro[0]
    assert "20000 transações" in mensagens_erro[0]
    assert "motivo de carga de arquivo desconhecido" not in mensagens_erro[0].lower()
    assert "não foi possível extrair" not in mensagens_erro[0].lower()
