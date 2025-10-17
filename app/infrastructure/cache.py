# app/infrastructure/cache.py
"""
Infraestrutura de cache unificado do Sirios Mosaic.

Suporta:
  - RedisCacheBackend (via redis-py)
  - LocalCacheBackend (fallback em memória)
Ambos seguem a interface CacheBackend (get/set/delete).
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Optional

from app.core.settings import settings


# ---------------------------------------------------------------------
# 🔹 Interfaces base
# ---------------------------------------------------------------------
class CacheBackend(ABC):
    @abstractmethod
    def get(self, key: str) -> Optional[str]:
        pass

    @abstractmethod
    def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        pass

    @abstractmethod
    def delete(self, key: str) -> None:
        pass


# ---------------------------------------------------------------------
# 🔹 Implementações
# ---------------------------------------------------------------------
class LocalCacheBackend(CacheBackend):
    """Cache em memória com TTL simples (para fallback)."""

    def __init__(self):
        self._store: dict[str, tuple[str, Optional[float]]] = {}

    def get(self, key: str) -> Optional[str]:
        v = self._store.get(key)
        if not v:
            return None
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
    """Cache Redis (usa redis-py sync)."""

    def __init__(self, url: str):
        import redis  # lazy import

        self._r = redis.from_url(url, decode_responses=True)

    def get(self, key: str) -> Optional[str]:
        try:
            return self._r.get(key)
        except Exception:
            return None

    def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        try:
            if ttl_seconds:
                self._r.setex(key, ttl_seconds, value)
            else:
                self._r.set(key, value)
        except Exception:
            pass

    def delete(self, key: str) -> None:
        try:
            self._r.delete(key)
        except Exception:
            pass


# ---------------------------------------------------------------------
# 🔹 Wrapper de namespace
# ---------------------------------------------------------------------
class NamespacedCache(CacheBackend):
    def __init__(self, inner: CacheBackend, prefix: str):
        self.inner = inner
        self.prefix = prefix.rstrip(":") + ":"

    def _k(self, k: str) -> str:
        return f"{self.prefix}{k}"

    def get(self, key: str) -> Optional[str]:
        return self.inner.get(self._k(key))

    def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        self.inner.set(self._k(key), value, ttl_seconds)

    def delete(self, key: str) -> None:
        self.inner.delete(self._k(key))


# ---------------------------------------------------------------------
# 🔹 Factory global
# ---------------------------------------------------------------------
def get_cache_backend() -> CacheBackend:
    """Seleciona backend com base nas settings (redis|local)."""
    if settings.cache_backend == "redis" and settings.redis_url:
        try:
            backend = RedisCacheBackend(settings.redis_url)
        except ModuleNotFoundError:
            # Redis client não instalado → fallback automático para cache local.
            backend = LocalCacheBackend()
        except Exception:
            # Qualquer falha na conexão inicial também cai no fallback local.
            backend = LocalCacheBackend()
    else:
        backend = LocalCacheBackend()
    return NamespacedCache(backend, prefix=settings.cache_namespace)
