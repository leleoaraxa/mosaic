from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, FrozenSet


@dataclass(frozen=True)
class SynonymSource:
    intent: str
    tokens: FrozenSet[str]
    weight: float


@dataclass(frozen=True)
class EntityAskMeta:
    intents: Tuple[str, ...] = ()
    keywords_normalized: Tuple[str, ...] = ()
    latest_words_normalized: Tuple[str, ...] = ()
    weights: Dict[str, float] = field(
        default_factory=lambda: {"keywords": 1.0, "synonyms": 2.0}
    )
    synonym_sources: Tuple[SynonymSource, ...] = ()
    intent_tokens: Dict[str, FrozenSet[str]] = field(default_factory=dict)


@dataclass
class QuestionContext:
    original: str
    normalized: str
    tokens: List[str]
    tickers: List[str]
    guessed_intent: Optional[str]
    has_domain_anchor: bool


@dataclass
class EntityScore:
    entity: str
    intent: Optional[str]
    score: float


from .context_builder import build_context as _build_context


def _qc_build(question: str) -> "QuestionContext":
    return _build_context(question)


# Monkey-patch classmethod (keeps external API)
QuestionContext.build = staticmethod(_qc_build)
