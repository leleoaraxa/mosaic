import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from prometheus_client import make_asgi_app

from app.core.settings import settings
from app.executor.service import executor_service
from app.gateway.router import healthz_full
from app.gateway.router import router as gateway_router
from app.observability.logging import (
    RequestIdMiddleware,
    get_logger,
    setup_json_logging,
)
from app.observability.metrics import APP_UP, prime_api_series
from app.orchestrator.service import warm_up_ticker_cache
from app.registry.preloader import preload_views

# inicializa logging antes de criar app
setup_json_logging(
    level=settings.log_level,
    fmt=settings.log_format,
    file_path=settings.log_file,
)
logger = get_logger("mosaic")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Prime series para que apareçam no /metrics antes da primeira requisição
    prime_api_series()
    preload_views()  # 🚀 carrega catálogo no boot (Redis/local)
    # primeira checagem de saúde imediata
    try:
        APP_UP.set(1)
        _ = healthz_full()
        try:
            warm_up_ticker_cache()  # aquece cache de tickers
        except Exception as e:
            logger.warning("warm-up tickers falhou: %s", e)
    except Exception:
        pass

    async def _worker():
        while True:
            try:
                APP_UP.set(1)
                _ = healthz_full()  # atualiza subsistemas e readiness
            except Exception:
                pass
            await asyncio.sleep(30)

    task = asyncio.create_task(_worker())
    try:
        yield
    finally:
        APP_UP.set(0)
        task.cancel()
        try:
            executor_service.pool.close()
        except Exception:
            pass


def create_app() -> FastAPI:
    app = FastAPI(title="Sirios Mosaic", lifespan=lifespan)

    # Middleware para request_id e tempo de requisição
    app.add_middleware(RequestIdMiddleware)

    # Rotas da aplicação
    app.include_router(gateway_router)

    # Expor /metrics (Prometheus)
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)

    return app


app = create_app()
