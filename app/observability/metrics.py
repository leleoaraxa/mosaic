from prometheus_client import Counter, Histogram, Gauge
import os

APP_VERSION = os.environ.get("MOSAIC_VERSION", "dev")
GIT_SHA = os.environ.get("GIT_SHA", "local")

APP_INFO = Gauge("mosaic_app_info", "Build/Version info", ["version", "git_sha"])
APP_INFO.labels(version=APP_VERSION, git_sha=GIT_SHA).set(1)

# ── /ask específicas (com label 'entity')
ASK_LATENCY_MS = Histogram(
    "mosaic_ask_latency_ms",
    "Latência do /ask em milissegundos",
    ["entity"],
    buckets=(10, 25, 50, 100, 250, 500, 1000, 2000, 5000),
)

ASK_ROWS = Counter(
    "mosaic_ask_rows_total",
    "Total de linhas retornadas pelo /ask",
    ["entity"],
)

ASK_ERRORS = Counter(
    "mosaic_ask_errors_total",
    "Total de erros no /ask",
    ["entity", "type"],
)

# ── DB executor (com label 'entity')
DB_LATENCY_MS = Histogram(
    "mosaic_db_latency_ms",
    "Latência de execução no Postgres (ms)",
    ["entity"],
    buckets=(5, 10, 20, 50, 100, 250, 500, 1000, 3000),
)

DB_QUERIES = Counter(
    "mosaic_db_queries_total",
    "Total de queries executadas",
    ["entity"],
)

DB_ROWS = Counter(
    "mosaic_db_rows_total",
    "Total de linhas retornadas pelo executor",
    ["entity"],
)

# ── Saúde e visão geral
APP_UP = Gauge("mosaic_app_up", "Flag de app up (1=up)")

API_LATENCY_MS = Gauge(
    "mosaic_api_latency_ms",
    "Latência do endpoint em milissegundos (última medição)",
    ["endpoint"],
)

API_ERRORS = Counter(
    "mosaic_api_errors_total",
    "Erros por endpoint e tipo",
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


def prime_api_series():
    """
    Garante que as principais séries apareçam em /metrics antes da 1ª chamada.
    Útil para testes e para dashboards que esperam as séries desde o boot.
    """
    # Endpoints principais
    for ep in ("/ask", "/views/run"):
        API_LATENCY_MS.labels(endpoint=ep).set(0.0)
        for etype in ("validation", "runtime"):
            API_ERRORS.labels(endpoint=ep, type=etype).inc(0)

    # Entidade agregada usada nos contadores do orchestrator
    try:
        ASK_LATENCY_MS.labels(entity="__all__").observe(0.0)
        ASK_ROWS.labels(entity="__all__").inc(0)
    except Exception:
        # Se o registro já existir ou algum collector estiver indisponível, ignore
        pass
