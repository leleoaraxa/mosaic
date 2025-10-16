# app/registry/preloader.py
"""
Preloader de catálogo de views (YAMLs) com cache Redis/local.

Objetivos:
- Reutilizar catálogo entre instâncias do Mosaic.
- Evitar re-leitura de YAMLs a cada boot.
"""

from __future__ import annotations
import json, hashlib, os
from typing import Dict, Any
from app.core.settings import settings
from app.infrastructure.cache import get_cache_backend
from app.registry.loader import load_views  # já existe


def _hash_views(payload: Dict[str, Dict[str, Any]]) -> str:
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def preload_views() -> Dict[str, Dict[str, Any]]:
    """
    Carrega o catálogo de views (preferindo cache, senão disco).
    Publica no cache se for carregado do disco.
    """
    cache = get_cache_backend()
    key_loaded = "views:loaded"
    ttl = int(settings.views_cache_ttl)

    # 1️⃣ Tenta do cache
    if cache.get(key_loaded) == "1":
        raw_list = cache.get("views:list")
        if raw_list:
            entities = json.loads(raw_list)
            cat: Dict[str, Dict[str, Any]] = {}
            for e in entities:
                raw = cache.get(f"views:{e}")
                if raw:
                    cat[e] = json.loads(raw)
            if cat:
                return cat

    # 2️⃣ Se falhou, carrega do disco
    views_dir = os.environ.get("VIEWS_DIR", os.path.abspath("data/views"))
    catalog = load_views(views_dir)

    # 3️⃣ Publica no cache
    entities = list(catalog.keys())
    cache.set("views:list", json.dumps(entities, ensure_ascii=False), ttl)
    for e, meta in catalog.items():
        cache.set(f"views:{e}", json.dumps(meta, ensure_ascii=False), ttl)
    cache.set("views:hash", _hash_views(catalog), ttl)
    cache.set(key_loaded, "1", ttl)

    return catalog
