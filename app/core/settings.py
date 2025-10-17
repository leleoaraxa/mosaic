# app/core/settings.py
"""Configurações centrais do Sirios Mosaic."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Banco e executor
    database_url: str
    executor_mode: str = "read-only"
    db_schema: str = "public"

    # Limiar mínimo de score e Multi-intenção (quantas entidades executar no máximo)
    ask_top_k: int = 2
    ask_min_score: float = 1.0

    # Observabilidade
    prometheus_url: str = "http://prometheus:9090"
    grafana_url: str = "http://grafana:3000"

    # Logging
    log_format: str = "json"
    log_level: str = "INFO"
    log_file: Optional[str] = None
    log_max_mb: int = 50
    log_backups: int = 3

    # Cache / limites / métricas
    views_cache_ttl: int = 86400
    tickers_cache_ttl: float = 300.0
    ask_default_limit: int = 100
    ask_max_limit: int = 1000
    api_latency_window: int = 60  # segundos (janela para dashboards)
    messages_path: str = "app/core/messages.yaml"

    # NLP / orchestrator
    nlp_relative_dates: bool = True

    # Assinatura de YAMLs (endurecimento opcional do pipeline)
    views_signature_mode: str = "none"  # none|sha256|hmac
    views_signature_key: Optional[str] = None
    views_signature_required: bool = False

    # Redis
    cache_backend: str = "local"  # local|redis
    redis_url: str | None = None
    cache_namespace: str = "mosaic"

    # Pool de DB
    db_pool_min: int = 1
    db_pool_max: int = 10

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # --- mensagens utilitárias ---
    @property
    def messages(self) -> Dict[str, Any]:
        return _load_messages(self.messages_path)

    def get_message(self, *keys: str, default: Optional[str] = None) -> Optional[str]:
        current: Any = self.messages
        for key in keys:
            if not isinstance(current, dict):
                return default
            current = current.get(key)
        if isinstance(current, str):
            return current
        return default


settings = Settings()


@lru_cache(maxsize=1)
def _load_messages(path: str) -> Dict[str, Any]:
    try:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except FileNotFoundError:
        return {}
    except Exception:
        return {}
    return {}
