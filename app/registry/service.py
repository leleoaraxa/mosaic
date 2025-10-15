# app/registry/service.py
import os
from typing import Dict, Any, List, Optional
from app.registry.loader import load_views


class RegistryService:
    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self.reload()

    def reload(self):
        views_dir = os.environ.get("VIEWS_DIR", os.path.abspath("data/views"))
        self._cache = load_views(views_dir)

    def _colnames(self, entity: str) -> List[str]:
        meta = self._cache.get(entity) or {}
        cols = meta.get("columns") or []
        out: List[str] = []
        for c in cols:
            if isinstance(c, str):
                out.append(c)
            elif isinstance(c, dict):
                name = c.get("name")  # <- nome real no DB
                if name:
                    out.append(name)
        return out

    def list_all(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for k in sorted(self._cache.keys()):
            items.append(
                {
                    "entity": k,
                    "columns": self._colnames(k),
                    "identifiers": self._cache[k].get("identifiers", []),
                }
            )
        return items

    def get(self, entity: str) -> Optional[Dict[str, Any]]:
        m = self._cache.get(entity)
        if not m:
            return None
        copy = dict(m)
        copy["columns"] = self._colnames(entity)
        return copy

    def get_columns(self, entity: str) -> List[str]:
        return self._colnames(entity)

    def get_identifiers(self, entity: str) -> List[str]:
        meta = self._cache.get(entity) or {}
        return meta.get("identifiers", [])

    def order_by_whitelist(self, entity: str) -> List[str]:
        meta = self.get(entity) or {}
        wl = meta.get("order_by_whitelist") or []
        if not wl:
            return self._colnames(entity)
        out: List[str] = []
        for c in wl:
            if isinstance(c, str):
                out.append(c)
            elif isinstance(c, dict):
                name = c.get("name")  # <- idem
                if name:
                    out.append(name)
        return out


registry_service = RegistryService()
