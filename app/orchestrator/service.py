from __future__ import annotations
from typing import Any, Dict, Optional

from app.core.settings import settings

from .cache import warm_up_ticker_cache
from .models import QuestionContext
from .routing import route_question as _route_question
from .planning import plan_question, default_date_field
from . import (
    context_builder as _context_builder,
)


def build_run_request(
    question: str, overrides: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    ctx = QuestionContext.build(question)
    from .routing import choose_entities_by_ask

    selected = choose_entities_by_ask(ctx, settings.ask_min_score, 1)
    if not selected:
        raise ValueError("Nenhuma entidade encontrada para a pergunta informada.")
    entity, intent, score = selected[0]
    plan = plan_question(ctx, entity, intent, overrides or {})
    return plan["run_request"]


def route_question(payload: Dict[str, Any]) -> Dict[str, Any]:
    return _route_question(payload)


__all__ = [
    "warm_up_ticker_cache",
    "default_date_field",
    "build_run_request",
    "route_question",
    "_context_builder",
]
