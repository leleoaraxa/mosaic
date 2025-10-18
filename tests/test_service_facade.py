from __future__ import annotations

from app.orchestrator.service import (
    build_run_request,
    default_date_field,
    route_question,
)


def test_build_run_request_targets_top_entity():
    run_request = build_run_request("último dividendo do HGLG11")

    assert run_request["entity"] == "view_fiis_history_dividends"
    assert run_request["order_by"] == {"field": "payment_date", "dir": "DESC"}
    assert run_request["limit"] == 1


def test_route_question_facade_forwards_to_routing(stub_routing_dependencies):
    response = route_question({"question": "qual o último dividendo do HGLG11"})

    assert response["status"]["reason"] == "ok"
    assert "dividends" in response["results"]


def test_default_date_field_uses_registry_stub():
    assert default_date_field("view_fiis_history_dividends") == "payment_date"
    assert default_date_field("view_fiis_history_prices") == "traded_at"
