from __future__ import annotations

from dataclasses import replace

import pytest

from app.orchestrator import scoring
from app.orchestrator.models import QuestionContext


def test_guess_intent_uses_global_tokens():
    intent = scoring.guess_intent(["dividendo", "recente"])
    assert intent == "dividends"


def test_score_entity_relies_on_ontology_when_view_missing_tokens(
    monkeypatch: pytest.MonkeyPatch,
):
    entity = "view_fiis_history_dividends"
    ctx = QuestionContext.build("quero o dividendo do HGLG11")

    original_meta = scoring.ASK_VOCAB.entity_meta(entity)
    stripped_meta = replace(
        original_meta,
        keywords_normalized=(),
        synonym_sources=(),
        intent_tokens={},
    )

    original_entity_meta = scoring.ASK_VOCAB.entity_meta
    monkeypatch.setattr(
        scoring.ASK_VOCAB,
        "entity_meta",
        lambda name: stripped_meta if name == entity else original_entity_meta(name),
    )

    score, intent = scoring.score_entity(ctx, entity)

    assert score > 0
    assert intent == "dividends"


def test_rank_entities_prefers_matching_intent():
    ctx = QuestionContext.build("quero o cadastro do HGLG11")

    rankings = scoring.rank_entities(ctx)
    top = max(rankings, key=lambda item: item.score)

    assert top.entity == "view_fiis_info"
    assert top.intent == "cadastro"
