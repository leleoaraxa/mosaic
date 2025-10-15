# app/observability/metrics.py
from prometheus_client import Counter, Histogram, Gauge
import os

APP_VERSION = os.environ.get("MOSAIC_VERSION", "dev")
GIT_SHA = os.environ.get("GIT_SHA", "local")

APP_INFO = Gauge("mosaic_app_info", "Build/Version info", ["version", "git_sha"])
APP_INFO.labels(version=APP_VERSION, git_sha=GIT_SHA).set(1)

# ── /ask específicas (agora com label 'entity')
ASK_LATENCY_MS = Histogram(
    "mosaic_ask_latency_ms",
    "Latência do /ask em milissegundos",
    ["entity"],  # <- add
    buckets=(10, 25, 50, 100, 250, 500, 1000, 2000, 5000),
)

ASK_ROWS = Counter(
    "mosaic_ask_rows_total",
    "Total de linhas retornadas pelo /ask",
    ["entity"],  # <- add
)

ASK_ERRORS = Counter(
    "mosaic_ask_errors_total",
    "Total de erros no /ask",
    ["entity", "type"],  # <- add 'entity'
)

# ── DB executor (com label 'entity')
DB_LATENCY_MS = Histogram(
    "mosaic_db_latency_ms",
    "Latência de execução no Postgres (ms)",
    ["entity"],  # <- add
    buckets=(5, 10, 20, 50, 100, 250, 500, 1000, 3000),
)

DB_QUERIES = Counter(
    "mosaic_db_queries_total",
    "Total de queries executadas",
    ["entity"],  # <- add
)

DB_ROWS = Counter(
    "mosaic_db_rows_total",
    "Total de linhas retornadas pelo executor",
    ["entity"],  # <- add
)

# ── Saúde e visão geral (mantém como está)
APP_UP = Gauge("mosaic_app_up", "Flag de app up (1=up)")

API_LATENCY_MS = Histogram(
    "mosaic_api_latency_ms",
    "Latência por endpoint em ms",
    ["endpoint"],
    buckets=(10, 25, 50, 100, 250, 500, 1000, 2000, 5000),
)

API_ERRORS = Counter(
    "mosaic_api_errors_total",
    "Erros por endpoint",
    ["endpoint", "type"],
)

# Saúde: 1=ok, 0=degradado
HEALTH_OK = Gauge(
    "mosaic_health_ok",
    "Estado de saúde por componente (1=ok, 0=degradado)",
    ["component"],  # db, prometheus, grafana, app
)


def set_health(component: str, ok: bool):
    HEALTH_OK.labels(component=component).set(1.0 if ok else 0.0)


# opcional: inicializa em “desconhecido” (0) até primeira checagem
for comp in ("app", "db", "prometheus", "grafana"):
    HEALTH_OK.labels(component=comp).set(0.0)
