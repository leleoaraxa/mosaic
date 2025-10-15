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
from app.observability.metrics import ASK_LATENCY_MS, ASK_ROWS

logger = logging.getLogger("orchestrator")

# ---------------------------------------------------------------------------
# 🔹 Utilidades internas (mantêm semântica original)
# ---------------------------------------------------------------------------


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
    for cand in (
        "payment_date",
        "price_date",
        "news_date",
        "indicator_date",
        "tax_date",
        "created_at",
        "updated_at",
    ):
        if cand in _cols(entity):
            return cand
    return None


# ---------------------------------------------------------------------------
# 🔹 Construção da consulta
# ---------------------------------------------------------------------------


def build_run_request(question: str) -> Dict[str, Any]:
    """Interpreta a pergunta e devolve RunViewRequest pronto."""
    valid_tickers = {
        r.get("ticker").upper()
        for r in executor_service.run("SELECT ticker FROM view_fiis_info;", {})
        if r.get("ticker")
    }
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

    rows = executor_service.run(sql, params, row_limit=normalized.limit)
    payload = {
        "request_id": req_id,
        "entity": normalized.entity,
        "rows": len(rows),
        "data": to_human(rows),
        "meta": {"elapsed_ms": int((time.time() - t0) * 1000)},
    }

    logger.info(
        "ASK_ROUTE",
        extra={
            "request_id": req_id,
            "entity": normalized.entity,
            "question": question,
            "rows": len(rows),
            "elapsed_ms": int((time.time() - t0) * 1000),
        },
    )

    ASK_LATENCY_MS.labels(entity=normalized.entity).observe((time.time() - t0) * 1000.0)
    ASK_ROWS.labels(entity=normalized.entity).inc(len(rows))

    return payload
