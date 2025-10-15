# tests/test_ask_errors.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_run_view_entity_inexistente():
    r = client.post("/views/run", json={"entity": "view_inexistente", "limit": 1})
    assert r.status_code in (400, 404)
