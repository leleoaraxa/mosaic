from __future__ import annotations
import re
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from dateutil.relativedelta import relativedelta

from app.registry.service import registry_service
from app.core.settings import settings

from .utils import unaccent_lower
from .vocab import ASK_VOCAB


if TYPE_CHECKING:
    from .models import QuestionContext


def _meta(entity: str) -> Dict[str, Any]:
    return registry_service.get(entity) or {}


def _cols(entity: str) -> List[str]:
    return registry_service.get_columns(entity) or []


def default_date_field(entity: str) -> Optional[str]:
    meta = _meta(entity)
    candidate = meta.get("default_date_field")
    if candidate and candidate in _cols(entity):
        return candidate
    cols = _cols(entity)
    for suffix in ("_date", "_until"):
        for col in cols:
            if col.endswith(suffix):
                return col
    for col in cols:
        if col.endswith("_at"):
            return col
    return None


def _parse_date_value(value: Optional[str]) -> Optional[str]:
    if not value or not isinstance(value, str):
        return None
    value = value.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            parsed = datetime.strptime(value, fmt)
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _relative_date_range(text_norm: str) -> Dict[str, str]:
    today = date.today()

    m = re.search(r"ultim[oa]s?\s+(\d+)\s+mes", text_norm)
    if m:
        months = int(m.group(1))
        start = today - relativedelta(months=months)
        return {
            "date_from": start.strftime("%Y-%m-%d"),
            "date_to": today.strftime("%Y-%m-%d"),
        }

    m = re.search(r"(\d+)\s+mes(?:es)?\s+antes", text_norm)
    if m:
        months = int(m.group(1))
        start = today - relativedelta(months=months)
        return {
            "date_from": start.strftime("%Y-%m-%d"),
            "date_to": today.strftime("%Y-%m-%d"),
        }

    if "mes anterior" in text_norm:
        first_this_month = today.replace(day=1)
        last_prev_month = first_this_month - timedelta(days=1)
        first_prev_month = last_prev_month.replace(day=1)
        return {
            "date_from": first_prev_month.strftime("%Y-%m-%d"),
            "date_to": last_prev_month.strftime("%Y-%m-%d"),
        }

    if "ano atual" in text_norm:
        start = date(today.year, 1, 1)
        end = date(today.year, 12, 31)
        return {
            "date_from": start.strftime("%Y-%m-%d"),
            "date_to": end.strftime("%Y-%m-%d"),
        }

    return {}


def _extract_dates_range(text: str) -> Dict[str, str]:
    if not text:
        return {}
    between = re.search(
        r"entre\s+(\d{2}/\d{2}/\d{4})\s+e\s+(\d{2}/\d{2}/\d{4})", text, re.IGNORECASE
    )
    if between:
        date_from = _parse_date_value(between.group(1))
        date_to = _parse_date_value(between.group(2))
        result: Dict[str, str] = {}
        if date_from:
            result["date_from"] = date_from
        if date_to:
            result["date_to"] = date_to
        if result:
            return result

    if not settings.nlp_relative_dates:
        return {}
    return _relative_date_range(unaccent_lower(text))


def resolve_date_range(
    question: str, explicit_range: Optional[Dict[str, Any]]
) -> Dict[str, str]:
    resolved: Dict[str, str] = {}
    if explicit_range:
        start = _parse_date_value(
            explicit_range.get("from") or explicit_range.get("start")
        )
        end = _parse_date_value(explicit_range.get("to") or explicit_range.get("end"))
        if start:
            resolved["date_from"] = start
        if end:
            resolved["date_to"] = end
    inferred = _extract_dates_range(question)
    for key, value in inferred.items():
        resolved.setdefault(key, value)
    return resolved


def plan_question(
    ctx: QuestionContext, entity: str, intent: Optional[str], payload: Dict[str, Any]
) -> Dict[str, Any]:
    tickers = ctx.tickers
    filters: Dict[str, Any] = {}
    planner_filters: Dict[str, Any] = {}

    if tickers:
        planner_filters["tickers"] = tickers
        if "ticker" in _cols(entity):
            filters["ticker"] = tickers if len(tickers) > 1 else tickers[0]

    resolved_range = resolve_date_range(ctx.original, payload.get("date_range"))
    date_field = default_date_field(entity)
    if date_field:
        planner_filters["date_field"] = date_field
    if resolved_range.get("date_from"):
        filters["date_from"] = resolved_range["date_from"]
        planner_filters["date_from"] = resolved_range["date_from"]
    if resolved_range.get("date_to"):
        filters["date_to"] = resolved_range["date_to"]
        planner_filters["date_to"] = resolved_range["date_to"]

    qnorm = ctx.normalized
    ask_meta = ASK_VOCAB.entity_meta(entity)
    latest_words_norm = list(ask_meta.latest_words_normalized)
    order_by = None
    limit = settings.ask_default_limit
    if latest_words_norm and any(word in qnorm for word in latest_words_norm):
        if date_field:
            order_by = {"field": date_field, "dir": "DESC"}
            limit = 1
    elif "entre" in qnorm and date_field:
        order_by = {"field": date_field, "dir": "ASC"}
        limit = min(settings.ask_max_limit, max(settings.ask_default_limit, 1))

    planner = {
        "intents": [intent] if intent else [],
        "entities": (
            [{"intent": intent, "entity": entity}] if intent else [{"entity": entity}]
        ),
        "filters": planner_filters,
    }

    run_request = {
        "entity": entity,
        "select": None,
        "filters": filters or None,
        "order_by": order_by,
        "limit": min(limit, settings.ask_max_limit),
    }

    return {"run_request": run_request, "planner": planner, "tickers": tickers}
