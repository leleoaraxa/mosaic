# app/main.py
import asyncio
import os
from fastapi import FastAPI
from prometheus_client import make_asgi_app

from app.observability.metrics import APP_UP
from app.observability.logging import (
    setup_json_logging,
    RequestIdMiddleware,
    get_logger,
)
from app.gateway.router import router as gateway_router
from app.gateway.router import healthz_full

# inicializa logging antes de criar app
setup_json_logging(
    level=os.getenv("LOG_LEVEL", "INFO"),
    fmt=os.getenv("LOG_FORMAT", "json"),
    file_path=os.getenv("LOG_FILE") or None,
)
logger = get_logger("mosaic")


def create_app() -> FastAPI:
    app = FastAPI(title="Sirios Mosaic")

    # Middleware para request_id e tempo de requisição
    app.add_middleware(RequestIdMiddleware)

    # Rotas da aplicação
    app.include_router(gateway_router)

    # Expor /metrics (Prometheus)
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)

    @app.on_event("startup")
    async def _bg_health_poller():
        async def _worker():
            while True:
                try:
                    APP_UP.set(1)
                    _ = healthz_full()  # atualiza subsistemas e readiness
                except Exception:
                    pass
                await asyncio.sleep(30)

        asyncio.create_task(_worker())

    @app.on_event("shutdown")
    async def _shutdown():
        APP_UP.set(0)

    return app


app = create_app()
