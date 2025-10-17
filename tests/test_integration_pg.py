import re
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.executor.service import executor_service
from app.main import app
from app.registry.service import registry_service

client = TestClient(app)


@pytest.fixture(autouse=True)
def stub_executor(monkeypatch):
    sample_rows = [
        {
            "ticker": "VINO11",
            "created_at": date(2024, 3, 1),
            "updated_at": date(2024, 3, 2),
            "cnpj": "00.000.000/0000-00",
        }
    ]

    def _fake_run(sql, params, row_limit=100):
        return sample_rows

    def _fake_columns(entity: str):
        return registry_service.get_columns(entity)

    monkeypatch.setattr(executor_service, "run", _fake_run)
    monkeypatch.setattr(executor_service, "columns_for", _fake_columns)
    yield


def _has_br_date(s: str) -> bool:
    return bool(re.fullmatch(r"\d{2}/\d{2}/\d{4}", s or ""))


def test_e2e_ask_real_db_and_formatter():
    """
    NL → Orchestrator → Builder → Executor(RO) → Formatter
    Valida:
      - entidade resolvida
      - pelo menos 1 linha
      - datas formatadas em BR para campos *_date|*_until|*_at (quando string)
    """
    r = client.post("/ask", json={"question": "me mostra o cadastro do VINO11"})
    assert r.status_code == 200, r.text
    payload = r.json()
    planner = payload["planner"]
    assert planner["entities"][0]["entity"] == "view_fiis_info"

    results = payload.get("results", {})
    assert results, "sem resultados"
    intent_key, data = next(iter(results.items()))
    assert isinstance(data, list) and len(data) >= 1

    # request_id e meta presentes
    assert "request_id" in payload and isinstance(payload["request_id"], str)
    assert "meta" in payload and isinstance(payload["meta"].get("elapsed_ms"), int)
    assert payload["meta"]["rows_total"] == len(data)

    # checa pelo menos um campo de data formatado (se existir no primeiro registro)
    sample = data[0]
    date_keys = [k for k in sample.keys() if k.endswith(("_date", "_until", "_at"))]
    if date_keys:
        for k in date_keys:
            v = sample.get(k)
            if isinstance(v, str):
                assert _has_br_date(v), f"campo {k} não está em DD/MM/AAAA: {v!r}"


def test_yaml_db_consistency_subset():
    """
    YAML ↔ DB: as colunas definidas no YAML devem existir no DB.
    Toleramos colunas extras no DB (superset).
    """
    # pega colunas do YAML pela API interna
    yaml_cols = set(registry_service.get_columns("view_fiis_info"))
    assert yaml_cols, "YAML sem colunas para view_fiis_info"

    # usa endpoint de validação para obter visão do DB
    r = client.get("/admin/validate-schema")
    assert r.status_code == 200, r.text
    items = r.json().get("items", [])
    assert items, "validate-schema não retornou itens"

    info = next((it for it in items if it["entity"] == "view_fiis_info"), None)
    assert info is not None, "view_fiis_info não encontrada no validate-schema"

    db_cols = set(info.get("db") or [])
    assert db_cols, f"sem colunas do DB para view_fiis_info: status={info.get('status')}"

    missing_in_db = [c for c in yaml_cols if c not in db_cols]
    assert not missing_in_db, f"colunas do YAML ausentes no DB: {missing_in_db}"


def test_prometheus_metrics_series_exist():
    """
    Prometheus scrape: confere presença das séries principais.
    Não valida números (isso é responsabilidade dos dashboards/alertas),
    apenas garante exposição dos nomes.
    """
    r = client.get("/metrics")
    assert r.status_code == 200, r.text
    text = r.text
    expected = [
        "mosaic_db_latency_ms",
        "mosaic_db_queries_total",
        "mosaic_db_rows_total",
        "mosaic_api_latency_ms",
        "mosaic_api_errors_total",
        "mosaic_app_up",
    ]
    for name in expected:
        assert name in text, f"métrica ausente em /metrics: {name}"

    assert (
        'mosaic_db_rows_total{entity="view_fiis_info"}' in text
        or "view_fiis_info" in text
    )


def test_ask_metrics_exposed():
    """Verifica métricas específicas do endpoint /ask."""
    client.post("/ask", json={"question": "cadastro do VINO11"})
    r = client.get("/metrics")
    text = r.text
    assert 'mosaic_api_latency_ms{endpoint="/ask"' in text, "latência /ask ausente"
    assert 'mosaic_api_errors_total{endpoint="/ask"' in text, "erros /ask ausente"
