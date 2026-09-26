"""
Testes do helper de tema v3 (fase 6, XCRE-54 item 3): injeta CSS
ESTÁTICO e VERSIONADO do repositório (assets/custom.css) uma vez por
execução de página, via st.markdown(unsafe_allow_html=True), sem NUNCA
receber dado do usuário. Cobre injeção, idempotência entre chamadas
repetidas, tolerância a arquivo ausente, e as regras de segurança do
próprio CSS (sem @import/url()/http(s)://, seletores estáveis, fallback
Inter/system-ui, nenhum alerta escondido) e do .streamlit/config.toml
(showSidebarNavigation preservado).

Não aplica o helper em nenhuma página ainda (isso é um sub-item
posterior) — só testa o helper e os arquivos estáticos isoladamente.

Dados 100% sintéticos / estáticos do próprio repositório.
"""
import inspect
import os
from unittest import mock

import streamlit as st

import modules.tema as tema

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# --- aplicar_tema(): injeção, idempotência, arquivo ausente ---

def test_aplicar_tema_injeta_o_css_do_repositorio_via_markdown():
    with mock.patch.object(st, "markdown") as markdown_mock:
        tema.aplicar_tema()

    markdown_mock.assert_called_once()
    args, kwargs = markdown_mock.call_args
    conteudo = args[0]
    assert kwargs.get("unsafe_allow_html") is True
    assert "<style" in conteudo and "</style>" in conteudo

    with open(tema.CSS_PATH, "r", encoding="utf-8") as f:
        css_real = f.read()
    assert css_real in conteudo


def test_aplicar_tema_e_idempotente_entre_chamadas_repetidas():
    with mock.patch.object(st, "markdown") as markdown_mock:
        tema.aplicar_tema()
        tema.aplicar_tema()
        tema.aplicar_tema()

    assert markdown_mock.call_count == 3
    chamadas = [c.args[0] for c in markdown_mock.call_args_list]
    assert chamadas[0] == chamadas[1] == chamadas[2]


def test_aplicar_tema_tolera_arquivo_ausente_sem_quebrar(monkeypatch, tmp_path):
    monkeypatch.setattr(tema, "CSS_PATH", str(tmp_path / "nao-existe.css"))

    with mock.patch.object(st, "markdown") as markdown_mock:
        tema.aplicar_tema()  # não deve levantar exceção

    markdown_mock.assert_not_called()


def test_ler_css_estatico_devolve_string_vazia_para_arquivo_ausente(monkeypatch, tmp_path):
    monkeypatch.setattr(tema, "CSS_PATH", str(tmp_path / "nao-existe.css"))
    assert tema._ler_css_estatico() == ""


def test_helper_nao_aceita_nenhum_parametro_ou_seja_nenhum_dado_do_usuario():
    assert list(inspect.signature(tema.aplicar_tema).parameters) == []
    assert list(inspect.signature(tema._ler_css_estatico).parameters) == []


# --- Regras de segurança do CSS estático versionado ---

def _ler_css_do_repositorio() -> str:
    with open(tema.CSS_PATH, "r", encoding="utf-8") as f:
        return f.read()


def test_css_estatico_nao_importa_nem_referencia_recurso_remoto():
    css_lower = _ler_css_do_repositorio().lower()
    assert "@import" not in css_lower
    assert "url(" not in css_lower
    assert "http://" not in css_lower
    assert "https://" not in css_lower


def test_css_estatico_usa_fallback_inter_system_ui():
    css = _ler_css_do_repositorio()
    assert "Inter" in css
    assert "system-ui" in css


def test_css_estatico_nao_usa_seletor_emotion_cache_fragil():
    assert "st-emotion-cache" not in _ler_css_do_repositorio()


def test_css_estatico_nao_esconde_alertas_ou_mensagens_de_erro():
    css = _ler_css_do_repositorio()
    for seletor_proibido in ("stAlert", "stException", "stError", "stWarning", "stSuccess", "stInfo"):
        assert seletor_proibido not in css


def test_css_estatico_usa_apenas_seletores_estaveis_do_streamlit():
    # Além de .st-emotion-cache-*, qualquer classe começando com "css-"
    # seguida de hash também é auto-gerada pelo Streamlit e instável.
    css = _ler_css_do_repositorio()
    assert "[data-testid=" in css  # usa os seletores estáveis documentados
    import re
    assert not re.search(r"\.css-[0-9a-z]{6,}\b", css)


# --- .streamlit/config.toml ---

def test_config_toml_preserva_sidebar_navigation_desabilitada():
    import toml
    caminho = os.path.join(REPO_ROOT, ".streamlit", "config.toml")
    config = toml.load(caminho)
    assert config["client"]["showSidebarNavigation"] is False
