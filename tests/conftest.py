from __future__ import annotations

import os
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Iterator, List

import pytest

# carregue o .env o mais cedo possível
env_file = Path(__file__).resolve().parents[1] / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if not line or line.strip().startswith("#"):
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())

# valores de fallback úteis no CI
os.environ.setdefault("EXECUTOR_MODE", "read-only")
os.environ.setdefault(
    "DATABASE_URL", "postgresql://edge_user:***@sirios_db:5432/edge_db"
)


REGISTRY_FIXTURE: Dict[str, Dict[str, Any]] = {
    "view_fiis_history_dividends": {
        "description": "Dividend history for FIIs",
        "default_date_field": "payment_date",
        "identifiers": ["ticker", "payment_date"],
        "columns": [
            {"name": "ticker", "description": "Ticker do FII."},
            {
                "name": "payment_date",
                "description": "Data de pagamento do dividendo.",
                "ask": {
                    "intents": ["dividends"],
                    "synonyms": {"dividends": ["pagamento", "pagou"]},
                    "keywords": ["pagamento"],
                },
            },
            {
                "name": "dividend_amt",
                "description": "Valor do dividendo pago.",
                "ask": {
                    "intents": ["dividends"],
                    "synonyms": {
                        "dividends": ["dividendo", "dividendos", "provento", "yield"]
                    },
                    "keywords": ["dividendo", "rendimentos"],
                    "weights": {"synonyms": 2.5},
                },
            },
            {"name": "created_at", "description": "Data de criação."},
        ],
        "ask": {
            "intents": ["dividends", "historico"],
            "keywords": ["dividendo", "dividendos", "provento", "rendimentos"],
            "synonyms": {
                "dividends": [
                    "dividendo",
                    "dividendos",
                    "provento",
                    "pagamento",
                    "pagamentos",
                    "rendimento",
                ],
                "historico": ["histórico", "linha do tempo"],
            },
            "latest_words": [],  # força uso do fallback global nas rotas
            "intent_tokens": {"historico": ["histórico", "historia"]},
        },
    },
    "view_fiis_history_prices": {
        "description": "Histórico de preços",
        "default_date_field": "traded_at",
        "identifiers": ["ticker", "traded_at"],
        "columns": [
            {"name": "ticker"},
            {"name": "traded_at"},
            {
                "name": "close_price",
                "ask": {
                    "intents": ["precos"],
                    "synonyms": {"precos": ["fechamento", "cotacao"]},
                    "keywords": ["preço", "preços", "cotação"],
                },
            },
        ],
        "ask": {
            "intents": ["precos"],
            "keywords": ["preço", "cotação"],
            "synonyms": {"precos": ["preço", "cotação", "fechamento"]},
        },
    },
    "view_fiis_info": {
        "description": "Informações cadastrais dos FIIs",
        "identifiers": ["ticker"],
        "columns": [
            {"name": "ticker"},
            {"name": "cnpj"},
            {
                "name": "fund_name",
                "ask": {"intents": ["cadastro"], "keywords": ["nome"]},
            },
        ],
        "ask": {
            "intents": ["cadastro"],
            "keywords": ["cadastro", "informações", "dados"],
            "synonyms": {
                "cadastro": ["cadastro", "dados", "informações", "registro"],
            },
        },
    },
}


class DummyRegistryService:
    def __init__(self, docs: Dict[str, Dict[str, Any]]):
        self._docs = deepcopy(docs)

    def _normalize_columns(self, entity: str) -> List[str]:
        doc = self._docs.get(entity) or {}
        cols: List[str] = []
        for col in doc.get("columns", []):
            if isinstance(col, dict):
                name = col.get("name")
                if name:
                    cols.append(name)
            elif isinstance(col, str):
                cols.append(col)
        return cols

    def list_all(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for entity in sorted(self._docs.keys()):
            items.append(
                {
                    "entity": entity,
                    "columns": self._normalize_columns(entity),
                    "identifiers": list(
                        self._docs.get(entity, {}).get("identifiers", [])
                    ),
                }
            )
        return items

    def get(self, entity: str) -> Dict[str, Any] | None:
        doc = self._docs.get(entity)
        if not doc:
            return None
        payload = deepcopy(doc)
        payload["columns"] = self._normalize_columns(entity)
        return payload

    def get_columns(self, entity: str) -> List[str]:
        return self._normalize_columns(entity)

    def get_document(self, entity: str) -> Dict[str, Any] | None:
        doc = self._docs.get(entity)
        if not doc:
            return None
        return deepcopy(doc)

    def iter_documents(self) -> Iterator[tuple[str, Dict[str, Any]]]:
        for entity in sorted(self._docs.keys()):
            yield entity, deepcopy(self._docs[entity])

    def order_by_whitelist(self, entity: str) -> List[str]:
        doc = self._docs.get(entity) or {}
        whitelist = doc.get("order_by_whitelist") or []
        if not whitelist:
            return self._normalize_columns(entity)
        out: List[str] = []
        for col in whitelist:
            if isinstance(col, dict):
                name = col.get("name")
                if name:
                    out.append(name)
            elif isinstance(col, str):
                out.append(col)
        return out

    def reload(self) -> None:  # pragma: no cover - mantido por compatibilidade
        return None


@pytest.fixture(autouse=True)
def orchestrator_registry_stub(monkeypatch: pytest.MonkeyPatch) -> DummyRegistryService:
    from app.orchestrator import planning, scoring, vocab
    from app.registry import service as registry_module

    stub = DummyRegistryService(REGISTRY_FIXTURE)
    monkeypatch.setattr(registry_module, "registry_service", stub)
    monkeypatch.setattr(vocab, "registry_service", stub)
    monkeypatch.setattr(scoring, "registry_service", stub)
    monkeypatch.setattr(planning, "registry_service", stub)

    # invalida o vocabulário para reconstruir com o stub recém-instalado
    vocab.ASK_VOCAB.invalidate()
    yield stub
    vocab.ASK_VOCAB.invalidate()


@pytest.fixture(autouse=True)
def stub_ticker_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.orchestrator import context_builder

    def extract(text: str) -> List[str]:
        if not text:
            return []
        tickers = re.findall(r"[A-Za-z]{4}\d{2}", text)
        return [token.upper() for token in tickers]

    monkeypatch.setattr(context_builder.TICKER_CACHE, "extract", extract)
    yield


class DummyMetric:
    def labels(self, **_kwargs: Any) -> "DummyMetric":
        return self

    def observe(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    def inc(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    def set(self, *_args: Any, **_kwargs: Any) -> None:
        return None


@pytest.fixture
def stub_routing_dependencies(monkeypatch: pytest.MonkeyPatch):
    from app.orchestrator import routing

    class DummyBuilder:
        def __init__(self) -> None:
            self.calls: List[Any] = []

        def build_sql(self, normalized: Any) -> tuple[str, Dict[str, Any]]:
            self.calls.append(normalized)
            return "SELECT 1", {}

    class DummyExecutor:
        def __init__(self) -> None:
            self.calls: List[Any] = []
            self.rows: List[Dict[str, Any]] = [{"ticker": "HGLG11", "valor": "R$ 1,00"}]

        def run(
            self, sql: str, params: Dict[str, Any], row_limit: int = 100
        ) -> List[Dict[str, Any]]:
            self.calls.append((sql, params, row_limit))
            return list(self.rows)

    builder = DummyBuilder()
    executor = DummyExecutor()

    monkeypatch.setattr(routing, "builder_service", builder)
    monkeypatch.setattr(routing, "executor_service", executor)
    monkeypatch.setattr(routing, "to_human", lambda rows: rows)

    for metric_name in (
        "API_LATENCY_MS",
        "ASK_LATENCY_MS",
        "ASK_ROWS",
        "DB_LATENCY_MS",
        "DB_QUERIES",
        "DB_ROWS",
    ):
        monkeypatch.setattr(routing, metric_name, DummyMetric())

    return builder, executor
