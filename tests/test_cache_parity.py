import os

os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres")

from app.core.settings import settings
from app.infrastructure.cache import LocalCacheBackend, NamespacedCache, get_cache_backend
from app.registry import preloader


class MemoryCache(LocalCacheBackend):
    """Permite compartilhar o estado do LocalCache em testes."""

    pass


def _namespaced(cache: LocalCacheBackend) -> NamespacedCache:
    return NamespacedCache(cache, prefix=settings.cache_namespace)


def test_preload_views_local_vs_redis_parity(monkeypatch):
    original_backend = settings.cache_backend
    try:
        # 1️⃣ Ambiente local padrão
        monkeypatch.setattr(preloader, "get_cache_backend", lambda: _namespaced(LocalCacheBackend()))
        settings.cache_backend = "local"
        local_catalog = preloader.preload_views()

        # 2️⃣ Ambiente "redis" com backend em memória compartilhado
        shared = MemoryCache()
        monkeypatch.setattr(preloader, "get_cache_backend", lambda: _namespaced(shared))
        settings.cache_backend = "redis"

        cold_load = preloader.preload_views()
        warm_load = preloader.preload_views()

        assert cold_load == warm_load == local_catalog
    finally:
        settings.cache_backend = original_backend


def test_get_cache_backend_fallback_without_redis(monkeypatch):
    from app import infrastructure

    original_backend = settings.cache_backend
    original_url = settings.redis_url
    try:
        settings.cache_backend = "redis"
        settings.redis_url = "redis://localhost:6379/0"

        def _raise_module_not_found(url: str):  # pragma: no cover - behaviour asserted below
            raise ModuleNotFoundError("redis")

        monkeypatch.setattr(infrastructure.cache, "RedisCacheBackend", _raise_module_not_found)

        backend = get_cache_backend()
        assert isinstance(backend.inner, LocalCacheBackend)
    finally:
        settings.cache_backend = original_backend
        settings.redis_url = original_url
