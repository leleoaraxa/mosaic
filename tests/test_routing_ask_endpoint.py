from __future__ import annotations

from app.orchestrator.routing import route_question


def test_route_question_returns_ok_for_known_intent(stub_routing_dependencies):
    response = route_question({"question": "qual o último dividendo do HGLG11"})

    assert response["status"]["reason"] == "ok"
    assert "dividends" in response["results"]
    assert response["planner"]["entities"][0]["entity"] == "view_fiis_history_dividends"


def test_route_question_handles_unknown_intent(stub_routing_dependencies):
    response = route_question({"question": "qual é a capital da frança"})

    assert response["status"]["reason"] == "intent_unmatched"
    assert response["results"] == {}


def test_route_question_supports_hybrid_vocabulary(stub_routing_dependencies):
    response = route_question(
        {"question": "pagamento mais recente de provento do HGLG11"}
    )

    assert response["status"]["reason"] == "ok"
    assert "dividends" in response["results"]
    assert response["planner"]["intents"][0] == "dividends"
