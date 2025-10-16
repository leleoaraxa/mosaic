# app/gateway/router.py
import os
import httpx
import time, uuid, re, unicodedata
import logging, hashlib, json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

from app.registry.service import registry_service
from app.extractors.normalizers import normalize_request, ExtractedRunRequest
from app.builder.service import builder_service
from app.executor.service import executor_service
from app.formatter.serializer import to_human
from app.orchestrator.service import route_question
from app.observability.metrics import (
    ASK_ERRORS,
    DB_LATENCY_MS,
    DB_QUERIES,
    DB_ROWS,
    API_LATENCY_MS,
    API_ERRORS,
)
from app.core.settings import settings

# --- pré-registro de séries Prometheus p/ garantir exposição mesmo com zero ---
# latência também (Gauge aparece só após set) – já vamos setar 0 inicial
API_LATENCY_MS.labels(endpoint="/ask").set(0.0)
API_LATENCY_MS.labels(endpoint="/views/run").set(0.0)

for ep in ("/ask", "/views/run"):
    for etype in ("validation", "runtime"):
        API_ERRORS.labels(endpoint=ep, type=etype).inc(0)


def _lbl(x: Optional[str]) -> str:
    return (x or "unknown").strip() or "unknown"


logger = logging.getLogger("gateway")
if not logger.handlers:
    # configuração simples; se você já usa logging no projeto, pode remover este bloco
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )

router = APIRouter()

# cache simples dos tickers válidos (vindo do DB)
_TICKERS_CACHE = {"ts": 0.0, "ttl": settings.tickers_cache_ttl, "set": set()}

PROM_URL = settings.prometheus_url
GRAF_URL = settings.grafana_url


def _load_valid_tickers(force: bool = False) -> set[str]:
    now = time.time()
    if (
        (not force)
        and _TICKERS_CACHE["set"]
        and (now - _TICKERS_CACHE["ts"] < _TICKERS_CACHE["ttl"])
    ):
        return _TICKERS_CACHE["set"]

    try:
        # pega os tickers direto da base
        req = RunViewRequest(
            entity="view_fiis_info",
            select=["ticker"],
            limit=min(10000, settings.ask_max_limit),
        )
        res = _execute_view(req)
        data = res.get("data", []) or []
        s = {str(r.get("ticker", "")).upper() for r in data if r.get("ticker")}
        _TICKERS_CACHE.update({"ts": now, "set": s})
        logger.info(f"loaded {len(s)} valid tickers into cache")
        return s
    except Exception as ex:
        logger.warning(f"failed to load valid tickers: {ex}")
        return _TICKERS_CACHE["set"] or set()


# ========================= helpers de catálogo =========================


def _safe_select(
    entity: str, select: Optional[List[str]], fallback_default: List[str]
) -> List[str]:
    """
    Garante que só pedimos colunas que existem naquela entidade.
    Se 'select' vier vazio/None, usa 'fallback_default' (filtrando ao que a entidade tem).
    """
    cols = set(_cols(entity))
    if select:
        return [c for c in select if c in cols] or [
            c for c in fallback_default if c in cols
        ]
    return [c for c in fallback_default if c in cols]


def _cols(entity: str) -> List[str]:
    return registry_service.get_columns(entity) or []


def _meta(entity: str) -> Dict[str, Any]:
    return registry_service.get(entity) or {}


def _ticker_base(ticker: Optional[str]) -> Optional[str]:
    if not ticker:
        return None
    m = re.match(r"^([A-Z]{4})", ticker.upper())
    return m.group(1) if m else None


def _rescue_info_by_prefix(base4: str, wanted_cols: Optional[list[str]]) -> list[dict]:
    """
    Rescue client-side: busca uma amostra em view_fiis_info e filtra por prefixo 'BASE4'.
    Evita mexer no Builder/SQL. Retorna no formato já serializado por to_human (list[dict]).
    """
    probe_cols = wanted_cols or ["ticker", "fii_cnpj"]
    req = RunViewRequest(entity="view_fiis_info", select=probe_cols, limit=500)
    res = _execute_view(req)
    rows = res.get("data", [])
    base4 = (base4 or "").upper()
    out = [r for r in rows if str(r.get("ticker", "")).upper().startswith(base4)]
    return out


def _default_date_field(entity: str) -> Optional[str]:
    m = _meta(entity)
    d = m.get("default_date_field")
    if d and d in _cols(entity):
        return d
    # heurística segura se não houver no YAML
    for cand in (
        "payment_date",
        "price_date",
        "news_date",
        "indicator_date",
        "tax_date",
        "created_at",
        "updated_at",
    ):
        if cand in _cols(entity):
            return cand
    return None


# ========================= helpers de NL =========================


def _unaccent_lower(s: str) -> str:
    if not isinstance(s, str):
        return ""
    return "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    ).lower()


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]{2,}", _unaccent_lower(text or ""))


def _extract_tickers(text: str) -> list[str]:
    """
    Extrai TODOS os tickers mencionados na pergunta, validando contra a lista real do DB.
    Regras:
      - match exato do token (case-insensitive) com um ticker válido (ex.: XPML11)
      - ou token de 4 letras seguido de '11' implicitamente (ex.: 'XPML' -> 'XPML11'), se existir no DB
    NÃO infere '11' para palavras comuns como 'QUAL' porque não estão no set de tickers válidos.
    """
    tokens = set(_tokenize(text))
    valid = _load_valid_tickers()
    found: list[str] = []

    # 1) matches exatos (ex.: xpml11) → XPML11
    for t in tokens:
        cand = t.upper()
        if cand in valid:
            found.append(cand)

    # 2) tokens de 4 letras que tenham 'XXYY11' válido no DB
    for t in tokens:
        if len(t) == 4 and t.isalpha():
            cand = t.upper() + "11"
            if cand in valid and cand not in found:
                found.append(cand)

    return found


def _first_ticker_or_none(text: str) -> Optional[str]:
    arr = _extract_tickers(text)
    return arr[0] if arr else None


def _extract_dates_range(text: str) -> Dict[str, str]:
    m = re.search(
        r"entre\s+(\d{2}/\d{2}/\d{4})\s+e\s+(\d{2}/\d{2}/\d{4})", text, re.IGNORECASE
    )
    return {"date_from": m.group(1), "date_to": m.group(2)} if m else {}


# ========================= COMMENT → YAML (ask + col docs) =========================


def _ask_meta(entity: str) -> dict:
    """Retorna bloco ask do YAML: {'keywords': [...], 'intents': [...], 'latest_words': [...]}."""
    m = _meta(entity)
    return m.get("ask", {}) or {}


def _col_keywords(entity: str) -> dict[str, list[str]]:
    """
    Para cada coluna, agrega tokens de:
      - name (DB)
      - alias (se existir, vindo do COMMENT após o pipe)
      - description (COMMENT, antes do pipe)
    Retorna: { column_name: [kw1, kw2, ...] }
    """
    m = _meta(entity)
    cols = m.get("columns") or []
    out: dict[str, list[str]] = {}
    for c in cols:
        if isinstance(c, str):
            name, alias, desc = c, "", ""
        elif isinstance(c, dict):
            name = c.get("name", "")
            alias = c.get("alias", "") or ""
            desc = c.get("description", "") or ""
        else:
            continue
        bag = set()
        for piece in (name, alias, desc):
            for t in _tokenize(piece):
                bag.add(t)
        if name:
            out[name] = list(bag)
    return out


def _select_from_question_by_comments(
    entity: str, question: str
) -> Optional[List[str]]:
    """
    Seleciona colunas com base em name/alias/description (COMMENT).
    Se nada casar, retorna None → Builder seleciona TODAS as colunas.
    """
    qtok = set(_tokenize(question))
    colkw = _col_keywords(entity)  # { name: [kw...] }
    matches = []
    for name, kws in colkw.items():
        if any(k in qtok for k in kws):
            matches.append(name)
    # dedup mantendo ordem
    seen = set()
    matches = [m for m in matches if not (m in seen or seen.add(m))]
    # se perguntou por “último...”, garanta campo de data junto
    qn = _unaccent_lower(question)
    if matches and ("ultimo" in qn or "último" in qn or "mais recente" in qn):
        df = _default_date_field(entity)
        if df and df not in matches and df in _cols(entity):
            matches.insert(0, df)
    return matches or None


def _choose_entity_by_ask(question: str) -> str:
    """
    Escolhe entidade usando apenas ask.keywords (do COMMENT da view).
    Fallback para view_fiis_info se ninguém pontuar.
    """
    qtok = set(_tokenize(question))
    items = registry_service.list_all()
    if not items:
        raise HTTPException(400, "Catálogo vazio.")
    best, best_score = None, -1
    for it in items:
        e = it["entity"]
        meta = _ask_meta(e)
        kws = set(_tokenize(" ".join(meta.get("keywords", []))))
        desc_tokens = set(_tokenize((_meta(e).get("description") or "")))
        bag = kws | desc_tokens
        score = sum(1 for t in qtok if t in bag) if bag else 0
        if score > best_score:
            best, best_score = e, score
    if best_score <= 0 and any(i["entity"] == "view_fiis_info" for i in items):
        return "view_fiis_info"
    return best or items[0]["entity"]


def _rank_entities_by_ask(
    question: str, top_k: int = 3, min_ratio: float = 0.6
) -> list[str]:
    """
    Retorna uma lista ordenada de entidades candidatas para a pergunta.
    Critério: score por interseção com ask.keywords + descrição da view.
    Seleção: pega até top_k entidades com score >= (max_score * min_ratio).
    Fallback: se ninguém pontuar, devolve apenas 'view_fiis_info' se existir, senão a primeira do catálogo.
    """
    qtok = set(_tokenize(question))
    items = registry_service.list_all()
    if not items:
        raise HTTPException(400, "Catálogo vazio.")

    scored = []
    for it in items:
        e = it["entity"]
        ask = _ask_meta(e)
        kws = set(_tokenize(" ".join(ask.get("keywords", []))))
        desc_tokens = set(_tokenize((_meta(e).get("description") or "")))
        bag = kws | desc_tokens
        score = sum(1 for t in qtok if t in bag) if bag else 0
        scored.append((e, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    if not scored or scored[0][1] <= 0:
        # fallback único
        if any(i["entity"] == "view_fiis_info" for i in items):
            return ["view_fiis_info"]
        return [items[0]["entity"]]

    max_score = scored[0][1]
    cutoff = max(1, int(max_score * min_ratio))
    out = [e for e, s in scored if s >= cutoff][:top_k]
    # garanta que não fique vazio
    return out or [scored[0][0]]


def _is_latest_by_ask(entity: str, question: str) -> bool:
    words = _ask_meta(entity).get("latest_words", [])
    if not words:
        return False
    qtok = set(_tokenize(question))
    wtok = set(_tokenize(" ".join(words)))
    return bool(qtok & wtok)


def _apply_filters_inferred(
    entity: str, ticker: Optional[str], question: str
) -> Dict[str, Any]:
    filters: Dict[str, Any] = {}
    if ticker and "ticker" in _cols(entity):
        filters["ticker"] = ticker
    span = _extract_dates_range(question)
    if span:
        filters.update(span)
    return filters


# ========================= modelos =========================


class RunViewRequest(BaseModel):
    entity: str
    select: Optional[List[str]] = None
    filters: Optional[Dict[str, Any]] = None
    order_by: Optional[Dict[str, str]] = None
    limit: Optional[int] = Field(default=100)


class AskRequest(BaseModel):
    question: str
    top_k: int = 3  # nº máx. de intenções (entidades) a considerar
    min_ratio: float = 0.6  # corte relativo ao melhor score (0–1)


# ========================= endpoints utilitários =========================
@router.get("/healthz")
def healthz():
    # leve e sempre 200 quando app está de pé
    return {"status": "ok"}


@router.get("/healthz/full")
def healthz_full():
    from app.observability.metrics import set_health  # import local p/ evitar ciclos

    status = {
        "app": "up",
        "db": {"ok": False, "error": None},
        "prometheus": {"ok": False, "error": None},
        "grafana": {"ok": False, "error": None},
    }

    # App está de pé
    set_health("app", True)

    # DB: tentativa leve (limit 1)
    try:
        probe = RunViewRequest(entity="view_fiis_info", select=["ticker"], limit=1)
        _ = _execute_view(probe)  # se falhar, cai no except
        status["db"]["ok"] = True
    except Exception as ex:
        status["db"]["error"] = str(ex)
    finally:
        set_health("db", bool(status["db"]["ok"]))

    # Prometheus readiness
    try:
        with httpx.Client(timeout=2.0) as c:
            r = c.get(f"{PROM_URL}/-/ready")
            ok = (r.status_code == 200) and ("Prometheus" in r.text)
            status["prometheus"]["ok"] = ok
    except Exception as ex:
        status["prometheus"]["error"] = str(ex)
    finally:
        set_health("prometheus", bool(status["prometheus"]["ok"]))

    # Grafana health
    try:
        with httpx.Client(timeout=2.0) as c:
            r = c.get(f"{GRAF_URL}/api/health")
            ok = (r.status_code == 200) and ("database" in r.text)
            status["grafana"]["ok"] = ok
    except Exception as ex:
        status["grafana"]["error"] = str(ex)
    finally:
        set_health("grafana", bool(status["grafana"]["ok"]))

    return status


@router.get("/views")
def list_views():
    return {"items": registry_service.list_all()}


@router.get("/views/{entity}")
def get_view(entity: str):
    meta = registry_service.get(entity)
    if not meta:
        raise HTTPException(404, f"entity '{entity}' not found")
    return meta


@router.get("/views/{entity}/columns")
def get_view_columns(entity: str):
    meta = registry_service.get(entity)
    if not meta:
        raise HTTPException(404, f"entity '{entity}' not found")
    return {"entity": entity, "columns": meta.get("columns", [])}


@router.post("/admin/views/reload")
def reload_registry():
    registry_service.reload()
    return {"status": "ok", "items": registry_service.list_all()}


@router.get("/admin/validate-schema")
def validate_schema():
    items = []
    for v in registry_service.list_all():
        entity = v["entity"]
        yaml_cols = registry_service.get_columns(entity)
        db_cols = executor_service.columns_for(entity)
        if not db_cols:
            items.append(
                {
                    "entity": entity,
                    "status": "skipped (dummy or no DB)",
                    "yaml": yaml_cols,
                    "db": db_cols,
                    "diff": [],
                }
            )
            continue
        missing_in_db = [c for c in yaml_cols if c not in db_cols]
        extra_in_db = [c for c in db_cols if c not in yaml_cols]
        ok = not missing_in_db and not extra_in_db
        items.append(
            {
                "entity": entity,
                "status": "ok" if ok else "mismatch",
                "yaml": yaml_cols,
                "db": db_cols,
                "diff": {"missing_in_db": missing_in_db, "extra_in_db": extra_in_db},
            }
        )
    return {"items": items}


# ========================= executor comum =========================
def _execute_view(req: RunViewRequest):
    t0 = time.time()
    req_id = str(uuid.uuid4())
    try:
        normalized: ExtractedRunRequest = normalize_request(req.model_dump())
        entity = normalized.entity
        sql, params = builder_service.build_sql(normalized)

        tdb0 = time.time()
        rows = executor_service.run(sql, params, row_limit=normalized.limit)
        elapsed_db_ms = (time.time() - tdb0) * 1000.0

        # ── métricas por entidade
        e = _lbl(entity)
        DB_LATENCY_MS.labels(entity=e).observe(elapsed_db_ms)
        DB_QUERIES.labels(entity=e).inc()
        DB_ROWS.labels(entity=e).inc(len(rows))

        return {
            "request_id": req_id,
            "entity": entity,
            "rows": len(rows),
            "data": to_human(rows),
            "meta": {"elapsed_ms": int((time.time() - t0) * 1000)},
        }
    except ValueError as e:
        # validação / entidade desconhecida, etc. → 400
        entity = getattr(req, "entity", None)
        logger.error(
            "EXECUTE_VIEW_VALIDATION_ERROR", extra={"error": str(e), "entity": entity}
        )
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        etype = e.__class__.__name__.lower()
        entity = getattr(req, "entity", None)
        ASK_ERRORS.labels(entity=_lbl(entity), type=etype).inc()
        logger.error("EXECUTE_VIEW_ERROR", extra={"error": str(e), "entity": entity})
        raise


@router.post("/views/run")
def run_view(req: RunViewRequest):
    t0 = time.time()
    try:
        resp = _execute_view(req)
        # era: API_LATENCY_MS.labels(endpoint="/views/run").observe(...)
        API_LATENCY_MS.labels(endpoint="/views/run").set((time.time() - t0) * 1000.0)
        return resp
    except HTTPException as e:
        API_ERRORS.labels(endpoint="/views/run", type="validation").inc()
        API_LATENCY_MS.labels(endpoint="/views/run").set((time.time() - t0) * 1000.0)
        raise
    except Exception as e:
        API_ERRORS.labels(endpoint="/views/run", type="runtime").inc()
        API_LATENCY_MS.labels(endpoint="/views/run").set((time.time() - t0) * 1000.0)
        raise


# ========================= /ask orientado por COMMENT =========================
@router.post("/ask")
def ask(req: AskRequest):
    t0 = time.time()
    try:
        result = route_question(req.question)
        API_LATENCY_MS.labels(endpoint="/ask").set((time.time() - t0) * 1000.0)
        return result
    except HTTPException:
        API_ERRORS.labels(endpoint="/ask", type="validation").inc()
        API_LATENCY_MS.labels(endpoint="/ask").set((time.time() - t0) * 1000.0)
        raise
    except Exception:
        API_ERRORS.labels(endpoint="/ask", type="runtime").inc()
        API_LATENCY_MS.labels(endpoint="/ask").set((time.time() - t0) * 1000.0)
        raise
