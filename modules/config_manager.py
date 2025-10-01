# modules/config_manager.py
import json
import os
from typing import Dict, Any, Optional
from datetime import datetime
import streamlit as st

class ConfigManager:
    """
    Gerenciador de configurações do sistema
    """
    
    def __init__(self):
        self.config_file = "config/conciliacao_config.json"
        self.default_config = {
            "matching": {
                "tolerancia_dias": 2,
                "tolerancia_valor": 0.02,
                "similaridade_minima": 80,
                "permite_1n": True,
                "permite_n1": True,
                "considera_taxas": True
            },
            "processamento": {
                "processar_pdf_ocr": False,
                "tentar_multiplos_encodings": True,
                "limite_transacoes": 10000
            },
            "relatorio": {
                "formato_padrao": "completo",
                "incluir_apendice": True,
                "incluir_auditoria": True,
                "empresa_padrao": "Empresa Exemplo Ltda"
            },
            "seguranca": {
                "log_auditoria": True,
                "retencao_logs_dias": 90,
                "criptografar_dados": False
            }
        }
        self._ensure_config_file()
    
    def _ensure_config_file(self):
        """Garante que o arquivo de configuração existe"""
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        if not os.path.exists(self.config_file):
            self._save_config(self.default_config)
    
    def _load_config(self) -> Dict[str, Any]:
        """Carrega configurações do arquivo"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return self.default_config.copy()
    
    def _save_config(self, config: Dict[str, Any]):
        """Salva configurações no arquivo"""
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    
    def get_config(self, section: Optional[str] = None, key: Optional[str] = None) -> Any:
        """
        Obtém valor de configuração
        
        Args:
            section: Seção da configuração
            key: Chave específica
            
        Returns:
            Valor da configuração
        """
        config = self._load_config()
        
        if section and key:
            return config.get(section, {}).get(key)
        elif section:
            return config.get(section, {})
        else:
            return config
    
    def set_config(self, section: str, key: str, value: Any):
        """Define valor de configuração"""
        config = self._load_config()
        
        if section not in config:
            config[section] = {}
        
        config[section][key] = value
        self._save_config(config)
    
    def get_matching_config(self) -> Dict[str, Any]:
        """Obtém configurações de matching"""
        return self.get_config("matching")
    
    def get_report_config(self) -> Dict[str, Any]:
        """Obtém configurações de relatório"""
        return self.get_config("relatorio")
    
    def reset_to_defaults(self):
        """Restaura configurações padrão"""
        self._save_config(self.default_config)

# Instância global do gerenciador de configurações
_config_manager = None

def get_config_manager() -> ConfigManager:
    """Retorna a instância global do gerenciador de configurações"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager