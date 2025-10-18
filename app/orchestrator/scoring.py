from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple

from app.registry.service import registry_service
from .models import EntityScore, QuestionContext
from .utils import tokenize, entity_family
from .vocab import ASK_VOCAB


def _meta(entity: str) -> Dict[str, Any]:
    return registry_service.get(entity) or {}


def _cols(entity: str) -> List[str]:
    return registry_service.get_columns(entity) or []


def _intent_matches(entity_intents: List[str], target: Optional[str]) -> bool:
    return bool(target and entity_intents and target in set(entity_intents))


def guess_intent(tokens: List[str]) -> Optional[str]:
    if not tokens:
        return None
    counts: Dict[str, int] = {}
    tset = set(tokens)
    for intent, words in ASK_VOCAB.global_intent_tokens().items():
        hits = len(tset & set(words))
        if hits:
            counts[intent] = hits
    if not counts:
        return None
    best = max(counts.values())
    winners = [k for k, v in counts.items() if v == best]
    return winners[0] if len(winners) == 1 else None


def score_entity(ctx: QuestionContext, entity: str) -> Tuple[float, Optional[str]]:
    tokens = ctx.tokens
    guessed = ctx.guessed_intent
    tset = set(tokens)
    ask_meta = ASK_VOCAB.entity_meta(entity)
    weights = ask_meta.weights

    kwset = set(ask_meta.keywords_normalized)
    keyword_hits = sum(1 for t in tokens if t in kwset)
    score_keywords = keyword_hits * weights.get("keywords", 1.0)

    intent_scores: Dict[str, float] = {}
    for source in ask_meta.synonym_sources:
        intent = source.intent
        token_set = source.tokens
        if not intent or not token_set:
            continue
        hits = len(tset & set(token_set))
        if not hits:
            continue
        weight_syn = float(source.weight or weights.get("synonyms", 2.0))
        score = hits * weight_syn
        intent_scores[intent] = intent_scores.get(intent, 0.0) + score

    best_intent = None
    best_intent_score = 0.0
    for intent, score in intent_scores.items():
        if score > best_intent_score:
            best_intent_score = score
            best_intent = intent

    desc_tokens = set(tokenize((_meta(entity).get("description") or "")))
    score_desc = sum(1 for t in tokens if t in desc_tokens) * 0.5

    bonus = 0.0
    if guessed:
        if best_intent and guessed == best_intent:
            bonus += 3.0
        if _intent_matches(list(ask_meta.intents), guessed):
            bonus += 2.0

    total = score_keywords + best_intent_score + score_desc + bonus

    fam = entity_family(entity)
    global_tokens = ASK_VOCAB.global_intent_tokens()
    boost_targets = set(ask_meta.intents or [])
    if fam:
        boost_targets.add(fam)
    for intent in boost_targets:
        words = global_tokens.get(intent)
        if not words:
            continue
        word_set = set(words)
        seq_hits = sum(1 for t in tokens if t in word_set)
        uniq_hits = len(tset & word_set)
        if seq_hits:
            total += seq_hits * 1.5
        if uniq_hits:
            total += uniq_hits * 2.0
        if guessed and intent == guessed:
            total += 2.0

    dividends_hits = tset & set(global_tokens.get("dividends", ()))
    if dividends_hits:
        if fam == "dividends":
            total += len(dividends_hits) * 2.5
        elif fam == "precos":
            total -= len(dividends_hits) * 1.5

    indicator_hits = tset & set(global_tokens.get("indicadores", ()))
    if indicator_hits:
        if fam == "indicadores" or {"indicadores", "mercado", "taxas"} & set(
            ask_meta.intents
        ):
            total += len(indicator_hits) * 3.0
        else:
            total -= len(indicator_hits) * 1.2

    judicial_hits = tset & set(global_tokens.get("judicial", ()))
    if judicial_hits:
        if fam == "judicial" or "judicial" in ask_meta.intents:
            total += len(judicial_hits) * 2.0
        else:
            total -= len(judicial_hits) * 1.0

    imoveis_hits = tset & set(global_tokens.get("imoveis", ()))
    if fam == "imoveis":
        if imoveis_hits:
            total += len(imoveis_hits) * 1.5
        else:
            total *= 0.4
    elif imoveis_hits and fam == "cadastro":
        total += len(imoveis_hits) * 0.5

    def mentions_processos_ativos(seq: List[str]) -> bool:
        for idx, token in enumerate(seq):
            if token.startswith("process"):
                window = seq[idx + 1 : idx + 4]
                if any(w.startswith("ativo") for w in window):
                    return True
            if token.startswith("ativo"):
                window = seq[max(0, idx - 3) : idx]
                if any(w.startswith("process") for w in window):
                    return True
        return False

    if mentions_processos_ativos(tokens):
        entity_intents = set(ask_meta.intents or [])
        if "judicial" in entity_intents:
            total += 5.0
        if "processos" in entity_intents:
            total += 2.0
        if "ativos" in entity_intents:
            total -= 4.0

    def default_intent_for_entity(name: str) -> Optional[str]:
        n = name.lower()
        if "prices" in n:
            return "precos"
        if "dividends" in n:
            return "dividends"
        if "judicial" in n:
            return "judicial"
        if "info" in n or "cadastro" in n:
            return "cadastro"
        if "assets" in n:
            return "imoveis"
        if "tax" in n or "indicator" in n:
            return "indicadores"
        return None

    if not best_intent:
        inferred = default_intent_for_entity(entity)
        if inferred:
            best_intent = inferred

    if not best_intent and guessed == "precos" and "prices" in (entity or ""):
        best_intent = "precos"

    if not best_intent:
        intents = list(ask_meta.intents)
        if intents:
            best_intent = intents[0]
    if fam and (best_intent is None or best_intent == "historico"):
        best_intent = fam

    return total, best_intent


def rank_entities(ctx: QuestionContext) -> List[EntityScore]:
    items = registry_service.list_all()
    if not items:
        raise ValueError("Catálogo vazio.")
    results: List[EntityScore] = []
    for it in items:
        entity = it["entity"]
        score, intent = score_entity(ctx, entity)
        if score > 0:
            results.append(EntityScore(entity=entity, intent=intent, score=score))
    return results
