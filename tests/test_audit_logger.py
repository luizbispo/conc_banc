"""
Testes de regressão para modules/audit_logger.py.

Cobrem: persistência em SQLite (a trilha de auditoria não pode sumir a
cada reinício do processo), clear_audit_log não apagar mais o histórico
persistido (append-only), a correção do bug de cópia rasa em
export_audit_log que apagava 'details'/'metadata' do log original quando
se exportava a versão resumida, e a rotação por tamanho (issue XCRE-42,
Parte A, item 5d): antes audit_log.db crescia indefinidamente, sem
nenhuma política de retenção.
"""
import os
import sqlite3

from modules.audit_logger import AuditLogger, AuditAction, AuditSeverity


def test_log_action_persists_to_sqlite(tmp_path):
    db_path = str(tmp_path / "audit.db")
    logger = AuditLogger(db_path=db_path)

    logger.log_action(
        action=AuditAction.FILE_UPLOAD,
        user="qa_user",
        description="Upload sintético de teste",
        details={"file_name": "extrato_sintetico.csv"},
    )

    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT user, description FROM audit_log").fetchall()
    conn.close()

    assert len(rows) == 1
    assert rows[0][0] == "qa_user"
    assert rows[0][1] == "Upload sintético de teste"


def test_persisted_trail_survives_new_instance_simulating_restart(tmp_path):
    """Simula um reinício do processo: uma NOVA instância de AuditLogger,
    apontando para o mesmo arquivo, deve enxergar o histórico gravado pela
    instância anterior."""
    db_path = str(tmp_path / "audit.db")

    logger1 = AuditLogger(db_path=db_path)
    logger1.log_action(action=AuditAction.USER_ACTION, user="ana", description="Login bem-sucedido")

    logger2 = AuditLogger(db_path=db_path)  # nova instância = "novo processo"
    trail = logger2.get_audit_trail(persisted=True)

    assert len(trail) == 1
    assert trail.iloc[0]["user"] == "ana"


def test_clear_audit_log_does_not_delete_persisted_history(tmp_path):
    db_path = str(tmp_path / "audit.db")
    logger = AuditLogger(db_path=db_path)
    logger.log_action(action=AuditAction.USER_ACTION, user="bruno", description="Ação sintética")

    logger.clear_audit_log()

    assert logger.audit_log == []  # cache em memória limpo
    trail = logger.get_audit_trail(persisted=True)
    assert len(trail) == 1  # histórico persistido preservado


def test_export_audit_log_without_details_does_not_mutate_original_log(tmp_path):
    db_path = str(tmp_path / "audit.db")
    logger = AuditLogger(db_path=db_path)
    logger.log_action(
        action=AuditAction.FILE_UPLOAD,
        user="carla",
        description="Upload sintético",
        details={"file_name": "B_1234490.ofx"},
    )

    logger.export_audit_log(include_details=False, persisted=False)

    # Antes deste fix, export_audit_log fazia self.audit_log.copy() (cópia
    # rasa) e depois log.pop('details', ...) — como os dicionários internos
    # continuavam sendo os MESMOS objetos, isso apagava 'details' também do
    # log em memória original.
    assert logger.audit_log[0]["details"] == {"file_name": "B_1234490.ofx"}


def test_get_audit_trail_filters_by_severity(tmp_path):
    db_path = str(tmp_path / "audit.db")
    logger = AuditLogger(db_path=db_path)
    logger.log_action(action=AuditAction.USER_ACTION, user="a", description="ok", severity=AuditSeverity.INFO)
    logger.log_action(action=AuditAction.USER_ACTION, user="b", description="falha", severity=AuditSeverity.WARNING)

    trail = logger.get_audit_trail(filters={"severity": "WARNING"}, persisted=True)

    assert len(trail) == 1
    assert trail.iloc[0]["user"] == "b"


# --- Rotação por tamanho (issue XCRE-42, Parte A, item 5d) ---

def test_nao_rotaciona_abaixo_do_limite(tmp_path):
    db_path = str(tmp_path / "audit.db")
    logger = AuditLogger(db_path=db_path)
    logger.max_size_bytes = 10 * 1024 * 1024  # 10MB — bem acima do que este teste grava

    for i in range(5):
        logger.log_action(action=AuditAction.USER_ACTION, user=f"user{i}", description="evento")

    # Nenhum arquivo rotacionado deve existir; tudo continua no arquivo ativo.
    arquivos = os.listdir(tmp_path)
    assert arquivos == ["audit.db"]
    conn = sqlite3.connect(db_path)
    assert conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0] == 5
    conn.close()


def test_rotaciona_ao_ultrapassar_limite_e_preserva_historico_antigo(tmp_path):
    db_path = str(tmp_path / "audit.db")
    logger = AuditLogger(db_path=db_path)  # max_size_bytes padrão (50MB): sem rotação ainda

    logger.log_action(action=AuditAction.USER_ACTION, user="ana", description="evento antigo")

    # Só agora reduzimos o limite para forçar a rotação na PRÓXIMA
    # gravação — o arquivo atual (contendo o evento da Ana) já excede 1
    # byte, então ele será arquivado antes do evento do Bruno ser gravado.
    logger.max_size_bytes = 1
    logger.log_action(action=AuditAction.USER_ACTION, user="bruno", description="evento novo")

    arquivos = sorted(os.listdir(tmp_path))
    arquivados = [a for a in arquivos if a != "audit.db"]
    assert len(arquivados) == 1  # arquivo antigo foi renomeado, não apagado

    # O histórico antigo (evento da Ana) continua íntegro no arquivo arquivado.
    conn_antigo = sqlite3.connect(str(tmp_path / arquivados[0]))
    linhas_antigas = conn_antigo.execute("SELECT user FROM audit_log").fetchall()
    conn_antigo.close()
    assert linhas_antigas == [("ana",)]

    # O arquivo ativo (novo) tem só o evento novo (Bruno) — a rotação
    # acontece ANTES de gravar o evento que dispara a checagem.
    conn_novo = sqlite3.connect(db_path)
    linhas_novas = conn_novo.execute("SELECT user FROM audit_log").fetchall()
    conn_novo.close()
    assert linhas_novas == [("bruno",)]


def test_rotacao_nao_quebra_leitura_apos_reinicio(tmp_path):
    """Uma nova instância (simulando reinício do processo) continua
    funcionando normalmente após uma rotação ter ocorrido."""
    db_path = str(tmp_path / "audit.db")
    logger1 = AuditLogger(db_path=db_path)
    logger1.max_size_bytes = 1
    logger1.log_action(action=AuditAction.USER_ACTION, user="ana", description="evento 1")
    logger1.log_action(action=AuditAction.USER_ACTION, user="bruno", description="evento 2")

    logger2 = AuditLogger(db_path=db_path)  # "reinício"
    trail = logger2.get_audit_trail(persisted=True)

    assert len(trail) == 1
    assert trail.iloc[0]["user"] == "bruno"


# --- log_report_generation: sucesso/falha, usuário, lote, formato (CT-AUD-01) ---
# O método já existia mas nunca era chamado por pages/gerar_relatorio.py
# — a geração de relatório não tinha nenhum evento de auditoria.

def test_log_report_generation_sucesso_registra_lote_formato_e_contagens(tmp_path):
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
    row = conn.execute(
        "SELECT action, user, severity, details FROM audit_log WHERE action = 'REPORT_GENERATION'"
    ).fetchone()
    conn.close()

    assert row is not None
    action, user, severity, details_json = row
    assert user == "qa_user"
    assert severity == "INFO"
    import json
    details = json.loads(details_json)
    assert details["formato"] == "completo"
    assert details["lote"] == "1234490 | 15/06/2025 a 14/07/2025"
    assert details["success"] is True
    assert details["included_matches"] == 14
    assert details["included_exceptions"] == 8


def test_log_report_generation_falha_registra_severidade_erro_e_motivo(tmp_path):
    db_path = str(tmp_path / "audit.db")
    logger = AuditLogger(db_path=db_path)

    logger.log_report_generation(
        formato="resumido",
        user="qa_user",
        lote="1234490 | 15/06/2025 a 14/07/2025",
        success=False,
        error_message="Arquivo PDF está vazio",
    )

    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT severity, details FROM audit_log WHERE action = 'REPORT_GENERATION'"
    ).fetchone()
    conn.close()

    assert row is not None
    severity, details_json = row
    assert severity == "ERROR"
    import json
    details = json.loads(details_json)
    assert details["success"] is False
    assert details["error_message"] == "Arquivo PDF está vazio"


def test_log_report_generation_nao_registra_segredos(tmp_path):
    """O detalhe deve conter só formato/lote/contagens/erro — nunca
    senha, token ou payload de sessão."""
    db_path = str(tmp_path / "audit.db")
    logger = AuditLogger(db_path=db_path)

    logger.log_report_generation(
        formato="completo", user="qa_user", lote="1234490 | período X", success=True,
    )

    conn = sqlite3.connect(db_path)
    details_json = conn.execute(
        "SELECT details FROM audit_log WHERE action = 'REPORT_GENERATION'"
    ).fetchone()[0]
    conn.close()

    for termo_proibido in ("senha", "password", "token", "secret"):
        assert termo_proibido not in details_json.lower()
