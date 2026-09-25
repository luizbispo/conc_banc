"""
Testes de regressão para a validação de entrada de OFX/CSV
(issue XCRE-49, Fase 5, item 1).

Antes destas funções, um upload vazio, binário, com encoding não
suportado ou sem as colunas mínimas (data/valor) só era detectado
quando pandas/ofxparse já tinha lançado uma exceção, cuja mensagem
crua (em inglês, sem tradução) chegava direto ao usuário via
`st.error(f"...: {e}")`. Agora `validar_entrada_csv`/`validar_entrada_ofx`
validam ANTES do parsing e devolvem sempre mensagens fixas em
português, sem stack trace e sem caminho de arquivo.

Segue o mesmo padrão de fixture de tests/test_importacao_limites.py
para lidar com o guard de autenticação em nível de módulo desta página
(enforce_auth() roda no import; por isso autenticamos e recarregamos o
módulo antes de cada teste).

Dados 100% sintéticos.
"""
import importlib
import io
import sqlite3
from unittest.mock import patch

import pandas as pd
import pytest
import streamlit as st


@pytest.fixture
def pagina_importacao(tmp_path, monkeypatch):
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

    import app
    success, user_info, token = app.login_user("usuario_teste", "SenhaNova1")
    assert success is True

    st.session_state["token"] = token
    st.session_state["user"] = user_info

    import pages.importacao_dados as pg
    importlib.reload(pg)  # roda enforce_auth() de novo com a sessão válida acima
    return pg


class ArquivoFalso(io.BytesIO):
    def __init__(self, content: bytes, name: str):
        super().__init__(content)
        self.name = name
        self.size = len(content)


def _csv_valido_utf8() -> bytes:
    return (
        "data,valor,descricao\n"
        "2024-01-01,100.00,PIX recebido\n"
        "2024-01-02,-50.00,Pagamento boleto\n"
    ).encode("utf-8")


def _ofx_valido() -> bytes:
    return (
        "OFXHEADER:100\n"
        "DATA:OFXSGML\n"
        "<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS>\n"
        "<BANKTRANLIST>\n"
        "<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20240101<TRNAMT>100.00"
        "<FITID>1<MEMO>PIX recebido</STMTTRN>\n"
        "</BANKTRANLIST>\n"
        "</STMTRS></STMTRNRS></BANKMSGSRSV1></OFX>\n"
    ).encode("utf-8")


# --- CSV: extensão ---

def test_csv_com_extensao_errada_e_rejeitado(pagina_importacao):
    pg = pagina_importacao
    arquivo = ArquivoFalso(_csv_valido_utf8(), "extrato.txt")

    valido, motivo, encoding, df = pg.validar_entrada_csv(arquivo)

    assert valido is False
    assert "extensão" in motivo.lower()
    assert df is None


# --- CSV: vazio ---

def test_csv_vazio_e_rejeitado(pagina_importacao):
    pg = pagina_importacao
    arquivo = ArquivoFalso(b"", "extrato.csv")

    valido, motivo, encoding, df = pg.validar_entrada_csv(arquivo)

    assert valido is False
    assert "vazio" in motivo.lower()
    assert df is None


# --- CSV: binário ---

def test_csv_binario_e_rejeitado(pagina_importacao):
    pg = pagina_importacao
    conteudo_binario = bytes(range(256)) * 4  # inclui NUL e bytes de controle
    arquivo = ArquivoFalso(conteudo_binario, "extrato.csv")

    valido, motivo, encoding, df = pg.validar_entrada_csv(arquivo)

    assert valido is False
    assert "binári" in motivo.lower()
    assert df is None


# --- CSV: colunas obrigatórias ---

def test_csv_sem_colunas_obrigatorias_e_rejeitado(pagina_importacao):
    pg = pagina_importacao
    conteudo = "descricao\nPIX recebido\nPagamento boleto\n".encode("utf-8")
    arquivo = ArquivoFalso(conteudo, "extrato.csv")

    valido, motivo, encoding, df = pg.validar_entrada_csv(arquivo)

    assert valido is False
    assert "data" in motivo.lower()
    assert "valor" in motivo.lower()
    assert df is None


def test_csv_sem_apenas_coluna_valor_e_rejeitado(pagina_importacao):
    pg = pagina_importacao
    conteudo = "data,descricao\n2024-01-01,PIX recebido\n".encode("utf-8")
    arquivo = ArquivoFalso(conteudo, "extrato.csv")

    valido, motivo, encoding, df = pg.validar_entrada_csv(arquivo)

    assert valido is False
    assert "valor" in motivo.lower()
    assert df is None


# --- CSV: encoding ---

def test_csv_valido_utf8_e_aceito(pagina_importacao):
    pg = pagina_importacao
    arquivo = ArquivoFalso(_csv_valido_utf8(), "extrato.csv")

    valido, motivo, encoding, df = pg.validar_entrada_csv(arquivo)

    assert valido is True
    assert motivo == ""
    assert encoding == "utf-8"
    assert len(df) == 2
    assert list(df.columns) == ["data", "valor", "descricao"]


def test_csv_valido_latin1_com_acentos_e_aceito(pagina_importacao):
    pg = pagina_importacao
    conteudo = (
        "data,valor,descricao\n"
        "2024-01-03,75.50,Depósito em conta\n"
    ).encode("latin-1")
    arquivo = ArquivoFalso(conteudo, "extrato.csv")

    valido, motivo, encoding, df = pg.validar_entrada_csv(arquivo)

    assert valido is True
    assert encoding in ("latin-1", "cp1252", "iso-8859-1")
    assert len(df) == 1


# --- OFX: extensão ---

def test_ofx_com_extensao_errada_e_rejeitado(pagina_importacao):
    pg = pagina_importacao
    arquivo = ArquivoFalso(_ofx_valido(), "extrato.txt")

    valido, motivo = pg.validar_entrada_ofx(arquivo)

    assert valido is False
    assert "extensão" in motivo.lower()


# --- OFX: vazio ---

def test_ofx_vazio_e_rejeitado(pagina_importacao):
    pg = pagina_importacao
    arquivo = ArquivoFalso(b"", "extrato.ofx")

    valido, motivo = pg.validar_entrada_ofx(arquivo)

    assert valido is False
    assert "vazio" in motivo.lower()


# --- OFX: binário ---

def test_ofx_binario_e_rejeitado(pagina_importacao):
    pg = pagina_importacao
    conteudo_binario = bytes(range(256)) * 4
    arquivo = ArquivoFalso(conteudo_binario, "extrato.ofx")

    valido, motivo = pg.validar_entrada_ofx(arquivo)

    assert valido is False
    assert "binári" in motivo.lower()


# --- OFX: sem cabeçalho OFX ---

def test_ofx_sem_cabecalho_e_rejeitado(pagina_importacao):
    pg = pagina_importacao
    conteudo = "isto e apenas um texto qualquer sem nenhuma tag valida\n".encode("utf-8")
    arquivo = ArquivoFalso(conteudo, "extrato.ofx")

    valido, motivo = pg.validar_entrada_ofx(arquivo)

    assert valido is False
    assert "cabeçalho" in motivo.lower()


def test_ofx_valido_e_aceito(pagina_importacao):
    pg = pagina_importacao
    arquivo = ArquivoFalso(_ofx_valido(), "extrato.ofx")

    valido, motivo = pg.validar_entrada_ofx(arquivo)

    assert valido is True
    assert motivo == ""


# --- Mensagens: sem stack trace, sem caminho de arquivo ---

@pytest.mark.parametrize("nome_invalido", ["extrato.txt"])
def test_mensagens_de_csv_nao_expoem_caminho_nem_stacktrace(pagina_importacao, nome_invalido):
    pg = pagina_importacao
    arquivo = ArquivoFalso(_csv_valido_utf8(), nome_invalido)

    _, motivo, _, _ = pg.validar_entrada_csv(arquivo)

    assert "Traceback" not in motivo
    assert "/" not in motivo
    assert "\\" not in motivo
    # o nome do upload (sem caminho) pode aparecer normalmente na mensagem
    assert nome_invalido in motivo


def test_mensagens_binarias_nao_expoem_caminho_nem_stacktrace(pagina_importacao):
    pg = pagina_importacao
    conteudo_binario = bytes(range(256)) * 4
    arquivo = ArquivoFalso(conteudo_binario, "extrato.csv")

    _, motivo, _, _ = pg.validar_entrada_csv(arquivo)

    assert "Traceback" not in motivo
    assert "/" not in motivo
    assert "\\" not in motivo


# --- Integração com processar_arquivo: tamanho máximo (10 MB) ---

def test_tamanho_maximo_e_dez_mebibytes_em_bytes(pagina_importacao):
    """Confirma a semântica exata do limite de 10 MB citado na issue: a
    constante é 10 * 1024 * 1024 bytes (10 MiB = 10.485.760 bytes), não
    10.000.000 bytes (10 MB decimal). A mensagem exibida ao usuário diz
    "10MB", mas o valor comparado é o binário."""
    pg = pagina_importacao
    assert pg.MAX_FILE_SIZE_BYTES == 10 * 1024 * 1024 == 10_485_760


def test_csv_grande_e_rejeitado_por_tamanho_antes_de_validar_conteudo(pagina_importacao):
    pg = pagina_importacao
    conteudo_grande = b"data,valor,descricao\n" + b"2024-01-01,1.00,x\n" * 1
    arquivo = ArquivoFalso(conteudo_grande, "extrato.csv")
    arquivo.size = pg.MAX_FILE_SIZE_BYTES + 1  # simula upload grande sem alocar memória real

    with patch.object(pg.st, "error") as mock_error:
        resultado = pg.processar_arquivo(arquivo, "csv")

    assert resultado is None
    mock_error.assert_called_once()
    mensagem = mock_error.call_args[0][0]
    assert "limite" in mensagem.lower()
    assert "Traceback" not in mensagem
    assert "/" not in mensagem


def test_csv_valido_dentro_do_limite_e_processado_por_processar_arquivo(pagina_importacao):
    pg = pagina_importacao
    arquivo = ArquivoFalso(_csv_valido_utf8(), "extrato.csv")

    with patch.object(pg.st, "error") as mock_error:
        resultado = pg.processar_arquivo(arquivo, "csv")

    mock_error.assert_not_called()
    assert isinstance(resultado, pd.DataFrame)
    assert len(resultado) == 2
