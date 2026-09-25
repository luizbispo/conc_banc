"""
Testes de regressão para o cache de parsing de OFX/CSV
(issue XCRE-49, Fase 5, item 4).

Antes, cada rerun do Streamlit (qualquer interação na página — mudar um
filtro, clicar em outro botão etc.) reprocessava o upload inteiro do
zero: `pd.read_csv`/`OfxParser.parse` rodavam de novo mesmo quando o
conteúdo do arquivo não tinha mudado. `_parsear_csv_cacheado` e
`_parsear_ofx_cacheado` (pages/importacao_dados.py) isolam o núcleo do
parsing (só bytes + parâmetros, sem Streamlit/sessão/credenciais) e
aplicam `st.cache_data`, cuja chave é um hash determinístico dos
argumentos — mesmo conteúdo (e mesmo parâmetro) reaproveita o resultado
já parseado; conteúdo OU parâmetro diferente reprocessa.

Segue o mesmo padrão de fixture de tests/test_importacao_limites.py
para lidar com o guard de autenticação em nível de módulo desta página
(enforce_auth() roda no import; por isso autenticamos e recarregamos o
módulo antes de cada teste) — e limpa explicitamente o cache logo
depois do reload, para que o resultado de um teste nunca influencie o
próximo (cache do Streamlit é indexado pelo código-fonte da função,
não pela identidade do objeto recarregado).

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

    # Isola o cache entre testes: st.cache_data indexa pelo código-fonte
    # da função, não pela identidade do objeto recarregado, então sem
    # isto um teste anterior com o mesmo conteúdo poderia "vazar" um
    # cache hit para este teste.
    pg._parsear_csv_cacheado.clear()
    pg._parsear_ofx_cacheado.clear()

    return pg


class ArquivoFalso(io.BytesIO):
    def __init__(self, content: bytes, name: str):
        super().__init__(content)
        self.name = name
        self.size = len(content)


def _csv_bytes(sufixo: str) -> bytes:
    return (
        "data,valor,descricao\n"
        f"2024-01-01,100.00,PIX recebido {sufixo}\n"
    ).encode("utf-8")


def _ofx_bytes(fitid: str) -> bytes:
    return (
        "OFXHEADER:100\n"
        "DATA:OFXSGML\n"
        "<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS>\n"
        "<BANKTRANLIST>\n"
        f"<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20240101<TRNAMT>100.00"
        f"<FITID>{fitid}<MEMO>PIX recebido</STMTTRN>\n"
        "</BANKTRANLIST>\n"
        "</STMTRS></STMTRNRS></BANKMSGSRSV1></OFX>\n"
    ).encode("utf-8")


# --- Isolamento: só bytes/parâmetros, nada de sessão/credenciais ---

def test_nucleo_de_parsing_csv_so_recebe_bytes_e_encoding(pagina_importacao):
    import inspect
    pg = pagina_importacao
    parametros = list(inspect.signature(pg._parsear_csv_cacheado.__wrapped__).parameters)
    assert parametros == ['conteudo', 'encoding']


def test_nucleo_de_parsing_ofx_so_recebe_bytes(pagina_importacao):
    import inspect
    pg = pagina_importacao
    parametros = list(inspect.signature(pg._parsear_ofx_cacheado.__wrapped__).parameters)
    assert parametros == ['conteudo']


# --- CSV: bytes idênticos não são reprocessados ---

def test_csv_bytes_identicos_nao_reprocessam(pagina_importacao):
    pg = pagina_importacao
    conteudo = _csv_bytes("A")
    chamadas_reais = []
    read_csv_original = pd.read_csv

    def read_csv_contado(*args, **kwargs):
        chamadas_reais.append(1)
        return read_csv_original(*args, **kwargs)

    with patch.object(pg.pd, "read_csv", side_effect=read_csv_contado):
        arquivo1 = ArquivoFalso(conteudo, "extrato.csv")
        valido1, motivo1, encoding1, df1 = pg.validar_entrada_csv(arquivo1)

        arquivo2 = ArquivoFalso(conteudo, "extrato.csv")  # mesmo conteúdo, outro objeto de upload
        valido2, motivo2, encoding2, df2 = pg.validar_entrada_csv(arquivo2)

    assert valido1 is True and valido2 is True
    assert len(chamadas_reais) == 1, "pd.read_csv deveria ter rodado uma única vez para bytes idênticos"
    pd.testing.assert_frame_equal(df1, df2)


# --- CSV: conteúdo diferente invalida o cache ---

def test_csv_conteudo_diferente_reprocessa(pagina_importacao):
    pg = pagina_importacao
    chamadas_reais = []
    read_csv_original = pd.read_csv

    def read_csv_contado(*args, **kwargs):
        chamadas_reais.append(1)
        return read_csv_original(*args, **kwargs)

    with patch.object(pg.pd, "read_csv", side_effect=read_csv_contado):
        arquivo1 = ArquivoFalso(_csv_bytes("A"), "extrato.csv")
        pg.validar_entrada_csv(arquivo1)

        arquivo2 = ArquivoFalso(_csv_bytes("B"), "extrato.csv")  # 1 byte diferente
        pg.validar_entrada_csv(arquivo2)

    assert len(chamadas_reais) == 2, "conteúdo diferente deveria reprocessar, não reaproveitar o cache"


# --- CSV: mudança de parâmetro (encoding) não reaproveita resultado incompatível ---

def test_csv_mesmo_conteudo_encoding_diferente_nao_reaproveita_cache(pagina_importacao):
    pg = pagina_importacao
    # bytes UTF-8 de "PIX é" — decodificados como latin-1 dão um resultado
    # (mojibake) diferente do decodificado como utf-8: mesmo argumento de
    # bytes, parâmetro `encoding` diferente, tem que dar cache MISS e
    # resultado de conteúdo diferente.
    conteudo = "data,valor,descricao\n2024-01-01,10.00,PIX é\n".encode("utf-8")

    chamadas_reais = []
    read_csv_original = pd.read_csv

    def read_csv_contado(*args, **kwargs):
        chamadas_reais.append(1)
        return read_csv_original(*args, **kwargs)

    with patch.object(pg.pd, "read_csv", side_effect=read_csv_contado):
        df_utf8 = pg._parsear_csv_cacheado(conteudo, "utf-8")
        df_latin1 = pg._parsear_csv_cacheado(conteudo, "latin-1")

    assert len(chamadas_reais) == 2, "mesmo conteúdo com encoding diferente deveria reprocessar"
    assert df_utf8.loc[0, "descricao"] == "PIX é"
    assert df_latin1.loc[0, "descricao"] != "PIX é"  # mojibake esperado


# --- CSV: cache não guarda estado mutável ---

def test_csv_cache_nao_e_contaminado_por_mutacao_do_resultado_anterior(pagina_importacao):
    pg = pagina_importacao
    conteudo = _csv_bytes("A")
    encoding = "utf-8"

    df1 = pg._parsear_csv_cacheado(conteudo, encoding)
    df1["coluna_injetada_por_fora"] = "não deveria aparecer de novo"

    df2 = pg._parsear_csv_cacheado(conteudo, encoding)

    assert "coluna_injetada_por_fora" not in df2.columns


# --- OFX: bytes idênticos não são reprocessados ---

def test_ofx_bytes_identicos_nao_reprocessam(pagina_importacao):
    pg = pagina_importacao
    conteudo = _ofx_bytes("FIT001")
    chamadas_reais = []

    from ofxparse import OfxParser
    parse_original = OfxParser.parse

    def parse_contado(*args, **kwargs):
        chamadas_reais.append(1)
        return parse_original(*args, **kwargs)

    with patch("ofxparse.OfxParser.parse", side_effect=parse_contado):
        arquivo1 = ArquivoFalso(conteudo, "extrato.ofx")
        df1 = pg.processar_ofx(arquivo1)

        arquivo2 = ArquivoFalso(conteudo, "extrato.ofx")
        df2 = pg.processar_ofx(arquivo2)

    assert len(chamadas_reais) == 1, "OfxParser.parse deveria ter rodado uma única vez para bytes idênticos"
    assert df1 is not None and df2 is not None
    pd.testing.assert_frame_equal(df1, df2)


# --- OFX: conteúdo diferente invalida o cache ---

def test_ofx_conteudo_diferente_reprocessa(pagina_importacao):
    pg = pagina_importacao
    chamadas_reais = []

    from ofxparse import OfxParser
    parse_original = OfxParser.parse

    def parse_contado(*args, **kwargs):
        chamadas_reais.append(1)
        return parse_original(*args, **kwargs)

    with patch("ofxparse.OfxParser.parse", side_effect=parse_contado):
        pg.processar_ofx(ArquivoFalso(_ofx_bytes("FIT001"), "extrato.ofx"))
        pg.processar_ofx(ArquivoFalso(_ofx_bytes("FIT002"), "extrato.ofx"))

    assert len(chamadas_reais) == 2, "conteúdo OFX diferente deveria reprocessar, não reaproveitar o cache"


# --- OFX: cache não guarda estado mutável nem dependente de sessão ---

def test_ofx_cache_nao_e_contaminado_por_coluna_de_sessao(pagina_importacao):
    """`sistema_validacao` (checkbox da sidebar) adiciona colunas
    'conta_bancaria'/'origem_arquivo'/'tipo_arquivo' em processar_ofx,
    DEPOIS do núcleo cacheado — essas colunas não podem aparecer no
    resultado cacheado em si (senão o cache ficaria acoplado à sessão/
    ao nome do arquivo, e não só ao conteúdo)."""
    pg = pagina_importacao
    conteudo = _ofx_bytes("FIT001")

    df_cacheado = pg._parsear_ofx_cacheado(conteudo)

    assert "conta_bancaria" not in df_cacheado.columns
    assert "origem_arquivo" not in df_cacheado.columns
    assert "tipo_arquivo" not in df_cacheado.columns
