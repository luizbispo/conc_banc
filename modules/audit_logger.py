# modules/audit_logger.py
import pandas as pd
import json
import os
import copy
import re
import sqlite3
from datetime import datetime
from typing import Dict, List, Any, Optional
import logging
import uuid
from enum import Enum

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Saneamento de campos controlados pelo usuário (revisão de segurança
# dedicada, SEC-R-05, XCRE-52): antes, um nome de usuário ou nome de
# arquivo de upload chegava ao SQLite E ao `logger` padrão exatamente
# como recebido — um username "alice\nINJECT" forjava uma segunda linha
# num log lido como texto simples, e um `file_name` com caminho completo
# (ex.: vindo de um objeto de upload malformado) vazava estrutura de
# diretório interna. As constantes/funções abaixo são o ÚNICO ponto de
# saneamento, aplicado dentro de `log_action` — o método por onde TODO
# `log_*` deste módulo passa — então cobre persistência (SQLite) e
# emissão no logger padrão com a mesma regra, sem depender de cada
# call site lembrar de sanear.
MAX_TEXTO_AUDITORIA_CARACTERES = int(os.getenv("CONCILIACAO_AUDIT_MAX_TEXTO_CARACTERES", "500"))
_MARCADOR_TRUNCAMENTO = "...(truncado)"

# C0 controls (0x00-0x1f) + DEL (0x7f): inclui CR e LF, que são a forma
# mais direta de forjar uma linha extra num log/CSV lido linha a linha.
_CONTROLES_AUDITORIA_RE = re.compile(r'[\x00-\x1f\x7f]')

# Rodada corretiva isolada de SEC-R-05 (re-verificação independente,
# XCRE-52): o saneamento acima (controle/tamanho/basename) NÃO impedia
# que senha, hash, token/JWT ou descrição de transação fossem
# persistidos — só neutralizava quebra de linha e diretório. A PoC
# independente confirmou o vazamento desses valores tanto no SQLite
# quanto no `logger`. Duas defesas complementares:
#
# 1) ALLOWLIST de chaves de TOPO em 'details'/'metadata': qualquer
#    chave fora deste conjunto de campos mínimos úteis (o inventário
#    real de todo call site de log_* neste código) é DESCARTADA antes
#    de persistir/logar — fecha por construção qualquer nome de campo
#    sensível (conhecido ou não: "senha", "password", "hash", "jwt",
#    "token", "descricao_transacao" etc. nunca estiveram nesta lista).
#    Só se aplica ao nível de TOPO de 'details'/'metadata' — dicts
#    aninhados livres já existentes (ex.: 'parameters', 'context',
#    'report_parameters', 'old_value'/'new_value') continuam passando,
#    porque suas chaves são configuração legítima e variável, não um
#    esquema fechado; o conteúdo em texto deles ainda passa pela
#    redação de conteúdo abaixo.
# 2) Redação de CONTEÚDO sensível nos campos de texto que sobrevivem
#    (incluindo o nome de arquivo): um segredo presente no valor de um
#    campo PERMITIDO, ou embutido no próprio nome do arquivo — não só
#    no diretório —, também precisa ser removido; reduzir ao basename
#    por si só não torna seguro um segredo presente no nome em si.
_CHAVES_PERMITIDAS_DETALHES_METADADOS = frozenset({
    # log_file_upload
    'file_name', 'file_type', 'file_size', 'success', 'error_message',
    # log_data_processing
    'process_type', 'input_records', 'output_records',
    'processing_time_seconds', 'success_rate', 'errors',
    # log_matching_layer
    'layer', 'matches_found', 'confidence_avg', 'confidence_min',
    'confidence_max', 'parameters',
    # log_match_decision
    'match_id', 'decision', 'reason', 'original_confidence',
    # log_report_generation
    'formato', 'lote', 'included_matches', 'included_exceptions',
    'report_parameters',
    # log_config_change
    'config_type', 'old_value', 'new_value',
    # log_error
    'error_type', 'stack_trace', 'context',
    # app.py (gestão de usuários) / auth_middleware.log_user_action
    'target_user', 'old_role', 'new_role', 'role', 'details',
})

# JWT: três segmentos base64url separados por ponto, sempre começando
# por "eyJ" (o header `{"..."}` codificado em base64url).
_PADRAO_JWT_RE = re.compile(r'\beyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\b')
# Hash hexadecimal "longo" (MD5=32, SHA-1=40, SHA-256=64 caracteres
# hexadecimais contíguos) — um UUID com hífens (formato usado para
# log_id/session_id/match_id neste módulo) nunca bate aqui, porque os
# hífens quebram a sequência contígua em blocos de no máximo 12 chars.
_PADRAO_HASH_HEX_RE = re.compile(r'\b[a-fA-F0-9]{32,}\b')
# Padrão "rótulo=valor"/"rótulo: valor" para os rótulos sensíveis mais
# comuns — cobre tanto um campo de texto livre ("token=ABC123") quanto
# um nome de arquivo com o mesmo padrão embutido (ex.:
# "relatorio_token=X.csv" — sem \b na frente de propósito, porque "_"
# antes de "token" é caractere de palavra e não conta como fronteira).
# O valor aceito é só [A-Za-z0-9_-] (sem ponto) de propósito: para em
# ".csv"/".ofx" no fim de um nome de arquivo em vez de engolir a
# extensão.
_PADRAO_SEGREDO_ROTULADO_RE = re.compile(
    r'(?i)(senha|password|secret|token|api[_-]?key|hash|jwt|chave)\s*[:=]\s*[A-Za-z0-9_\-]+'
)


def _redigir_conteudo_sensivel(texto: str) -> str:
    """Substitui trechos com formato de segredo (JWT, hash hexadecimal
    longo, "rótulo=valor" tipo "token=..."/"senha=...") por um marcador
    fixo — aplicado a QUALQUER texto que sobreviva a este módulo,
    inclusive nome de arquivo e campos permitidos pela allowlist."""
    texto = _PADRAO_JWT_RE.sub('[REDACTED_JWT]', texto)
    texto = _PADRAO_HASH_HEX_RE.sub('[REDACTED_HASH]', texto)
    texto = _PADRAO_SEGREDO_ROTULADO_RE.sub(lambda m: f"{m.group(1)}=[REDACTED]", texto)
    return texto


def _sanear_texto_auditoria(valor: Any, max_caracteres: int = MAX_TEXTO_AUDITORIA_CARACTERES) -> Any:
    """Substitui caracteres de controle (CR, LF e demais C0/DEL) por
    espaço, redige conteúdo com formato de segredo (JWT/hash/rótulo de
    senha-token) e trunca para no máximo `max_caracteres`. Só atua em
    `str` — números, bool, None, dict e list são devolvidos sem
    alteração, pois não representam texto livre digitado/enviado por
    alguém."""
    if not isinstance(valor, str):
        return valor
    sem_controles = _CONTROLES_AUDITORIA_RE.sub(' ', valor)
    sem_segredos = _redigir_conteudo_sensivel(sem_controles)
    if len(sem_segredos) > max_caracteres:
        return sem_segredos[:max_caracteres] + _MARCADOR_TRUNCAMENTO
    return sem_segredos


def _sanear_nome_arquivo_auditoria(nome: Any) -> Any:
    """Reduz um nome de arquivo controlado pelo usuário ao basename —
    remove qualquer diretório/caminho (inclusive tentativa de path
    traversal, ex.: "../../etc/x.csv" -> "x.csv") — e então aplica o
    saneamento de texto normal (que agora também redige um segredo
    presente no NOME em si, ex. "relatorio_token=X.csv", não só no
    caminho que já foi removido). Só atua em `str`."""
    if not isinstance(nome, str):
        return nome
    return _sanear_texto_auditoria(os.path.basename(nome))


def _sanear_valor_auditoria(valor: Any, chave: Optional[str] = None, nivel_topo: bool = False) -> Any:
    """Aplica o saneamento acima recursivamente a dict/list — usado para
    'details'/'metadata'/'transaction_ids', que podem conter texto livre
    em qualquer nível de aninhamento. A chave 'file_name' (única usada
    hoje para nome de upload, ver log_file_upload) recebe o saneamento de
    NOME DE ARQUIVO em vez do saneamento de texto genérico. `nivel_topo`
    só é True na chamada inicial (a partir de `log_action`, para o
    próprio dict 'details'/'metadata'): só nesse nível a ALLOWLIST de
    chaves é aplicada — dicts aninhados (ex.: 'parameters') não têm suas
    chaves internas filtradas, só o conteúdo de texto saneado."""
    if isinstance(valor, dict):
        itens = valor.items()
        if nivel_topo:
            itens = [(k, v) for k, v in itens if k in _CHAVES_PERMITIDAS_DETALHES_METADADOS]
        return {k: _sanear_valor_auditoria(v, chave=k) for k, v in itens}
    if isinstance(valor, list):
        return [_sanear_valor_auditoria(v, chave=chave) for v in valor]
    if chave == 'file_name':
        return _sanear_nome_arquivo_auditoria(valor)
    return _sanear_texto_auditoria(valor)

class AuditAction(Enum):
    """Ações que podem ser auditadas no sistema"""
    FILE_UPLOAD = "FILE_UPLOAD"
    DATA_PROCESSING = "DATA_PROCESSING"
    MATCHING_EXATO = "MATCHING_EXATO"
    MATCHING_HEURISTICO = "MATCHING_HEURISTICO"
    MATCHING_IA = "MATCHING_IA"
    MATCH_APPROVAL = "MATCH_APPROVAL"
    MATCH_REJECTION = "MATCH_REJECTION"
    REPORT_GENERATION = "REPORT_GENERATION"
    CONFIG_CHANGE = "CONFIG_CHANGE"
    USER_ACTION = "USER_ACTION"
    ERROR = "ERROR"

class AuditSeverity(Enum):
    """Níveis de severidade para logs de auditoria"""
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class AuditLogger:
    """
    Logger de auditoria para registrar todas as ações do sistema
    Mantém trilha completa para compliance e auditoria.

    A trilha é persistida em SQLite (append-only) desde a criação: antes,
    tudo ficava só em self.audit_log (memória do processo), então um
    reinício apagava a auditoria inteira e não havia nenhuma chamada real
    a este logger no fluxo de login/upload/matching — só as definições
    existiam. Isso foi corrigido tanto na persistência quanto na
    integração (ver app.py e pages/importacao_dados.py).
    """

    def __init__(self, db_path: Optional[str] = None):
        self.audit_log = []
        self.session_id = str(uuid.uuid4())
        self.db_path = db_path or os.getenv("CONCILIACAO_AUDIT_DB_PATH", "audit_log.db")
        # Política de rotação por TAMANHO: sem nenhum limite, audit_log.db
        # cresce para sempre. Ao ultrapassar max_size_bytes, o arquivo
        # ATIVO é renomeado com um sufixo de timestamp (arquivo antigo
        # preservado, nunca editado/apagado — continua append-only) e um
        # arquivo novo é iniciado no caminho original. Nenhuma linha
        # existente é tocada; só decide QUANDO começar um arquivo novo.
        self.max_size_bytes = int(os.getenv("CONCILIACAO_AUDIT_MAX_SIZE_MB", "50")) * 1024 * 1024
        self._init_storage()

    def _init_storage(self) -> None:
        conn = sqlite3.connect(self.db_path)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS audit_log (
                log_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                action TEXT NOT NULL,
                user TEXT NOT NULL,
                description TEXT,
                details TEXT,
                severity TEXT,
                transaction_ids TEXT,
                metadata TEXT
            )
        ''')
        conn.commit()
        conn.close()

    def _rotacionar_se_necessario(self) -> None:
        """Arquiva o arquivo ativo se ele já ultrapassou o limite de
        tamanho, e recria um arquivo novo no caminho original."""
        if not os.path.exists(self.db_path):
            return
        if os.path.getsize(self.db_path) < self.max_size_bytes:
            return
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        destino = f"{self.db_path}.{timestamp}"
        if os.path.exists(destino):
            destino = f"{destino}_{uuid.uuid4().hex[:8]}"
        os.rename(self.db_path, destino)
        logger.info("audit_log.db rotacionado por tamanho: histórico preservado em %s", destino)
        self._init_storage()

    def _persist(self, log_entry: Dict[str, Any]) -> None:
        self._rotacionar_se_necessario()
        conn = sqlite3.connect(self.db_path)
        conn.execute('''
            INSERT INTO audit_log
                (log_id, session_id, timestamp, action, user, description, details, severity, transaction_ids, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            log_entry['log_id'],
            log_entry['session_id'],
            log_entry['timestamp'],
            log_entry['action'],
            log_entry['user'],
            log_entry['description'],
            json.dumps(log_entry['details'], default=str, ensure_ascii=False),
            log_entry['severity'],
            json.dumps(log_entry['transaction_ids'], default=str, ensure_ascii=False),
            json.dumps(log_entry['metadata'], default=str, ensure_ascii=False),
        ))
        conn.commit()
        conn.close()

    def log_action(self, 
                   action: AuditAction,
                   user: str = "Sistema",
                   description: str = "",
                   details: Dict[str, Any] = None,
                   severity: AuditSeverity = AuditSeverity.INFO,
                   transaction_ids: List[str] = None,
                   metadata: Dict[str, Any] = None) -> str:
        """
        Registra uma ação no log de auditoria
        
        Args:
            action: Tipo de ação realizada
            user: Usuário ou sistema que realizou a ação
            description: Descrição legível da ação
            details: Detalhes técnicos da ação
            severity: Nível de severidade
            transaction_ids: IDs das transações envolvidas
            metadata: Metadados adicionais
            
        Returns:
            ID do log gerado
        """
        
        log_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()

        # Saneamento único (SEC-R-05, XCRE-52), ANTES de montar o
        # log_entry: tudo que sai daqui — para self.audit_log, para
        # _persist (SQLite) e para log_message (logger padrão, abaixo) —
        # já usa os valores saneados.
        user = _sanear_texto_auditoria(user)
        description = _sanear_texto_auditoria(description)
        details = _sanear_valor_auditoria(details or {}, nivel_topo=True)
        transaction_ids = _sanear_valor_auditoria(transaction_ids or [])
        metadata = _sanear_valor_auditoria(metadata or {}, nivel_topo=True)

        log_entry = {
            'log_id': log_id,
            'session_id': self.session_id,
            'timestamp': timestamp,
            'action': action.value,
            'user': user,
            'description': description,
            'details': details or {},
            'severity': severity.value,
            'transaction_ids': transaction_ids or [],
            'metadata': metadata or {}
        }
        
        self.audit_log.append(log_entry)
        self._persist(log_entry)

        # Log também no sistema de logging padrão
        log_message = f"AUDIT [{severity.value}] {action.value}: {description}"
        if severity == AuditSeverity.ERROR:
            logger.error(log_message)
        elif severity == AuditSeverity.WARNING:
            logger.warning(log_message)
        else:
            logger.info(log_message)
            
        return log_id
    
    def log_file_upload(self, 
                        file_name: str, 
                        file_type: str,
                        file_size: int,
                        user: str = "Sistema",
                        success: bool = True,
                        error_message: str = None) -> str:
        """Log de upload de arquivo"""
        # Reduz ao basename ANTES de compor a descrição (SEC-R-05,
        # XCRE-52): o saneamento genérico de `log_action` só remove
        # caracteres de controle da string já pronta — se um caminho
        # completo fosse interpolado aqui, ele sobreviveria dentro de
        # `description` mesmo com o `details['file_name']` corrigido.
        nome_arquivo_seguro = _sanear_nome_arquivo_auditoria(file_name)
        return self.log_action(
            action=AuditAction.FILE_UPLOAD,
            user=user,
            description=f"Upload de arquivo {file_type}: {nome_arquivo_seguro}",
            details={
                'file_name': nome_arquivo_seguro,
                'file_type': file_type,
                'file_size': file_size,
                'success': success,
                'error_message': error_message
            },
            severity=AuditSeverity.ERROR if not success else AuditSeverity.INFO
        )
    
    def log_data_processing(self,
                           process_type: str,
                           input_records: int,
                           output_records: int,
                           processing_time: float,
                           user: str = "Sistema",
                           errors: List[str] = None) -> str:
        """Log de processamento de dados"""
        return self.log_action(
            action=AuditAction.DATA_PROCESSING,
            user=user,
            description=f"Processamento {process_type}: {input_records} → {output_records} registros",
            details={
                'process_type': process_type,
                'input_records': input_records,
                'output_records': output_records,
                'processing_time_seconds': processing_time,
                'success_rate': (output_records / input_records * 100) if input_records > 0 else 0,
                'errors': errors or []
            }
        )
    
    def log_matching_layer(self,
                          layer: str,
                          matches_found: int,
                          confidence_stats: Dict[str, float],
                          processing_time: float,
                          parameters: Dict[str, Any],
                          user: str = "Sistema") -> str:
        """Log de execução de camada de matching"""
        return self.log_action(
            action=getattr(AuditAction, f"MATCHING_{layer.upper()}"),
            user=user,
            description=f"Matching {layer}: {matches_found} correspondências encontradas",
            details={
                'layer': layer,
                'matches_found': matches_found,
                'confidence_avg': confidence_stats.get('avg', 0),
                'confidence_min': confidence_stats.get('min', 0),
                'confidence_max': confidence_stats.get('max', 0),
                'processing_time_seconds': processing_time,
                'parameters': parameters
            }
        )
    
    def log_match_decision(self,
                          match_id: str,
                          decision: str,  # 'approved' or 'rejected'
                          user: str,
                          reason: str = "",
                          confidence: float = 0,
                          transaction_ids: List[str] = None) -> str:
        """Log de decisão do usuário sobre um match"""
        action = AuditAction.MATCH_APPROVAL if decision == 'approved' else AuditAction.MATCH_REJECTION
        
        return self.log_action(
            action=action,
            user=user,
            description=f"Match {decision}: {match_id} (Confiança: {confidence}%)",
            details={
                'match_id': match_id,
                'decision': decision,
                'reason': reason,
                'original_confidence': confidence
            },
            transaction_ids=transaction_ids or []
        )
    
    def log_report_generation(self,
                             formato: str,
                             user: str,
                             lote: str,
                             success: bool = True,
                             included_matches: int = 0,
                             included_exceptions: int = 0,
                             error_message: Optional[str] = None,
                             report_parameters: Dict[str, Any] = None) -> str:
        """Log de geração de relatório PDF (sucesso ou falha).

        Este método já existia mas nunca era chamado por
        pages/gerar_relatorio.py — CT-AUD-01 (issue XCRE-42) apontou a
        ausência do evento de relatório na auditoria. lote identifica QUAL
        conciliação foi reportada (ex.: conta analisada + período), para
        distinguir gerações de relatórios diferentes sem expor dados
        sensíveis; nenhum segredo (senha, token) é aceito nos campos
        deste método — quem chama é responsável por não passar nenhum."""
        descricao = (
            f"Relatório {formato} gerado para o lote '{lote}': "
            f"{included_matches} matches, {included_exceptions} exceções"
            if success else
            f"Falha ao gerar relatório {formato} para o lote '{lote}': {error_message}"
        )
        return self.log_action(
            action=AuditAction.REPORT_GENERATION,
            user=user,
            description=descricao,
            details={
                'formato': formato,
                'lote': lote,
                'success': success,
                'included_matches': included_matches,
                'included_exceptions': included_exceptions,
                'error_message': error_message,
                'report_parameters': report_parameters or {},
            },
            severity=AuditSeverity.ERROR if not success else AuditSeverity.INFO,
        )
    
    def log_config_change(self,
                         config_type: str,
                         old_value: Any,
                         new_value: Any,
                         user: str,
                         reason: str = "") -> str:
        """Log de mudança de configuração"""
        return self.log_action(
            action=AuditAction.CONFIG_CHANGE,
            user=user,
            description=f"Configuração alterada: {config_type}",
            details={
                'config_type': config_type,
                'old_value': old_value,
                'new_value': new_value,
                'reason': reason
            },
            severity=AuditSeverity.WARNING
        )
    
    def log_error(self,
                 error_type: str,
                 error_message: str,
                 user: str = "Sistema",
                 stack_trace: str = None,
                 context: Dict[str, Any] = None) -> str:
        """Log de erro do sistema"""
        return self.log_action(
            action=AuditAction.ERROR,
            user=user,
            description=f"Erro {error_type}: {error_message}",
            details={
                'error_type': error_type,
                'error_message': error_message,
                'stack_trace': stack_trace,
                'context': context or {}
            },
            severity=AuditSeverity.ERROR
        )
    
    def get_audit_trail(self,
                       filters: Dict[str, Any] = None,
                       sort_by: str = "timestamp",
                       ascending: bool = False,
                       persisted: bool = True) -> pd.DataFrame:
        """
        Retorna a trilha de auditoria como DataFrame

        Args:
            filters: Filtros para aplicar (ex: {'action': 'FILE_UPLOAD', 'severity': 'ERROR'})
            sort_by: Campo para ordenação
            ascending: Ordem ascendente ou descendente
            persisted: se True (padrão), lê o histórico completo persistido em
                disco (sobrevive a reinícios); se False, usa apenas o cache em
                memória desta instância/sessão

        Returns:
            DataFrame com logs de auditoria
        """
        if persisted:
            conn = sqlite3.connect(self.db_path)
            df = pd.read_sql_query("SELECT * FROM audit_log", conn)
            conn.close()
            if df.empty:
                return df
            for col in ('details', 'transaction_ids', 'metadata'):
                df[col] = df[col].apply(lambda v: json.loads(v) if v else ({} if col != 'transaction_ids' else []))
        else:
            if not self.audit_log:
                return pd.DataFrame()
            df = pd.DataFrame(self.audit_log)

        # Aplicar filtros
        if filters:
            for key, value in filters.items():
                if key in df.columns:
                    df = df[df[key] == value]
        
        # Ordenar
        if sort_by in df.columns:
            df = df.sort_values(sort_by, ascending=ascending)
        
        return df
    
    def get_audit_summary(self) -> Dict[str, Any]:
        """Retorna resumo estatístico da auditoria"""
        if not self.audit_log:
            return {}
        
        df = pd.DataFrame(self.audit_log)
        
        summary = {
            'total_actions': len(self.audit_log),
            'session_duration': self._get_session_duration(),
            'actions_by_type': df['action'].value_counts().to_dict(),
            'actions_by_severity': df['severity'].value_counts().to_dict(),
            'actions_by_user': df['user'].value_counts().to_dict(),
            'first_action': df['timestamp'].min() if not df.empty else None,
            'last_action': df['timestamp'].max() if not df.empty else None
        }
        
        return summary
    
    def _get_session_duration(self) -> float:
        """Calcula duração da sessão em segundos"""
        if not self.audit_log:
            return 0
        
        timestamps = [datetime.fromisoformat(log['timestamp']) for log in self.audit_log]
        return (max(timestamps) - min(timestamps)).total_seconds()
    
    def export_audit_log(self,
                        format: str = 'json',
                        include_details: bool = True,
                        persisted: bool = True) -> str:
        """
        Exporta o log de auditoria

        Args:
            format: Formato de exportação ('json', 'csv')
            include_details: Incluir detalhes completos
            persisted: exportar o histórico completo persistido (padrão) em
                vez de apenas o cache em memória da sessão atual

        Returns:
            String com o log exportado
        """
        source = self.get_audit_trail(persisted=persisted).to_dict('records') if persisted else self.audit_log
        if not source:
            return ""

        # copy.deepcopy: a versão anterior fazia list.copy() (cópia rasa) e
        # depois log.pop('details', ...) em cada item — como os dicionários
        # internos continuavam sendo os MESMOS objetos do log original,
        # isso apagava 'details'/'metadata' também do log em memória, não
        # só da exportação resumida.
        export_data = copy.deepcopy(source)

        if not include_details:
            # Remover campos detalhados para versão resumida
            for log in export_data:
                log.pop('details', None)
                log.pop('metadata', None)

        if format == 'json':
            return json.dumps(export_data, indent=2, ensure_ascii=False, default=str)
        elif format == 'csv':
            df = pd.DataFrame(export_data)
            return df.to_csv(index=False, encoding='utf-8')
        else:
            raise ValueError(f"Formato não suportado: {format}")
    
    def clear_audit_log(self):
        """Limpa APENAS o cache em memória da instância atual.

        O histórico persistido (self.db_path, append-only) nunca é apagado
        por este método — uma trilha de auditoria que pode ser destruída
        por uma chamada de código não é uma trilha confiável. Antes, este
        método fazia self.audit_log.clear() sobre a única cópia existente
        dos dados (não havia persistência), ou seja, apagava a auditoria
        de verdade."""
        self.audit_log.clear()
        logger.warning("Cache de auditoria em memória limpo; histórico persistido em %s preservado", self.db_path)

# Instância global do logger de auditoria
_audit_logger = None

def get_audit_logger() -> AuditLogger:
    """Retorna a instância global do logger de auditoria"""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger

# Funções de conveniência para uso rápido
def log_quick_action(action: str, description: str, user: str = "Sistema") -> str:
    """Log rápido de ação sem muitos detalhes"""
    logger = get_audit_logger()
    try:
        audit_action = AuditAction[action.upper()]
    except KeyError:
        audit_action = AuditAction.USER_ACTION
    
    return logger.log_action(
        action=audit_action,
        user=user,
        description=description
    )

def get_session_audit_trail() -> pd.DataFrame:
    """Retorna a trilha de auditoria completa da sessão atual"""
    return get_audit_logger().get_audit_trail()

def export_session_audit() -> str:
    """Exporta a auditoria completa da sessão em JSON"""
    return get_audit_logger().export_audit_log(format='json')

# Exemplo de uso:
"""
# No código do Streamlit:
from modules.audit_logger import get_audit_logger, AuditAction, AuditSeverity

logger = get_audit_logger()

# Log de upload
logger.log_file_upload(
    file_name="extrato.ofx",
    file_type="OFX",
    file_size=1024,
    user="contador@empresa.com"
)

# Log de matching
logger.log_matching_layer(
    layer="exato",
    matches_found=15,
    confidence_stats={'avg': 95, 'min': 80, 'max': 100},
    processing_time=2.5,
    parameters={'tolerancia_dias': 2, 'tolerancia_valor': 0.02}
)

# Log de decisão do usuário
logger.log_match_decision(
    match_id="match_123",
    decision="approved",
    user="contador@empresa.com",
    reason="Correspondência exata por TXID PIX",
    confidence=100
)
"""