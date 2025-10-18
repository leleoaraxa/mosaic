
from __future__ import annotations
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from app.core.settings import settings
from app.builder.service import builder_service
from app.executor.service import executor_service
from app.formatter.serializer import to_human
from app.observability.metrics import API_LATENCY_MS, ASK_LATENCY_MS, ASK_ROWS, DB_LATENCY_MS, DB_QUERIES, DB_ROWS

from .models import EntityScore, QuestionContext
from .planning import plan_question
from .scoring import rank_entities

def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None: return None
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

def choose_entities_by_ask(ctx: QuestionContext, min_score: float, top_k: int) -> List[Tuple[str, str, float]]:
    scores = rank_entities(ctx)
    guessed = ctx.guessed_intent

    if guessed:
        compat: List[EntityScore] = []
        incomp: List[EntityScore] = []
        for item in scores:
            # Lazy access to entity meta is fine here; scoring already used it.
            if item.intent == guessed:
                compat.append(item)
            else:
                incomp.append(item)
        if compat:
            scores = sorted(compat, key=lambda x: x.score, reverse=True)
        else:
            scores = sorted(incomp, key=lambda x: x.score, reverse=True)
    else:
        scores.sort(key=lambda x: x.score, reverse=True)

    if len(scores) >= 2:
        s1 = scores[0].score; s2 = scores[1].score
        if s2 <= 0 or s1 >= (1.5 * s2):
            scores = scores[:1]

    selected = [(item.entity, item.intent, item.score) for item in scores if item.score >= min_score][:top_k]
    return selected

def route_question(payload: Dict[str, Any]) -> Dict[str, Any]:
    t0 = time.time()
    question = (payload or {}).get("question") or ""
    req_id = str(uuid.uuid4())

    ctx = QuestionContext.build(question)  # filled by facade
    if not ctx.has_domain_anchor:
        elapsed_ms = int((time.time() - t0) * 1000)
        response = {
            "request_id": req_id,
            "original_question": question,
            "client": _client_echo(payload.get("client")),
            "status": {"reason": "intent_unmatched", "message": settings.get_message("ask","fallback","intent_unmatched", default="Intenção não reconhecida.")},
            "planner": {"intents": [], "entities": [], "filters": {}},
            "results": {},
            "meta": {"elapsed_ms": elapsed_ms, "rows_total": 0, "rows_by_intent": {}, "limits": {"top_k": payload.get("top_k") or 0}},
            "usage": {"tokens_prompt": 0,"tokens_completion": 0,"cost_estimated": 0.0},
        }
        API_LATENCY_MS.labels(endpoint="/ask").set((time.time() - t0) * 1000.0)
        ASK_LATENCY_MS.labels(entity="__all__").observe((time.time() - t0) * 1000.0)
        ASK_ROWS.labels(entity="__all__").inc(0)
        return response

    selected = choose_entities_by_ask(ctx, settings.ask_min_score, settings.ask_top_k)
    if not selected:
        elapsed_ms = int((time.time() - t0) * 1000)
        response = {
            "request_id": req_id,
            "original_question": question,
            "client": _client_echo(payload.get("client")),
            "status": {"reason": "intent_unmatched", "message": settings.get_message("ask","fallback","intent_unmatched", default="Intenção não reconhecida.")},
            "planner": {"intents": [], "entities": [], "filters": {}},
            "results": {},
            "meta": {"elapsed_ms": elapsed_ms, "rows_total": 0, "rows_by_intent": {}, "limits": {"top_k": payload.get("top_k") or 0}},
            "usage": {"tokens_prompt": 0,"tokens_completion": 0,"cost_estimated": 0.0},
        }
        API_LATENCY_MS.labels(endpoint="/ask").set((time.time() - t0) * 1000.0)
        ASK_LATENCY_MS.labels(entity="__all__").observe((time.time() - t0) * 1000.0)
        ASK_ROWS.labels(entity="__all__").inc(0)
        return response

    results: Dict[str, Any] = {}
    planner_entities: List[Dict[str, Any]] = []
    rows_by_intent: Dict[str, int] = {}
    primary_key: Optional[str] = None
    entity_label = "__all__"
    total_rows_run = 0

    for entity, intent, score in selected:
        plan = plan_question(ctx, entity, intent, payload)
        run_request = plan["run_request"]
        from app.extractors.normalizers import normalize_request
        normalized: ExtractedRunRequest = normalize_request(run_request)
        sql, params = builder_service.build_sql(normalized)

        entity_label = normalized.entity
        import time as _t
        tdb0 = _t.time()
        rows = executor_service.run(sql, params, row_limit=normalized.limit)
        elapsed_db_ms = (_t.time() - tdb0) * 1000.0
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
        total_rows_run += len(rows)

    elapsed_total = (time.time() - t0) * 1000.0
    response = {
        "request_id": req_id,
        "original_question": question,
        "client": _client_echo(payload.get("client")),
        "status": {"reason": "ok", "message": settings.get_message("ask","status","ok", default="ok")},
        "planner": {"intents": [i for _, i, _ in selected if i], "entities": planner_entities, "filters": {}},
        "results": results,
        "meta": {"elapsed_ms": int(elapsed_total), "rows_total": (rows_by_intent.get(primary_key) if primary_key else total_rows_run), "rows_by_intent": rows_by_intent, "limits": {"top_k": settings.ask_top_k}},
        "usage": {"tokens_prompt": 0,"tokens_completion": 0,"cost_estimated": 0.0},
    }
    ASK_LATENCY_MS.labels(entity=entity_label).observe(elapsed_total)
    ASK_ROWS.labels(entity=entity_label).inc(total_rows_run)
    ASK_LATENCY_MS.labels(entity="__all__").observe(elapsed_total)
    ASK_ROWS.labels(entity="__all__").inc(total_rows_run)
    API_LATENCY_MS.labels(endpoint="/ask").set(elapsed_total)
    return response
