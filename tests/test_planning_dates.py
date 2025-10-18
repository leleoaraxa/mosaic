from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest

from app.orchestrator import planning
from app.orchestrator.models import QuestionContext
from app.orchestrator.vocab import ASK_VOCAB


def test_plan_question_uses_global_latest_words_when_missing(
    monkeypatch: pytest.MonkeyPatch,
):
    entity = "view_fiis_history_dividends"
    ASK_VOCAB.invalidate()
    original_meta = ASK_VOCAB.entity_meta(entity)
    patched_meta = replace(original_meta, latest_words_normalized=())

    original_entity_meta = planning.ASK_VOCAB.entity_meta
    monkeypatch.setattr(
        planning.ASK_VOCAB,
        "entity_meta",
        lambda name: patched_meta if name == entity else original_entity_meta(name),
    )

    ctx = QuestionContext.build("último dividendo do HGLG11")

    plan = planning.plan_question(ctx, entity, "dividends", payload={})
    run_request = plan["run_request"]

    assert run_request["limit"] == 1
    assert run_request["order_by"] == {"field": "payment_date", "dir": "DESC"}


def test_plan_question_resolves_relative_month_range(monkeypatch: pytest.MonkeyPatch):
    class FrozenDate(date):
        @classmethod
        def today(cls) -> date:
            return cls(2023, 5, 20)

    monkeypatch.setattr(planning, "date", FrozenDate)

    ctx = QuestionContext.build("mostre os últimos 2 meses de dividendos do HGLG11")

    plan = planning.plan_question(
        ctx, "view_fiis_history_dividends", "dividends", payload={}
    )
    filters = plan["run_request"]["filters"]

    assert filters["date_from"] == "2023-03-20"
    assert filters["date_to"] == "2023-05-20"
