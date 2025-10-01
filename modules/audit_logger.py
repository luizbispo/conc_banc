# modules/audit_logger.py
import pandas as pd
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
import logging
import uuid
from enum import Enum

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    Mantém trilha completa para compliance e auditoria
    """
    
    def __init__(self):
        self.audit_log = []
        self.session_id = str(uuid.uuid4())
        
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
        return self.log_action(
            action=AuditAction.FILE_UPLOAD,
            user=user,
            description=f"Upload de arquivo {file_type}: {file_name}",
            details={
                'file_name': file_name,
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
                             report_type: str,
                             user: str,
                             included_matches: int,
                             included_exceptions: int,
                             report_parameters: Dict[str, Any]) -> str:
        """Log de geração de relatório"""
        return self.log_action(
            action=AuditAction.REPORT_GENERATION,
            user=user,
            description=f"Relatório {report_type} gerado: {included_matches} matches, {included_exceptions} exceções",
            details={
                'report_type': report_type,
                'included_matches': included_matches,
                'included_exceptions': included_exceptions,
                'report_parameters': report_parameters
            }
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
                       ascending: bool = False) -> pd.DataFrame:
        """
        Retorna a trilha de auditoria como DataFrame
        
        Args:
            filters: Filtros para aplicar (ex: {'action': 'FILE_UPLOAD', 'severity': 'ERROR'})
            sort_by: Campo para ordenação
            ascending: Ordem ascendente ou descendente
            
        Returns:
            DataFrame com logs de auditoria
        """
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
                        include_details: bool = True) -> str:
        """
        Exporta o log de auditoria
        
        Args:
            format: Formato de exportação ('json', 'csv')
            include_details: Incluir detalhes completos
            
        Returns:
            String com o log exportado
        """
        if not self.audit_log:
            return ""
        
        export_data = self.audit_log.copy()
        
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
        """Limpa o log de auditoria (usar com cuidado!)"""
        self.audit_log.clear()
        logger.warning("Log de auditoria limpo")

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