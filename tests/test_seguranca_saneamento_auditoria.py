"""
Testes sintéticos da correção de SEC-R-05 (revisão de segurança dedicada,
docs/revisao-seguranca-fase-5.md, issue XCRE-52): campos controlados
pelo usuário (nome de usuário no login, nome de arquivo de upload,
mensagens de erro) chegavam ao SQLite E ao logger padrão sem nenhum
saneamento — um username "alice\\nINJECT" ou um nome de arquivo com
caminho interno completo (`arquivo.name` de um upload do Streamlit)
eram persistidos e logados exatamente como recebidos, permitindo
forjar uma linha extra num log que alguém leia como texto simples ou
vazar estrutura de diretório interna.

Este arquivo reproduz o achado ANTES da correção (os testes abaixo
devem falhar contra `modules/audit_logger.py` anterior a esta issue) e
passa a valer como regressão depois. Segue o mesmo padrão de
tests/test_audit_logger.py (AuditLogger(db_path=tmp_path/...), sem
necessidade da fixture de autenticação do Streamlit, que esse módulo
não usa). Dados 100% sintéticos.
"""
import json
import logging
import sqlite3

import pytest

from modules.audit_logger import AuditLogger, AuditAction, AuditSeverity


def _linha_unica(db_path: str, coluna: str) -> str:
    conn = sqlite3.connect(db_path)
    valor = conn.execute(f"SELECT {coluna} FROM audit_log").fetchone()[0]
    conn.close()
    return valor


# --- Quebra de linha / caracteres de controle em campos livres ---

def test_descricao_com_quebra_de_linha_nao_forja_linha_extra_no_sqlite(tmp_path):
    db_path = str(tmp_path / "audit.db")
    logger = AuditLogger(db_path=db_path)
    payload = "Login bem-sucedido\nFAKE 2024-01-01 00:00:00 CRITICAL: senha vazada em texto puro"

    logger.log_action(action=AuditAction.USER_ACTION, user="qa_user", description=payload)

    descricao_persistida = _linha_unica(db_path, "description")
    assert "\n" not in descricao_persistida
    assert "\r" not in descricao_persistida
    # o conteúdo (sem a quebra de linha) continua presente — saneamento
    # não é o mesmo que apagar a informação.
    assert "FAKE" in descricao_persistida
    assert "CRITICAL" in descricao_persistida

    conn = sqlite3.connect(db_path)
    total_linhas = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
    conn.close()
    assert total_linhas == 1


def test_descricao_com_quebra_de_linha_nao_forja_linha_extra_no_logger(tmp_path, caplog):
    db_path = str(tmp_path / "audit.db")
    logger = AuditLogger(db_path=db_path)
    payload = "Login bem-sucedido\nFAKE 2024-01-01 00:00:00 CRITICAL: acesso root concedido"

    with caplog.at_level(logging.INFO, logger="modules.audit_logger"):
        logger.log_action(action=AuditAction.USER_ACTION, user="qa_user", description=payload)

    mensagens = [registro.getMessage() for registro in caplog.records]
    assert len(mensagens) == 1, "a quebra de linha não pode virar um segundo registro de log"
    assert "\n" not in mensagens[0]
    assert "\r" not in mensagens[0]


def test_usuario_com_caracteres_de_controle_e_saneado_no_sqlite(tmp_path):
    db_path = str(tmp_path / "audit.db")
    logger = AuditLogger(db_path=db_path)
    usuario_malicioso = "alice\r\nINJECT: fake admin login"

    logger.log_action(action=AuditAction.USER_ACTION, user=usuario_malicioso, description="Login")

    usuario_persistido = _linha_unica(db_path, "user")
    assert "\r" not in usuario_persistido
    assert "\n" not in usuario_persistido
    assert "alice" in usuario_persistido
    assert "INJECT" in usuario_persistido


@pytest.mark.parametrize("caractere_controle", ["\x00", "\x07", "\x1b", "\x0b", "\x0c"])
def test_outros_caracteres_de_controle_sao_saneados(tmp_path, caractere_controle):
    db_path = str(tmp_path / "audit.db")
    logger = AuditLogger(db_path=db_path)
    payload = f"antes{caractere_controle}depois"

    logger.log_action(action=AuditAction.USER_ACTION, user="qa", description=payload)

    descricao_persistida = _linha_unica(db_path, "description")
    assert caractere_controle not in descricao_persistida
    assert "antes" in descricao_persistida
    assert "depois" in descricao_persistida


# --- Nome de arquivo: basename saneado, sem vazar caminho/token interno ---

def test_nome_de_arquivo_com_traversal_e_reduzido_ao_basename(tmp_path):
    db_path = str(tmp_path / "audit.db")
    logger = AuditLogger(db_path=db_path)

    logger.log_file_upload(
        file_name="../../etc/relatorio_token=ABC123XYZ.csv",
        file_type="CSV",
        file_size=100,
        user="qa_user",
    )

    conn = sqlite3.connect(db_path)
    description, details_json = conn.execute(
        "SELECT description, details FROM audit_log"
    ).fetchone()
    conn.close()
    details = json.loads(details_json)

    # Basename apenas: sem ".." nem diretório algum.
    assert details["file_name"] == "relatorio_token=ABC123XYZ.csv"
    assert ".." not in details["file_name"]
    assert "/" not in details["file_name"]
    # O nome do arquivo em si (escolhido por quem fez upload) é
    # preservado — só o CAMINHO é removido, não o conteúdo do nome.
    assert "token=ABC123XYZ" in details["file_name"]
    # A descrição (que embute o nome do arquivo na mensagem) também não
    # pode vazar o caminho original.
    assert "../../etc" not in description
    assert ".." not in description


def test_nome_de_arquivo_com_diretorio_interno_nao_vaza_caminho_nem_token_de_sessao(tmp_path):
    """Cenário mais próximo do risco real: um caminho interno completo
    (ex.: um diretório temporário de sessão com um identificador) sendo
    passado por engano como `file_name` — o basename remove TANTO o
    caminho quanto qualquer identificador que estivesse só no diretório,
    não no nome do arquivo em si."""
    db_path = str(tmp_path / "audit.db")
    logger = AuditLogger(db_path=db_path)

    logger.log_file_upload(
        file_name="/var/tmp/uploads/sessao_token=SEGREDOxyz789/relatorio.csv",
        file_type="CSV",
        file_size=100,
        user="qa_user",
    )

    conn = sqlite3.connect(db_path)
    description, details_json = conn.execute(
        "SELECT description, details FROM audit_log"
    ).fetchone()
    conn.close()
    details = json.loads(details_json)

    assert details["file_name"] == "relatorio.csv"
    assert "SEGREDOxyz789" not in details["file_name"]
    assert "SEGREDOxyz789" not in description
    assert "/var/tmp/uploads" not in description
    assert "/var/tmp/uploads" not in details["file_name"]


def test_nome_de_arquivo_normal_sem_caminho_permanece_intacto(tmp_path):
    """Regressão: um nome de upload normal (sem caminho, o caso comum
    real — o Streamlit já entrega só `arquivo.name`, sem diretório) não
    pode ser alterado pelo saneamento."""
    db_path = str(tmp_path / "audit.db")
    logger = AuditLogger(db_path=db_path)

    logger.log_file_upload(
        file_name="B_1234490.ofx", file_type="OFX", file_size=2048, user="qa_user",
    )

    conn = sqlite3.connect(db_path)
    details_json = conn.execute("SELECT details FROM audit_log").fetchone()[0]
    conn.close()
    details = json.loads(details_json)

    assert details["file_name"] == "B_1234490.ofx"


# --- Truncamento de campos excedentes ---

def test_campo_muito_longo_e_truncado_sem_excecao(tmp_path):
    db_path = str(tmp_path / "audit.db")
    logger = AuditLogger(db_path=db_path)
    texto_gigante = "X" * 5000

    log_id = logger.log_action(action=AuditAction.USER_ACTION, user="qa", description=texto_gigante)

    assert log_id  # não levantou exceção
    descricao_persistida = _linha_unica(db_path, "description")
    assert len(descricao_persistida) < len(texto_gigante)
    assert len(descricao_persistida) < 600  # bem abaixo do texto original, com folga para o marcador


def test_campo_dentro_do_limite_nao_e_truncado(tmp_path):
    db_path = str(tmp_path / "audit.db")
    logger = AuditLogger(db_path=db_path)
    texto_normal = "Descrição de tamanho normal, dentro do limite de auditoria."

    logger.log_action(action=AuditAction.USER_ACTION, user="qa", description=texto_normal)

    descricao_persistida = _linha_unica(db_path, "description")
    assert descricao_persistida == texto_normal


# --- transaction_ids: lista de strings também é saneada ---

def test_transaction_ids_com_quebra_de_linha_sao_saneados(tmp_path):
    db_path = str(tmp_path / "audit.db")
    logger = AuditLogger(db_path=db_path)

    logger.log_action(
        action=AuditAction.MATCH_APPROVAL,
        user="qa",
        description="Aprovação de match",
        transaction_ids=["id_1\nINJECT", "id_2"],
    )

    conn = sqlite3.connect(db_path)
    transaction_ids_json = conn.execute("SELECT transaction_ids FROM audit_log").fetchone()[0]
    conn.close()
    ids = json.loads(transaction_ids_json)

    assert ids == ["id_1 INJECT", "id_2"]


# --- Campos não-string, aninhados e ausentes não quebram o saneamento ---

def test_saneamento_preserva_valores_nao_string_em_details(tmp_path):
    db_path = str(tmp_path / "audit.db")
    logger = AuditLogger(db_path=db_path)

    logger.log_action(
        action=AuditAction.DATA_PROCESSING,
        user="qa",
        description="Processamento",
        details={
            "input_records": 100,
            "output_records": 95,
            "success_rate": 95.0,
            "aprovado": True,
            "erro": None,
            "aninhado": {"mensagem": "erro\ncom quebra", "codigo": 42},
            "lista_aninhada": ["ok\ncom quebra", 1, None, True],
        },
    )

    conn = sqlite3.connect(db_path)
    details_json = conn.execute("SELECT details FROM audit_log").fetchone()[0]
    conn.close()
    details = json.loads(details_json)

    assert details["input_records"] == 100
    assert details["output_records"] == 95
    assert details["success_rate"] == 95.0
    assert details["aprovado"] is True
    assert details["erro"] is None
    assert "\n" not in details["aninhado"]["mensagem"]
    assert details["aninhado"]["codigo"] == 42
    assert "\n" not in details["lista_aninhada"][0]
    assert details["lista_aninhada"][1] == 1
    assert details["lista_aninhada"][2] is None
    assert details["lista_aninhada"][3] is True


def test_saneamento_funciona_sem_details_nem_transaction_ids(tmp_path):
    """Regressão: os defaults (`details=None`, `transaction_ids=None`)
    continuam funcionando exatamente como antes do saneamento."""
    db_path = str(tmp_path / "audit.db")
    logger = AuditLogger(db_path=db_path)

    log_id = logger.log_action(action=AuditAction.USER_ACTION, user="qa", description="ok")

    assert log_id
    conn = sqlite3.connect(db_path)
    details_json, transaction_ids_json = conn.execute(
        "SELECT details, transaction_ids FROM audit_log"
    ).fetchone()
    conn.close()
    assert json.loads(details_json) == {}
    assert json.loads(transaction_ids_json) == []


# --- Mensagem de erro (dentro de details) também é saneada ---

def test_mensagem_de_erro_com_controles_e_saneada_em_log_file_upload(tmp_path):
    db_path = str(tmp_path / "audit.db")
    logger = AuditLogger(db_path=db_path)

    logger.log_file_upload(
        file_name="extrato.csv",
        file_type="CSV",
        file_size=10,
        user="qa",
        success=False,
        error_message="Falha ao processar\x00\x07\x1bpayload malicioso\ncom quebra",
    )

    conn = sqlite3.connect(db_path)
    details_json = conn.execute("SELECT details FROM audit_log").fetchone()[0]
    conn.close()
    details = json.loads(details_json)

    for proibido in ("\x00", "\x07", "\x1b", "\n"):
        assert proibido not in details["error_message"]
    assert "Falha ao processar" in details["error_message"]
    assert "payload malicioso" in details["error_message"]
