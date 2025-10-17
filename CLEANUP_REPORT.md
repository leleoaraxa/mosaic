# Cleanup Report

## Símbolos removidos
- app/gateway/router.py:L40 → `_TICKERS_CACHE`
- app/gateway/router.py:L44-L67 → `_load_valid_tickers`
- app/gateway/router.py:L69-L81 → `_safe_select`
- app/gateway/router.py:L82 → `_cols`
- app/gateway/router.py:L84 → `_meta`
- app/gateway/router.py:L86-L90 → `_ticker_base`
- app/gateway/router.py:L91-L102 → `_rescue_info_by_prefix`
- app/gateway/router.py:L103-L120 → `_default_date_field`
- app/gateway/router.py:L122-L127 → `_unaccent_lower`
- app/gateway/router.py:L128-L129 → `_tokenize`
- app/gateway/router.py:L130-L152 → `_extract_tickers`
- app/gateway/router.py:L153-L155 → `_first_ticker_or_none`
- app/gateway/router.py:L156-L159 → `_extract_dates_range`
- app/gateway/router.py:L162-L165 → `_ask_meta`
- app/gateway/router.py:L166-L192 → `_col_keywords`
- app/gateway/router.py:L193-L215 → `_select_from_question_by_comments`
- app/gateway/router.py:L216-L248 → `_rank_entities_by_ask`
- app/gateway/router.py:L249-L255 → `_is_latest_by_ask`
- app/gateway/router.py:L256-L265 → `_apply_filters_inferred`

## TODO(deprecate)
- Nenhum item marcado nesta rodada.

## Itens ignorados (uso dinâmico/side-effects)
- `app/observability/metrics` continua importado no router e em outros módulos pelo efeito colateral de registrar métricas (necessário para Prometheus).
- Serviços globais (`registry_service`, `executor_service`, `builder_service`, `route_question`) foram mantidos porque são importados dinamicamente por FastAPI e outros componentes.
- `app/observability/logging` e middlewares associados preservados para manter o comportamento de logging solicitado pela aplicação.

## Execução de ferramentas
- `ruff check . --select F401,F841,F822,F823,F631,F706,F704,F701 --fix` → concluído com sucesso. 【cd06cc†L1-L2】
- `ruff check . --select I001 --fix` → concluído com sucesso. 【e11047†L1-L2】
- `ruff check .` → concluído com sucesso. 【f6a61c†L1-L2】
- `vulture app --min-confidence 80 --exclude 'app/tests/*,tests/*'` → não executado (instalação bloqueada pelo proxy ao tentar instalar `vulture`). 【78beee†L1-L4】
- `pytest -q` → falhou: ambiente sem acesso ao host PostgreSQL `sirios_db` (OperationalError). 【56589f†L1-L170】
