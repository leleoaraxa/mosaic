from __future__ import annotations

from app.orchestrator.models import QuestionContext


def test_question_context_build_includes_tokens_and_tickers():
    question = "Qual o último dividendo do HGLG11?"

    ctx = QuestionContext.build(question)

    assert ctx.original == question
    assert "ultimo" in ctx.tokens
    assert "dividendo" in ctx.tokens
    assert ctx.tickers == ["HGLG11"]
    assert ctx.has_domain_anchor is True


def test_question_context_uses_global_tokens_for_anchor():
    ctx = QuestionContext.build("quero dividendo atualizado")

    assert ctx.has_domain_anchor is True
    assert ctx.guessed_intent == "dividends"
