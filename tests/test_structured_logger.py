"""
Testes de regressão para o log estruturado JSONL
(issue XCRE-49, Fase 5, item 5).

Antes, não havia nenhum log operacional em JSON linha a linha no
projeto — só `logging.basicConfig` (texto livre, sem formato
estruturado) em alguns módulos. `modules/structured_logger.py`
adiciona um log JSONL enxuto para login, carga de arquivo, análise e
geração de relatório, com uma lista de campos proibidos (senha, hash,
credencial, conteúdo, descrição, caminho, stack trace, valor) validada
em tempo de execução — nunca confiando só na revisão de código.

Dados 100% sintéticos.
"""
import importlib
import json
import os
import sqlite3

import pytest
import streamlit as st

from modules.structured_logger import StructuredLogger


@pytest.fixture
def logger_em_arquivo_temporario(tmp_path):
    caminho = str(tmp_path / "eventos.jsonl")
    return StructuredLogger(caminho=caminho, max_size_mb=50)


def _ler_linhas_jsonl(caminho):
    with open(caminho, "r", encoding="utf-8") as f:
        return [json.loads(linha) for linha in f if linha.strip()]


# --- Parseabilidade: cada linha é um objeto JSON válido ---

def test_cada_linha_gravada_e_json_valido(logger_em_arquivo_temporario):
    log = logger_em_arquivo_temporario
    log.log_login(sucesso=True, motivo='sucesso', duracao_segundos=0.01, usuario='contador1')
    log.log_carga_arquivo(formato='csv', sucesso=True, motivo='sucesso', registros=10,
                          tamanho_bytes=2048, duracao_segundos=0.2)
    log.log_analise(total_extrato=18, total_contabil=18, total_matches=14,
                    total_divergencias=8, duracao_segundos=1.5)
    log.log_geracao_relatorio(formato='pdf', sucesso=True, matches_incluidos=14,
                              divergencias_incluidas=8, duracao_segundos=0.8)

    registros = _ler_linhas_jsonl(log.caminho)
    assert len(registros) == 4
    for registro in registros:
        assert isinstance(registro, dict)
        assert 'timestamp' in registro
        assert 'evento' in registro


# --- Eventos: tipo e campos esperados ---

def test_evento_login_tem_os_campos_esperados_sem_dado_sensivel(logger_em_arquivo_temporario):
    log = logger_em_arquivo_temporario
    registro = log.log_login(sucesso=False, motivo='senha_incorreta',
                             duracao_segundos=0.05, usuario='contador1')

    assert registro['evento'] == 'login'
    assert registro['sucesso'] is False
    assert registro['motivo'] == 'senha_incorreta'
    assert registro['usuario'] == 'contador1'
    assert set(registro.keys()) == {'timestamp', 'evento', 'sucesso', 'motivo', 'usuario', 'duracao_segundos'}


def test_evento_carga_arquivo_tem_os_campos_esperados(logger_em_arquivo_temporario):
    log = logger_em_arquivo_temporario
    registro = log.log_carga_arquivo(formato='ofx', sucesso=True, motivo='sucesso',
                                     registros=42, tamanho_bytes=8192, duracao_segundos=0.3)

    assert registro['evento'] == 'carga_arquivo'
    assert registro['formato'] == 'ofx'
    assert registro['registros'] == 42
    assert registro['tamanho_bytes'] == 8192
    assert set(registro.keys()) == {
        'timestamp', 'evento', 'formato', 'sucesso', 'motivo',
        'registros', 'tamanho_bytes', 'duracao_segundos',
    }


def test_evento_analise_tem_os_campos_esperados(logger_em_arquivo_temporario):
    log = logger_em_arquivo_temporario
    registro = log.log_analise(total_extrato=18, total_contabil=18, total_matches=14,
                               total_divergencias=8, duracao_segundos=1.23)

    assert registro['evento'] == 'analise'
    assert registro['total_extrato'] == 18
    assert registro['total_matches'] == 14
    assert registro['total_divergencias'] == 8
    assert set(registro.keys()) == {
        'timestamp', 'evento', 'total_extrato', 'total_contabil',
        'total_matches', 'total_divergencias', 'duracao_segundos',
    }


def test_evento_geracao_relatorio_tem_os_campos_esperados(logger_em_arquivo_temporario):
    log = logger_em_arquivo_temporario
    registro = log.log_geracao_relatorio(formato='Executivo', sucesso=True,
                                         matches_incluidos=14, divergencias_incluidas=8,
                                         duracao_segundos=0.9)

    assert registro['evento'] == 'geracao_relatorio'
    assert registro['formato'] == 'Executivo'
    assert registro['matches_incluidos'] == 14
    assert registro['divergencias_incluidas'] == 8
    assert set(registro.keys()) == {
        'timestamp', 'evento', 'formato', 'sucesso', 'motivo',
        'matches_incluidos', 'divergencias_incluidas', 'duracao_segundos',
    }


# --- Contagens e duração ---

def test_duracao_e_contagens_sao_preservadas_como_numeros(logger_em_arquivo_temporario):
    log = logger_em_arquivo_temporario
    registro = log.log_carga_arquivo(formato='csv', sucesso=True, motivo='sucesso',
                                     registros=7, tamanho_bytes=1234, duracao_segundos=0.123456789)

    registros_relidos = _ler_linhas_jsonl(log.caminho)
    assert registros_relidos[0]['registros'] == 7
    assert registros_relidos[0]['tamanho_bytes'] == 1234
    assert isinstance(registros_relidos[0]['duracao_segundos'], float)
    assert registros_relidos[0]['duracao_segundos'] == pytest.approx(0.123457, abs=1e-6)


# --- Validação: motivo desconhecido nunca é gravado ---

@pytest.mark.parametrize("metodo,kwargs", [
    ("log_login", dict(sucesso=False, motivo='motivo_inventado', duracao_segundos=0.1)),
    ("log_carga_arquivo", dict(formato='csv', sucesso=False, motivo='motivo_inventado',
                               registros=0, tamanho_bytes=10, duracao_segundos=0.1)),
    ("log_geracao_relatorio", dict(formato='pdf', sucesso=False, motivo='motivo_inventado',
                                   matches_incluidos=0, divergencias_incluidas=0, duracao_segundos=0.1)),
])
def test_motivo_desconhecido_levanta_valueerror_e_nao_grava_nada(logger_em_arquivo_temporario, metodo, kwargs):
    log = logger_em_arquivo_temporario
    with pytest.raises(ValueError):
        getattr(log, metodo)(**kwargs)
    assert not os.path.exists(log.caminho)


# --- Guarda em tempo de execução contra campo proibido ---

@pytest.mark.parametrize("chave_proibida", [
    "senha", "password", "password_hash", "credencial", "token",
    "conteudo", "descricao", "caminho", "stack_trace", "valor",
])
def test_campo_proibido_levanta_valueerror_e_nao_grava_nada(logger_em_arquivo_temporario, chave_proibida):
    log = logger_em_arquivo_temporario
    with pytest.raises(ValueError):
        log.registrar('carga_arquivo', **{chave_proibida: 'dado sensivel'})
    assert not os.path.exists(log.caminho)


# --- Rotação por tamanho (mesmo esquema de modules/audit_logger.py) ---

def test_rotaciona_arquivo_ao_ultrapassar_tamanho_maximo(tmp_path):
    caminho = str(tmp_path / "eventos.jsonl")
    log = StructuredLogger(caminho=caminho, max_size_mb=0)  # qualquer bytes já ultrapassa

    log.registrar('login', sucesso=True, motivo='sucesso', duracao_segundos=0.01)
    assert os.path.exists(caminho)

    log.registrar('login', sucesso=True, motivo='sucesso', duracao_segundos=0.02)

    arquivos = os.listdir(tmp_path)
    rotacionados = [a for a in arquivos if a.startswith("eventos.jsonl.") and a != "eventos.jsonl"]
    assert len(rotacionados) == 1, f"esperava exatamente 1 arquivo rotacionado, achei: {arquivos}"

    # o arquivo antigo preserva a primeira linha; o ativo só tem a segunda
    linhas_antigas = _ler_linhas_jsonl(str(tmp_path / rotacionados[0]))
    linhas_ativas = _ler_linhas_jsonl(caminho)
    assert len(linhas_antigas) == 1
    assert len(linhas_ativas) == 1
    assert linhas_antigas[0]['duracao_segundos'] == pytest.approx(0.01)
    assert linhas_ativas[0]['duracao_segundos'] == pytest.approx(0.02)


# --- Varredura contra dados sensíveis em cenário sintético B x C ---

def test_varredura_do_cenario_sintetico_b_x_c_nao_encontra_dado_sensivel(logger_em_arquivo_temporario):
    """Simula uma execução completa (login, carga de dois arquivos,
    análise, geração de relatório) com o formato de dados do cenário
    B x C sintético do projeto (14 matches, 8 divergências) e varre
    TODAS as linhas gravadas procurando por senha, hash, credencial,
    descrição de transação ou valor monetário — nenhuma dessas
    strings pode aparecer porque os métodos de log só aceitam campos
    estruturados fixos (contagens, formato, duração, categoria)."""
    log = logger_em_arquivo_temporario

    senha_sintetica = "SenhaSuperSecreta123!"
    hash_sintetico = "5f4dcc3b5aa765d61d8327deb882cf99"
    descricao_transacao_sintetica = "PIX recebido de Cliente Fictício LTDA"
    valor_sintetico_str = "R$ 1.234,56"
    caminho_local_sintetico = "/home/usuario/uploads/extrato_secreto.csv"

    log.log_login(sucesso=True, motivo='sucesso', duracao_segundos=0.05, usuario='contador_teste')
    log.log_carga_arquivo(formato='csv', sucesso=True, motivo='sucesso', registros=18,
                          tamanho_bytes=4096, duracao_segundos=0.4)
    log.log_carga_arquivo(formato='csv', sucesso=True, motivo='sucesso', registros=18,
                          tamanho_bytes=4096, duracao_segundos=0.35)
    log.log_analise(total_extrato=18, total_contabil=18, total_matches=14,
                    total_divergencias=8, duracao_segundos=1.1)
    log.log_geracao_relatorio(formato='Executivo', sucesso=True, matches_incluidos=14,
                              divergencias_incluidas=8, duracao_segundos=0.75)

    conteudo_bruto = open(log.caminho, "r", encoding="utf-8").read()

    for dado_proibido in (senha_sintetica, hash_sintetico, descricao_transacao_sintetica,
                          valor_sintetico_str, caminho_local_sintetico, "Traceback"):
        assert dado_proibido not in conteudo_bruto

    registros = _ler_linhas_jsonl(log.caminho)
    assert [r['evento'] for r in registros] == [
        'login', 'carga_arquivo', 'carga_arquivo', 'analise', 'geracao_relatorio',
    ]
    assert registros[3]['total_matches'] == 14
    assert registros[3]['total_divergencias'] == 8


# --- Integração: login real via app.py grava evento sem senha/hash ---

@pytest.fixture
def app_autenticavel(tmp_path, monkeypatch):
    db_path = str(tmp_path / "users.db")
    audit_path = str(tmp_path / "audit.db")
    log_path = str(tmp_path / "eventos_login.jsonl")
    monkeypatch.setenv("CONCILIACAO_DB_PATH", db_path)
    monkeypatch.setenv("CONCILIACAO_AUDIT_DB_PATH", audit_path)
    monkeypatch.setenv("CONCILIACAO_STRUCTURED_LOG_PATH", log_path)

    from modules.auth_middleware import hash_password, init_security_tables
    senha = "SenhaValida123"
    password_hash, salt = hash_password(senha)

    conn = sqlite3.connect(db_path)
    conn.execute('''
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            password_salt TEXT,
            full_name TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        )
    ''')
    conn.execute(
        "INSERT INTO users (username, email, password_hash, password_salt, full_name, role, is_active) "
        "VALUES (?, ?, ?, ?, ?, 'user', 1)",
        ("contador_teste", "contador@example.com", password_hash, salt, "Contador Teste"),
    )
    conn.commit()
    init_security_tables(conn)
    conn.close()

    import modules.audit_logger as audit_logger_module
    audit_logger_module._audit_logger = None
    import modules.structured_logger as structured_logger_module
    structured_logger_module._structured_logger = None

    import app
    importlib.reload(app)
    return app, senha, log_path


def test_login_bem_sucedido_grava_evento_sem_senha_nem_hash(app_autenticavel):
    app, senha, log_path = app_autenticavel

    sucesso, user_info, token = app.login_user("contador_teste", senha)
    assert sucesso is True

    registros = _ler_linhas_jsonl(log_path)
    eventos_login = [r for r in registros if r['evento'] == 'login']
    assert len(eventos_login) == 1
    assert eventos_login[0]['sucesso'] is True
    assert eventos_login[0]['motivo'] == 'sucesso'
    assert eventos_login[0]['usuario'] == 'contador_teste'
    assert 'duracao_segundos' in eventos_login[0]

    conteudo_bruto = open(log_path, "r", encoding="utf-8").read()
    assert senha not in conteudo_bruto
    assert token not in conteudo_bruto


def test_login_com_senha_errada_grava_evento_de_falha_sem_a_senha(app_autenticavel):
    app, senha_correta, log_path = app_autenticavel

    senha_errada = "SenhaErradaXPTO"
    sucesso, user_info, token = app.login_user("contador_teste", senha_errada)
    assert sucesso is False

    registros = _ler_linhas_jsonl(log_path)
    eventos_login = [r for r in registros if r['evento'] == 'login']
    assert len(eventos_login) == 1
    assert eventos_login[0]['sucesso'] is False
    assert eventos_login[0]['motivo'] == 'senha_incorreta'
    assert 'usuario' not in eventos_login[0]  # login falho: não grava nem o usuário digitado

    conteudo_bruto = open(log_path, "r", encoding="utf-8").read()
    assert senha_errada not in conteudo_bruto
