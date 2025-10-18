from __future__ import annotations
from typing import List

from .models import QuestionContext
from .cache import TICKER_CACHE
from .utils import unaccent_lower, tokenize
from .scoring import guess_intent
from .vocab import ASK_VOCAB


def has_domain_anchor(tokens: List[str]) -> bool:
    if not tokens:
        return False
    domain = set()
    for words in ASK_VOCAB.global_intent_tokens().values():
        domain.update(words)
    tset = set(tokens)
    return bool(tset & domain)


def build_context(question: str) -> QuestionContext:
    question = question or ""
    tokens = tokenize(question)
    tickers = TICKER_CACHE.extract(question)
    guessed = guess_intent(tokens)
    anchor = bool(tickers) or has_domain_anchor(tokens)
    return QuestionContext(
        original=question,
        normalized=unaccent_lower(question),
        tokens=tokens,
        tickers=tickers,
        guessed_intent=guessed,
        has_domain_anchor=anchor,
    )
