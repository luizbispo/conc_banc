"""
Smoke test de SEC-R-07 (revisão de segurança dedicada,
docs/revisao-seguranca-fase-5.md, issue XCRE-52): confirma que `app.py`
carrega de ponta a ponta (imports, `st.set_page_config`, `init_db()`,
tela de login) com as dependências diretas pinadas em
`requirements.txt`, sem levantar exceção.

Sem `pytest` (só a stdlib + o próprio `streamlit`) de propósito: além de
rodar dentro da suíte normal (`pytest tests/test_smoke_import_app.py`),
este arquivo também é chamado diretamente com
`python tests/test_smoke_import_app.py` a partir da raiz do repositório
— é assim que a revisão verifica a instalação limpa em cada versão de
Python (3.10/3.12/3.13), num venv só com `requirements.txt` instalado
(sem `requirements-dev.txt`, que traz o `pytest`).

Não substitui a suíte completa nem testes de comportamento — só
confirma que a árvore de dependências resolvida por `requirements.txt`
permite o app SUBIR.
"""
import os
import tempfile

# AppTest.from_file resolve caminho relativo a partir do arquivo que
# CHAMA (este arquivo, em tests/), não do cwd — por isso o caminho
# absoluto até app.py na raiz do repositório.
_APP_PY = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")


def test_app_carrega_via_streamlit_apptest():
    from streamlit.testing.v1 import AppTest

    db_path_original = os.environ.get("CONCILIACAO_DB_PATH")
    audit_path_original = os.environ.get("CONCILIACAO_AUDIT_DB_PATH")
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["CONCILIACAO_DB_PATH"] = os.path.join(tmp, "users.db")
        os.environ["CONCILIACAO_AUDIT_DB_PATH"] = os.path.join(tmp, "audit.db")
        try:
            at = AppTest.from_file(_APP_PY)
            at.run()
            assert not at.exception, f"app.py levantou exceção ao carregar: {at.exception}"
        finally:
            if db_path_original is None:
                os.environ.pop("CONCILIACAO_DB_PATH", None)
            else:
                os.environ["CONCILIACAO_DB_PATH"] = db_path_original
            if audit_path_original is None:
                os.environ.pop("CONCILIACAO_AUDIT_DB_PATH", None)
            else:
                os.environ["CONCILIACAO_AUDIT_DB_PATH"] = audit_path_original


if __name__ == "__main__":
    test_app_carrega_via_streamlit_apptest()
    print("SMOKE OK: app.py carregou via AppTest sem exceção")
