# app/core/settings.py
"""
Configurações centrais do Sirios Mosaic.
Usa pydantic-settings para permitir overrides via .env ou variáveis do Docker.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    # Banco e executor
    database_url: str
    executor_mode: str = "read-only"
    db_schema: str = "public"

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
    tickers_cache_ttl: float = 300.0  # segundos
    ask_default_limit: int = 100
    ask_max_limit: int = 1000
    api_latency_window: int = 60  # segundos (janela para dashboards)
    # Assinatura de YAMLs (endurecimento opcional do pipeline)
    views_signature_mode: str = "none"  # none|sha256|hmac
    views_signature_key: Optional[str] = None
    views_signature_required: bool = False

    # Redis
    cache_backend: str = "local"  # local|redis
    redis_url: str | None = None
    cache_namespace: str = "mosaic"

    views_cache_ttl: int = 86400
    tickers_cache_ttl: float = 300.0

    # Pool de DB
    db_pool_min: int = 1
    db_pool_max: int = 10

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
