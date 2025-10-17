# app/gateway/router.py
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.builder.service import builder_service
from app.core.settings import settings
from app.executor.service import executor_service
from app.extractors.normalizers import ExtractedRunRequest, normalize_request
from app.formatter.serializer import to_human
from app.observability.metrics import (
    API_ERRORS,
    API_LATENCY_MS,
    ASK_ERRORS,
    DB_LATENCY_MS,
    DB_QUERIES,
    DB_ROWS,
)
from app.orchestrator.service import route_question
from app.registry.service import registry_service

# --- pré-registro de séries Prometheus p/ garantir exposição mesmo com zero ---
# latência também (Gauge aparece só após set) – já vamos setar 0 inicial
API_LATENCY_MS.labels(endpoint="/ask").set(0.0)
API_LATENCY_MS.labels(endpoint="/views/run").set(0.0)

for ep in ("/ask", "/views/run"):
    for etype in ("validation", "runtime"):
        API_ERRORS.labels(endpoint=ep, type=etype).inc(0)


def _lbl(x: Optional[str]) -> str:
    return (x or "unknown").strip() or "unknown"


logger = logging.getLogger("gateway")
if not logger.handlers:
    # configuração simples; se você já usa logging no projeto, pode remover este bloco
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )

router = APIRouter()

PROM_URL = settings.prometheus_url
GRAF_URL = settings.grafana_url


# ========================= modelos =========================


class RunViewRequest(BaseModel):
    entity: str
    select: Optional[List[str]] = None
    filters: Optional[Dict[str, Any]] = None
    order_by: Optional[Dict[str, str]] = None
    limit: Optional[int] = Field(default=100)


class AskRequest(BaseModel):
    question: str
    top_k: int = 3  # nº máx. de intenções (entidades) a considerar
    min_ratio: float = 0.6  # corte relativo ao melhor score (0–1)


# ========================= endpoints utilitários =========================
@router.get("/healthz")
def healthz():
    # leve e sempre 200 quando app está de pé
    return {"status": "ok"}


@router.get("/healthz/full")
def healthz_full():
    from app.observability.metrics import set_health  # import local p/ evitar ciclos

    status = {
        "app": "up",
        "db": {"ok": False, "error": None},
        "prometheus": {"ok": False, "error": None},
        "grafana": {"ok": False, "error": None},
    }

    # App está de pé
    set_health("app", True)

    # DB: tentativa leve (limit 1)
    try:
        probe = RunViewRequest(entity="view_fiis_info", select=["ticker"], limit=1)
        _ = _execute_view(probe)  # se falhar, cai no except
        status["db"]["ok"] = True
    except Exception as ex:
        status["db"]["error"] = str(ex)
    finally:
        set_health("db", bool(status["db"]["ok"]))

    # Prometheus readiness
    try:
        with httpx.Client(timeout=2.0) as c:
            r = c.get(f"{PROM_URL}/-/ready")
            ok = (r.status_code == 200) and ("Prometheus" in r.text)
            status["prometheus"]["ok"] = ok
    except Exception as ex:
        status["prometheus"]["error"] = str(ex)
    finally:
        set_health("prometheus", bool(status["prometheus"]["ok"]))

    # Grafana health
    try:
        with httpx.Client(timeout=2.0) as c:
            r = c.get(f"{GRAF_URL}/api/health")
            ok = (r.status_code == 200) and ("database" in r.text)
            status["grafana"]["ok"] = ok
    except Exception as ex:
        status["grafana"]["error"] = str(ex)
    finally:
        set_health("grafana", bool(status["grafana"]["ok"]))

    return status


@router.get("/views")
def list_views():
    return {"items": registry_service.list_all()}


@router.get("/views/{entity}")
def get_view(entity: str):
    meta = registry_service.get(entity)
    if not meta:
        raise HTTPException(404, f"entity '{entity}' not found")
    return meta


@router.get("/views/{entity}/columns")
def get_view_columns(entity: str):
    meta = registry_service.get(entity)
    if not meta:
        raise HTTPException(404, f"entity '{entity}' not found")
    return {"entity": entity, "columns": meta.get("columns", [])}


@router.post("/admin/views/reload")
def reload_registry():
    registry_service.reload()
    return {"status": "ok", "items": registry_service.list_all()}


@router.get("/admin/validate-schema")
def validate_schema():
    items = []
    for v in registry_service.list_all():
        entity = v["entity"]
        yaml_cols = registry_service.get_columns(entity)
        db_cols = executor_service.columns_for(entity)
        if not db_cols:
            items.append(
                {
                    "entity": entity,
                    "status": "skipped (dummy or no DB)",
                    "yaml": yaml_cols,
                    "db": db_cols,
                    "diff": [],
                }
            )
            continue
        missing_in_db = [c for c in yaml_cols if c not in db_cols]
        extra_in_db = [c for c in db_cols if c not in yaml_cols]
        ok = not missing_in_db and not extra_in_db
        items.append(
            {
                "entity": entity,
                "status": "ok" if ok else "mismatch",
                "yaml": yaml_cols,
                "db": db_cols,
                "diff": {"missing_in_db": missing_in_db, "extra_in_db": extra_in_db},
            }
        )
    return {"items": items}


# ========================= executor comum =========================
def _execute_view(req: RunViewRequest):
    t0 = time.time()
    req_id = str(uuid.uuid4())
    try:
        normalized: ExtractedRunRequest = normalize_request(req.model_dump())
        entity = normalized.entity
        sql, params = builder_service.build_sql(normalized)

        tdb0 = time.time()
        rows = executor_service.run(sql, params, row_limit=normalized.limit)
        elapsed_db_ms = (time.time() - tdb0) * 1000.0

        # ── métricas por entidade
        e = _lbl(entity)
        DB_LATENCY_MS.labels(entity=e).observe(elapsed_db_ms)
        DB_QUERIES.labels(entity=e).inc()
        DB_ROWS.labels(entity=e).inc(len(rows))

        return {
            "request_id": req_id,
            "entity": entity,
            "rows": len(rows),
            "data": to_human(rows),
            "meta": {"elapsed_ms": int((time.time() - t0) * 1000)},
        }
    except ValueError as e:
        # validação / entidade desconhecida, etc. → 400
        entity = getattr(req, "entity", None)
        logger.error(
            "EXECUTE_VIEW_VALIDATION_ERROR", extra={"error": str(e), "entity": entity}
        )
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        etype = e.__class__.__name__.lower()
        entity = getattr(req, "entity", None)
        ASK_ERRORS.labels(entity=_lbl(entity), type=etype).inc()
        logger.error("EXECUTE_VIEW_ERROR", extra={"error": str(e), "entity": entity})
        raise


@router.post("/views/run")
def run_view(req: RunViewRequest):
    t0 = time.time()
    try:
        resp = _execute_view(req)
        # era: API_LATENCY_MS.labels(endpoint="/views/run").observe(...)
        API_LATENCY_MS.labels(endpoint="/views/run").set((time.time() - t0) * 1000.0)
        return resp
    except HTTPException:
        API_ERRORS.labels(endpoint="/views/run", type="validation").inc()
        API_LATENCY_MS.labels(endpoint="/views/run").set((time.time() - t0) * 1000.0)
        raise
    except Exception:
        API_ERRORS.labels(endpoint="/views/run", type="runtime").inc()
        API_LATENCY_MS.labels(endpoint="/views/run").set((time.time() - t0) * 1000.0)
        raise


# ========================= /ask orientado por COMMENT =========================
@router.post("/ask")
def ask(req: AskRequest):
    t0 = time.time()
    try:
        result = route_question(req.question)
        API_LATENCY_MS.labels(endpoint="/ask").set((time.time() - t0) * 1000.0)
        return result
    except HTTPException:
        API_ERRORS.labels(endpoint="/ask", type="validation").inc()
        API_LATENCY_MS.labels(endpoint="/ask").set((time.time() - t0) * 1000.0)
        raise
    except Exception:
        API_ERRORS.labels(endpoint="/ask", type="runtime").inc()
        API_LATENCY_MS.labels(endpoint="/ask").set((time.time() - t0) * 1000.0)
        raise
