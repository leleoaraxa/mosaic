# app/formatter/serializer.py
from typing import List, Dict, Any, Optional, Union
from datetime import datetime, date
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

Number = Union[int, float, Decimal]


DATE_SUFFIXES = ("_date", "_until", "_at")
MONEY_SUFFIXES = ("_amt", "_price")
LEGACY_MONEY_SUFFIXES = ("_amount",)
PERCENT_SUFFIXES = ("_pct",)
AREA_SUFFIXES = ("_area",)
VALUE_SUFFIXES = ("_value",)
RATIO_SUFFIXES = ("_ratio",)
FOUR_DECIMAL_SUFFIXES = RATIO_SUFFIXES
THREE_DECIMAL_SUFFIXES = ("_rate", "_share", "_alpha", "_index")
INT_SUFFIXES = ("_count",)

# ---------- Datas ----------
_ISO_DATE_PREFIX = re.compile(r"^\d{4}-\d{2}-\d{2}")


def _to_br_from_dateobj(d: Union[date, datetime]) -> str:
    return d.strftime("%d/%m/%Y")


def _iso_to_br_date(s: str) -> str:
    """
    Converte:
      - 'YYYY-MM-DD' -> 'DD/MM/YYYY'
      - 'YYYY-MM-DDTHH:MM:SS(.fff)?(Z|±HH:MM)?' -> 'DD/MM/YYYY'
    Caso não reconheça, retorna s inalterado.
    """
    try:
        if not isinstance(s, str) or not _ISO_DATE_PREFIX.match(s):
            return s
        return datetime.strptime(s[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        return s


# ---------- Números em BR ----------
def _to_decimal(x: Any) -> Optional[Decimal]:
    if isinstance(x, Decimal):
        return x
    if isinstance(x, (int, float)):
        return Decimal(str(x))
    if isinstance(x, str):
        s = x.strip()
        if not s:
            return None
        try:
            return Decimal(s)
        except InvalidOperation:
            s2 = s.replace(".", "").replace(",", ".")
            try:
                return Decimal(s2)
            except InvalidOperation:
                return None
    return None


def _fmt_br(n: Decimal, places: int) -> str:
    q = Decimal(10) ** -places
    n = n.quantize(q, rounding=ROUND_HALF_UP)
    s = f"{n:f}"
    if "." in s:
        int_part, frac = s.split(".")
    else:
        int_part, frac = s, ""
    int_part_with_sep = ""
    while len(int_part) > 3:
        int_part_with_sep = "." + int_part[-3:] + int_part_with_sep
        int_part = int_part[:-3]
    int_part_with_sep = int_part + int_part_with_sep
    if places > 0:
        frac = (frac + "0" * places)[:places]
        return f"{int_part_with_sep},{frac}"
    else:
        return int_part_with_sep


def _fmt_money_br(x: Any) -> Optional[str]:
    d = _to_decimal(x)
    if d is None:
        return None
    return f"R$ {_fmt_br(d, 2)}"


def _fmt_value_br(x: Any, places: int = 2) -> Optional[str]:
    d = _to_decimal(x)
    if d is None:
        return None
    return _fmt_br(d, places)


def _fmt_percent_br(x: Any) -> Optional[str]:
    d = _to_decimal(x)
    if d is None:
        return None
    if d.copy_abs() <= Decimal("1"):
        d = d * Decimal(100)
    return f"{_fmt_br(d, 2)} %"


def _fmt_int_br(x: Any) -> Optional[str]:
    d = _to_decimal(x)
    if d is None:
        return None
    return _fmt_br(d, 0)


def _format_field(key: str, val: Any) -> Any:
    # Datas por sufixo (aceita date/datetime ou string ISO)
    if any(key.endswith(suf) for suf in DATE_SUFFIXES):
        if isinstance(val, (date, datetime)):
            return _to_br_from_dateobj(val)
        if isinstance(val, str):
            return _iso_to_br_date(val)
        return val

    # Moeda (novos + legado)
    if any(key.endswith(suf) for suf in MONEY_SUFFIXES + LEGACY_MONEY_SUFFIXES):
        out = _fmt_money_br(val)
        return out if out is not None else val

    # Percentual
    if any(key.endswith(suf) for suf in PERCENT_SUFFIXES) or key.endswith("_range"):
        out = _fmt_percent_br(val)
        return out if out is not None else val

    # Área m² (2 casas)
    if any(key.endswith(suf) for suf in AREA_SUFFIXES):
        num = _fmt_value_br(val, 2)
        return f"{num} m²" if num is not None else val

    # Valores com 2 casas padrão
    if any(key.endswith(suf) for suf in VALUE_SUFFIXES):
        out = _fmt_value_br(val, 2)
        return out if out is not None else val

    # Razões com 4 casas
    if any(key.endswith(suf) for suf in FOUR_DECIMAL_SUFFIXES):
        out = _fmt_value_br(val, 4)
        return out if out is not None else val

    # Taxas/índices com 3 casas
    if any(key.endswith(suf) for suf in THREE_DECIMAL_SUFFIXES):
        out = _fmt_value_br(val, 3)
        return out if out is not None else val

    # Contadores inteiros
    if any(key.endswith(suf) for suf in INT_SUFFIXES):
        out = _fmt_int_br(val)
        return out if out is not None else val

    return val


def to_human(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for r in rows:
        d: Dict[str, Any] = {}
        for k, v in r.items():
            d[k] = _format_field(k, v)
        out.append(d)
    return out
