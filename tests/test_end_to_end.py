# tests/test_end_to_end.py
from fastapi.testclient import TestClient
import pytest

from app.executor.service import executor_service
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def stub_executor(monkeypatch):
    def _fake_run(sql, params, row_limit=100):
        return [
            {
                "ticker": "VINO11",
                "cnpj": "00.000.000/0000-00",
                "nickname": "Vino",
            }
        ]

    monkeypatch.setattr(executor_service, "run", _fake_run)
    yield


def test_views_listing():
    r = client.get("/views")
    assert r.status_code == 200
    assert "items" in r.json()


def test_ask_route_basic():
    payload = {
        "question": "me mostra o cadastro do VINO11",
        "client": {
            "client_id": "cli_123",
            "token": "opaque-token",
            "nickname": "Leleo",
            "balance": 123.45,
        },
    }
    r = client.post("/ask", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["original_question"] == payload["question"]
    assert data["client"]["client_id"] == "cli_123"
    assert data["client"]["balance_before"] == 123.45
    assert data["status"]["reason"] == "ok"
    assert data["planner"]["entities"][0]["entity"] == "view_fiis_info"
    assert data["results"]
    intent_key = next(iter(data["results"]))
    assert isinstance(data["results"][intent_key], list)


def test_ask_route_fallback_message():
    r = client.post("/ask", json={"question": "qual é a capital da frança?"})
    assert r.status_code == 200
    data = r.json()
    assert data["status"]["reason"] == "intent_unmatched"
    assert data["results"] == {}
    assert data["planner"]["intents"] == []
