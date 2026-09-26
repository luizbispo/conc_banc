"""Tema visual v3 (fase 6, XCRE-54 item 3).

Helper pequeno que injeta o CSS ESTÁTICO e VERSIONADO do repositório
(assets/custom.css) uma vez por execução de página, via
st.markdown(unsafe_allow_html=True). NUNCA recebe nem interpola dado do
usuário — só o conteúdo do arquivo do repositório é injetado, por isso
`aplicar_tema()` e `_ler_css_estatico()` não têm nenhum parâmetro.
"""
import os

import streamlit as st

_ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
CSS_PATH = os.path.join(_ASSETS_DIR, "custom.css")


def _ler_css_estatico() -> str:
    """Lê o CSS estático do repositório. Tolera arquivo ausente devolvendo
    string vazia, sem levantar exceção (a página continua funcionando sem
    estilo, em vez de quebrar)."""
    try:
        with open(CSS_PATH, "r", encoding="utf-8") as arquivo:
            return arquivo.read()
    except FileNotFoundError:
        return ""


def aplicar_tema() -> None:
    """Injeta o CSS estático do tema v3 na página atual.

    Idempotente: chamadas repetidas na mesma execução sempre leem o mesmo
    arquivo e produzem o mesmo `st.markdown(...)`, sem acumular estado
    nem depender de quantas vezes já foi chamado. De propósito, NÃO usa
    uma flag de `st.session_state` para pular reinjeções: o Streamlit
    recria a árvore de elementos da página a cada execução/navegação, e
    uma flag que persiste entre execuções (como o `session_state` faz)
    faria o CSS não ser reinjetado ao entrar numa página nova — por isso
    cada página precisa chamar este helper por si, e ele precisa
    responder da mesma forma toda vez que for chamado.
    """
    css = _ler_css_estatico()
    if not css:
        return
    st.markdown(f"<style>\n{css}\n</style>", unsafe_allow_html=True)
