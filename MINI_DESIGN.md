# Mini Design — CacheAdapter + Preloader Redis (Mosaic v3/v4)

## 0) Objetivo

* Substituir caches em memória por Redis (quando disponível).
* Carregar e compartilhar o **catálogo de views** (YAMLs) no boot via Redis, com verificação por hash.
* Manter compatível com ambiente sem Redis (fallback em memória).

---

## 1) Arquitetura (visão rápida)

```
+-----------------------+             +-----------------------+
|  app/core/settings.py |             |  app/infrastructure/  |
|  (config central)     |             |  cache.py             |
+-----------+-----------+             +-----------+-----------+
            |                                     |
            | settings.cache_backend=redis        |  CacheBackend
            | settings.redis_url=redis://...      |   ├─ RedisCacheBackend
            v                                     |   └─ LocalCacheBackend
+-----------+-----------+                         |
|  app/registry/        |<------------------------+
|  service.py           |   usa cache para views (preloader)
+-----------+-----------+
            ^
            |
            | usa cache leve (tickers)
+-----------+-----------+
|  app/orchestrator/    |
|  service.py           |
+-----------------------+
```

---

## 2) Arquivos (novos/alterados)

**Novos**

* `app/infrastructure/cache.py` (adapter)
* `app/registry/preloader.py` (boot loader de catálogo)
* `docs/ops/redis_cache.md` (nota operacional curta)

**Alterados**

* `app/core/settings.py` (novas vars)
* `app/orchestrator/service.py` (usar cache p/ tickers)
* `app/registry/service.py` (tentar ler catálogo do cache; fallback disco; opcionalmente publicar no cache)
* `app/main.py` (startup: chamar preloader)

---

## 3) Configuração (settings)

`.env` (exemplo)

```
# Cache
CACHE_BACKEND=redis             # redis | local
REDIS_URL=redis://mosaic-redis:6379/0
CACHE_NAMESPACE=mosaic

# Catálogo
VIEWS_CACHE_TTL=86400           # 24h (ajustável)
VIEWS_SIGNATURE_MODE=none       # none|sha256|hmac
VIEWS_SIGNATURE_KEY=            # se hmac
VIEWS_SIGNATURE_REQUIRED=false

# Tickers
TICKERS_CACHE_TTL=300
```

`app/core/settings.py` (novos campos)

```python
cache_backend: str = "local"          # local|redis
redis_url: str | None = None
cache_namespace: str = "mosaic"

views_cache_ttl: int = 86400
tickers_cache_ttl: float = 300.0
```

---

## 4) Cache Adapter (interface & chaves)

**Interface mínima**

```python
# app/infrastructure/cache.py
from abc import ABC, abstractmethod
from typing import Any, Optional
import json, time

class CacheBackend(ABC):
    @abstractmethod
    def get(self, key: str) -> Optional[str]: ...
    @abstractmethod
    def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None: ...
    @abstractmethod
    def delete(self, key: str) -> None: ...

class LocalCacheBackend(CacheBackend):
    def __init__(self):
        self._store = {}  # key -> (value, expire_ts|None)
    def get(self, key: str) -> Optional[str]:
        v = self._store.get(key)
        if not v: return None
        value, exp = v
        if exp and exp < time.time():
            self._store.pop(key, None)
            return None
        return value
    def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        exp = time.time() + ttl_seconds if ttl_seconds else None
        self._store[key] = (value, exp)
    def delete(self, key: str) -> None:
        self._store.pop(key, None)

class RedisCacheBackend(CacheBackend):
    def __init__(self, url: str):
        import redis  # redis-py sync
        self._r = redis.from_url(url, decode_responses=True)
    def get(self, key: str) -> Optional[str]:
        return self._r.get(key)
    def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        if ttl_seconds: self._r.setex(key, ttl_seconds, value)
        else: self._r.set(key, value)
    def delete(self, key: str) -> None:
        self._r.delete(key)

# factory
def get_cache_backend(settings) -> CacheBackend:
    ns = settings.cache_namespace.rstrip(":")
    if settings.cache_backend == "redis" and settings.redis_url:
        backend = RedisCacheBackend(settings.redis_url)
    else:
        backend = LocalCacheBackend()
    # wrap com namespace
    return NamespacedCache(backend, prefix=f"{ns}:")

class NamespacedCache(CacheBackend):
    def __init__(self, inner: CacheBackend, prefix: str):
        self.inner, self.prefix = inner, prefix
    def _k(self, k: str) -> str: return f"{self.prefix}{k}"
    def get(self, key: str): return self.inner.get(self._k(key))
    def set(self, key: str, value: str, ttl_seconds: int | None = None):
        return self.inner.set(self._k(key), value, ttl_seconds)
    def delete(self, key: str): return self.inner.delete(self._k(key))
```

**Naming (chaves Redis)**

```
mosaic:tickers:list                -> JSON list[str]  | TTL = settings.tickers_cache_ttl
mosaic:views:list                  -> JSON list[str]  | TTL = settings.views_cache_ttl
mosaic:views:{entity}              -> JSON metadata   | TTL = settings.views_cache_ttl
mosaic:views:hash                  -> SHA256 catálogo | TTL = settings.views_cache_ttl
mosaic:views:loaded                -> "1"             | TTL = settings.views_cache_ttl
```

---

## 5) Preloader do Catálogo (boot)

`app/registry/preloader.py`

```python
import json, hashlib, os
from typing import Dict, Any
from app.core.settings import settings
from app.infrastructure.cache import get_cache_backend
from app.registry.loader import load_views  # já existe

def _hash_views(payload: Dict[str, Dict[str, Any]]) -> str:
    # hash determinístico por JSON ordenado
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()

def preload_views() -> Dict[str, Dict[str, Any]]:
    cache = get_cache_backend(settings)

    # 1) tenta do cache
    if cache.get("views:loaded") == "1":
        entities = json.loads(cache.get("views:list") or "[]")
        cat: Dict[str, Dict[str, Any]] = {}
        for e in entities:
            raw = cache.get(f"views:{e}")
            if raw:
                cat[e] = json.loads(raw)
        if cat:
            return cat  # sucesso via cache

    # 2) carrega do disco
    views_dir = os.environ.get("VIEWS_DIR", os.path.abspath("data/views"))
    catalog = load_views(views_dir)

    # 3) publica no cache
    entities = list(catalog.keys())
    ttl = int(settings.views_cache_ttl)
    cache.set("views:list", json.dumps(entities), ttl)
    for e, meta in catalog.items():
        cache.set(f"views:{e}", json.dumps(meta, ensure_ascii=False), ttl)
    cache.set("views:hash", _hash_views(catalog), ttl)
    cache.set("views:loaded", "1", ttl)
    return catalog
```

**Integração**

* `app/registry/service.py::__init__`
  Tentar `preload_views()` **antes** do `load_views()` atual.
  Se vier vazio do cache → cai no disco e **depois** publica (acima já publica).
* `app/gateway/router.py:/admin/views/reload`
  Ao recarregar do disco, chamar `preload_views()` para repopular o Redis.

---

## 6) Orchestrator — cache de tickers

Trocar dicionário local por cache:

```python
# app/orchestrator/service.py
from app.infrastructure.cache import get_cache_backend
from app.core.settings import settings
import json, time

_cache = get_cache_backend(settings)

def _load_valid_tickers(force: bool = False) -> set[str]:
    key = "tickers:list"
    if not force:
        raw = _cache.get(key)
        if raw:
            return set(json.loads(raw))
    rows = executor_service.run("SELECT ticker FROM view_fiis_info;", {})
    s = {str(r.get("ticker","")).upper() for r in rows if r.get("ticker")}
    _cache.set(key, json.dumps(sorted(s)), int(settings.tickers_cache_ttl))
    return s
```

---

## 7) Métricas & Logs

* Expor `mosaic_views_reloaded_total` (Counter) em `/admin/views/reload`.
* Opcional: `mosaic_cache_hit_total` / `mosaic_cache_miss_total` com labels `kind=(tickers|views)`.
* Logar `views_hash` no boot (facilita auditoria de catálogo carregado).

---

## 8) Segurança

* Sanitizar `entity` em `executor.columns_for` (já alinhado no seu P0 anterior).
* Se `views_signature_mode=hmac`, verificar assinatura antes de publicar no Redis (pipeline “hardening” quando necessário).
* Namespace obrigatório (`settings.cache_namespace`) para não colidir com outras apps no mesmo Redis.

---

## 9) Falhas & Comportamento

| Situação                          | Comportamento                                                            |
| --------------------------------- | ------------------------------------------------------------------------ |
| Redis indisponível                | Fallback automático para `LocalCacheBackend`; o sistema continua.        |
| Catálogo ausente no Redis         | Carrega do disco e publica.                                              |
| Catálogo divergente (hash trocou) | `/admin/views/reload` repopula; dashboards podem alertar hash diferente. |
| TTL expirado                      | Recarrega sob demanda (tickers) ou permanece até reload (views).         |

---

## 10) Testes (essenciais)

* **Unit:** `test_cache_local_backend`, `test_cache_redis_backend` (mock do `redis`).
* **Registry:** `test_preloader_uses_cache_then_disk` (simula cache vazio → disco → cache).
* **E2E:** subir sem Redis (local), com Redis (real ou fake), conferir:

  * `/views` responde igual nos dois modos
  * `/admin/views/reload` incrementa `mosaic_views_reloaded_total`
* **Perf leve:** medir latência do `_load_valid_tickers` com e sem Redis.

---

## 11) Rollout sugerido

1. v3.1 — **CacheAdapter + tickers em Redis** (feature flag via `CACHE_BACKEND`).
2. v4.0 — **Preloader de views** no Redis; `/admin/views/reload` repovoa; expor hash em log/metrics.
3. v4.1 — Broadcast de reload (opcional) e `cache_hits/misses` em Prometheus.

---
