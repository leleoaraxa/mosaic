from __future__ import annotations

import os
from pathlib import Path
import pytest

# 1) Carrega o .env cedo, mas não sobrescreve DATABASE_URL (usa o banco real)
env_file = Path(__file__).resolve().parents[1] / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if not line or line.strip().startswith("#"):
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())

# 2) Aquecer caches reais (vocabulário + tickers) para evitar latência na 1ª chamada
from app.orchestrator.vocab import ASK_VOCAB
from app.orchestrator.service import warm_up_ticker_cache


@pytest.fixture(scope="session", autouse=True)
def _warm_orchestrator_caches() -> None:
    ASK_VOCAB.invalidate()
    warm_up_ticker_cache()
