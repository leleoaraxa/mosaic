from __future__ import annotations

from app.orchestrator.vocab import ASK_VOCAB


def test_latest_words_defaults_exposes_ontology_tokens():
    ASK_VOCAB.invalidate()
    defaults = ASK_VOCAB.latest_words_defaults()

    assert "ultimo" in defaults
    assert "recente" in defaults


def test_timewords_defaults_normalizes_accents():
    ASK_VOCAB.invalidate()
    defaults = ASK_VOCAB.timewords_defaults()

    assert "mes passado" in defaults
    assert "ontem" in defaults


def test_global_tokens_merge_ontology_and_views():
    ASK_VOCAB.invalidate()
    tokens = ASK_VOCAB.global_intent_tokens()

    assert "dividendo" in tokens["dividends"]
    assert "pagamento" in tokens["dividends"]


def test_entity_meta_contains_column_level_intent_tokens():
    ASK_VOCAB.invalidate()
    meta = ASK_VOCAB.entity_meta("view_fiis_history_dividends")

    assert "historico" in meta.intent_tokens
    assert "historia" in meta.intent_tokens["historico"]
