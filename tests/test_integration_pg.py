# tests/test_integration_pg.py
import re
from fastapi.testclient import TestClient
from app.main import app
from app.registry.service import registry_service

client = TestClient(app)


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
    assert payload["entity"] == "view_fiis_info"
    rows = payload.get("rows", 0)
    data = payload.get("data", [])
    assert rows == len(data) and rows >= 1

    # request_id e meta presentes
    assert "request_id" in payload and isinstance(payload["request_id"], str)
    assert "meta" in payload and isinstance(payload["meta"].get("elapsed_ms"), int)

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
    # se o executor estiver indisponível, o endpoint pode marcar 'skipped'; neste caso, falha com mensagem clara
    assert (
        db_cols
    ), f"sem colunas do DB para view_fiis_info: status={info.get('status')}"

    # todas as colunas do YAML devem existir no DB
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
    # Principais métricas expostas pelo app (nomenclatura 'mosaic_*' conforme módulo metrics)
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

    # série da entidade principal deve existir
    assert (
        'mosaic_db_rows_total{entity="view_fiis_info"}' in text
        or "view_fiis_info" in text
    )
