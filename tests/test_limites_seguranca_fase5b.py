"""
Testes de limites/DoS e nomes maliciosos na importação (Fase 5b,
XCRE-50, item 3).

Complementa a suíte já existente da Fase 5
(tests/test_validacao_entrada_ofx_csv.py: tamanho/binário/encoding/
colunas obrigatórias; tests/test_importacao_limites.py: MAX_PDF_PAGINAS/
MAX_CNAB_LINHAS; tests/test_cache_parsing.py: cache por hash de bytes)
com os ângulos pedidos nesta rodada que ainda não tinham teste:

1. CSV com MUITAS linhas e com colunas/linha GIGANTES: não há (nem esta
   rodada cria) um limite separado de linhas/colunas para CSV — o teto
   existente é `MAX_FILE_SIZE_BYTES` (10 MiB, já testado em
   test_validacao_entrada_ofx_csv.py). Os testes abaixo DERIVAM desse
   limite já configurado (ficam abaixo dele) e confirmam que o
   processamento é limitado pelo tamanho em bytes, não trava, e não
   truncava dado nenhum. Isso documenta a ausência de um teto dedicado
   de linhas/colunas como comportamento atual, não como lacuna nova.
2. OFX malformado com entidades DOCTYPE/ENTITY expandidas (padrão
   "billion laughs"): `ofxparse` usa BeautifulSoup com o parser
   `html.parser` da biblioteca padrão (ver modules/data_analyzer.py não
   se aplica aqui — é pages/importacao_dados.py::_parsear_ofx_cacheado),
   que NÃO é um parser XML/DTD-aware e não expande ENTITY de DOCTYPE.
   O teste confirma isso factualmente (tempo limitado, sem amplificação
   de tamanho), em vez de assumir.
3. Nome de arquivo com `../`, `..\\` e caracteres de controle: nenhuma
   função de importação usa o nome do upload para acessar o sistema de
   arquivos (sempre lê os bytes em memória via `arquivo.seek/read`);
   `validar_formato_nome` (âncora regex `^(B|C)_(\\d+)\\.(ext)$`) já
   rejeita qualquer nome fora desse padrão, incluindo os maliciosos.
4. Cache: complementa test_cache_parsing.py provando POR COMPORTAMENTO
   (não só inspecionando a assinatura da função) que o cache é o MESMO
   para o mesmo conteúdo mesmo com nomes de arquivo diferentes —
   inclusive nomes com tentativa de path traversal — ou seja, a chave
   de cache nunca inclui/depende do caminho ou nome do upload.

Dados 100% sintéticos.
"""
import importlib
import io
import sqlite3
import time
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

    # Isola o cache entre testes (mesmo racional de test_cache_parsing.py).
    pg._parsear_csv_cacheado.clear()
    pg._parsear_ofx_cacheado.clear()

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


def _ofx_com_entidades_expandidas() -> bytes:
    """OFX malformado no estilo "billion laughs": um DOCTYPE com ENTITY
    aninhadas, cada uma referenciando a anterior 10 vezes (6 níveis a
    partir de uma base de 3 caracteres -> ~3.000.000 de caracteres SE
    o parser expandisse). Ainda contém o cabeçalho "OFX" textual (para
    passar no pré-check de `validar_entrada_ofx`) e chega deformado ao
    fechamento das tags (malformado de propósito)."""
    entidades = ['<!ENTITY laugh0 "lol">']
    anterior = 'laugh0'
    for nivel in range(1, 7):
        nome = f'laugh{nivel}'
        entidades.append(f'<!ENTITY {nome} "' + ('&' + anterior + ';') * 10 + '">')
        anterior = nome
    doctype = '<!DOCTYPE ofx [\n' + '\n'.join(entidades) + '\n]>'
    return (
        "OFXHEADER:100\n"
        "DATA:OFXSGML\n"
        f"{doctype}\n"
        "<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS>\n"
        "<BANKTRANLIST>\n"
        f"<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20240101<TRNAMT>100.00"
        f"<FITID>1<MEMO>&{anterior};</STMTTRN>\n"
        "</BANKTRANLIST>\n"
        "</STMTRS></STMTRNRS></BANKMSGSRSV1></OFX>\n"
    ).encode("utf-8")


# --- 1. CSV com muitas linhas / colunas ou linha gigante ---

def test_csv_com_muitas_linhas_dentro_do_limite_de_tamanho_e_processado_sem_travar(pagina_importacao):
    """Deriva do limite JÁ CONFIGURADO (MAX_FILE_SIZE_BYTES, 10 MiB):
    gera um CSV com 50.000 linhas que cabe dentro desse teto e confirma
    que é aceito, todas as linhas chegam ao DataFrame e o tempo de
    processamento fica bem abaixo de qualquer timeout de request real
    (não introduz um teto novo de linhas — documenta que hoje o teto
    efetivo para CSV é o de bytes, não o de linhas)."""
    pg = pagina_importacao
    n_linhas = 50_000
    linhas = "\n".join(f"2024-01-01,10.00,Transacao sintetica {i}" for i in range(n_linhas))
    conteudo = ("data,valor,descricao\n" + linhas + "\n").encode("utf-8")
    assert len(conteudo) < pg.MAX_FILE_SIZE_BYTES, "pré-condição: tem que caber no limite já existente"

    arquivo = ArquivoFalso(conteudo, "extrato_grande.csv")

    inicio = time.monotonic()
    valido, motivo, encoding, df = pg.validar_entrada_csv(arquivo)
    duracao = time.monotonic() - inicio

    assert valido is True
    assert len(df) == n_linhas
    assert duracao < 10.0, f"processamento de 50k linhas não deveria travar (levou {duracao:.2f}s)"


def test_csv_com_muitas_colunas_e_processado_sem_erro(pagina_importacao):
    """Não há teto de número de colunas; um CSV com 2.000 colunas extras
    (ainda pequeno em bytes) precisa ser aceito e preservar todas as
    colunas, sem estourar exceção."""
    pg = pagina_importacao
    n_colunas_extra = 2000
    cabecalho = "data,valor," + ",".join(f"extra_{i}" for i in range(n_colunas_extra))
    linha = "2024-01-01,10.00," + ",".join(str(i) for i in range(n_colunas_extra))
    conteudo = (cabecalho + "\n" + linha + "\n").encode("utf-8")
    arquivo = ArquivoFalso(conteudo, "extrato_largo.csv")

    valido, motivo, encoding, df = pg.validar_entrada_csv(arquivo)

    assert valido is True
    assert len(df.columns) == n_colunas_extra + 2


def test_csv_com_celula_gigante_e_processado_sem_truncar(pagina_importacao):
    """Uma única célula de texto muito grande (500 KB, ainda dentro do
    limite de 10 MiB do arquivo inteiro) precisa ser aceita e preservada
    por completo, sem truncar nem lançar exceção."""
    pg = pagina_importacao
    descricao_gigante = "X" * 500_000
    conteudo = (
        "data,valor,descricao\n"
        f"2024-01-01,10.00,{descricao_gigante}\n"
    ).encode("utf-8")
    assert len(conteudo) < pg.MAX_FILE_SIZE_BYTES

    arquivo = ArquivoFalso(conteudo, "extrato_celula_gigante.csv")

    valido, motivo, encoding, df = pg.validar_entrada_csv(arquivo)

    assert valido is True
    assert len(df.loc[0, "descricao"]) == 500_000


# --- 2. OFX malformado com entidades DOCTYPE/ENTITY expandidas ---

def test_ofx_com_entidades_expandidas_nao_amplifica_nem_trava(pagina_importacao):
    pg = pagina_importacao
    conteudo = _ofx_com_entidades_expandidas()
    assert b"OFX" in conteudo[:2048]  # passa no pré-check textual de validar_entrada_ofx

    arquivo = ArquivoFalso(conteudo, "extrato_malformado.ofx")
    valido, motivo = pg.validar_entrada_ofx(arquivo)
    assert valido is True  # pré-check textual não analisa DOCTYPE/ENTITY

    inicio = time.monotonic()
    with patch.object(pg.st, "error") as mock_error:
        resultado = pg.processar_ofx(arquivo)
    duracao = time.monotonic() - inicio

    assert duracao < 5.0, f"parsing não deveria travar/demorar por causa de ENTITY (levou {duracao:.2f}s)"

    # A defesa aqui é ESTRUTURAL: ofxparse usa BeautifulSoup com o
    # parser html.parser (stdlib), que não processa DOCTYPE/ENTITY como
    # um parser XML faria — então a referência à entidade nunca é
    # expandida; ela chega literal (ou é descartada) no MEMO, nunca
    # amplificada para milhões de caracteres.
    if resultado is not None and not resultado.empty and "descricao" in resultado.columns:
        for valor in resultado["descricao"].astype(str):
            assert len(valor) < 1000, "entidade parece ter sido expandida — investigar antes de prosseguir"

    # Se o parsing falhar (arquivo malformado o suficiente para o
    # ofxparse rejeitar), o erro precisa ser tratado, não vazar exceção
    # nem stack trace para o usuário.
    for chamada in mock_error.call_args_list:
        assert "Traceback" not in chamada[0][0]


# --- 3. Nome de arquivo com path traversal / caracteres de controle ---

@pytest.mark.parametrize("nome_malicioso", [
    "../../../etc/passwd.csv",
    "..\\..\\windows\\win.ini.csv",
    "extrato\x00.csv",
    "extrato\ncom\nquebra.csv",
    "B_../../123.csv",
    "C_\x01\x02123.csv",
])
def test_validar_formato_nome_rejeita_path_traversal_e_caracteres_de_controle(pagina_importacao, nome_malicioso):
    """`validar_formato_nome` é âncorado (`^(B|C)_(\\d+)\\.(ext)$`) — um
    nome com `../`, `..\\`, NUL ou quebra de linha nunca casa com o
    padrão, então é sempre rejeitado, sem exceção e sem qualquer
    interpretação como caminho de sistema de arquivos."""
    pg = pagina_importacao

    valido, tipo, conta, extensao = pg.validar_formato_nome(nome_malicioso)

    assert valido is False
    assert tipo is None
    assert conta is None
    assert extensao is None


@pytest.mark.parametrize("nome_malicioso", [
    "../../../etc/passwd.csv",
    "..\\..\\windows\\win.ini.csv",
    "extrato\x00malicioso.csv",
    "extrato\ncom\nquebra.csv",
])
def test_csv_com_nome_malicioso_e_validado_apenas_pelo_conteudo(pagina_importacao, nome_malicioso):
    """`validar_entrada_csv` só usa o nome do upload para checar a
    extensão (string) e compor mensagens — nunca para abrir/juntar um
    caminho no sistema de arquivos. Um nome de upload com tentativa de
    path traversal ou caractere de controle não deve travar nem alterar
    o resultado, que continua dependendo só do CONTEÚDO."""
    pg = pagina_importacao
    arquivo = ArquivoFalso(_csv_valido_utf8(), nome_malicioso)

    valido, motivo, encoding, df = pg.validar_entrada_csv(arquivo)

    assert valido is True
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    assert "Traceback" not in motivo


# --- 4. Cache: a chave nunca depende do nome/caminho do arquivo ---

def test_cache_csv_e_compartilhado_entre_nomes_de_arquivo_diferentes_mesmo_conteudo(pagina_importacao):
    """Complementa test_cache_parsing.py (que confirma, por assinatura,
    que `_parsear_csv_cacheado` só recebe bytes+encoding): aqui provamos
    POR COMPORTAMENTO que dois uploads com o MESMO conteúdo mas nomes
    completamente diferentes — incluindo um nome com tentativa de path
    traversal — reaproveitam o mesmo cache (uma única chamada real a
    `pd.read_csv`). A chave de cache nunca vaza/depende do caminho."""
    pg = pagina_importacao
    conteudo = _csv_valido_utf8()
    chamadas_reais = []
    read_csv_original = pd.read_csv

    def read_csv_contado(*args, **kwargs):
        chamadas_reais.append(1)
        return read_csv_original(*args, **kwargs)

    with patch.object(pg.pd, "read_csv", side_effect=read_csv_contado):
        arquivo1 = ArquivoFalso(conteudo, "extrato_janeiro_conta_1234.csv")
        pg.validar_entrada_csv(arquivo1)

        arquivo2 = ArquivoFalso(conteudo, "../../../etc/nome_completamente_diferente.csv")
        pg.validar_entrada_csv(arquivo2)

    assert len(chamadas_reais) == 1, (
        "o cache deveria ser o MESMO independente do nome do arquivo "
        "(a chave é só o conteúdo + encoding)"
    )


def test_cache_ofx_e_compartilhado_entre_nomes_de_arquivo_diferentes_mesmo_conteudo(pagina_importacao):
    pg = pagina_importacao
    conteudo = (
        "OFXHEADER:100\n"
        "DATA:OFXSGML\n"
        "<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS>\n"
        "<BANKTRANLIST>\n"
        "<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20240101<TRNAMT>100.00"
        "<FITID>1<MEMO>PIX recebido</STMTTRN>\n"
        "</BANKTRANLIST>\n"
        "</STMTRS></STMTRNRS></BANKMSGSRSV1></OFX>\n"
    ).encode("utf-8")

    chamadas_reais = []
    from ofxparse import OfxParser
    parse_original = OfxParser.parse

    def parse_contado(*args, **kwargs):
        chamadas_reais.append(1)
        return parse_original(*args, **kwargs)

    with patch("ofxparse.OfxParser.parse", side_effect=parse_contado):
        pg.processar_ofx(ArquivoFalso(conteudo, "extrato.ofx"))
        pg.processar_ofx(ArquivoFalso(conteudo, "../../../etc/outro_nome.ofx"))

    assert len(chamadas_reais) == 1, (
        "o cache OFX deveria ser o MESMO independente do nome do arquivo"
    )
