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


def _linha_completa_como_texto(db_path: str) -> str:
    """Concatena TODAS as colunas da única linha gravada, para varrer o
    registro inteiro por um segredo vazado — mesma abordagem da PoC
    independente do arquiteto (varredura da linha inteira, não só de um
    campo que já se sabia sanear)."""
    conn = sqlite3.connect(db_path)
    linha = conn.execute("SELECT * FROM audit_log").fetchone()
    conn.close()
    return " | ".join(str(v) for v in linha)


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
    """Atualizado pela rodada corretiva isolada de SEC-R-05 (re-verificação
    independente): a Rodada 4 original preservava o valor de "token=..."
    quando embutido no NOME do arquivo (só removia o caminho), sob o
    argumento de que era o nome escolhido por quem fez upload. A PoC
    independente do arquiteto considerou isso insuficiente — "o basename
    remove o diretório, mas não torna seguro um segredo presente no
    próprio nome do arquivo" — então agora o valor também é redigido."""
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
    assert details["file_name"] == "relatorio_token=[REDACTED].csv"
    assert ".." not in details["file_name"]
    assert "/" not in details["file_name"]
    # O valor do token é redigido; o restante do nome (prefixo +
    # extensão) continua reconhecível.
    assert "ABC123XYZ" not in details["file_name"]
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
    """Usa só chaves de topo REAIS (da allowlist da rodada corretiva de
    R-05: 'input_records'/'output_records'/'success_rate'/'parameters'/
    'errors') — uma chave de topo inventada seria descartada pela
    allowlist por design; o que este teste cobre é que TIPOS não-string
    (int/float/bool/None) e conteúdo aninhado dentro de um campo
    PERMITIDO sobrevivem normalmente ao saneamento."""
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
            "parameters": {"mensagem": "erro\ncom quebra", "codigo": 42, "aprovado": True, "erro": None},
            "errors": ["ok\ncom quebra", 1, None, True],
        },
    )

    conn = sqlite3.connect(db_path)
    details_json = conn.execute("SELECT details FROM audit_log").fetchone()[0]
    conn.close()
    details = json.loads(details_json)

    assert details["input_records"] == 100
    assert details["output_records"] == 95
    assert details["success_rate"] == 95.0
    assert details["parameters"]["aprovado"] is True
    assert details["parameters"]["erro"] is None
    assert "\n" not in details["parameters"]["mensagem"]
    assert details["parameters"]["codigo"] == 42
    assert "\n" not in details["errors"][0]
    assert details["errors"][1] == 1
    assert details["errors"][2] is None
    assert details["errors"][3] is True


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


# =====================================================================
# Rodada corretiva isolada de SEC-R-05 (re-verificação independente do
# arquiteto, issue XCRE-52): a correção anterior (saneamento de
# controle/tamanho/basename) NÃO impedia que senha, hash, token/JWT e
# descrição de transação fossem persistidos/logados — só neutralizava
# quebra de linha e diretório. A PoC independente confirmou vazamento
# desses valores tanto no SQLite quanto no logger.
#
# Correção: (1) ALLOWLIST de chaves de topo em 'details'/'metadata' —
# qualquer chave fora da lista de campos mínimos úteis é DESCARTADA,
# não só saneada (fecha por construção qualquer nome de chave sensível,
# conhecido ou não); (2) redação de CONTEÚDO sensível (JWT, hash
# hexadecimal longo, padrão "rótulo=valor" tipo "token=..."/"senha=...")
# nos campos de texto que sobrevivem, incluindo o nome de arquivo
# (o basename por si só NÃO torna seguro um segredo presente no próprio
# nome, como apontado pela PoC independente).
#
# Os testes abaixo reproduzem a PoC independente ANTES desta correção
# (devem falhar contra o audit_logger.py da rodada anterior) e passam a
# valer como regressão depois. Dados 100% sintéticos.
# =====================================================================

_SEGREDOS_SINTETICOS = {
    "senha": "MinhaSenh@Sintetica123",
    "hash": "5f4dcc3b5aa765d61d8327deb882cf99e5f4dcc3b5aa765d61d8327deb882cf",  # 64 hex, formato SHA-256
    "jwt": "eyJhbGciOiJIUzI1NiJ9.eyJ1c2VyIjoiYWxpY2UifQ.c2lnbmF0dXJlLXNpbnRldGljYQ",
    "token_arquivo": "SEGREDOxyz789",
    "descricao_transacao": "PIX recebido de João da Silva, CPF 123.456.789-00, R$ 500,00",
}


def test_senha_passada_em_details_e_descartada_pela_allowlist(tmp_path):
    db_path = str(tmp_path / "audit.db")
    logger = AuditLogger(db_path=db_path)

    logger.log_action(
        action=AuditAction.USER_ACTION,
        user="qa",
        description="Ação sintética",
        details={"senha": _SEGREDOS_SINTETICOS["senha"], "password": _SEGREDOS_SINTETICOS["senha"]},
    )

    linha_completa = _linha_completa_como_texto(db_path)
    assert _SEGREDOS_SINTETICOS["senha"] not in linha_completa

    conn = sqlite3.connect(db_path)
    details_json = conn.execute("SELECT details FROM audit_log").fetchone()[0]
    conn.close()
    details = json.loads(details_json)
    assert "senha" not in details
    assert "password" not in details


def test_hash_passado_em_details_e_descartado_pela_allowlist(tmp_path):
    db_path = str(tmp_path / "audit.db")
    logger = AuditLogger(db_path=db_path)

    logger.log_action(
        action=AuditAction.USER_ACTION,
        user="qa",
        description="Ação sintética",
        details={"hash": _SEGREDOS_SINTETICOS["hash"]},
    )

    linha_completa = _linha_completa_como_texto(db_path)
    assert _SEGREDOS_SINTETICOS["hash"] not in linha_completa

    conn = sqlite3.connect(db_path)
    details_json = conn.execute("SELECT details FROM audit_log").fetchone()[0]
    conn.close()
    assert "hash" not in json.loads(details_json)


def test_hash_hexadecimal_longo_embutido_em_campo_permitido_e_redigido(tmp_path):
    """Mesmo dentro de um campo PERMITIDO pela allowlist (error_message),
    um valor com formato de hash hexadecimal longo não pode sobreviver
    ao saneamento — a allowlist protege por NOME de chave, a redação de
    conteúdo protege o CONTEÚDO de campos legítimos."""
    db_path = str(tmp_path / "audit.db")
    logger = AuditLogger(db_path=db_path)

    logger.log_file_upload(
        file_name="extrato.csv",
        file_type="CSV",
        file_size=10,
        user="qa",
        success=False,
        error_message=f"Checksum divergente: {_SEGREDOS_SINTETICOS['hash']} esperado",
    )

    linha_completa = _linha_completa_como_texto(db_path)
    assert _SEGREDOS_SINTETICOS["hash"] not in linha_completa
    assert "Checksum divergente" in linha_completa


def test_jwt_passado_em_details_e_descartado_pela_allowlist(tmp_path):
    db_path = str(tmp_path / "audit.db")
    logger = AuditLogger(db_path=db_path)

    logger.log_action(
        action=AuditAction.USER_ACTION,
        user="qa",
        description="Ação sintética",
        details={"jwt": _SEGREDOS_SINTETICOS["jwt"], "token": _SEGREDOS_SINTETICOS["jwt"]},
    )

    linha_completa = _linha_completa_como_texto(db_path)
    assert _SEGREDOS_SINTETICOS["jwt"] not in linha_completa

    conn = sqlite3.connect(db_path)
    details_json = conn.execute("SELECT details FROM audit_log").fetchone()[0]
    conn.close()
    details = json.loads(details_json)
    assert "jwt" not in details
    assert "token" not in details


def test_jwt_embutido_em_campo_permitido_e_redigido(tmp_path):
    db_path = str(tmp_path / "audit.db")
    logger = AuditLogger(db_path=db_path)

    logger.log_file_upload(
        file_name="extrato.csv",
        file_type="CSV",
        file_size=10,
        user="qa",
        success=False,
        error_message=f"Authorization: Bearer {_SEGREDOS_SINTETICOS['jwt']} rejeitado",
    )

    linha_completa = _linha_completa_como_texto(db_path)
    assert _SEGREDOS_SINTETICOS["jwt"] not in linha_completa
    assert "rejeitado" in linha_completa


def test_descricao_de_transacao_passada_em_details_e_descartada_pela_allowlist(tmp_path):
    db_path = str(tmp_path / "audit.db")
    logger = AuditLogger(db_path=db_path)

    logger.log_action(
        action=AuditAction.USER_ACTION,
        user="qa",
        description="Ação sintética",
        details={
            "descricao_transacao": _SEGREDOS_SINTETICOS["descricao_transacao"],
            "transaction_description": _SEGREDOS_SINTETICOS["descricao_transacao"],
        },
    )

    linha_completa = _linha_completa_como_texto(db_path)
    assert _SEGREDOS_SINTETICOS["descricao_transacao"] not in linha_completa
    assert "João da Silva" not in linha_completa
    assert "123.456.789-00" not in linha_completa

    conn = sqlite3.connect(db_path)
    details_json = conn.execute("SELECT details FROM audit_log").fetchone()[0]
    conn.close()
    details = json.loads(details_json)
    assert "descricao_transacao" not in details
    assert "transaction_description" not in details


def test_token_no_proprio_nome_do_arquivo_e_redigido_nao_so_o_diretorio(tmp_path):
    """A PoC independente apontou especificamente isto: reduzir ao
    basename remove o DIRETÓRIO, mas um segredo presente no próprio
    NOME do arquivo (não só no caminho) sobrevivia. Agora o conteúdo do
    basename também passa pela redação de padrão rótulo=valor."""
    db_path = str(tmp_path / "audit.db")
    logger = AuditLogger(db_path=db_path)

    logger.log_file_upload(
        file_name=f"relatorio_token={_SEGREDOS_SINTETICOS['token_arquivo']}.csv",
        file_type="CSV",
        file_size=100,
        user="qa_user",
    )

    linha_completa = _linha_completa_como_texto(db_path)
    assert _SEGREDOS_SINTETICOS["token_arquivo"] not in linha_completa

    conn = sqlite3.connect(db_path)
    details_json = conn.execute("SELECT details FROM audit_log").fetchone()[0]
    conn.close()
    details = json.loads(details_json)
    # O restante do nome (prefixo + extensão) continua reconhecível —
    # só o valor do token é redigido, não o arquivo inteiro.
    assert details["file_name"].startswith("relatorio_token=")
    assert details["file_name"].endswith(".csv")
    assert "[REDACTED]" in details["file_name"]


def test_usuario_com_newline_e_descricao_de_transacao_juntos_no_logger(tmp_path, caplog):
    """Reproduz a combinação usada na PoC independente: usuário com
    quebra de linha JUNTO com um segredo/descrição sensível — os dois
    problemas precisam estar corrigidos ao mesmo tempo, na mesma
    chamada, tanto no SQLite quanto no `logger` padrão."""
    db_path = str(tmp_path / "audit.db")
    logger = AuditLogger(db_path=db_path)
    usuario_malicioso = "alice\nINJECT"

    with caplog.at_level(logging.INFO, logger="modules.audit_logger"):
        logger.log_action(
            action=AuditAction.USER_ACTION,
            user=usuario_malicioso,
            description="Login processado",
            details={
                "senha": _SEGREDOS_SINTETICOS["senha"],
                "descricao_transacao": _SEGREDOS_SINTETICOS["descricao_transacao"],
            },
        )

    mensagens_log = " | ".join(registro.getMessage() for registro in caplog.records)
    linha_completa = _linha_completa_como_texto(db_path)

    for segredo in (_SEGREDOS_SINTETICOS["senha"], _SEGREDOS_SINTETICOS["descricao_transacao"]):
        assert segredo not in linha_completa
        assert segredo not in mensagens_log

    assert "\n" not in _linha_unica(db_path, "user")
    assert "\n" not in mensagens_log


# --- Regressão: campos mínimos úteis continuam funcionando ---

def test_allowlist_preserva_campos_minimos_uteis_de_log_report_generation(tmp_path):
    """A allowlist não pode derrubar os campos que os call sites reais
    já usam — só descarta chaves DESCONHECIDAS."""
    db_path = str(tmp_path / "audit.db")
    logger = AuditLogger(db_path=db_path)

    logger.log_report_generation(
        formato="completo",
        user="qa_user",
        lote="1234490 | 15/06/2025 a 14/07/2025",
        success=True,
        included_matches=14,
        included_exceptions=8,
        report_parameters={"incluir_estatisticas": True},
    )

    conn = sqlite3.connect(db_path)
    details_json = conn.execute(
        "SELECT details FROM audit_log WHERE action = 'REPORT_GENERATION'"
    ).fetchone()[0]
    conn.close()
    details = json.loads(details_json)

    assert details["formato"] == "completo"
    assert details["lote"] == "1234490 | 15/06/2025 a 14/07/2025"
    assert details["success"] is True
    assert details["included_matches"] == 14
    assert details["included_exceptions"] == 8
    assert details["report_parameters"] == {"incluir_estatisticas": True}


def test_allowlist_preserva_campos_de_log_matching_layer_e_match_decision(tmp_path):
    db_path = str(tmp_path / "audit.db")
    logger = AuditLogger(db_path=db_path)

    logger.log_matching_layer(
        layer="exato",
        matches_found=15,
        confidence_stats={"avg": 95, "min": 80, "max": 100},
        processing_time=2.5,
        parameters={"tolerancia_dias": 2},
    )
    logger.log_match_decision(
        match_id="match_123",
        decision="approved",
        user="qa",
        reason="Correspondência exata por TXID PIX",
        confidence=100,
    )

    conn = sqlite3.connect(db_path)
    linhas = conn.execute(
        "SELECT action, details FROM audit_log ORDER BY rowid"
    ).fetchall()
    conn.close()

    detalhes_matching = json.loads(linhas[0][1])
    assert detalhes_matching["layer"] == "exato"
    assert detalhes_matching["matches_found"] == 15
    assert detalhes_matching["parameters"] == {"tolerancia_dias": 2}

    detalhes_decisao = json.loads(linhas[1][1])
    assert detalhes_decisao["match_id"] == "match_123"
    assert detalhes_decisao["decision"] == "approved"
    assert detalhes_decisao["reason"] == "Correspondência exata por TXID PIX"


def test_nome_de_arquivo_normal_continua_intacto_apos_correcao_isolada(tmp_path):
    """Regressão da correção da Rodada 4: um nome de upload normal (sem
    caminho, sem rótulo de segredo) não pode ser alterado."""
    db_path = str(tmp_path / "audit.db")
    logger = AuditLogger(db_path=db_path)

    logger.log_file_upload(
        file_name="B_1234490.ofx", file_type="OFX", file_size=2048, user="qa_user",
    )

    conn = sqlite3.connect(db_path)
    details_json = conn.execute("SELECT details FROM audit_log").fetchone()[0]
    conn.close()
    assert json.loads(details_json)["file_name"] == "B_1234490.ofx"
