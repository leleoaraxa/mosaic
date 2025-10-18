from __future__ import annotations
import time
import yaml
from pathlib import Path
from collections import defaultdict
from typing import Any, Dict, List, Set, FrozenSet, Tuple

from app.registry.service import registry_service
from .models import EntityAskMeta, SynonymSource
from .utils import ensure_list, tokenize_list, unaccent_lower, parse_weight


def _load_ontology() -> dict:
    # ajuste o caminho conforme o seu projeto
    path = Path("data/ask/ontology.yaml")
    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


class AskVocabulary:
    def __init__(self, ttl_seconds: int = 60):
        self._ttl_seconds = ttl_seconds
        self._expires_at = 0.0
        self._global_tokens: Dict[str, Set[str]] = {}
        self._entity_meta: Dict[str, EntityAskMeta] = {}
        # Defaults vindos da ontologia global (fallback quando a view não define)
        self._latest_words_defaults: Tuple[str, ...] = ()
        self._timewords_defaults: Tuple[str, ...] = ()

    def invalidate(self) -> None:
        self._expires_at = 0.0

    def _ensure(self) -> None:
        if time.time() >= self._expires_at:
            self._reload()

    def _reload(self) -> None:
        ontology = _load_ontology()
        global_tokens: Dict[str, Set[str]] = defaultdict(set)

        # 1) sementes globais (ontologia)
        ont_intent_tokens = ontology.get("intent_tokens", {}) or {}
        for intent, words in ont_intent_tokens.items():
            for w in ensure_list(words):
                global_tokens[intent].add(unaccent_lower(w))

        # 2) views do registry
        entity_meta: Dict[str, EntityAskMeta] = {}
        for entity, doc in registry_service.iter_documents():
            meta = self._build_entity_meta(doc or {})
            entity_meta[entity] = meta
            for intent, tokens in meta.intent_tokens.items():
                if tokens:
                    global_tokens[intent].update(tokens)

        # salvar defaults globais para fallback no planner
        self._latest_words_defaults = tuple(
            unaccent_lower(w)
            for w in ensure_list(ontology.get("latest_words_defaults", []))
        )
        self._timewords_defaults = tuple(
            unaccent_lower(w)
            for w in ensure_list(ontology.get("timewords_defaults", []))
        )

        self._global_tokens = {k: frozenset(v) for k, v in global_tokens.items()}
        self._entity_meta = entity_meta
        self._expires_at = time.time() + self._ttl_seconds

    def latest_words_defaults(self) -> Tuple[str, ...]:
        """Lista normalizada (lower+unaccent) de 'último/recente' globais da ontologia."""
        self._ensure()
        return self._latest_words_defaults

    def timewords_defaults(self) -> Tuple[str, ...]:
        """Lista normalizada (lower+unaccent) de palavras temporais globais da ontologia."""
        self._ensure()
        return self._timewords_defaults

    def _build_entity_meta(self, doc: Dict[str, Any]) -> EntityAskMeta:
        ask_block = doc.get("ask") or {}
        intents = self._unique(ensure_list(ask_block.get("intents")))
        keywords = ensure_list(ask_block.get("keywords"))
        keywords_norm = list(dict.fromkeys(tokenize_list(keywords)))
        latest_words = ensure_list(ask_block.get("latest_words"))
        latest_norm = [
            unaccent_lower(w)
            for w in latest_words
            if isinstance(w, str) and unaccent_lower(w)
        ]
        weights = self._extract_weights(ask_block, {})
        synonyms_map = self._extract_synonyms(ask_block)
        synonym_sources: List[SynonymSource] = []
        base_syn_weight = weights.get("synonyms", 2.0)
        for intent, words in synonyms_map.items():
            tokens = self._normalize_tokens(words)
            if tokens:
                synonym_sources.append(
                    SynonymSource(
                        intent=intent, tokens=frozenset(tokens), weight=base_syn_weight
                    )
                )

        for col in self._normalize_columns(doc.get("columns")):
            ask_meta = col.get("ask") or {}
            if not isinstance(ask_meta, dict):
                continue
            col_intents = self._unique(ensure_list(ask_meta.get("intents")))
            for intent in col_intents:
                if intent and intent not in intents:
                    intents.append(intent)
            col_synonyms = self._extract_synonyms(ask_meta)
            col_weights = self._extract_weights(ask_meta, weights)
            syn_weight = col_weights.get("synonyms", base_syn_weight)
            for intent, words in col_synonyms.items():
                tokens = self._normalize_tokens(words)
                if tokens:
                    synonym_sources.append(
                        SynonymSource(
                            intent=intent, tokens=frozenset(tokens), weight=syn_weight
                        )
                    )

        intent_tokens = self._extract_intent_tokens(ask_block)

        return EntityAskMeta(
            intents=tuple(intents),
            keywords_normalized=tuple(keywords_norm),
            latest_words_normalized=tuple(latest_norm),
            weights=dict(weights),
            synonym_sources=tuple(synonym_sources),
            intent_tokens=intent_tokens,
        )

    def entity_meta(self, entity: str) -> EntityAskMeta:
        self._ensure()
        return self._entity_meta.get(entity) or EntityAskMeta()

    def global_intent_tokens(self) -> Dict[str, Set[str]]:
        self._ensure()
        return self._global_tokens

    @staticmethod
    def _unique(values: List[str]) -> List[str]:
        seen: Set[str] = set()
        out: List[str] = []
        for v in values:
            if v and v not in seen:
                seen.add(v)
                out.append(v)
        return out

    @staticmethod
    def _normalize_columns(columns: Any) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for col in columns or []:
            if isinstance(col, dict):
                items.append(dict(col))
            elif isinstance(col, str):
                items.append({"name": col})
        return items

    @staticmethod
    def _extract_synonyms(data: Dict[str, Any]) -> Dict[str, List[str]]:
        result: Dict[str, List[str]] = {}
        raw = data.get("synonyms")
        if isinstance(raw, dict):
            for key, value in raw.items():
                result[key] = ensure_list(value)
        for key, value in data.items():
            if isinstance(key, str) and key.startswith("synonyms."):
                intent = key.split(".", 1)[1]
                result[intent] = ensure_list(value)
        return result

    @staticmethod
    def _extract_weights(
        data: Dict[str, Any], base: Dict[str, float]
    ) -> Dict[str, float]:
        weights = dict(base)
        raw = data.get("weights")
        if isinstance(raw, dict):
            for key, value in raw.items():
                weights[key] = parse_weight(value, default=base.get(key, 1.0))
        for key, value in data.items():
            if isinstance(key, str) and key.startswith("weights."):
                name = key.split(".", 1)[1]
                weights[name] = parse_weight(value, default=base.get(name, 1.0))
        if "keywords" not in weights:
            weights["keywords"] = 1.0
        if "synonyms" not in weights:
            weights["synonyms"] = 2.0
        return weights

    @staticmethod
    def _normalize_tokens(values: List[str]) -> Set[str]:
        from .utils import tokenize_list, unaccent_lower

        tokens = set(tokenize_list(values))
        if not tokens:
            tokens = {unaccent_lower(v) for v in values if isinstance(v, str)}
        return {t for t in tokens if t}

    @staticmethod
    def _extract_intent_tokens(data: Dict[str, Any]) -> Dict[str, FrozenSet[str]]:

        result: Dict[str, FrozenSet[str]] = {}
        raw = data.get("intent_tokens")
        if isinstance(raw, dict):
            for key, value in raw.items():
                values = ensure_list(value)
                normalized = {
                    unaccent_lower(v)
                    for v in values
                    if isinstance(v, str) and unaccent_lower(v)
                }
                if normalized:
                    result[key] = frozenset(normalized)
        return result


ASK_VOCAB = AskVocabulary()
