"""
Testes sintéticos da correção de SEC-R-02 (revisão de segurança dedicada,
docs/revisao-seguranca-fase-5.md, issue XCRE-52): o PDF do relatório
Executivo era escrito em tempfile.gettempdir() com nome previsível
(timestamp), permissões padrão do processo (tipicamente 0644) e NUNCA
era apagado — qualquer usuário local do mesmo host podia ler relatórios
de outras execuções.

Este arquivo reproduz o achado ANTES da correção (os testes abaixo
devem falhar contra o `modules/report_executivo.py` anterior a esta
issue) e passa a valer como regressão depois. Dados 100% sintéticos.

Os testes espiam `shutil.rmtree` (chamado no `finally` de
gerar_relatorio_executivo, já depois do chmod e da leitura dos bytes,
mas antes de apagar) para inspecionar o arquivo/diretório temporário
ENQUANTO eles ainda existem, e conferem que somem logo em seguida.
"""
import os
import re
import stat
from unittest import mock

import pandas as pd
import pytest

import modules.report_executivo as report_executivo
from modules.report_executivo import gerar_relatorio_executivo

_ORIGINAL_RMTREE = report_executivo.shutil.rmtree
_ORIGINAL_CHMOD = os.chmod


def _dados_sinteticos():
    extrato = pd.DataFrame({
        "id": [1],
        "data": pd.to_datetime(["2025-06-15"]),
        "valor": [123.45],
        "descricao": ["Lançamento sintético A"],
    })
    contabil = pd.DataFrame({
        "id": [1],
        "data": pd.to_datetime(["2025-06-15"]),
        "valor": [123.45],
        "descricao": ["Lançamento sintético A"],
    })
    resultados = {"matches": [], "excecoes": []}
    return resultados, extrato, contabil


def _rmtree_espiao(captura):
    """Espiona o shutil.rmtree usado no `finally`: captura o estado do
    arquivo/diretório (modo, bytes) exatamente antes de serem apagados,
    e delega para o rmtree real em seguida."""
    def _espiao(target, *args, **kwargs):
        target_str = str(target)
        captura["dir"] = target_str
        entradas = os.listdir(target_str)
        assert len(entradas) == 1, "esperado exatamente um arquivo no diretório privado do PDF"
        caminho_arquivo = os.path.join(target_str, entradas[0])
        captura["path"] = caminho_arquivo
        captura["modo_dir"] = stat.S_IMODE(os.stat(target_str).st_mode)
        captura["modo_arquivo"] = stat.S_IMODE(os.stat(caminho_arquivo).st_mode)
        with open(caminho_arquivo, "rb") as f:
            captura["bytes_no_disco"] = f.read()
        return _ORIGINAL_RMTREE(target_str, *args, **kwargs)
    return _espiao


def _gerar_com_sucesso(captura):
    resultados, extrato, contabil = _dados_sinteticos()
    with mock.patch.object(report_executivo.shutil, "rmtree", _rmtree_espiao(captura)):
        return gerar_relatorio_executivo(
            resultados_analise=resultados,
            extrato_df=extrato,
            contabil_df=contabil,
            empresa_nome="Empresa QA",
            analista_nome="Analista QA",
            periodo="15/06/2025 a 15/06/2025",
            conta_analisada="0000000",
        )


def _gerar_com_falha_apos_escrever(captura):
    """Injeta uma falha logo após o PDF já ter sido escrito e ajustado
    para 0600 (no `os.chmod` do módulo), simulando uma exceção
    inesperada depois que o artefato sensível já existe em disco."""
    resultados, extrato, contabil = _dados_sinteticos()

    def _chmod_espiao(path, modo, *args, **kwargs):
        _ORIGINAL_CHMOD(path, modo, *args, **kwargs)
        raise RuntimeError("falha sintética injetada após preparar o PDF")

    with mock.patch.object(report_executivo.shutil, "rmtree", _rmtree_espiao(captura)), \
         mock.patch.object(report_executivo.os, "chmod", _chmod_espiao):
        return gerar_relatorio_executivo(
            resultados_analise=resultados,
            extrato_df=extrato,
            contabil_df=contabil,
            empresa_nome="Empresa QA",
            analista_nome="Analista QA",
            periodo="15/06/2025 a 15/06/2025",
            conta_analisada="0000000",
        )


def test_arquivo_e_diretorio_tem_permissoes_restritas_durante_a_geracao():
    captura = {}
    _gerar_com_sucesso(captura)
    assert captura["modo_arquivo"] == 0o600, (
        f"arquivo do PDF deveria ser 0600, mas era {oct(captura['modo_arquivo'])}"
    )
    assert captura["modo_dir"] == 0o700, (
        f"diretório do PDF deveria ser 0700, mas era {oct(captura['modo_dir'])}"
    )


def test_nome_do_arquivo_e_do_diretorio_sao_imprevisiveis():
    captura_1, captura_2 = {}, {}
    _gerar_com_sucesso(captura_1)
    _gerar_com_sucesso(captura_2)

    nome_1 = os.path.basename(captura_1["path"])
    nome_2 = os.path.basename(captura_2["path"])
    # Nada de timestamp com segundos/microssegundos como único fator de
    # variação: exige um componente de alta entropia (hex longo) no nome.
    assert re.search(r"[0-9a-f]{16,}", nome_1), f"nome pouco imprevisível: {nome_1}"
    assert nome_1 != nome_2
    assert captura_1["dir"] != captura_2["dir"]


def test_arquivo_e_diretorio_sao_removidos_apos_sucesso():
    captura = {}
    pdf_bytes = _gerar_com_sucesso(captura)
    assert len(pdf_bytes) > 0
    assert not os.path.exists(captura["path"]), "o PDF temporário não foi apagado após o sucesso"
    assert not os.path.exists(captura["dir"]), "o diretório temporário não foi apagado após o sucesso"


def test_arquivo_e_diretorio_sao_removidos_mesmo_com_excecao_apos_escrita():
    captura = {}
    with pytest.raises(RuntimeError, match="falha sintética injetada"):
        _gerar_com_falha_apos_escrever(captura)
    assert not os.path.exists(captura["path"]), "o PDF temporário não foi apagado após a exceção"
    assert not os.path.exists(captura["dir"]), "o diretório temporário não foi apagado após a exceção"


def test_bytes_devolvidos_para_download_sao_identicos_aos_gravados_em_disco():
    captura = {}
    pdf_bytes = _gerar_com_sucesso(captura)
    assert pdf_bytes == captura["bytes_no_disco"]


def test_caminho_interno_nao_aparece_em_excecao_de_falha_de_geracao():
    """Sem vazar o caminho interno (/tmp/...) numa mensagem de erro que
    poderia chegar à interface — reproduz uma falha de geração e confere
    que o caminho gerado não aparece na representação da exceção."""
    captura = {}
    with pytest.raises(RuntimeError) as exc_info:
        _gerar_com_falha_apos_escrever(captura)
    assert captura["path"] not in str(exc_info.value)
