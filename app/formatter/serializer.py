from typing import List, Dict, Any
from datetime import datetime

def _iso_to_br(s: str) -> str:
    try:
        return datetime.strptime(s, "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        return s

def to_human(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for r in rows:
        d = {}
        for k, v in r.items():
            if isinstance(v, str) and (k.endswith("date") or k.endswith("data")):
                d[k] = _iso_to_br(v)
            else:
                d[k] = v
        out.append(d)
    return out
