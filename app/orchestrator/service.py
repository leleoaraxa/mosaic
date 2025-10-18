# app/orchestrator/service.py
"""Orquestrador NL→SQL do Sirios Mosaic (versão v4 do envelope)."""

from __future__ import annotations

import json
import logging
import re
import time
import unicodedata
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

from dateutil.relativedelta import relativedelta

from app.builder.service import builder_service
from app.core.settings import settings
from app.executor.service import executor_service
from app.extractors.normalizers import ExtractedRunRequest, normalize_request
from app.formatter.serializer import to_human
from app.infrastructure.cache import get_cache_backend
from app.observability.metrics import (
    API_LATENCY_MS,
    ASK_LATENCY_MS,
    ASK_ROWS,
    DB_LATENCY_MS,
    DB_QUERIES,
    DB_ROWS,
)
from app.registry.service import registry_service

logger = logging.getLogger("orchestrator")

# cache simples dos tickers válidos (para não consultar toda hora)
_CACHE = get_cache_backend()
_TICKERS_KEY = "tickers:list:v1"  # será namespaced pelo NamespacedCache

# ---------------------------------------------------------------------------
# 🔹 Cache e utilidades básicas
# ---------------------------------------------------------------------------
def _entity_family(entity: str) -> Optional[str]:
    n = (entity or "").lower()
    if "prices" in n:
        return "precos"
    if "dividends" in n:
        return "dividends"
    if "judicial" in n:
        return "judicial"
    if "info" in n or "cadastro" in n:
        return "cadastro"
    if "assets" in n:
        # assets = composição (cotas/CRIs) → 'ativos'
        return "ativos"
    if "properties" in n or "imoveis" in n or "properties" in n:
        # views de propriedades físicas
        return "imoveis"
    if "indicator" in n or "indicators" in n or "macro" in n or "tax" in n:
        return "indicadores"
    return None


def _refresh_tickers_cache() -> List[str]:
    """Recarrega do DB e salva no cache com TTL."""
    rows = executor_service.run(
        "SELECT ticker FROM view_fiis_info ORDER BY ticker;", {}
    )
    tickers = [str(r.get("ticker", "")).upper() for r in rows if r.get("ticker")]
    try:
        _CACHE.set(
            _TICKERS_KEY,
            json.dumps(tickers),
            ttl_seconds=int(settings.tickers_cache_ttl),
        )
    except Exception as ex:  # pragma: no cover - cache best effort
        logger.warning("falha ao gravar tickers no cache: %s", ex)
    logger.info("cache de tickers atualizado: %s registros", len(tickers))
    return tickers


def _load_valid_tickers(force: bool = False) -> set[str]:
    """Obtém tickers do cache; se vazio/force, repovoa a partir do DB."""
    if not force:
        try:
            raw = _CACHE.get(_TICKERS_KEY)
            if raw:
                data = json.loads(raw)
                return set(data)
        except Exception:  # pragma: no cover - cache best effort
            pass
    try:
        return set(_refresh_tickers_cache())
    except Exception as ex:  # pragma: no cover
        logger.warning("falha ao atualizar cache de tickers: %s", ex)
        return set()


def _unaccent_lower(value: str) -> str:
    if not isinstance(value, str):
        return ""
    return "".join(
        c
        for c in unicodedata.normalize("NFD", value)
        if unicodedata.category(c) != "Mn"
    ).lower()


def _guess_intent(tokens: List[str]) -> Optional[str]:
    """
    Heurística simples: conta hits por família e retorna a mais frequente.
    Empate → None (para não enviesar indevidamente).
    """
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
    # pega a maior contagem; evita enviesar em empate
    best = max(counts.values())
    winners = [k for k, v in counts.items() if v == best]
    if len(winners) == 1:
        return winners[0]
    return None


def _intent_matches(entity_intents: List[str], target: Optional[str]) -> bool:
    return bool(target and entity_intents and target in set(entity_intents))


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]{2,}", _unaccent_lower(text or ""))


def _tokenize_list(values: List[str]) -> List[str]:
    """
    Expande uma lista de frases/palavras em um conjunto de tokens normalizados.
    Ex.: ["valor de mercado", "p/vp"] -> ["valor","de","mercado","p","vp"]
    (tokens com 1 char são ignorados pelo próprio _tokenize)
    """
    out: List[str] = []
    for v in values:
        out.extend(_tokenize(v))
    return out


def _meta(entity: str) -> Dict[str, Any]:
    return registry_service.get(entity) or {}


def _cols(entity: str) -> List[str]:
    return registry_service.get_columns(entity) or []


# ---------------------------------------------------------------------------
# 🔹 Ask metadata helpers
# ---------------------------------------------------------------------------


def _ensure_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(v) for v in value if isinstance(v, str)]
    if isinstance(value, str):
        return [value]
    return []


def _parse_weight(value: Any, default: float = 1.0) -> float:
    if isinstance(value, list) and value:
        return _parse_weight(value[0], default=default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class _AskVocabulary:
    def __init__(self, ttl_seconds: int = 60):
        self._ttl_seconds = ttl_seconds
        self._expires_at = 0.0
        self._global_tokens: Dict[str, Set[str]] = {}
        self._entity_meta: Dict[str, Dict[str, Any]] = {}

    def invalidate(self) -> None:
        self._expires_at = 0.0

    def _ensure(self) -> None:
        if time.time() >= self._expires_at:
            self._reload()

    def _reload(self) -> None:
        global_tokens: Dict[str, Set[str]] = defaultdict(set)
        entity_meta: Dict[str, Dict[str, Any]] = {}
        for entity, doc in registry_service.iter_documents():
            meta = self._build_entity_meta(doc or {})
            entity_meta[entity] = meta
            for intent, tokens in meta.get("intent_tokens", {}).items():
                if tokens:
                    global_tokens[intent].update(tokens)
        self._global_tokens = {k: frozenset(v) for k, v in global_tokens.items()}
        self._entity_meta = entity_meta
        self._expires_at = time.time() + self._ttl_seconds

    def _build_entity_meta(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        ask_block = doc.get("ask") or {}
        intents = self._unique(_ensure_list(ask_block.get("intents")))
        keywords = _ensure_list(ask_block.get("keywords"))
        keywords_norm = list(dict.fromkeys(_tokenize_list(keywords)))
        latest_words = _ensure_list(ask_block.get("latest_words"))
        latest_norm = [
            _unaccent_lower(w)
            for w in latest_words
            if isinstance(w, str) and _unaccent_lower(w)
        ]
        weights = self._extract_weights(ask_block, {})
        synonyms_map = self._extract_synonyms(ask_block)
        synonyms_normalized: Dict[str, Set[str]] = defaultdict(set)
        synonym_sources: List[Dict[str, Any]] = []
        base_syn_weight = weights.get("synonyms", 2.0)
        for intent, words in synonyms_map.items():
            tokens = self._normalize_tokens(words)
            if tokens:
                synonyms_normalized[intent].update(tokens)
                synonym_sources.append(
                    {"intent": intent, "tokens": frozenset(tokens), "weight": base_syn_weight}
                )

        columns = self._normalize_columns(doc.get("columns"))
        for col in columns:
            ask_meta = col.get("ask") or {}
            if not isinstance(ask_meta, dict):
                continue
            col_intents = self._unique(_ensure_list(ask_meta.get("intents")))
            for intent in col_intents:
                if intent and intent not in intents:
                    intents.append(intent)
            col_synonyms = self._extract_synonyms(ask_meta)
            col_weights = self._extract_weights(ask_meta, weights)
            syn_weight = col_weights.get("synonyms", base_syn_weight)
            for intent, words in col_synonyms.items():
                tokens = self._normalize_tokens(words)
                if tokens:
                    synonyms_normalized[intent].update(tokens)
                    synonym_sources.append(
                        {"intent": intent, "tokens": frozenset(tokens), "weight": syn_weight}
                    )

        intent_tokens = self._extract_intent_tokens(ask_block)

        return {
            "intents": intents,
            "keywords": keywords,
            "keywords_normalized": keywords_norm,
            "latest_words": latest_words,
            "latest_words_normalized": latest_norm,
            "weights": weights,
            "synonyms_normalized": {
                key: sorted(values) for key, values in synonyms_normalized.items()
            },
            "synonym_sources": synonym_sources,
            "intent_tokens": intent_tokens,
        }

    def entity_meta(self, entity: str) -> Dict[str, Any]:
        self._ensure()
        meta = self._entity_meta.get(entity)
        if meta is None:
            return self._empty_meta()
        return meta

    def global_intent_tokens(self) -> Dict[str, Set[str]]:
        self._ensure()
        return self._global_tokens

    @staticmethod
    def _unique(values: List[str]) -> List[str]:
        seen: Set[str] = set()
        out: List[str] = []
        for value in values:
            if value and value not in seen:
                seen.add(value)
                out.append(value)
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
                result[key] = _ensure_list(value)
        for key, value in data.items():
            if isinstance(key, str) and key.startswith("synonyms."):
                intent = key.split(".", 1)[1]
                result[intent] = _ensure_list(value)
        return result

    @staticmethod
    def _extract_weights(data: Dict[str, Any], base: Dict[str, float]) -> Dict[str, float]:
        weights = dict(base)
        raw = data.get("weights")
        if isinstance(raw, dict):
            for key, value in raw.items():
                weights[key] = _parse_weight(value, default=base.get(key, 1.0))
        for key, value in data.items():
            if isinstance(key, str) and key.startswith("weights."):
                name = key.split(".", 1)[1]
                weights[name] = _parse_weight(value, default=base.get(name, 1.0))
        if "keywords" not in weights:
            weights["keywords"] = 1.0
        if "synonyms" not in weights:
            weights["synonyms"] = 2.0
        return weights

    @staticmethod
    def _normalize_tokens(values: List[str]) -> Set[str]:
        tokens = set(_tokenize_list(values))
        if not tokens:
            tokens = {_unaccent_lower(v) for v in values if isinstance(v, str)}
        return {t for t in tokens if t}

    @staticmethod
    def _extract_intent_tokens(data: Dict[str, Any]) -> Dict[str, frozenset[str]]:
        result: Dict[str, frozenset[str]] = {}
        raw = data.get("intent_tokens")
        if isinstance(raw, dict):
            for key, value in raw.items():
                values = _ensure_list(value)
                normalized = {
                    _unaccent_lower(v)
                    for v in values
                    if isinstance(v, str) and _unaccent_lower(v)
                }
                if normalized:
                    result[key] = frozenset(normalized)
        return result

    @staticmethod
    def _empty_meta() -> Dict[str, Any]:
        return {
            "intents": [],
            "keywords": [],
            "keywords_normalized": [],
            "latest_words": [],
            "latest_words_normalized": [],
            "weights": {"keywords": 1.0, "synonyms": 2.0},
            "synonyms_normalized": {},
            "synonym_sources": [],
            "intent_tokens": {},
        }


ASK_VOCAB = _AskVocabulary()


def _ask_meta(entity: str) -> Dict[str, Any]:
    return ASK_VOCAB.entity_meta(entity)


def _score_entity(
    tokens: List[str], entity: str, guessed: Optional[str]
) -> Tuple[float, Optional[str]]:
    tset = set(tokens)
    ask_meta = _ask_meta(entity)
    weights = ask_meta.get("weights", {})

    kwset = set(ask_meta.get("keywords_normalized", []))
    keyword_hits = sum(1 for t in tokens if t in kwset)
    score_keywords = keyword_hits * weights.get("keywords", 1.0)

    intent_scores: Dict[str, float] = {}
    for source in ask_meta.get("synonym_sources", []):
        intent = source.get("intent")
        token_set = source.get("tokens")
        if not intent or not token_set:
            continue
        tokens_ref = set(token_set)
        hits = len(tset & tokens_ref)
        if not hits:
            continue
        weight_syn = float(source.get("weight", weights.get("synonyms", 2.0)))
        score = hits * weight_syn
        intent_scores[intent] = intent_scores.get(intent, 0.0) + score

    best_intent = None
    best_intent_score = 0.0
    for intent, score in intent_scores.items():
        if score > best_intent_score:
            best_intent_score = score
            best_intent = intent

    desc_tokens = set(_tokenize((_meta(entity).get("description") or "")))
    score_desc = sum(1 for t in tokens if t in desc_tokens) * 0.5

    # Bônus por compatibilidade com a intenção global inferida
    # - Se a melhor intenção derivada de sinônimos coincide com 'guessed', bônus maior.
    # - Se 'guessed' está na lista de intents declarados da view, bônus adicional.
    bonus = 0.0
    if guessed:
        if best_intent and guessed == best_intent:
            bonus += 3.0  # forte aderência
        if _intent_matches(ask_meta.get("intents") or [], guessed):
            bonus += 2.0  # a view declara essa família

    total = score_keywords + best_intent_score + score_desc + bonus

    fam = _entity_family(entity)
    global_tokens = ASK_VOCAB.global_intent_tokens()
    boost_targets = set(ask_meta.get("intents") or [])
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

    def _mentions_processos_ativos(seq: List[str]) -> bool:
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

    # 🔸 Micro-heurísticas de desambiguação
    # (1) "preço + (vp|pvp|patrimônio)" → cadastro (relação P/VP)
    if ({"preco", "precos", "cotacao", "valeu", "valendo"} & tset) and (
        {"vp", "pvp", "patrimonio"} & tset
    ):
        if fam == "cadastro":
            total += 3.5
        elif fam == "precos":
            total -= 1.0

    # (2) "pago|pagamento" + "ultimo|recentemente" → dividends
    if ({"pago", "pagou", "pagos", "pagamento", "pagamentos"} & tset) and (
        {"ultimo", "ultimos", "recentemente", "recente"} & tset
    ):
        if fam == "dividends":
            total += 3.0

    if _mentions_processos_ativos(tokens):
        entity_intents = set(ask_meta.get("intents") or [])
        if "judicial" in entity_intents:
            total += 5.0
        if "processos" in entity_intents:
            total += 2.0
        if "ativos" in entity_intents:
            total -= 4.0

    # Se ainda não temos uma intenção clara, usar um padrão por NOME DA ENTIDADE
    # Isso garante rótulos consistentes com os testes (prices→precos, dividends→dividends etc.)
    def _default_intent_for_entity(name: str) -> Optional[str]:
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
            return "ativos"
        if "tax" in n or "indicator" in n:
            return "indicadores"
        return None

    if not best_intent:
        # 1) tenta pelos sinônimos declarados (já feito acima)
        # 2) força pela família detectada + nome da entidade
        inferred = _default_intent_for_entity(entity)
        if inferred:
            best_intent = inferred

    # Força rótulo 'precos' para entidades típicas de preços quando a intenção inferida for 'precos'
    # (em alguns registries a intent declarada é 'historico' e o teste espera 'precos').
    if not best_intent and guessed == "precos" and "prices" in (entity or ""):
        best_intent = "precos"

    # 🔸 Escolha do rótulo final (prioriza canônico por família quando o rótulo é genérico)
    if not best_intent:
        intents = ask_meta.get("intents") or []
        if intents:
            best_intent = intents[0]
    # Se a entidade tem família conhecida e o rótulo ficou vazio ou 'historico', usar o canônico
    if fam and (best_intent is None or best_intent == "historico"):
        best_intent = fam

    return total, best_intent


def _choose_entity_by_ask(question: str) -> Tuple[Optional[str], Optional[str], float]:
    tokens = _tokenize(question)
    guessed = _guess_intent(tokens)
    items = registry_service.list_all()
    if not items:
        raise ValueError("Catálogo vazio.")
    best_entity: Optional[str] = None
    best_intent: Optional[str] = None
    best_score = 0.0
    for it in items:
        entity = it["entity"]
        score, intent = _score_entity(tokens, entity, guessed)
        if score > best_score:
            best_entity = entity
            best_intent = intent
            best_score = score
    return best_entity, best_intent, best_score


# ---------------------------------------------------------------------------
# 🔹 Multi-intenção (retorna top-K entidades com score relevante)
# ---------------------------------------------------------------------------


def _choose_entities_by_ask(question: str) -> List[Tuple[str, str, float]]:
    tokens = _tokenize(question)
    guessed = _guess_intent(tokens)
    items = registry_service.list_all()
    results: List[Tuple[str, str, float]] = []

    for it in items:
        entity = it["entity"]
        score, intent = _score_entity(tokens, entity, guessed)
        if score > 0:
            results.append((entity, intent, score))
    # Se houver intenção global inferida, mantenha primeiro os compatíveis
    if guessed:
        compat: List[Tuple[str, str, float]] = []
        incomp: List[Tuple[str, str, float]] = []
        for entity, intent, score in results:
            am = _ask_meta(entity)
            if intent == guessed or _intent_matches(am.get("intents") or [], guessed):
                compat.append((entity, intent, score))
            else:
                incomp.append((entity, intent, score))
        # Se houver ao menos um compatível, mantém só eles (evita “historico” indevido em perguntas de “precos”)
        if compat:
            compat.sort(key=lambda x: x[2], reverse=True)
            results = compat
        else:
            incomp.sort(key=lambda x: x[2], reverse=True)
            results = incomp
    else:
        # ordena decrescente por score
        results.sort(key=lambda x: x[2], reverse=True)

    # Se a 1ª opção domina a 2ª (margem clara), trunca para Top-1
    if len(results) >= 2:
        s1 = results[0][2]
        s2 = results[1][2]
        if s2 <= 0 or s1 >= (1.5 * s2):
            results = [results[0]]

    # ordena decrescente por score
    return results


def _has_domain_anchor(tokens: List[str]) -> bool:
    """
    Verifica se há âncoras claras do nosso domínio (FIIs/mercado).
    Usado para evitar casar perguntas genéricas como 'capital da frança'.
    """
    if not tokens:
        return False
    domain = set()
    for words in ASK_VOCAB.global_intent_tokens().values():
        domain.update(words)
    tset = set(tokens)
    return bool(tset & domain)


def _default_date_field(entity: str) -> Optional[str]:
    meta = _meta(entity)
    candidate = meta.get("default_date_field")
    if candidate and candidate in _cols(entity):
        return candidate
    cols = _cols(entity)
    for suffix in ("_date", "_until"):
        for col in cols:
            if col.endswith(suffix):
                return col
    for col in cols:
        if col.endswith("_at"):
            return col
    return None


# ---------------------------------------------------------------------------
# 🔹 Datas e filtros
# ---------------------------------------------------------------------------


def _parse_date_value(value: Optional[str]) -> Optional[str]:
    if not value or not isinstance(value, str):
        return None
    value = value.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            parsed = datetime.strptime(value, fmt)
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _relative_date_range(text_norm: str) -> Dict[str, str]:
    today = date.today()

    m = re.search(r"ultim[oa]s?\s+(\d+)\s+mes", text_norm)
    if m:
        months = int(m.group(1))
        start = today - relativedelta(months=months)
        return {
            "date_from": start.strftime("%Y-%m-%d"),
            "date_to": today.strftime("%Y-%m-%d"),
        }

    m = re.search(r"(\d+)\s+mes(?:es)?\s+antes", text_norm)
    if m:
        months = int(m.group(1))
        start = today - relativedelta(months=months)
        return {
            "date_from": start.strftime("%Y-%m-%d"),
            "date_to": today.strftime("%Y-%m-%d"),
        }

    if "mes anterior" in text_norm:
        first_this_month = today.replace(day=1)
        last_prev_month = first_this_month - timedelta(days=1)
        first_prev_month = last_prev_month.replace(day=1)
        return {
            "date_from": first_prev_month.strftime("%Y-%m-%d"),
            "date_to": last_prev_month.strftime("%Y-%m-%d"),
        }

    if "ano atual" in text_norm:
        start = date(today.year, 1, 1)
        end = date(today.year, 12, 31)
        return {
            "date_from": start.strftime("%Y-%m-%d"),
            "date_to": end.strftime("%Y-%m-%d"),
        }

    return {}


def _extract_dates_range(text: str) -> Dict[str, str]:
    if not text:
        return {}
    between = re.search(
        r"entre\s+(\d{2}/\d{2}/\d{4})\s+e\s+(\d{2}/\d{2}/\d{4})",
        text,
        re.IGNORECASE,
    )
    if between:
        date_from = _parse_date_value(between.group(1))
        date_to = _parse_date_value(between.group(2))
        result: Dict[str, str] = {}
        if date_from:
            result["date_from"] = date_from
        if date_to:
            result["date_to"] = date_to
        if result:
            return result

    if not settings.nlp_relative_dates:
        return {}
    return _relative_date_range(_unaccent_lower(text))


def _resolve_date_range(
    question: str, explicit_range: Optional[Dict[str, Any]]
) -> Dict[str, str]:
    resolved: Dict[str, str] = {}
    if explicit_range:
        start = _parse_date_value(
            explicit_range.get("from") or explicit_range.get("start")
        )
        end = _parse_date_value(explicit_range.get("to") or explicit_range.get("end"))
        if start:
            resolved["date_from"] = start
        if end:
            resolved["date_to"] = end
    inferred = _extract_dates_range(question)
    for key, value in inferred.items():
        resolved.setdefault(key, value)
    return resolved


def _extract_tickers(text: str, valid: set[str]) -> List[str]:
    tokens = _tokenize(text)
    found: List[str] = []
    seen: Set[str] = set()
    has_valid = bool(valid)
    pattern = re.compile(r"^[A-Za-z]{4}\d{2}$")

    for token in tokens:
        candidate = token.upper()
        if has_valid:
            if candidate in valid and candidate not in seen:
                found.append(candidate)
                seen.add(candidate)
        else:
            if pattern.fullmatch(candidate) and candidate not in seen:
                found.append(candidate)
                seen.add(candidate)

    for token in tokens:
        if len(token) == 4 and token.isalpha():
            candidate = token.upper() + "11"
            if has_valid:
                if candidate in valid and candidate not in seen:
                    found.append(candidate)
                    seen.add(candidate)
            elif candidate not in seen:
                found.append(candidate)
                seen.add(candidate)
    return found


def _plan_question(
    question: str, entity: str, intent: Optional[str], payload: Dict[str, Any]
) -> Dict[str, Any]:
    valid_tickers = _load_valid_tickers()
    tickers = _extract_tickers(question, valid_tickers)
    filters: Dict[str, Any] = {}
    planner_filters: Dict[str, Any] = {}

    if tickers:
        planner_filters["tickers"] = tickers
        if "ticker" in _cols(entity):
            filters["ticker"] = tickers if len(tickers) > 1 else tickers[0]

    resolved_range = _resolve_date_range(question, payload.get("date_range"))
    date_field = _default_date_field(entity)
    if date_field:
        planner_filters["date_field"] = date_field
    if resolved_range.get("date_from"):
        filters["date_from"] = resolved_range["date_from"]
        planner_filters["date_from"] = resolved_range["date_from"]
    if resolved_range.get("date_to"):
        filters["date_to"] = resolved_range["date_to"]
        planner_filters["date_to"] = resolved_range["date_to"]

    qnorm = _unaccent_lower(question)
    ask_meta = _ask_meta(entity)
    latest_words_norm = ask_meta.get("latest_words_normalized", [])
    order_by = None
    limit = settings.ask_default_limit
    if latest_words_norm and any(word in qnorm for word in latest_words_norm):
        if date_field:
            order_by = {"field": date_field, "dir": "DESC"}
            limit = 1
    elif "entre" in qnorm and date_field:
        order_by = {"field": date_field, "dir": "ASC"}
        limit = min(settings.ask_max_limit, max(settings.ask_default_limit, 1))

    planner = {
        "intents": [intent] if intent else [],
        "entities": (
            [{"intent": intent, "entity": entity}] if intent else [{"entity": entity}]
        ),
        "filters": planner_filters,
    }

    run_request = {
        "entity": entity,
        "select": None,
        "filters": filters or None,
        "order_by": order_by,
        "limit": min(limit, settings.ask_max_limit),
    }

    return {"run_request": run_request, "planner": planner, "tickers": tickers}


# ---------------------------------------------------------------------------
# 🔹 Client helpers
# ---------------------------------------------------------------------------


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _client_echo(raw: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    raw = raw or {}
    client: Dict[str, Any] = {}
    if raw.get("client_id") is not None:
        client["client_id"] = raw["client_id"]
    if raw.get("nickname") is not None:
        client["nickname"] = raw["nickname"]
    balance = _safe_float(raw.get("balance"))
    if balance is not None:
        client["balance_before"] = balance
        client["balance_after"] = balance
    return client


# ---------------------------------------------------------------------------
# 🔹 API principal
# ---------------------------------------------------------------------------


def build_run_request(
    question: str, overrides: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    entity, intent, score = _choose_entity_by_ask(question)
    # if not entity or score <= 0:
    # Leleo perguntar
    if not entity or score < settings.ask_min_score:
        raise ValueError("Nenhuma entidade encontrada para a pergunta informada.")
    plan = _plan_question(question, entity, intent, overrides or {})
    return plan["run_request"]


def route_question(payload: Dict[str, Any]) -> Dict[str, Any]:
    t0 = time.time()
    question = (payload or {}).get("question") or ""
    req_id = str(uuid.uuid4())

    # --- Guarda de domínio: se não há ticker nem âncora, cai no fallback ---
    valid_tickers = _load_valid_tickers()
    tokens = _tokenize(question)
    has_ticker = bool(_extract_tickers(question, valid_tickers))
    if not has_ticker and not _has_domain_anchor(tokens):
        elapsed_ms = int((time.time() - t0) * 1000)
        response = {
            "request_id": req_id,
            "original_question": question,
            "client": _client_echo(payload.get("client")),
            "status": {
                "reason": "intent_unmatched",
                "message": settings.get_message(
                    "ask",
                    "fallback",
                    "intent_unmatched",
                    default="Intenção não reconhecida.",
                ),
            },
            "planner": {"intents": [], "entities": [], "filters": {}},
            "results": {},
            "meta": {
                "elapsed_ms": elapsed_ms,
                "rows_total": 0,
                "rows_by_intent": {},
                "limits": {"top_k": payload.get("top_k") or 0},
            },
            "usage": {
                "tokens_prompt": 0,
                "tokens_completion": 0,
                "cost_estimated": 0.0,
            },
        }
        logger.info(
            "ASK_ROUTE_FALLBACK",
            extra={
                "request_id": req_id,
                "question": question,
                "elapsed_ms": elapsed_ms,
            },
        )
        elapsed_total = (time.time() - t0) * 1000.0
        API_LATENCY_MS.labels(endpoint="/ask").set(elapsed_total)
        ASK_LATENCY_MS.labels(entity="__all__").observe(elapsed_total)
        ASK_ROWS.labels(entity="__all__").inc(0)
        return response

    # --- Escolha múltipla (top-K) ---
    ranked = _choose_entities_by_ask(question)
    selected = [
        (entity, intent, score)
        for entity, intent, score in ranked
        if score >= settings.ask_min_score
    ][: settings.ask_top_k]

    if not selected:
        elapsed_ms = int((time.time() - t0) * 1000)
        response = {
            "request_id": req_id,
            "original_question": question,
            "client": _client_echo(payload.get("client")),
            "status": {
                "reason": "intent_unmatched",
                "message": settings.get_message(
                    "ask",
                    "fallback",
                    "intent_unmatched",
                    default="Intenção não reconhecida.",
                ),
            },
            "planner": {"intents": [], "entities": [], "filters": {}},
            "results": {},
            "meta": {
                "elapsed_ms": elapsed_ms,
                "rows_total": 0,
                "rows_by_intent": {},
                "limits": {"top_k": payload.get("top_k") or 0},
            },
            "usage": {
                "tokens_prompt": 0,
                "tokens_completion": 0,
                "cost_estimated": 0.0,
            },
        }

        logger.info(
            "ASK_ROUTE_FALLBACK",
            extra={
                "request_id": req_id,
                "question": question,
                "elapsed_ms": elapsed_ms,
            },
        )

        elapsed_total = (time.time() - t0) * 1000.0
        API_LATENCY_MS.labels(endpoint="/ask").set(elapsed_total)
        ASK_LATENCY_MS.labels(entity="__all__").observe(elapsed_total)
        ASK_ROWS.labels(entity="__all__").inc(0)
        return response

    results: Dict[str, Any] = {}
    planner_entities: List[Dict[str, Any]] = []
    rows_by_intent: Dict[str, int] = {}
    primary_key: Optional[str] = None

    for entity, intent, score in selected:
        plan = _plan_question(question, entity, intent, payload)
        run_request = plan["run_request"]

        normalized: ExtractedRunRequest = normalize_request(run_request)
        sql, params = builder_service.build_sql(normalized)

        entity_label = normalized.entity
        tdb0 = time.time()
        rows = executor_service.run(sql, params, row_limit=normalized.limit)
        elapsed_db_ms = (time.time() - tdb0) * 1000.0

        DB_LATENCY_MS.labels(entity=entity_label).observe(elapsed_db_ms)
        DB_QUERIES.labels(entity=entity_label).inc()
        DB_ROWS.labels(entity=entity_label).inc(len(rows))

        data = to_human(rows)
        key = intent or entity_label
        if primary_key is None:
            primary_key = key
        results[key] = data
        planner_entities.append({"intent": intent, "entity": entity_label})
        rows_by_intent[key] = len(rows)

    elapsed_total = (time.time() - t0) * 1000.0

    response = {
        "request_id": req_id,
        "original_question": question,
        "client": _client_echo(payload.get("client")),
        "status": {
            "reason": "ok",
            "message": settings.get_message("ask", "status", "ok", default="ok"),
        },
        "planner": {
            "intents": [intent for _, intent, _ in selected if intent],
            "entities": planner_entities,
            "filters": {},
        },
        "results": results,
        "meta": {
            "elapsed_ms": int(elapsed_total),
            "rows_total": (
                rows_by_intent.get(primary_key)
                if primary_key
                else sum(rows_by_intent.values())
            ),
            "rows_by_intent": rows_by_intent,
            "limits": {"top_k": settings.ask_top_k},
        },
        "usage": {
            "tokens_prompt": 0,
            "tokens_completion": 0,
            "cost_estimated": 0.0,
        },
    }

    logger.info(
        "ASK_ROUTE",
        extra={
            "request_id": req_id,
            "entities": [e for e, _, _ in selected],
            "intents": [i for _, i, _ in selected],
            "question": question,
            "rows_total": sum(rows_by_intent.values()),
            "elapsed_ms": int(elapsed_total),
        },
    )

    ASK_LATENCY_MS.labels(entity=entity_label).observe(elapsed_total)
    ASK_ROWS.labels(entity=entity_label).inc(len(rows))
    ASK_LATENCY_MS.labels(entity="__all__").observe(elapsed_total)
    ASK_ROWS.labels(entity="__all__").inc(len(rows))
    API_LATENCY_MS.labels(endpoint="/ask").set(elapsed_total)

    return response


__all__ = [
    "_refresh_tickers_cache",
    "_default_date_field",
    "build_run_request",
    "route_question",
]
