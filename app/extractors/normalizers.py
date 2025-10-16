# app/extractors/normalizers.py
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
import re
from app.registry.service import registry_service


class ExtractedRunRequest(BaseModel):
    entity: str
    select: Optional[List[str]] = None
    # Evita defaults mutáveis compartilhados entre instâncias
    filters: Dict[str, Any] = Field(default_factory=dict)
    order_by: Optional[Dict[str, str]] = None
    limit: int = 100


def _normalize_ticker(value: str) -> str:
    if not value:
        return value
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


def _normalize_ticker_or_guess(value: str) -> str:
    # HGLG -> HGLG11 ; HGLG11 permanece
    return _normalize_ticker(value)


def _normalize_dates_in_filters(filters: Dict[str, Any]) -> Dict[str, Any]:
    # Cópia defensiva
    norm = dict(filters)
    for k, v in list(filters.items()):
        lk = k.lower()
        if lk.endswith("_from") or lk.endswith("_to") or lk in ("date_from", "date_to"):
            if isinstance(v, str):
                norm[k] = _br_to_iso(v)
        if lk.endswith("date") or lk.endswith("data") or lk.endswith("_until") or lk.endswith("_at"):
            if isinstance(v, str):
                norm[k] = _br_to_iso(v)
    return norm


def normalize_request(req: Dict[str, Any]) -> ExtractedRunRequest:
    # Cópia defensiva da requisição para evitar mutação externa
    req_local = dict(req or {})
    entity = req_local.get("entity")
    if not registry_service.get(entity):
        raise ValueError(f"entity '{entity}' desconhecida")
    # Cópia defensiva dos filtros
    raw_filters = req_local.get("filters") or {}
    filters = dict(raw_filters)

    if "ticker" in filters and isinstance(filters["ticker"], str):
        filters["ticker"] = _normalize_ticker_or_guess(filters["ticker"])

    # Normalização unificada de datas (inclui *_from/_to e ...date/data)
    filters = _normalize_dates_in_filters(filters)

    limit = int(req_local.get("limit") or 100)
    limit = max(1, min(limit, 1000))

    # Cópia defensiva de order_by (se existir)
    order_by = dict(req_local.get("order_by") or {}) or None
    return ExtractedRunRequest(
        entity=entity,
        select=req_local.get("select"),
        filters=dict(filters),
        order_by=order_by,
        limit=limit,
    )
