"""
Testes de regressão para SEC-R-07 (revisão de segurança dedicada,
docs/revisao-seguranca-fase-5.md, issue XCRE-52): as dependências
diretas de `requirements.txt` estavam sem versão fixada (exceto
`weasyprint`/`Jinja2`, já pinados numa fase anterior) — uma reinstalação
em outro momento podia puxar versões diferentes das testadas, inclusive
com vulnerabilidades conhecidas não avaliadas.

Não reexecuta a instalação em múltiplos Pythons nem o `pip-audit` (isso
é verificado manualmente pela revisão, registrado no comentário da
issue) — só trava, via teste, que o arquivo continua com TODAS as
dependências diretas pinadas por versão exata e que `packages.txt`
(dependências de sistema do WeasyPrint) não foi tocado por engano.

Dados 100% sintéticos (o próprio arquivo de dependências do repo).
"""
import os
import re

REQUIREMENTS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "requirements.txt")
PACKAGES_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "packages.txt")

# Conteúdo esperado de packages.txt (dependências de SISTEMA do
# WeasyPrint) — SEC-R-07 não deve alterar este arquivo; qualquer
# diferença aqui precisa de uma decisão separada, não desta correção.
_PACOTES_SISTEMA_ESPERADOS = [
    "libpango-1.0-0",
    "libpangocairo-1.0-0",
    "libpangoft2-1.0-0",
    "libharfbuzz0b",
    "libharfbuzz-subset0",
    "libcairo2",
    "libgdk-pixbuf-2.0-0",
    "libffi8",
]


def _ler_linhas_nao_vazias(caminho: str):
    with open(caminho, encoding="utf-8") as f:
        return [linha.strip() for linha in f if linha.strip() and not linha.strip().startswith("#")]


def test_todas_as_dependencias_diretas_tem_versao_exata_fixada():
    linhas = _ler_linhas_nao_vazias(REQUIREMENTS_PATH)
    assert linhas, "requirements.txt não pode estar vazio"

    padrao_pin_exato = re.compile(r'^[A-Za-z0-9_.\-]+==[A-Za-z0-9_.\-]+$')
    sem_pin_exato = [linha for linha in linhas if not padrao_pin_exato.match(linha)]

    assert not sem_pin_exato, (
        f"dependências sem versão EXATA fixada (==) em requirements.txt: {sem_pin_exato}"
    )


def test_weasyprint_e_jinja2_continuam_nas_versoes_documentadas():
    linhas = _ler_linhas_nao_vazias(REQUIREMENTS_PATH)
    assert "weasyprint==70.0" in linhas
    assert "Jinja2==3.1.6" in linhas


def test_packages_txt_nao_foi_alterado_por_esta_correcao():
    linhas = _ler_linhas_nao_vazias(PACKAGES_PATH)
    assert linhas == _PACOTES_SISTEMA_ESPERADOS
