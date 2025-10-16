# app/orchestrator/service.py
"""
Orchestrator NL→SQL do Sirios Mosaic
------------------------------------

Responsável por:
- Interpretar a pergunta em linguagem natural.
- Identificar entidades (views), tickers e períodos.
- Construir requisições RunViewRequest para o executor.

Todo o conteúdo de heurística e regras NL foi movido do gateway.
"""

from __future__ import annotations

import re, time, uuid, hashlib, unicodedata, logging
from typing import Any, Dict, List, Optional
import json

from app.core.settings import settings
from app.infrastructure.cache import get_cache_backend
from app.registry.service import registry_service
from app.extractors.normalizers import ExtractedRunRequest, normalize_request
from app.builder.service import builder_service
from app.executor.service import executor_service
from app.formatter.serializer import to_human
from app.observability.metrics import (
    ASK_LATENCY_MS,
    ASK_ROWS,
    DB_LATENCY_MS,
    DB_QUERIES,
    DB_ROWS,
    API_LATENCY_MS,
)


logger = logging.getLogger("orchestrator")

# ---------------------------------------------------------------------------
# 🔹 Utilidades internas (mantêm semântica original)
# ---------------------------------------------------------------------------
# cache simples dos tickers válidos (para não consultar toda hora)
_CACHE = get_cache_backend()
_TICKERS_KEY = "tickers:list:v1"  # será namespaced pelo NamespacedCache


def _refresh_tickers_cache() -> list[str]:
    """Recarrega do DB e salva no cache com TTL."""
    rows = executor_service.run(
        "SELECT ticker FROM view_fiis_info ORDER BY ticker;", {}
    )
    tickers = [str(r.get("ticker", "")).upper() for r in rows if r.get("ticker")]
    try:
        _CACHE.set(
            _TICKERS_KEY,
            json.dumps(tickers),
            ttl_seconds=int(settings.tickers_cache_ttl),
        )
    except Exception as ex:
        logger.warning(f"falha ao gravar tickers no cache: {ex}")
    logger.info(f"cache de tickers atualizado: {len(tickers)} registros")
    return tickers


def _load_valid_tickers(force: bool = False) -> set[str]:
    """Obtém tickers do cache; se vazio/force, repovoa a partir do DB."""
    if not force:
        try:
            raw = _CACHE.get(_TICKERS_KEY)
            if raw:
                data = json.loads(raw)
                return set(data)
        except Exception:
            pass
    # fallback: repopula
    try:
        return set(_refresh_tickers_cache())
    except Exception as ex:
        logger.warning(f"falha ao atualizar cache de tickers: {ex}")
        return set()


def _unaccent_lower(s: str) -> str:
    if not isinstance(s, str):
        return ""
    return "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    ).lower()


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]{2,}", _unaccent_lower(text or ""))


def _meta(entity: str) -> dict:
    return registry_service.get(entity) or {}


def _cols(entity: str) -> list[str]:
    return registry_service.get_columns(entity) or []


# ---------------------------------------------------------------------------
# 🔹 Extração semântica
# ---------------------------------------------------------------------------


def _extract_tickers(text: str, valid: set[str]) -> list[str]:
    tokens = set(_tokenize(text))
    found: list[str] = []

    # matches exatos
    for t in tokens:
        cand = t.upper()
        if cand in valid:
            found.append(cand)

    # tokens de 4 letras → +11
    for t in tokens:
        if len(t) == 4 and t.isalpha():
            cand = t.upper() + "11"
            if cand in valid and cand not in found:
                found.append(cand)
    return found


def _extract_dates_range(text: str) -> Dict[str, str]:
    m = re.search(
        r"entre\s+(\d{2}/\d{2}/\d{4})\s+e\s+(\d{2}/\d{2}/\d{4})",
        text,
        re.IGNORECASE,
    )
    return {"date_from": m.group(1), "date_to": m.group(2)} if m else {}


# ---------------------------------------------------------------------------
# 🔹 Entidade e colunas
# ---------------------------------------------------------------------------


def _ask_meta(entity: str) -> dict:
    return _meta(entity).get("ask", {}) or {}


def _choose_entity_by_ask(question: str) -> str:
    qtok = set(_tokenize(question))
    items = registry_service.list_all()
    if not items:
        raise ValueError("Catálogo vazio.")
    best, best_score = None, -1
    for it in items:
        e = it["entity"]
        kws = set(_tokenize(" ".join(_ask_meta(e).get("keywords", []))))
        desc_tokens = set(_tokenize((_meta(e).get("description") or "")))
        bag = kws | desc_tokens
        score = sum(1 for t in qtok if t in bag) if bag else 0
        if score > best_score:
            best, best_score = e, score
    if best_score <= 0 and any(i["entity"] == "view_fiis_info" for i in items):
        return "view_fiis_info"
    return best or items[0]["entity"]


def _default_date_field(entity: str) -> Optional[str]:
    m = _meta(entity)
    d = m.get("default_date_field")
    if d and d in _cols(entity):
        return d
    cols = _cols(entity)
    # ordem de preferência
    for suf in ("_date", "_until"):
        for c in cols:
            if c.endswith(suf):
                return c
    for c in cols:
        if c.endswith("_at"):
            return c
    return None


# ---------------------------------------------------------------------------
# 🔹 Construção da consulta
# ---------------------------------------------------------------------------


def build_run_request(question: str) -> Dict[str, Any]:
    """Interpreta a pergunta e devolve RunViewRequest pronto."""
    valid_tickers = _load_valid_tickers()
    entity = _choose_entity_by_ask(question)
    tickers = _extract_tickers(question, valid_tickers)
    filters: Dict[str, Any] = {}
    if tickers and "ticker" in _cols(entity):
        filters["ticker"] = tickers[0]
    filters.update(_extract_dates_range(question))

    order_by = None
    date_field = _default_date_field(entity)
    limit = settings.ask_default_limit
    qnorm = _unaccent_lower(question)
    if date_field:
        if any(x in qnorm for x in ("ultimo", "último", "mais recente")):
            order_by = {"field": date_field, "dir": "DESC"}
            limit = 1
        elif "entre" in qnorm:
            order_by = {"field": date_field, "dir": "ASC"}
            limit = min(settings.ask_max_limit, 500)

    return {
        "entity": entity,
        "select": None,
        "filters": filters or None,
        "order_by": order_by,
        "limit": limit,
    }


# ---------------------------------------------------------------------------
# 🔹 Função principal
# ---------------------------------------------------------------------------


def route_question(question: str) -> Dict[str, Any]:
    """
    Interpreta a pergunta, gera SQL e executa a view.
    Retorna payload pronto para /ask.
    """
    t0 = time.time()
    req_id = str(uuid.uuid4())
    base_req = build_run_request(question)
    normalized: ExtractedRunRequest = normalize_request(base_req)
    sql, params = builder_service.build_sql(normalized)

    entity = normalized.entity
    date_field = _default_date_field(entity)

    # log de depuração (leve e serializável)
    logger.debug(
        "ask.filters",
        extra={
            "request_id": req_id,
            "entity": entity,
            "filters": normalized.filters or {},
            "date_field": date_field,
        },
    )

    # ---- Execução com métricas ----
    tdb0 = time.time()
    rows = executor_service.run(sql, params, row_limit=normalized.limit)
    elapsed_db_ms = (time.time() - tdb0) * 1000.0

    DB_LATENCY_MS.labels(entity=entity).observe(elapsed_db_ms)
    DB_QUERIES.labels(entity=entity).inc()
    DB_ROWS.labels(entity=entity).inc(len(rows))

    payload = {
        "request_id": req_id,
        "entity": entity,
        "rows": len(rows),
        "data": to_human(rows),
        "meta": {"elapsed_ms": int((time.time() - t0) * 1000)},
    }

    logger.info(
        "ASK_ROUTE",
        extra={
            "request_id": req_id,
            "entity": entity,
            "question": question,
            "rows": len(rows),
            "elapsed_ms": int((time.time() - t0) * 1000),
        },
    )

    ASK_LATENCY_MS.labels(entity=entity).observe((time.time() - t0) * 1000.0)
    ASK_ROWS.labels(entity=entity).inc(len(rows))
    ASK_LATENCY_MS.labels(entity="__all__").observe((time.time() - t0) * 1000.0)
    ASK_ROWS.labels(entity="__all__").inc(len(rows))

    # Métricas de API (/ask)
    try:
        API_LATENCY_MS.labels(endpoint="/ask").observe((time.time() - t0) * 1000.0)
    except Exception:
        pass

    return payload
