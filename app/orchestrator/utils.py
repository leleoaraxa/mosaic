from __future__ import annotations
import re, unicodedata
from typing import Any, List, Optional


def unaccent_lower(value: str) -> str:
    if not isinstance(value, str):
        return ""
    return "".join(
        c
        for c in unicodedata.normalize("NFD", value)
        if unicodedata.category(c) != "Mn"
    ).lower()


def tokenize(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]{2,}", unaccent_lower(text or ""))


def tokenize_list(values: List[str]) -> List[str]:
    out: List[str] = []
    for v in values or []:
        out.extend(tokenize(v))
    return out


def ensure_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(v) for v in value if isinstance(v, str)]
    if isinstance(value, str):
        return [value]
    return []


def parse_weight(value: Any, default: float = 1.0) -> float:
    if isinstance(value, list) and value:
        return parse_weight(value[0], default=default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def entity_family(entity: str) -> Optional[str]:
    n = (entity or "").lower()
    if "prices" in n:
        return "precos"
    if "dividends" in n:
        return "dividends"
    if "judicial" in n:
        return "judicial"
    if "info" in n or "cadastro" in n:
        return "cadastro"
    if "assets" in n or "properties" in n or "imoveis" in n:
        return "imoveis"
    if "indicator" in n or "indicators" in n or "macro" in n or "tax" in n:
        return "indicadores"
    return None
