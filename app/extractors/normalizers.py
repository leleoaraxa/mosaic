from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime
import re
from app.registry.service import registry_service

class ExtractedRunRequest(BaseModel):
    entity: str
    select: Optional[List[str]] = None
    filters: Dict[str, Any] = {}
    order_by: Optional[Dict[str, str]] = None
    limit: int = 100

def _normalize_ticker(value: str) -> str:
    if not value: return value
    m = re.match(r"^([A-Za-z]{4})(11)?$", value)
    if m:
        return (m.group(1) + "11").upper()
    return value.upper()

def _br_to_iso(date_str: str) -> str:
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except Exception:
            pass
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y-%m-%d")
    except Exception:
        return date_str

def normalize_request(req: Dict[str, Any]) -> ExtractedRunRequest:
    entity = req.get("entity")
    if not registry_service.get(entity):
        raise ValueError(f"entity '{entity}' desconhecida")
    filters = req.get("filters") or {}

    if "ticker" in filters and isinstance(filters["ticker"], str):
        filters["ticker"] = _normalize_ticker(filters["ticker"])

    for k, v in list(filters.items()):
        if any(x in k for x in ["date", "data"]):
            if isinstance(v, str):
                filters[k] = _br_to_iso(v)

    limit = int(req.get("limit") or 100)
    limit = max(1, min(limit, 1000))

    order_by = req.get("order_by")
    return ExtractedRunRequest(
        entity=entity,
        select=req.get("select"),
        filters=filters,
        order_by=order_by,
        limit=limit,
    )

def _normalize_ticker_or_guess(value: str) -> str:
    # HGLG -> HGLG11 ; HGLG11 stays
    return _normalize_ticker(value)

def _normalize_dates_in_filters(filters: Dict[str, Any]) -> Dict[str, Any]:
    norm = dict(filters)
    for k, v in list(filters.items()):
        lk = k.lower()
        if lk.endswith("_from") or lk.endswith("_to") or lk in ("date_from","date_to"):
            if isinstance(v, str):
                norm[k] = _br_to_iso(v)
        # normalize possible single 'date' field too
        if lk.endswith("date") or lk.endswith("data"):
            if isinstance(v, str):
                norm[k] = _br_to_iso(v)
    return norm
