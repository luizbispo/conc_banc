"""
Testes de regressão para modules/audit_logger.py.

Cobrem: persistência em SQLite (a trilha de auditoria não pode sumir a
cada reinício do processo), clear_audit_log não apagar mais o histórico
persistido (append-only), e a correção do bug de cópia rasa em
export_audit_log que apagava 'details'/'metadata' do log original quando
se exportava a versão resumida.
"""
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
