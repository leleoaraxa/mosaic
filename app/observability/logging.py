# app/observability/logging.py
import os
import logging
import uuid
import contextvars
from typing import Optional
from logging.handlers import RotatingFileHandler

from pythonjsonlogger import jsonlogger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# ────────────────────────────────────────────────────────────────────────────────
# API pública estável:
#   - setup_json_logging(level="INFO", fmt="json", file_path=None)
#   - get_logger(name)
#   - RequestIdMiddleware (injeta request_id no contexto e no response header)
# ────────────────────────────────────────────────────────────────────────────────

# contextvar para carregar o request_id em qualquer log durante a request
_request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default="-"
)


class RequestIdFilter(logging.Filter):
    """Injeta request_id no registro de log (para JSON/Text)."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            record.request_id = _request_id_ctx.get()
        except Exception:
            record.request_id = "-"
        return True


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Gera/propaga X-Request-ID, injeta no contexto e no response."""

    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("x-request-id") or str(uuid.uuid4())
        token = _request_id_ctx.set(rid)
        try:
            # também deixa disponível em request.state
            request.state.request_id = rid
            response: Response = await call_next(request)
            response.headers["X-Request-ID"] = rid
            return response
        finally:
            _request_id_ctx.reset(token)


_LEVELS = {
    "CRITICAL": logging.CRITICAL,
    "ERROR": logging.ERROR,
    "WARNING": logging.WARNING,
    "INFO": logging.INFO,
    "DEBUG": logging.DEBUG,
}

# campos padrão para JSON (inclui request_id!)
_DEFAULT_JSON_FMT = (
    "%(asctime)s %(levelname)s %(name)s %(process)d %(threadName)s "
    "%(message)s %(pathname)s %(lineno)d %(request_id)s"
)


def _ensure_level(level: str) -> int:
    return _LEVELS.get(str(level or "INFO").upper(), logging.INFO)


def _build_console_handler_json() -> logging.Handler:
    handler = logging.StreamHandler()
    formatter = jsonlogger.JsonFormatter(_DEFAULT_JSON_FMT)
    handler.setFormatter(formatter)
    handler.addFilter(RequestIdFilter())
    return handler


def _build_console_handler_text() -> logging.Handler:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s %(name)s [rid=%(request_id)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    handler.addFilter(RequestIdFilter())
    return handler


def _build_file_handler(file_path: str, json_mode: bool) -> logging.Handler:
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    handler = RotatingFileHandler(file_path, maxBytes=10 * 1024 * 1024, backupCount=5)
    if json_mode:
        formatter = jsonlogger.JsonFormatter(_DEFAULT_JSON_FMT)
    else:
        formatter = logging.Formatter(
            fmt="%(asctime)s %(levelname)s %(name)s [rid=%(request_id)s]: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    handler.setFormatter(formatter)
    handler.addFilter(RequestIdFilter())
    return handler


def setup_json_logging(
    level: str = "INFO", fmt: str = "json", file_path: Optional[str] = None
) -> logging.Logger:
    """
    Inicializa logging global.
      - level: "DEBUG"/"INFO"/"WARNING"/"ERROR"/"CRITICAL"
      - fmt: "json" (default) ou "text"
      - file_path: se informado, também loga em arquivo (com rotation)
    """
    logger = logging.getLogger()  # root
    logger.setLevel(_ensure_level(level))

    # remove handlers antigos (evita duplicação em reload)
    for h in list(logger.handlers):
        logger.removeHandler(h)

    json_mode = str(fmt or "json").lower() == "json"
    # console
    logger.addHandler(
        _build_console_handler_json() if json_mode else _build_console_handler_text()
    )

    # arquivo opcional
    if file_path:
        logger.addHandler(_build_file_handler(file_path, json_mode))

    # reduzir ruído de libs verbosas
    logging.getLogger("uvicorn.error").setLevel(_ensure_level(level))
    logging.getLogger("uvicorn.access").setLevel(_ensure_level(level))
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    return logger


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
