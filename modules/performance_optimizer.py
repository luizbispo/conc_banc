# modules/performance_optimizer.py
import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import List, Dict, Any, Callable
import pickle
import gzip
import os
import hashlib

@dataclass
class PerformanceConfig:
    CHUNK_SIZE: int = 1000
    CACHE_ENABLED: bool = True
    MEMORY_LIMIT_MB: int = 500

class DataChunker:
    def __init__(self, config: PerformanceConfig = None):
        self.config = config or PerformanceConfig()
    
    def process_in_chunks(self, df: pd.DataFrame, process_func: Callable) -> pd.DataFrame:
        """Processa DataFrame em chunks para evitar memory overflow"""
        if len(df) <= self.config.CHUNK_SIZE:
            return process_func(df)
        
        chunks = []
        for i in range(0, len(df), self.config.CHUNK_SIZE):
            chunk = df.iloc[i:i + self.config.CHUNK_SIZE].copy()
            processed_chunk = process_func(chunk)
            chunks.append(processed_chunk)
        
        return pd.concat(chunks, ignore_index=True)

class CacheManager:
    def __init__(self, cache_dir: str = ".cache"):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
    
    def get_cache_key(self, *args) -> str:
        """Gera chave única baseada nos argumentos"""
        key_string = "|".join(str(arg) for arg in args)
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def get(self, key: str) -> Any:
        cache_file = os.path.join(self.cache_dir, f"{key}.pkl.gz")
        if os.path.exists(cache_file):
            try:
                with gzip.open(cache_file, 'rb') as f:
                    return pickle.load(f)
            except:
                return None
        return None
    
    def set(self, key: str, data: Any):
        cache_file = os.path.join(self.cache_dir, f"{key}.pkl.gz")
        with gzip.open(cache_file, 'wb') as f:
            pickle.dump(data, f)

# Instância global
chunker = DataChunker()
cache_manager = CacheManager()