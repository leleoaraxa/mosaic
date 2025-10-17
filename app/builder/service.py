# app/builder/service.py
from typing import Any, Dict, Tuple

from app.extractors.normalizers import ExtractedRunRequest
from app.registry.service import registry_service


class BuilderService:
    def build_sql(self, req: ExtractedRunRequest) -> Tuple[str, Dict[str, Any]]:
        meta = registry_service.get(req.entity) or {}
        columns = meta.get("columns", [])
        identifiers = meta.get("identifiers", [])
        order_wl = registry_service.order_by_whitelist(req.entity)
        default_date_field = meta.get("default_date_field")

        select_cols = req.select or columns or ["*"]
        for c in select_cols:
            if columns and c not in columns:
                raise ValueError(f"coluna '{c}' não permitida para {req.entity}")

        where = []
        params: Dict[str, Any] = {}

        # First pass to collect range pairs
        ranges = {}  # base_field -> {"from": val, "to": val}
        date_from = req.filters.get("date_from")
        date_to = req.filters.get("date_to")

        for k, v in (req.filters or {}).items():
            if k in ("date_from", "date_to"):
                continue
            if k.endswith("_from"):
                base = k[:-5]
                ranges.setdefault(base, {})["from"] = v
                continue
            if k.endswith("_to"):
                base = k[:-3]
                ranges.setdefault(base, {})["to"] = v
                continue

            # Standard filters: equality or IN
            if columns and k not in columns and k not in identifiers:
                raise ValueError(f"filtro '{k}' não permitido para {req.entity}")
            if isinstance(v, (list, tuple)):
                if not v:
                    continue
                placeholder = ", ".join([f"%({k}_{i})s" for i, _ in enumerate(v)])
                where.append(f"{k} IN ({placeholder})")
                for i, val in enumerate(v):
                    params[f"{k}_{i}"] = val
            else:
                where.append(f"{k} = %({k})s")
                params[k] = v

        # Apply explicit ranges *_from/_to
        for base, rt in ranges.items():
            if columns and base not in columns:
                raise ValueError(
                    f"campo '{base}' não permitido para range em {req.entity}"
                )
            if "from" in rt:
                where.append(f"{base} >= %({base}_from)s")
                params[f"{base}_from"] = rt["from"]
            if "to" in rt:
                where.append(f"{base} <= %({base}_to)s")
                params[f"{base}_to"] = rt["to"]

        # Apply generic date_from/date_to using default_date_field or heuristic
        if date_from or date_to:
            date_field = default_date_field

            # 🔹 heurística genérica baseada em sufixos de data
            if not date_field:
                for cand in columns:
                    if any(cand.endswith(suf) for suf in ("_date", "_until", "_at")):
                        date_field = cand
                        break

            if not date_field:
                raise ValueError(
                    "date_from/date_to requerem uma coluna de data (*_date|*_until|*_at) ou 'default_date_field' configurado"
                )

            if date_from:
                where.append(f"{date_field} >= %(date_from)s")
                params["date_from"] = date_from

            if date_to:
                where.append(f"{date_field} <= %(date_to)s")
                params["date_to"] = date_to

        sql = f"SELECT {', '.join(select_cols)} FROM {req.entity}"
        if where:
            sql += " WHERE " + " AND ".join(where)

        if req.order_by:
            field = req.order_by.get("field")
            direction = (req.order_by.get("dir") or "ASC").upper()
            if field not in order_wl:
                raise ValueError(f"order_by '{field}' não permitido para {req.entity}")
            if direction not in ("ASC", "DESC"):
                direction = "ASC"
            sql += f" ORDER BY {field} {direction}"

        sql += f" LIMIT {int(req.limit)}"
        return sql, params


builder_service = BuilderService()
