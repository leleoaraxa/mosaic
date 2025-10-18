
from __future__ import annotations
import json, logging, re
from typing import List, Set

from app.executor.service import executor_service
from app.infrastructure.cache import get_cache_backend
from app.core.settings import settings

logger = logging.getLogger("orchestrator")

_CACHE = get_cache_backend()
_TICKERS_KEY = "tickers:list:v1"

class TickerCache:
    def __init__(self, backend, cache_key: str, ttl_seconds: int) -> None:
        self._backend = backend
        self._cache_key = cache_key
        self._ttl_seconds = int(ttl_seconds)

    def load(self, force: bool = False) -> Set[str]:
        if not force:
            try:
                raw = self._backend.get(self._cache_key)
                if raw:
                    return set(json.loads(raw))
            except Exception:
                pass
        try:
            return self._refresh()
        except Exception as ex:
            logger.warning("falha ao atualizar cache de tickers: %s", ex)
            return set()

    def _refresh(self) -> Set[str]:
        rows = executor_service.run("SELECT ticker FROM view_fiis_info ORDER BY ticker;", {})
        tickers = [str(r.get("ticker", "")).upper() for r in rows if r.get("ticker")]
        payload = json.dumps(tickers)
        try:
            self._backend.set(self._cache_key, payload, ttl_seconds=self._ttl_seconds)
        except Exception as ex:
            logger.warning("falha ao gravar tickers no cache: %s", ex)
        logger.info("cache de tickers atualizado: %s registros", len(tickers))
        return set(tickers)

    def extract(self, text: str) -> List[str]:
        valid = self.load()
        tokens = re.findall(r"[A-Za-z0-9]{2,}", (text or ""))
        found: List[str] = []
        seen: Set[str] = set()
        has_valid = bool(valid)
        pattern = re.compile(r"^[A-Za-z]{4}\d{2}$")

        for token in tokens:
            candidate = token.upper()
            if has_valid:
                if candidate in valid and candidate not in seen:
                    found.append(candidate); seen.add(candidate)
            elif pattern.fullmatch(candidate) and candidate not in seen:
                found.append(candidate); seen.add(candidate)

        for token in tokens:
            if len(token) == 4 and token.isalpha():
                candidate = token.upper() + "11"
                if has_valid:
                    if candidate in valid and candidate not in seen:
                        found.append(candidate); seen.add(candidate)
                elif candidate not in seen:
                    found.append(candidate); seen.add(candidate)
        return found

TICKER_CACHE = TickerCache(_CACHE, _TICKERS_KEY, settings.tickers_cache_ttl)

def warm_up_ticker_cache() -> None:
    TICKER_CACHE.load(force=True)
