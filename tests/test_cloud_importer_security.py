"""
Testes de regressão para modules/data_processor.CloudImporter (issue
XCRE-42, Parte A, item 5c): antes não havia timeout em nenhuma
requisição HTTP, a "allowlist" de domínio comparava substring na URL
inteira em vez do hostname real (uma URL como
"https://drive.google.com.evil.example/x" também "continha"
drive.google.com e passava) e não havia limite de redirecionamentos
configurado explicitamente.

Dados 100% sintéticos; nenhuma requisição de rede real é feita.
"""
from unittest.mock import MagicMock, patch

from modules.data_processor import (
    CloudImporter,
    CLOUD_MAX_REDIRECTS,
    CLOUD_REQUEST_TIMEOUT_SEGUNDOS,
    _hostname_permitido,
)


# --- Allowlist por hostname real (não substring) ---

def test_hostname_permitido_aceita_dominio_real():
    assert _hostname_permitido("https://drive.google.com/file/d/abc123/view") is True


def test_hostname_permitido_aceita_subdominio():
    assert _hostname_permitido("https://empresa.sharepoint.com/:f:/g/xyz") is True


def test_hostname_permitido_rejeita_dominio_espelho():
    """Domínio-espelho: contém 'drive.google.com' como substring da URL,
    mas o hostname real é 'drive.google.com.evil.example'."""
    assert _hostname_permitido("https://drive.google.com.evil.example/x") is False


def test_hostname_permitido_rejeita_substring_em_query_string():
    assert _hostname_permitido("https://evil.example/?u=drive.google.com") is False


def test_hostname_permitido_rejeita_dominio_desconhecido():
    assert _hostname_permitido("https://pastebin.com/raw/xyz") is False


def test_hostname_permitido_rejeita_url_invalida():
    assert _hostname_permitido("nao-e-uma-url") is False


# --- identificar_tipo_url usa a allowlist real ---

def test_identificar_tipo_url_rejeita_dominio_espelho():
    importer = CloudImporter()
    assert importer.identificar_tipo_url("https://drive.google.com.evil.example/file/d/abc/view") == 'desconhecido'


def test_identificar_tipo_url_aceita_google_drive_real():
    importer = CloudImporter()
    assert importer.identificar_tipo_url("https://drive.google.com/file/d/abc123/view") == 'google_drive_file'


def test_identificar_tipo_url_aceita_sharepoint_real():
    importer = CloudImporter()
    assert importer.identificar_tipo_url("https://empresa.sharepoint.com/:f:/g/xyz") == 'sharepoint_folder'


# --- Timeout e limite de redirecionamentos ---

def test_session_configura_limite_de_redirects():
    importer = CloudImporter()
    assert importer.session.max_redirects == CLOUD_MAX_REDIRECTS


def test_baixar_google_drive_file_passa_timeout_na_requisicao():
    importer = CloudImporter()
    resposta_falsa = MagicMock(status_code=200, url="https://drive.google.com/uc?id=abc", content=b"dado", headers={})

    with patch.object(importer.session, "get", return_value=resposta_falsa) as mock_get:
        importer.baixar_google_drive_file("abc123", "arquivo.csv")

    mock_get.assert_called_once()
    _, kwargs = mock_get.call_args
    assert kwargs.get("timeout") == CLOUD_REQUEST_TIMEOUT_SEGUNDOS


def test_listar_arquivos_google_drive_folder_passa_timeout_na_requisicao():
    importer = CloudImporter()
    resposta_falsa = MagicMock(status_code=200, text="")

    with patch.object(importer.session, "get", return_value=resposta_falsa) as mock_get:
        importer.listar_arquivos_google_drive_folder("https://drive.google.com/drive/folders/abc123def456789012345678")

    mock_get.assert_called_once()
    _, kwargs = mock_get.call_args
    assert kwargs.get("timeout") == CLOUD_REQUEST_TIMEOUT_SEGUNDOS


# --- buscar_arquivos_por_padrao nunca chega a fazer requisição para tipo 'desconhecido' ---

def test_buscar_arquivos_por_padrao_nao_requisita_dominio_nao_permitido():
    importer = CloudImporter()
    with patch.object(importer.session, "get") as mock_get:
        resultado = importer.buscar_arquivos_por_padrao(
            "https://pastebin.com/raw/xyz", "extrato", "Junho", "desconhecido"
        )
    mock_get.assert_not_called()
    assert resultado == []
