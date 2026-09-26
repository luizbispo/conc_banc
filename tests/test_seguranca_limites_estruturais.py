"""
Testes sintéticos da correção de SEC-R-03 (revisão de segurança dedicada,
docs/revisao-seguranca-fase-5.md, issue XCRE-52): não havia limite
ESTRUTURAL (contagem de transações/linhas/colunas/tamanho de campo) na
importação de OFX/CSV — só o teto de bytes do upload
(MAX_FILE_SIZE_BYTES, 10 MiB). Um OFX de 50.000 transações cabe
folgado nesse teto de bytes e levava ~119s no parser (`ofxparse`),
crescimento pior que linear — uma negação de serviço barata de montar.

Este arquivo reproduz o achado ANTES da correção (os testes abaixo
devem falhar contra `pages/importacao_dados.py` anterior a esta issue)
e passa a valer como regressão depois. Segue o mesmo padrão de fixture
de tests/test_validacao_entrada_ofx_csv.py e tests/test_importacao_limites.py
para lidar com o guard de autenticação em nível de módulo desta página.

Dados 100% sintéticos.
"""
import importlib
import io
import os
import sqlite3
import time
from unittest.mock import patch

import pytest
import streamlit as st

EXEMPLOS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Exemplos")


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

    # Isola o cache entre testes (mesmo racional de test_cache_parsing.py).
    pg._parsear_csv_cacheado.clear()
    pg._parsear_ofx_cacheado.clear()

    return pg


class ArquivoFalso(io.BytesIO):
    def __init__(self, content: bytes, name: str):
        super().__init__(content)
        self.name = name
        self.size = len(content)


def _arquivo_de_exemplo(nome: str) -> ArquivoFalso:
    caminho = os.path.join(EXEMPLOS_DIR, nome)
    with open(caminho, "rb") as f:
        conteudo = f.read()
    return ArquivoFalso(conteudo, nome)


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


# --- OFX: limite de transações (contagem literal de <STMTTRN> nos bytes) ---

def test_ofx_com_50_mil_transacoes_e_rejeitado_em_menos_de_2_segundos(pagina_importacao):
    pg = pagina_importacao
    conteudo = _ofx_com_n_transacoes(50_000)
    arquivo = ArquivoFalso(conteudo, "extrato_gigante.ofx")

    inicio = time.monotonic()
    valido, motivo = pg.validar_entrada_ofx(arquivo)
    duracao = time.monotonic() - inicio

    assert valido is False
    assert "limite" in motivo.lower()
    assert duracao < 2.0, f"rejeição de 50k transações OFX levou {duracao:.2f}s, deveria ser < 2s"
    assert "Traceback" not in motivo
    assert "/" not in motivo
    assert "\\" not in motivo


def test_ofx_no_limite_exato_de_transacoes_e_aceito(pagina_importacao):
    pg = pagina_importacao
    conteudo = _ofx_com_n_transacoes(pg.LIMITE_OFX_MAX_TRANSACOES)
    arquivo = ArquivoFalso(conteudo, "extrato_no_limite.ofx")

    valido, motivo = pg.validar_entrada_ofx(arquivo)

    assert valido is True
    assert motivo == ""


def test_ofx_um_a_mais_que_o_limite_de_transacoes_e_rejeitado(pagina_importacao):
    pg = pagina_importacao
    conteudo = _ofx_com_n_transacoes(pg.LIMITE_OFX_MAX_TRANSACOES + 1)
    arquivo = ArquivoFalso(conteudo, "extrato_acima_do_limite.ofx")

    valido, motivo = pg.validar_entrada_ofx(arquivo)

    assert valido is False
    assert str(pg.LIMITE_OFX_MAX_TRANSACOES) in motivo


# --- CSV: limite de linhas ---

def test_csv_acima_do_limite_de_linhas_e_rejeitado(pagina_importacao):
    pg = pagina_importacao
    pg.LIMITE_CSV_MAX_LINHAS = 100
    conteudo = _csv_com_n_linhas(150)
    arquivo = ArquivoFalso(conteudo, "extrato_muitas_linhas.csv")

    valido, motivo, encoding, df = pg.validar_entrada_csv(arquivo)

    assert valido is False
    assert "linha" in motivo.lower()
    assert df is None
    assert "Traceback" not in motivo


def test_csv_no_limite_exato_de_linhas_e_aceito(pagina_importacao):
    pg = pagina_importacao
    pg.LIMITE_CSV_MAX_LINHAS = 100
    # 99 linhas de dados + 1 cabeçalho = 100 linhas totais (no limite).
    conteudo = _csv_com_n_linhas(99)
    arquivo = ArquivoFalso(conteudo, "extrato_no_limite.csv")

    valido, motivo, encoding, df = pg.validar_entrada_csv(arquivo)

    assert valido is True
    assert len(df) == 99


# --- CSV: limite de colunas ---

def test_csv_acima_do_limite_de_colunas_e_rejeitado(pagina_importacao):
    pg = pagina_importacao
    pg.LIMITE_CSV_MAX_COLUNAS = 50
    conteudo = _csv_com_n_colunas(80)
    arquivo = ArquivoFalso(conteudo, "extrato_muitas_colunas.csv")

    valido, motivo, encoding, df = pg.validar_entrada_csv(arquivo)

    assert valido is False
    assert "coluna" in motivo.lower()
    assert df is None


def test_csv_no_limite_exato_de_colunas_e_aceito(pagina_importacao):
    pg = pagina_importacao
    pg.LIMITE_CSV_MAX_COLUNAS = 50
    conteudo = _csv_com_n_colunas(50)
    arquivo = ArquivoFalso(conteudo, "extrato_no_limite_colunas.csv")

    valido, motivo, encoding, df = pg.validar_entrada_csv(arquivo)

    assert valido is True
    assert len(df.columns) == 50


# --- CSV: limite de caracteres por campo ---

def test_csv_com_campo_acima_do_limite_de_caracteres_e_rejeitado(pagina_importacao):
    pg = pagina_importacao
    pg.LIMITE_CSV_MAX_CARACTERES_CAMPO = 1000
    conteudo = _csv_com_campo_de_n_caracteres(1500)
    arquivo = ArquivoFalso(conteudo, "extrato_campo_gigante.csv")

    valido, motivo, encoding, df = pg.validar_entrada_csv(arquivo)

    assert valido is False
    assert "caracteres" in motivo.lower()
    assert df is None


def test_csv_com_campo_maior_que_o_teto_padrao_do_modulo_csv_e_rejeitado_sem_stacktrace(pagina_importacao):
    """Regressão específica: o módulo `csv` da stdlib tem um teto próprio
    (field_size_limit, 131072 por padrão) que, sem ajuste, faria
    `csv.reader` levantar `_csv.Error` — um erro cru, não a mensagem fixa
    — para qualquer campo maior que esse valor. Usa o limite padrão de
    produção (10.000) para confirmar que o campo de 500.000 caracteres
    é rejeitado com a MESMA mensagem fixa, sem stack trace vazando."""
    pg = pagina_importacao
    conteudo = _csv_com_campo_de_n_caracteres(500_000)
    arquivo = ArquivoFalso(conteudo, "extrato_campo_enorme.csv")

    valido, motivo, encoding, df = pg.validar_entrada_csv(arquivo)

    assert valido is False
    assert "caracteres" in motivo.lower()
    assert df is None
    assert "Traceback" not in motivo
    assert "_csv.Error" not in motivo
    assert "field larger than field limit" not in motivo


def test_csv_com_campo_no_limite_exato_de_caracteres_e_aceito(pagina_importacao):
    pg = pagina_importacao
    pg.LIMITE_CSV_MAX_CARACTERES_CAMPO = 1000
    conteudo = _csv_com_campo_de_n_caracteres(1000)
    arquivo = ArquivoFalso(conteudo, "extrato_campo_no_limite.csv")

    valido, motivo, encoding, df = pg.validar_entrada_csv(arquivo)

    assert valido is True
    assert len(df.loc[0, "descricao"]) == 1000


# --- Arquivos de Exemplos/* continuam aceitos com os limites padrão ---

@pytest.mark.parametrize("nome", [
    "B_1234490.ofx",
    "C_1234490.ofx",
    "extrato_bancario_janeiro.ofx",
    "extrato_simples.ofx",
])
def test_ofx_de_exemplo_continua_aceito_com_limite_padrao(pagina_importacao, nome):
    pg = pagina_importacao
    arquivo = _arquivo_de_exemplo(nome)

    valido, motivo = pg.validar_entrada_ofx(arquivo)

    assert valido is True, f"{nome} deveria continuar aceito: {motivo}"


@pytest.mark.parametrize("nome", [
    "contabil_janeiro.csv",
    "extrato_bancario_janeiro.csv",
    "extrato_simples.csv",
    "lancamentos_contabeis.csv",
    "lancamentos_erp.csv",
])
def test_csv_de_exemplo_continua_aceito_com_limite_padrao(pagina_importacao, nome):
    pg = pagina_importacao
    arquivo = _arquivo_de_exemplo(nome)

    valido, motivo, encoding, df = pg.validar_entrada_csv(arquivo)

    assert valido is True, f"{nome} deveria continuar aceito: {motivo}"
