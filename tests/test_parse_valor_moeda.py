"""
Testes de regressão para pages/gerar_relatorio.parse_valor_moeda.

Bug real encontrado no E2E (ver issue): o "Total em divergência" do
relatório inflava os valores porque o parser antigo assumia sempre
convenção BRL (milhar '.', decimal ',') ao ler de volta as strings da
coluna "Valor", mas essas strings são geradas com f"R$ {valor:,.2f}"
(convenção do Python: milhar ',', decimal '.'). Ex. observado:
"R$ 1,300.00" virava 1.3 em vez de 1300.0 (o único '.' era removido como
se fosse separador de milhar).

Casos pedidos explicitamente na revisão: "R$ 60,50", "R$ 1.300,00" e
valores negativos — cobertos abaixo, junto com a convenção real usada
pelo próprio app (que era o caso que realmente estava quebrado em
produção).
"""
import pytest

from pages.gerar_relatorio import parse_valor_moeda


# --- Convenção BRL explícita (milhar '.', decimal ',') ---

def test_brl_simples():
    assert parse_valor_moeda("R$ 60,50") == pytest.approx(60.50)


def test_brl_com_milhar():
    assert parse_valor_moeda("R$ 1.300,00") == pytest.approx(1300.00)


def test_brl_sem_prefixo():
    assert parse_valor_moeda("60,50") == pytest.approx(60.50)


def test_brl_milhar_grande():
    assert parse_valor_moeda("R$ 12.345,67") == pytest.approx(12345.67)


# --- Convenção real gerada por este arquivo (f"R$ {valor:,.2f}") ---
# Esta é a convenção que realmente causava o bug em produção.

def test_formato_app_sem_milhar():
    assert parse_valor_moeda("R$ 60.50") == pytest.approx(60.50)


def test_formato_app_com_milhar_bug_relatado():
    """Reproduz exatamente o valor citado no relatório do E2E: uma
    transação de R$ 1.300,00 (BRL), exibida pelo app como "R$ 1,300.00",
    virava 1.3 com o parser antigo em vez de 1300.0."""
    assert parse_valor_moeda("R$ 1,300.00") == pytest.approx(1300.00)


def test_formato_app_milhar_grande():
    assert parse_valor_moeda("R$ 12,345.67") == pytest.approx(12345.67)


# --- Negativos ---

def test_negativo_formato_brl():
    assert parse_valor_moeda("R$ -20,80") == pytest.approx(-20.80)


def test_negativo_formato_app():
    assert parse_valor_moeda("R$ -20.80") == pytest.approx(-20.80)


def test_negativo_com_milhar_brl():
    assert parse_valor_moeda("R$ -1.300,00") == pytest.approx(-1300.00)


def test_negativo_com_milhar_formato_app():
    assert parse_valor_moeda("R$ -1,300.00") == pytest.approx(-1300.00)


def test_negativo_notacao_contabil_parenteses():
    assert parse_valor_moeda("R$ (60,50)") == pytest.approx(-60.50)


# --- Regressão exata do bug relatado (soma de linhas) ---

def test_soma_total_divergencia_bancaria_nao_infla():
    """Reproduz o cálculo de 'Total em divergência' do bloco de
    transações bancárias sem correspondência com os valores reais dos
    anexos sintéticos (B/C_1234490): 60,50 / 4,92 / 1.300,00 / 20,80 —
    total esperado R$ 1.386,22, não R$ 8.623,30 (valor inflado
    observado no E2E)."""
    valores_str = ["R$ 60.50", "R$ 4.92", "R$ 1,300.00", "R$ 20.80"]
    total = sum(abs(parse_valor_moeda(v)) for v in valores_str)
    assert total == pytest.approx(1386.22)


def test_soma_total_divergencia_contabil_nao_infla():
    """Idem para o lado contábil: 50,63 / 62,50 / 1.400,00 / 25,80 —
    total esperado R$ 1.538,93, não R$ 13.894,40 (valor inflado
    observado no E2E)."""
    valores_str = ["R$ 50.63", "R$ 62.50", "R$ 1,400.00", "R$ 25.80"]
    total = sum(abs(parse_valor_moeda(v)) for v in valores_str)
    assert total == pytest.approx(1538.93)


# --- Casos extremos ---

def test_zero():
    assert parse_valor_moeda("R$ 0,00") == pytest.approx(0.0)


def test_sem_separador_decimal():
    assert parse_valor_moeda("R$ 500") == pytest.approx(500.0)


def test_valor_none_levanta_excecao():
    with pytest.raises(ValueError):
        parse_valor_moeda(None)


def test_valor_vazio_levanta_excecao():
    with pytest.raises(ValueError):
        parse_valor_moeda("R$ ")


def test_valor_nao_numerico_levanta_excecao():
    with pytest.raises(ValueError):
        parse_valor_moeda("R$ abc")
