"""
Teste de regressão para pages/analise_dados._registrar_auditoria_matching
(issue XCRE-42, Parte A, item 4): as funções log_matching_layer /
log_match_decision existiam em modules/audit_logger.py, mas nunca eram
chamadas a partir do fluxo real de matching — só login/upload/relatório
eram auditados. A decisão de aceitar um par (inclusive a confiança e a
camada) ficava sem trilha.

Dados 100% sintéticos.
"""
import sqlite3

import pytest

import pages.analise_dados as pagina
from modules.audit_logger import AuditLogger


@pytest.fixture
def audit_isolado(tmp_path, monkeypatch):
    db_path = str(tmp_path / "audit_matching.db")
    logger_isolado = AuditLogger(db_path=db_path)
    monkeypatch.setattr(pagina, "audit", logger_isolado)
    return db_path


def _resultado_sintetico():
    return {
        'matches': [
            {
                'tipo_match': '1:1', 'camada': 'exata',
                'ids_extrato': [1], 'ids_contabil': [1],
                'valor_total': 100.0, 'confianca': 100,
                'chave_match': 'EXATO_1_1',
            },
            {
                'tipo_match': '1:1', 'camada': 'heuristica',
                'ids_extrato': [2], 'ids_contabil': [2],
                'valor_total': 40.30, 'confianca': 82.5,
                'chave_match': 'HEUR_2_2',
            },
        ],
        'estatisticas': {
            'total_matches': 2,
            'matches_exatos': 1,
            'matches_heuristicos': 1,
            'matches_ia': 0,
            'total_excecoes': 0,
        },
    }


def test_registra_uma_decisao_por_match_aceito(audit_isolado):
    pagina._registrar_auditoria_matching(_resultado_sintetico(), tolerancia_percentual=2.0, usuario="qa_user")

    conn = sqlite3.connect(audit_isolado)
    rows = conn.execute(
        "SELECT action, user, details, transaction_ids FROM audit_log WHERE action = 'MATCH_APPROVAL'"
    ).fetchall()
    conn.close()

    assert len(rows) == 2
    for action, user, details, transaction_ids in rows:
        assert user == "qa_user"
        assert "camada" in details
        assert transaction_ids != "[]"


def test_registra_resumo_por_camada_de_matching(audit_isolado):
    pagina._registrar_auditoria_matching(_resultado_sintetico(), tolerancia_percentual=2.0, usuario="qa_user")

    conn = sqlite3.connect(audit_isolado)
    rows = conn.execute(
        "SELECT action, details FROM audit_log WHERE action LIKE 'MATCHING_%'"
    ).fetchall()
    conn.close()

    actions = {row[0] for row in rows}
    assert actions == {"MATCHING_EXATO", "MATCHING_HEURISTICO", "MATCHING_IA"}
    for _, details in rows:
        assert "tolerancia_valor_percentual" in details
