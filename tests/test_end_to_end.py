# tests/test_end_to_end.py
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_views_listing():
    r = client.get("/views")
    assert r.status_code == 200
    assert "items" in r.json()


def test_ask_route_basic():
    r = client.post("/ask", json={"question": "me mostra o cadastro do VINO11"})
    assert r.status_code == 200
    data = r.json()
    assert data["entity"] == "view_fiis_info"
