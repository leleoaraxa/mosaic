# app/formatter/serializer.py
from typing import List, Dict, Any
from datetime import datetime
from decimal import Decimal

# ---------------------------------------------------------------------------
# 🔹 utilidades internas
# ---------------------------------------------------------------------------


def _iso_to_br_date(s: str) -> str:
    """
    Converte ISO date/datetime para DD/MM/AAAA.
    Aceita 'YYYY-MM-DD' e variações ISO com 'T' (ignora o horário).
    """
    if not isinstance(s, str):
        return s
    s_trim = s.strip()
    # tenta só data
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(s_trim, fmt).strftime("%d/%m/%Y")
        except Exception:
            pass
    # tenta datetime ISO
    try:
        # remove fuso se existir
        core = s_trim.replace("Z", "").split("")[0]
        # corta milissegundos
        core = core.split(".")[0]
        dt = datetime.strptime(core, "%Y-%m-%dT%H:%M:%S")
        return dt.strftime("%d/%m/%Y")
    except Exception:
        return s


def _to_float(v: Any) -> float | None:
    try:
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, Decimal):
            return float(v)
        if isinstance(v, str):
            # aceita “1.234,56” e “1234.56”
            s = v.strip().replace(".", "").replace(",", ".")
            return float(s)
    except Exception:
        return None
    return None


def _format_currency_brl(v: Any) -> str:
    """Formata valores numéricos em R$ com separador decimal BR."""
    num = _to_float(v)
    if num is None:
        return str(v)
    return f"R$ {num:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _format_percent_br(v: Any) -> str:
    """Formata valores em percentual (0–1 vira 0–100%)."""
    num = _to_float(v)
    if num is None:
        return str(v)
    if abs(num) < 1:
        num *= 100
    return f"{num:.2f}%".replace(".", ",")


def _format_number_br(v: Any) -> str:
    """Formata número sem símbolo (ex.: valores *_value, *_ratio)."""
    num = _to_float(v)
    if num is None:
        return str(v)
    return f"{num:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _format_area_m2(v: Any) -> str:
    """Formata áreas como número  ' m²'."""
    num = _to_float(v)
    if num is None:
        return str(v)
    return f"{num:,.2f} m²".replace(",", "X").replace(".", ",").replace("X", ".")


# ---------------------------------------------------------------------------
# 🔹 conversão principal
# ---------------------------------------------------------------------------
def to_human(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for r in rows:
        d = {}
        for k, v in r.items():
            kl = k.lower()
            # Datas: *_date, *_until, *_at
            if kl.endswith("_date") or kl.endswith("_until") or kl.endswith("_at"):
                d[k] = _iso_to_br_date(v) if isinstance(v, str) else v
            # Preços (R$): *_price, *_amount
            elif kl.endswith("_price") or kl.endswith("_amount"):
                d[k] = _format_currency_brl(v)
            # Percentuais: *_pct, *_range
            elif kl.endswith("_pct") or kl.endswith("_range"):
                d[k] = _format_percent_br(v)
            # Área: *_area
            elif kl.endswith("_area"):
                d[k] = _format_area_m2(v)
            # Números: *_value, *_ratio (sem símbolo)
            elif kl.endswith("_value") or kl.endswith("_ratio"):
                d[k] = _format_number_br(v)
            else:
                d[k] = v

        out.append(d)
    return out
