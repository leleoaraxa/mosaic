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
)

logger = logging.getLogger("orchestrator")

# ---------------------------------------------------------------------------
# 🔹 Utilidades internas (mantêm semântica original)
# ---------------------------------------------------------------------------
# cache simples dos tickers válidos (para não consultar toda hora)
_TICKERS_CACHE = {"ts": 0.0, "ttl": 300.0, "set": set()}


def _load_valid_tickers(force: bool = False) -> set[str]:
    now = time.time()
    if (
        not force
        and _TICKERS_CACHE["set"]
        and (now - _TICKERS_CACHE["ts"] < _TICKERS_CACHE["ttl"])
    ):
        return _TICKERS_CACHE["set"]
    try:
        rows = executor_service.run("SELECT ticker FROM view_fiis_info;", {})
        s = {str(r.get("ticker", "")).upper() for r in rows if r.get("ticker")}
        _TICKERS_CACHE.update({"ts": now, "set": s})
        logger.info(f"cache de tickers atualizado: {len(s)} registros")
        return s
    except Exception as ex:
        logger.warning(f"falha ao atualizar cache de tickers: {ex}")
        return _TICKERS_CACHE["set"] or set()


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
        r"entre\\s+(\\d{2}/\\d{2}/\\d{4})\\s+e\\s+(\\d{2}/\\d{2}/\\d{4})",
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
    # 🔹 heurística genérica por sufixos padrão
    cols = _cols(entity)
    for cand in cols:
        if any(cand.endswith(suf) for suf in ("_date", "_until", "_at")):
            return cand
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
    limit = 100
    qnorm = _unaccent_lower(question)
    if date_field:
        if any(x in qnorm for x in ("ultimo", "último", "mais recente")):
            order_by = {"field": date_field, "dir": "DESC"}
            limit = 1
        elif "entre" in qnorm:
            order_by = {"field": date_field, "dir": "ASC"}
            limit = 500

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

    # ---- Execução com métricas ----
    tdb0 = time.time()
    rows = executor_service.run(sql, params, row_limit=normalized.limit)
    elapsed_db_ms = (time.time() - tdb0) * 1000.0

    entity = normalized.entity
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

    return payload
