"""
Testes de regressão para modules/file_processor.py.

Cobrem a correção do fallback mock silencioso: antes, qualquer erro de
parsing (arquivo corrompido, encoding inválido, colunas inesperadas) fazia
FileProcessor.processar_extrato/processar_contabeis retornar dados
FICTÍCIOS como se fossem o arquivo real, sem nenhum sinal de falha. Agora
uma falha de parsing sempre propaga como exceção.
"""
import pytest

from modules.file_processor import FileProcessor


def test_processar_extrato_raises_instead_of_returning_mock_data_on_missing_file():
    processor = FileProcessor()
    with pytest.raises(RuntimeError):
        processor.processar_extrato("/caminho/que/nao/existe.csv")


def test_processar_contabeis_raises_instead_of_returning_mock_data_on_missing_file():
    processor = FileProcessor()
    with pytest.raises(RuntimeError):
        processor.processar_contabeis("/caminho/que/nao/existe.csv")


def test_processar_extrato_raises_on_corrupted_file(tmp_path):
    arquivo_corrompido = tmp_path / "corrompido.csv"
    # bytes binários inválidos como CSV/UTF-8
    arquivo_corrompido.write_bytes(b"\xff\xfe\x00\x01binlixo\x00\x02")

    processor = FileProcessor()
    with pytest.raises(RuntimeError):
        processor.processar_extrato(str(arquivo_corrompido))


def test_mock_fallback_methods_were_removed():
    """Trava de regressão explícita: os métodos que geravam dados fictícios
    de fallback não devem mais existir na classe."""
    assert not hasattr(FileProcessor, "_criar_dados_extrato_mock")
    assert not hasattr(FileProcessor, "_criar_dados_contabil_mock")


def test_processar_extrato_succeeds_on_valid_synthetic_csv(tmp_path):
    arquivo_valido = tmp_path / "extrato_sintetico.csv"
    arquivo_valido.write_text(
        "data,valor,descricao\n"
        "2024-01-01,100.00,PIX recebido\n"
        "2024-01-02,-50.00,Pagamento boleto\n",
        encoding="utf-8",
    )

    processor = FileProcessor()
    df = processor.processar_extrato(str(arquivo_valido))

    assert len(df) == 2
    assert set(["data", "valor", "descricao"]).issubset(df.columns)
