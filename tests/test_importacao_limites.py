"""
Testes de regressão para os limites de página/linha de importação
(issue XCRE-42, Parte A, item 5c): antes MAX_FILE_SIZE_BYTES limitava
bytes no upload, mas um PDF ou CNAB pequeno em disco com um número
extremo de páginas/linhas podia fazer processar_pdf/processar_cnab
iterar sem nenhum teto — consumo de CPU não limitado pelo tamanho em
bytes já validado.

Segue o mesmo padrão de tests/test_logout_revocation.py para lidar com
o guard de autenticação em nível de módulo desta página (enforce_auth()
roda no import; por isso autenticamos e recarregamos o módulo antes de
cada teste).

Dados 100% sintéticos.
"""
import importlib
import io
import sqlite3
from unittest.mock import patch

import fpdf
import pytest
import pypdf
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


def _pdf_com_n_paginas(n: int) -> bytes:
    writer = pypdf.PdfWriter()
    for _ in range(n):
        writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _pdf_com_texto(linhas: list) -> bytes:
    """Gera um PDF de verdade (via fpdf) com texto extraível, para
    exercitar pdf_reader.extract_text() com dados reais de transação
    (data + valor), e não só páginas em branco."""
    pdf = fpdf.FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    for linha in linhas:
        pdf.cell(0, 10, txt=linha, ln=1)
    return pdf.output(dest="S").encode("latin-1")


# --- PDF ---

def test_pdf_acima_do_limite_de_paginas_e_rejeitado(pagina_importacao):
    pg = pagina_importacao
    pg.MAX_PDF_PAGINAS = 3
    arquivo = ArquivoFalso(_pdf_com_n_paginas(5), "extrato.pdf")

    with patch.object(pg.st, "error") as mock_error:
        resultado = pg.processar_pdf(arquivo)

    assert resultado is None
    mock_error.assert_called_once()
    assert "limite" in mock_error.call_args[0][0].lower()


def test_pdf_dentro_do_limite_de_paginas_nao_e_rejeitado_por_limite(pagina_importacao):
    pg = pagina_importacao
    pg.MAX_PDF_PAGINAS = 3
    arquivo = ArquivoFalso(_pdf_com_n_paginas(2), "extrato.pdf")

    with patch.object(pg.st, "error") as mock_error:
        pg.processar_pdf(arquivo)

    # Páginas em branco não têm texto/transações, então o retorno pode
    # ser None por "nenhuma transação encontrada" — o que importa aqui é
    # que NENHUMA chamada a st.error mencione o limite de páginas.
    for chamada in mock_error.call_args_list:
        assert "limite" not in chamada[0][0].lower()


def test_pdf_valido_com_texto_extrai_transacoes(pagina_importacao):
    """Migração PyPDF2 -> pypdf (item 1, fase 5d): confirma que
    pdf_reader.pages / extract_text() de um PDF real (gerado com fpdf,
    não só páginas em branco) continua produzindo as mesmas transações
    de antes com a nova lib."""
    pg = pagina_importacao
    pg.MAX_PDF_PAGINAS = 10
    conteudo = _pdf_com_texto([
        "15/06/2025 R$ 1.234,56 Pagamento fornecedor sintetico",
        "20/06/2025 R$ 500,00 Recebimento cliente sintetico",
    ])
    arquivo = ArquivoFalso(conteudo, "extrato.pdf")

    with patch.object(pg.st, "error") as mock_error:
        resultado = pg.processar_pdf(arquivo)

    mock_error.assert_not_called()
    assert resultado is not None
    assert len(resultado) == 2
    assert set(resultado["tipo"]) == {"PDF"}


def test_pdf_malformado_nao_gera_excecao_nao_tratada(pagina_importacao):
    """Migração PyPDF2 -> pypdf (item 1, fase 5d): pypdf usa uma
    hierarquia de exceções diferente da PyPDF2 (ex.: PdfStreamError em
    vez de PdfReadError) para conteúdo corrompido. processar_pdf captura
    Exception de forma ampla; este teste comprova que esse contrato
    continua valendo com a lib nova: nenhuma exceção escapa, o app
    mostra UM erro amigável e retorna None em vez de quebrar a página."""
    pg = pagina_importacao
    pg.MAX_PDF_PAGINAS = 10
    arquivo = ArquivoFalso(b"isto nao e um PDF valido - bytes arbitrarios sinteticos", "corrompido.pdf")

    with patch.object(pg.st, "error") as mock_error:
        resultado = pg.processar_pdf(arquivo)

    assert resultado is None
    mock_error.assert_called_once()
    assert "erro ao processar pdf" in mock_error.call_args[0][0].lower()


# --- CNAB ---

def test_cnab_acima_do_limite_de_linhas_e_rejeitado(pagina_importacao):
    pg = pagina_importacao
    pg.MAX_CNAB_LINHAS = 10
    conteudo = "\n".join(f"linha_sintetica_{i}" for i in range(50)).encode("latin-1")
    arquivo = ArquivoFalso(conteudo, "retorno.ret")

    with patch.object(pg.st, "error") as mock_error:
        resultado = pg.processar_cnab(arquivo)

    assert resultado is None
    mock_error.assert_called_once()
    assert "limite" in mock_error.call_args[0][0].lower()


def test_cnab_dentro_do_limite_de_linhas_nao_e_rejeitado_por_limite(pagina_importacao):
    pg = pagina_importacao
    pg.MAX_CNAB_LINHAS = 100
    conteudo = "\n".join(f"linha_sintetica_{i}" for i in range(5)).encode("latin-1")
    arquivo = ArquivoFalso(conteudo, "retorno.ret")

    with patch.object(pg.st, "error") as mock_error, patch.object(pg.st, "warning"), patch.object(pg.st, "info"):
        pg.processar_cnab(arquivo)

    for chamada in mock_error.call_args_list:
        assert "limite" not in chamada[0][0].lower()


def test_contar_linhas_arquivo_devolve_cursor_ao_inicio(pagina_importacao):
    pg = pagina_importacao
    conteudo = b"linha1\nlinha2\nlinha3"
    arquivo = ArquivoFalso(conteudo, "retorno.ret")

    total = pg._contar_linhas_arquivo(arquivo)

    assert total == 3
    assert arquivo.read() == conteudo  # cursor voltou ao inicio
