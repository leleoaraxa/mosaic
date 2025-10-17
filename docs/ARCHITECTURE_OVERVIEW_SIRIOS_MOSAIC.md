# Arquitetura do Sirios Mosaic

> Documento interno de arquitetura cobrindo módulos, integrações e pipeline NL→SQL.

## Sumário
- [1. Introdução](#1-introdução)
- [2. Visão geral da pasta `app/`](#2-visão-geral-da-pasta-app)
  - [2.1 Estrutura macro da API (`gateway/`)](#21-estrutura-macro-da-api-gateway)
  - [2.2 Núcleo de configurações (`core/`)](#22-núcleo-de-configurações-core)
  - [2.3 Executor SQL (`executor/`)](#23-executor-sql-executor)
  - [2.4 Extratores e normalização (`extractors/`)](#24-extratores-e-normalização-extractors)
  - [2.5 Builder SQL (`builder/`)](#25-builder-sql-builder)
  - [2.6 Formatação de resultados (`formatter/`)](#26-formatação-de-resultados-formatter)
  - [2.7 Infraestrutura de cache (`infrastructure/`)](#27-infraestrutura-de-cache-infrastructure)
  - [2.8 Observabilidade embutida (`observability/`)](#28-observabilidade-embutida-observability)
  - [2.9 Registro de catálogo (`registry/`)](#29-registro-de-catálogo-registry)
  - [2.10 Orquestrador NL→SQL (`orchestrator/`)](#210-orquestrador-nlsql-orchestrator)
  - [2.11 Inicialização e composição (`main.py`)](#211-inicialização-e-composição-mainpy)
  - [2.12 Serviços auxiliares e notas](#212-serviços-auxiliares-e-notas)
  - [2.13 Fluxo NL→SQL ponta-a-ponta](#213-fluxo-nlsql-ponta-a-ponta)
  - [2.14 Métricas e observabilidade](#214-métricas-e-observabilidade)
  - [2.15 🔹 Pipeline de geração dos YAMLs](#215--pipeline-de-geração-dos-yamls)
- [3. Plataforma de observabilidade externa (`observability/` na raiz)](#3-plataforma-de-observabilidade-externa-observability-na-raiz)
- [4. Estratégia de testes (`tests/`)](#4-estratégia-de-testes-tests)
  - [4.1 Filosofia e camadas de testes](#41-filosofia-e-camadas-de-testes)
  - [4.2 Testes de API e NL→SQL](#42-testes-de-api-e-nl→sql)
  - [4.3 Testes de infraestrutura e utilitários](#43-testes-de-infraestrutura-e-utilitários)
  - [4.4 Catálogo de testes automatizados](#44-catálogo-de-testes-automatizados)
- [5. Ferramentas de catálogo (`tools/`)](#5-ferramentas-de-catálogo-tools)
  - [5.1 Snapshot do banco → YAML](#51-snapshot-do-banco--yaml)
  - [5.2 Enriquecimento com comentários/ASK](#52-enriquecimento-com-comentáriosask)
  - [5.3 Diferença YAML × banco](#53-diferença-yaml--banco)
  - [5.4 Higienização e prune](#54-higienização-e-prune)
  - [5.5 Pipeline de sincronização](#55-pipeline-de-sincronização)
- [6. Apêndice — Integrações, configuração e endpoints](#6-apêndice--integrações-configuração-e-endpoints)
  - [6.1 Variáveis de ambiente críticas](#61-variáveis-de-ambiente-críticas)
  - [6.2 Endpoints FastAPI expostos](#62-endpoints-fastapi-expostos)
  - [6.3 Interação dos testes automatizados](#63-interação-dos-testes-automatizados)

---

## 1. Introdução

O Sirios Mosaic é uma aplicação FastAPI que transforma perguntas em linguagem natural (NL) em consultas SQL sobre materialized views financeiras, formatando a resposta para consumo humano e enriquecendo o processo com métricas e logs de observabilidade. O projeto é composto por uma camada de orquestração inteligente (v4 do envelope), um pipeline de catálogos YAML sincronizados com o banco, e um conjunto robusto de ferramentas e testes. 🚀

Este documento técnico descreve minuciosamente a estrutura de diretórios do repositório, detalhando responsabilidades, fluxos e dependências cruzadas. O foco é permitir que engenheiros compreendam o comportamento de cada componente, desde a captura da requisição até a entrega dos resultados e monitoração.

---

## 2. Visão geral da pasta `app/`

A pasta `app/` contém toda a lógica de aplicação. Apesar do requisito histórico citar `app/api/` e `app/services/`, a base atual consolida as rotas em `app/gateway/` e os serviços em módulos específicos (como `builder/service.py`). A documentação abaixo cobre cada subdiretório real e explica a equivalência com os nomes esperados.

### 2.1 Estrutura macro da API (`gateway/`)

A camada de entrada da API está em `app/gateway/router.py`. Este módulo expõe as rotas FastAPI, aplica métricas e faz o ponte entre o payload HTTP e os serviços internos. Componentes principais:

```python
from fastapi import APIRouter, HTTPException
from fastapi import status
from typing import Any, Dict, List, Optional

router = APIRouter()
```

**Modelos públicos (Pydantic)**:

| Classe | Assinatura | Finalidade |
| ------ | ---------- | ---------- |
| `RunViewRequest` | `RunViewRequest(entity: str, select: Optional[List[str]] = None, filters: Optional[Dict[str, Any]] = None, order_by: Optional[Dict[str, str]] = None, limit: Optional[int] = 100)` | Request enxuto para `/views/run`; usa `normalize_request` e `builder_service`.
| `ClientPayload` | `ClientPayload(client_id: Optional[str] = None, token: Optional[str] = None, nickname: Optional[str] = None, balance: Optional[float] = None)` | Transporta dados de cliente, refletidos na resposta por `_client_echo`.
| `DateRangePayload` | `DateRangePayload(from: Optional[str] = None, to: Optional[str] = None)` | Permite sobrescrever `date_from`/`date_to`; alias `from`/`to` via `model_config`.
| `TracePayload` | `TracePayload(request_id: Optional[str] = None)` | Propaga `request_id` opcional.
| `AskRequest` | `AskRequest(question: str, top_k: Optional[int] = None, min_ratio: Optional[float] = None, date_range: Optional[DateRangePayload] = None, client: Optional[ClientPayload] = None, trace: Optional[TracePayload] = None)` | Payload completo do `/ask`.

**Funções e rotas públicas**:

| Função | Assinatura | Responsabilidade | Métricas |
| ------ | ---------- | ---------------- | -------- |
| `healthz()` | `() -> Dict[str, str]` | Check simples (status 200) | Nenhuma |
| `healthz_full()` | `() -> Dict[str, Any]` | Chama DB (`_execute_view`), Prometheus (`/-/ready`), Grafana (`/api/health`), atualiza `HEALTH_OK` | `HEALTH_OK` |
| `list_views()` | `() -> Dict[str, Any]` | Lista catálogo (`registry_service.list_all()`) | Nenhuma |
| `get_view(entity)` | `(str) -> Dict[str, Any]` | Retorna YAML expandido; 404 se não encontrado | Nenhuma |
| `get_view_columns(entity)` | `(str) -> Dict[str, Any]` | Exibe apenas colunas registradas | Nenhuma |
| `reload_registry()` | `() -> Dict[str, Any]` | Reexecuta `registry_service.reload()` e devolve snapshot | Nenhuma |
| `validate_schema()` | `() -> Dict[str, Any]` | Compara YAML × DB (`executor_service.columns_for`) | Nenhuma |
| `_execute_view(req)` | `(RunViewRequest) -> Dict[str, Any]` | Função interna usada em `/views/run` e `healthz_full()` | `DB_LATENCY_MS`, `DB_QUERIES`, `DB_ROWS` |
| `run_view(req)` | `(RunViewRequest) -> Dict[str, Any]` | Exposição pública; trata `HTTPException` vs erros gerais | `API_LATENCY_MS`, `API_ERRORS` |
| `ask(req)` | `(AskRequest) -> Dict[str, Any]` | Encaminha payload para `route_question` e monitora falhas | `API_LATENCY_MS`, `API_ERRORS` |

**Dependências cruzadas**:

- `builder_service` (app/builder) e `executor_service` (app/executor) são importados diretamente para montar e executar SQL.
- `registry_service` (app/registry) é usado para consulta de metadados, validação de schema e reload.
- `to_human` (app/formatter) formata respostas de `/views/run`.
- `API_LATENCY_MS`, `API_ERRORS`, `ASK_ERRORS`, `DB_LATENCY_MS`, `DB_QUERIES`, `DB_ROWS` (app/observability/metrics) produzem métricas Prometheus desde o bootstrap do módulo.

### 2.2 Núcleo de configurações (`core/`)

**`settings.py`**

- Classe principal: `Settings(BaseSettings)`.
- Fonte: `.env` (via `SettingsConfigDict`).
- Métodos e propriedades relevantes:

| Membro | Assinatura | Descrição |
| ------ | ---------- | --------- |
| `database_url` | `str` | DSN obrigatório para Postgres; usado por `ExecutorService` e ferramentas. |
| `executor_mode` | `str = "read-only"` | Controla `ExecutorService` (read-only vs permissivo). |
| `ask_top_k` | `int = 2` | Limite superior de intents executadas no orquestrador. |
| `ask_min_score` | `float = 1.0` | Score mínimo para aceitar entidade. |
| `ask_default_limit` / `ask_max_limit` | `int` | Parâmetros aplicados pelo builder e orquestrador. |
| `nlp_relative_dates` | `bool = True` | Liga/desliga inferência de datas relativas (`_relative_date_range`). |
| `views_cache_ttl` / `tickers_cache_ttl` | `int` | TTL em segundos para catálogo e tickers. |
| `cache_backend`, `redis_url`, `cache_namespace` | `str`, `Optional[str]`, `str` | Configuração para `get_cache_backend()`. |
| `prometheus_url`, `grafana_url` | `str` | URLs usadas por `healthz_full()`. |
| `messages_path` | `str` | Caminho de `messages.yaml`. |
| `views_signature_mode`, `views_signature_key`, `views_signature_required` | `str`, `Optional[str]`, `bool` | Governam validação de assinatura em `registry.validator`. |
| `get_message(*keys, default=None)` | `def` | Percorre `messages.yaml` e retorna string ou default. |
| `messages` | `@property` | Cacheia `messages.yaml` com `lru_cache`.

**`messages.yaml`**

- Estrutura YAML com copy em português.
- Chaves usadas atualmente: `ask.status.ok`, `ask.fallback.intent_unmatched`.
- Expandível para mensagens de erro adicionais sem mudar código.

### 2.3 Executor SQL (`executor/`)

**`service.py`**

| Elemento | Assinatura | Detalhes |
| -------- | ---------- | -------- |
| `ExecutorService.__init__` | `(self)` | Inicializa pool (`ConnectionPool`), valida `database_url` e aplica `settings.db_pool_min/max`. |
| `ExecutorService._connect` | `() -> contextmanager` | Abstração para `pool.connection()`; usado internamente por `run` e `columns_for`. |
| `ExecutorService.run` | `(sql: str, params: Dict[str, Any] | None = None, row_limit: int = 100) -> List[Dict[str, Any]]` | Executa `cur.execute`, aplica `SET TRANSACTION READ ONLY` quando `executor_mode == "read-only"`, coleta linhas e imprime log hash do SQL. |
| `ExecutorService.columns_for` | `(entity: str) -> list[str]` | Usa `psycopg.sql.Identifier` para proteger nomes e retorna colunas reais da view. Levanta `ValueError` se entity contiver caracteres inválidos. |
| `executor_service` | Instância global | Singleton compartilhado.

**Dependências**

- `settings` para DSN, pool, modo de execução.
- Orquestrador (`route_question`), gateway (`_execute_view`), ferramentas (`snapshot`, `diff`, `augment`) dependem deste serviço.

### 2.4 Extratores e normalização (`extractors/`)

**`normalizers.py`**

- Classe principal: `ExtractedRunRequest(BaseModel)` com campos `entity`, `select`, `filters`, `order_by`, `limit` e defaults seguros (`Field(default_factory=dict)`).
- Funções auxiliares:

| Função | Assinatura | Propósito |
| ------ | ---------- | --------- |
| `_normalize_ticker(value)` | `(str) -> str` | Força padrão `AAAA11` (adiciona sufixo `11` quando necessário). |
| `_normalize_ticker_or_guess(value)` | `(str) -> str` | Wrapper para `_normalize_ticker`; usado para filtros `ticker`. |
| `_br_to_iso(date_str)` | `(str) -> str` | Converte datas `DD/MM/AAAA` ou `DD/MM/AA` para ISO. |
| `_normalize_dates_in_filters(filters)` | `(Dict[str, Any]) -> Dict[str, Any]` | Processa campos `*_from`, `*_to`, `date_from`, `date_to`, `*_date`, `*_until`, `*_at`. |
| `normalize_request(req)` | `(Dict[str, Any]) -> ExtractedRunRequest` | Cópia defensiva, valida entidade (`registry_service`), aplica normalizações e clampa `limit` ∈ [1, 1000]. |

**Uso cruzado**: `gateway._execute_view`, `gateway.healthz_full`, `orchestrator.route_question`, `orchestrator.build_run_request`.

### 2.5 Builder SQL (`builder/`)

**`service.py`**

- Classe: `BuilderService`.
- Métodos expostos:

| Método | Assinatura | Observações |
| ------ | ---------- | ----------- |
| `build_sql(req)` | `(ExtractedRunRequest) -> Tuple[str, Dict[str, Any]]` | Constrói SELECT, valida colunas contra YAML (`registry_service`), monta `WHERE`, detecta ranges (`*_from/_to`, `date_from/date_to`), aplica heurística de coluna de data (`default_date_field` ou sufixo `_date/_until/_at`), valida `order_by` usando `registry_service.order_by_whitelist`, aplica `LIMIT`. |

- Instância: `builder_service = BuilderService()`.
- Dependências diretas: `app.registry.service.registry_service` para colunas, identificadores, whitelist e `default_date_field`.

### 2.6 Formatação de resultados (`formatter/`)

**`serializer.py`**

| Elemento | Assinatura | Papel |
| -------- | ---------- | ----- |
| `_iso_to_br_date(s)` | `(str) -> str` | Converte ISO `YYYY-MM-DD` (ou com hora) em `DD/MM/YYYY`. |
| `_fmt_money_br(x)` | `(Any) -> Optional[str]` | Formata valores monetários (`R$ 1.234,56`). |
| `_fmt_percent_br(x)` | `(Any) -> Optional[str]` | Formata percentuais; multiplica por 100 quando necessário. |
| `_fmt_value_br(x, places)` / `_fmt_int_br(x)` | `(Any, int) -> Optional[str]` | Formatação genérica com separador `.` e vírgula decimal. |
| `_format_field(key, val)` | `(str, Any) -> Any` | Seleciona formatação com base no sufixo (`DATE_SUFFIXES`, `MONEY_SUFFIXES`, etc.). |
| `to_human(rows)` | `(List[Dict[str, Any]]) -> List[Dict[str, Any]]` | Aplica `_format_field` a cada campo em cada linha. |

- Constantes: `DATE_SUFFIXES`, `MONEY_SUFFIXES`, `PERCENT_SUFFIXES`, `AREA_SUFFIXES`, `VALUE_SUFFIXES`, `RATIO_SUFFIXES`, `THREE_DECIMAL_SUFFIXES`, `INT_SUFFIXES`.
- Importante para respostas de `/ask` e `/views/run`, garantindo legibilidade em PT-BR.

### 2.7 Infraestrutura de cache (`infrastructure/`)

**`cache.py`**

| Classe/Função | Assinatura | Comportamento |
| ------------- | ---------- | ------------- |
| `CacheBackend` | `ABC` | Define interface com `get`, `set`, `delete`. |
| `LocalCacheBackend` | `()` | Guarda pares `(valor, expiração)` em memória; TTL avaliado a cada `get`. |
| `RedisCacheBackend(url)` | `(str)` | Usa `redis.from_url`, suporta `setex` para TTL, e ignora falhas silenciosamente (fail-safe). |
| `NamespacedCache(inner, prefix)` | `(CacheBackend, str)` | Prefixa chaves (`namespace:key`). |
| `get_cache_backend()` | `() -> CacheBackend` | Seleciona `RedisCacheBackend` quando `CACHE_BACKEND=redis` e `REDIS_URL` válido; fallback para `LocalCacheBackend`. Sempre envolve em `NamespacedCache` usando `settings.cache_namespace`.

**Uso**

- `registry.preloader`: cacheia catálogo (`views:list`, `views:{entity}`, `views:hash`).
- `orchestrator.service`: `_CACHE` + `_TICKERS_KEY` para cachear lista de tickers válidos com TTL `settings.tickers_cache_ttl`.

### 2.8 Observabilidade embutida (`observability/`)

**`logging.py`**

| Componente | Assinatura | Descrição |
| ---------- | ---------- | --------- |
| `RequestIdFilter.filter(record)` | `(logging.LogRecord) -> bool` | Injeta `record.request_id` a partir de `contextvars`. |
| `RequestIdMiddleware.dispatch(request, call_next)` | `async` | Gera/propaga `X-Request-ID`, injeta em `request.state`, garante cabeçalho na resposta. |
| `setup_json_logging(level, fmt, file_path)` | `(str, str, Optional[str]) -> logging.Logger` | Reseta handlers do root logger, configura saída console (JSON ou texto) e arquivo com rotação (`RotatingFileHandler`). |
| `get_logger(name)` | `(str) -> logging.Logger` | Retorna logger configurado. |

**`metrics.py`**

- Gauge: `APP_INFO`, `APP_UP`, `API_LATENCY_MS`, `HEALTH_OK`.
- Histogram: `ASK_LATENCY_MS`, `DB_LATENCY_MS`.
- Counter: `ASK_ROWS`, `ASK_ERRORS`, `DB_QUERIES`, `DB_ROWS`, `API_ERRORS`.
- Funções:

| Função | Assinatura | Uso |
| ------ | ---------- | --- |
| `set_health(component, ok)` | `(str, bool) -> None` | Atualiza `HEALTH_OK`. |
| `prime_api_series()` | `() -> None` | Pré-registra séries (`/ask`, `/views/run`, entidade `__all__`) para evitar buracos nos dashboards e facilitar testes. |

### 2.9 Registro de catálogo (`registry/`)

**`loader.py`**

- Função `load_views(views_dir)` percorre `*.yaml`, carrega via `yaml.safe_load`, anexa `__file__`, valida estrutura (`validate_yaml_structure`) e assinatura (`verify_signature`), registrando warnings quando há erros.
- Dependências: `settings.views_signature_required` controla severidade dos erros de assinatura.

**`validator.py`**

- Modelos `AskBlock`, `ViewSchema` (`pydantic`) garantem formato.
- Funções:

| Função | Assinatura | Observação |
| ------ | ---------- | ---------- |
| `validate_yaml_structure(data)` | `(Dict[str, Any]) -> List[str]` | Retorna lista de mensagens de erro amigáveis quando `pydantic` falha. |
| `verify_signature(raw_text, data)` | `(str, Dict[str, Any]) -> Optional[str]` | Implementa modos `none`, `sha256`, `hmac` usando `settings.views_signature_mode/key`. |

**`preloader.py`**

- Função `preload_views()`:
  1. Consulta cache (`views:loaded`, `views:list`, `views:{entity}`).
  2. Se vazio, chama `load_views(views_dir)` (`views_dir` via env `VIEWS_DIR` ou `data/views`).
  3. Persiste catálogo no cache (`views:list`, `views:{entity}`, `views:hash` com `hashlib.sha256`).
- Utiliza `settings.views_cache_ttl` para TTL.

**`service.py`**

- Classe `RegistryService` com cache interno `_cache: Dict[str, Dict[str, Any]]`.
- Métodos públicos:

| Método | Assinatura | Descrição |
| ------ | ---------- | --------- |
| `reload()` | `() -> None` | Recarrega `_cache` via `preload_views()`.
| `list_all()` | `() -> List[Dict[str, Any]]` | Lista entidades ordenadas com `columns` (como strings) e `identifiers`.
| `get(entity)` | `(str) -> Optional[Dict[str, Any]]` | Retorna cópia do metadado com colunas normalizadas (`name` → string). |
| `get_columns(entity)` | `(str) -> List[str]` | Lista colunas (strings) da entidade. |
| `get_ask_block(entity)` | `(str) -> Dict[str, Any]` | Retorna bloco `ask` (dict). |
| `get_identifiers(entity)` | `(str) -> List[str]` | Identificadores declarados. |
| `order_by_whitelist(entity)` | `(str) -> List[str]` | Usa whitelist do YAML (normalizada) ou fallback para todas as colunas. |

- Instância global: `registry_service = RegistryService()` (carregada no import).

### 2.10 Orquestrador NL→SQL (`orchestrator/`)

O coração do envelope v4 reside em `app/orchestrator/service.py`. Principais elementos:

- **Cache de tickers**:
  - `_CACHE = get_cache_backend()` e `_TICKERS_KEY = "tickers:list:v1"` (namespaced automaticamente).
  - `_refresh_tickers_cache()` consulta `executor_service.run("SELECT ticker FROM view_fiis_info…")`, salva JSON com TTL `settings.tickers_cache_ttl`.
  - `_load_valid_tickers(force=False)` tenta `get` no cache; se falhar, chama `_refresh_tickers_cache()`. O TTL padrão vem de settings (ex.: 300s).

- **Helpers de metadados**:
  - `_meta(entity)` e `_cols(entity)` consultam `registry_service`.
  - `_ask_meta(entity)` monta dicionário com intents, keywords, synonyms, weights, latest_words e `top_k` do bloco `ask`. Também normaliza tokens (`_tokenize`, `_unaccent_lower`).
  - `_parse_weight` aceita valores float/int/strings/listas e cai no default 1.0.

- **Scoring com `ask_min_score`, `ask_top_k`, `synonyms`, `weights`**:
  - `_score_entity(tokens, entity)` calcula score = `keywords_hits * weights['keywords'] + synonym_hits * weights['synonyms'] + description_hits*0.5`. O melhor intent é retornado.
  - `_choose_entity_by_ask(question)` itera `registry_service.list_all()` e retorna `(best_entity, best_intent, score)`.
  - `_choose_entities_by_ask(question)` retorna lista ordenada de `(entity, intent, score)` para todas com score > 0. `route_question` aplica `settings.ask_min_score` e fatiamento `[:settings.ask_top_k]` para multi-intenção.

- **Datas relativas (`nlp_relative_dates`)**:
  - `_extract_dates_range(question)` procura expressões `entre dd/mm/aaaa e dd/mm/aaaa`. Caso não encontre e `settings.nlp_relative_dates` seja `True`, usa `_relative_date_range` para interpretar frases como `últimos 6 meses`, `ano atual`, `mês anterior` (via `relativedelta`).
  - `_resolve_date_range(question, explicit_range)` combina data explícita do payload (`date_range.from/to`) com as inferidas.

- **Planejamento e filtros**:
  - `_plan_question(question, entity, intent, payload)` junta tickers extraídos (`_extract_tickers` + cache) e datas resolvidas. Cria `planner_filters` (para telemetria) e `run_request` pronto para normalização.
  - Regras de ordenação: se `latest_words` casarem, força `order_by` DESC por `default_date_field`, `limit = 1`. Se pergunta contiver `entre` e houver data, ordena ASC.

- **Cliente e trace**:
  - `_client_echo(raw)` replica `client_id`, `nickname` e normaliza saldo (`balance_before`, `balance_after`), preservando request_id do payload.

- **API principal**:
  - `build_run_request(question, overrides=None)` fornece o `run_request` pronto (usado em testes ou no `/views/run`). Falha se score < `settings.ask_min_score`.
  - `route_question(payload)` implementa fluxo completo: mede latência total (`ASK_LATENCY_MS`, `API_LATENCY_MS`), seleciona entidades (`ask_top_k`), normaliza (via `normalize_request`), constrói SQL (`builder_service.build_sql`), executa (`executor_service.run`), formata (`to_human`), agrega resultados por intent e publica métricas de banco. Em fallback, retorna mensagem de `settings.get_message("ask", "fallback", "intent_unmatched")`.

**Tabela resumida de funções**

| Função | Assinatura | Descrição |
| ------ | ---------- | --------- |
| `_refresh_tickers_cache()` | `() -> List[str]` | Atualiza cache de tickers consultando DB; TTL controlado por `settings.tickers_cache_ttl`. |
| `_load_valid_tickers(force=False)` | `(bool) -> set[str]` | Obtém tickers (cache-first). |
| `_tokenize(text)` | `(str) -> List[str]` | Normaliza texto (unaccent + regex `[a-z0-9]{2,}`). |
| `_ask_meta(entity)` | `(str) -> Dict[str, Any]` | Extrai intents, keywords, synonyms, weights, latest_words, top_k. |
| `_score_entity(tokens, entity)` | `(List[str], str) -> Tuple[float, Optional[str]]` | Calcula score ponderado e melhor intent. |
| `_choose_entity_by_ask(question)` | `(str) -> Tuple[Optional[str], Optional[str], float]` | Retorna melhor entidade+intent. |
| `_choose_entities_by_ask(question)` | `(str) -> List[Tuple[str, str, float]]` | Lista entidades ranqueadas (para multi-intenção). |
| `_relative_date_range(text_norm)` | `(str) -> Dict[str, str]` | Interpreta frases relativas (últimos meses, mês anterior, ano atual). |
| `_extract_dates_range(text)` | `(str) -> Dict[str, str]` | Detecta range explícito `entre dd/mm/aaaa e dd/mm/aaaa` e delega para `_relative_date_range`. |
| `_resolve_date_range(question, explicit_range)` | `(str, Optional[Dict[str, Any]]) -> Dict[str, str]` | Consolida datas do payload + inferidas. |
| `_extract_tickers(text, valid)` | `(str, set[str]) -> List[str]` | Detecta tickers e variantes (XXXX + sufixo 11 implícito). |
| `_plan_question(question, entity, intent, payload)` | `(str, str, Optional[str], Dict[str, Any]) -> Dict[str, Any]` | Prepara `run_request`, `planner`, lista `tickers` detectados. |
| `_client_echo(raw)` | `(Optional[Dict[str, Any]]) -> Dict[str, Any]` | Normaliza bloco `client` na resposta (ecoando IDs, saldos). |
| `build_run_request(question, overrides=None)` | `(str, Optional[Dict[str, Any]]) -> Dict[str, Any]` | Retorna `run_request` resolvido (erro se score < min). |
| `route_question(payload)` | `(Dict[str, Any]) -> Dict[str, Any]` | Orquestra NL→SQL, atualiza métricas, devolve envelope completo. |

### 2.11 Inicialização e composição (`main.py`)

| Função | Assinatura | Responsabilidade |
| ------ | ---------- | ---------------- |
| `lifespan(app)` | `asynccontextmanager` | Antes de servir: `prime_api_series()`, `preload_views()`, `healthz_full()`, `_refresh_tickers_cache()`. Inicia tarefa periódica (30s) para atualizar `APP_UP` e revalidar saúde. No final: define `APP_UP=0`, cancela tarefa, fecha `executor_service.pool`. |
| `create_app()` | `() -> FastAPI` | Configura `FastAPI(title="Sirios Mosaic", lifespan=lifespan)`, aplica `RequestIdMiddleware`, inclui `gateway_router`, monta `/metrics` (`make_asgi_app()`), retorna instância. |
| `app` | Instância global | Resultado de `create_app()` importável por WSGI/ASGI servers. |

- Logging configurado no módulo (antes de criar app) via `setup_json_logging(level=settings.log_level, fmt=settings.log_format, file_path=settings.log_file)`.

### 2.12 Serviços auxiliares e notas

- Embora não haja `app/services/` dedicado, cada serviço (builder/executor/orchestrator/registry) expõe instâncias singletons (`*_service`) que cumprem o papel solicitado.
- `app/__init__.py`, `app/builder/__init__.py`, etc. estão vazios apenas para marcar pacotes Python.

### 2.13 Fluxo NL→SQL ponta-a-ponta

1. **Entrada HTTP**: `/ask` recebe `AskRequest` (FastAPI → Pydantic).
2. **Orquestração**: `route_question` pontua entidades (`synonyms`, `keywords`, `weights`), respeita `ask_min_score` e `ask_top_k`.
3. **Planejamento**: `_plan_question` monta `run_request` com filtros (`tickers`, `date_from/to`, `order_by`). Datas relativas dependem de `settings.nlp_relative_dates`.
4. **Normalização**: `normalize_request` valida entidade (`registry_service`), normaliza ticker (NL→`XXXX11`) e datas (BR→ISO).
5. **Construção SQL**: `builder_service.build_sql` aplica restrições do catálogo YAML (colunas permitidas, `order_by_whitelist`, `default_date_field`).
6. **Execução**: `executor_service.run` (psycopg) executa SQL e mede latência; `DB_LATENCY_MS`, `DB_QUERIES`, `DB_ROWS` são atualizados.
7. **Formatação**: `formatter.to_human` converte datas e números para formato brasileiro.
8. **Resposta**: Orquestrador agrega `results`, `planner`, `status`, `meta` (inclui `rows_total`, `rows_by_intent`, `limits.top_k`) e `usage` (placeholder). Métricas `ASK_LATENCY_MS`, `ASK_ROWS`, `API_LATENCY_MS` são emitidas.
9. **Observabilidade**: Logs estruturados via `RequestIdMiddleware`, métricas expostas em `/metrics` para Prometheus.

### 2.14 Métricas e observabilidade

- `ASK_ROWS` e `ASK_LATENCY_MS` recebem labels `entity` (real e `__all__` agregado). Cada execução incrementa contadores e histograma.
- `DB_LATENCY_MS`, `DB_QUERIES`, `DB_ROWS` são atualizados por entidade em `_execute_view` e no orquestrador.
- `API_LATENCY_MS` (Gauge) é setado com latência da última requisição por endpoint (`/ask`, `/views/run`). `API_ERRORS` é incrementado para `validation` ou `runtime`.
- `healthz_full()` atualiza `HEALTH_OK` para `app`, `db`, `prometheus`, `grafana`.
- `APP_UP` (Gauge) indica disponibilidade (1 durante lifespan ativo, 0 ao encerrar).

### 2.15 🔹 Pipeline de geração dos YAMLs

Fluxo completo de manutenção do catálogo:

1. **COMMENT ON MATERIALIZED VIEW**: o time de dados documenta views/colunas no Postgres usando `COMMENT ON MATERIALIZED VIEW` e `COMMENT ON COLUMN`, incluindo bloco `||ask:` para intents, keywords e synonyms.
2. **`tools/snapshot_views_from_db.py`**: gera YAML base com `entity`, `identifiers`, `default_date_field`, `order_by_whitelist` e colunas (sem descrições) a partir do banco.
3. **`tools/augment_yaml_from_db_comments.py`**: lê comentários do Postgres e injeta `description`, `ask`, `columns[].description`/`alias` no YAML. Flags `--overwrite-view-desc`, `--overwrite-columns` controlam substituição. O script parseia `||ask:` e separa blocos (e.g. `synonyms`, `keywords`).
4. **`data/views/*.yaml`**: arquivos versionados com metadados completos (colunas, ask, descriptions, assinatura opcional). `registry_service` carrega estes arquivos e os expõe.
5. **`registry_service` reload**: `POST /admin/views/reload` ou boot do app chama `preload_views()`; se Redis estiver habilitado (`CACHE_BACKEND=redis`), o catálogo é cacheado para múltiplas instâncias.
6. **Orquestrador**: consome `registry_service.get_ask_block()` para pontuar intents e montar planos.

Resumo linear:

```text
COMMENT (DB) → snapshot (YAML base) → augment (YAML + ask) → registry reload → orquestrador
```

---

## 3. Plataforma de observabilidade externa (`observabilidade/` na raiz)

A pasta raiz `observability/` agrupa a stack Prometheus/Grafana/Loki/Promtail configurada via `docker-compose.yml`. 🧠

- `prometheus/prometheus.yml`: define scrapes para `prometheus` e `mosaic` (`metrics_path: /metrics`). Intervalo padrão 15s.
- `prometheus/alert_rules.yml`: regras de alerta para taxa de erro no `/ask`, P95 do banco (`histogram_quantile` sobre `mosaic_db_latency_ms`) e disponibilidade (`mosaic_app_up`).
- `grafana/dashboards/*.json`: dashboards provisionados (home, monthly, ops, overview, perf) montados automaticamente via `provisioning/`.
- `grafana/provisioning/`: datasources, alerting e playlists definindo conexões com Prometheus/Loki.
- `loki-config.yaml` + `promtail-config.yml`: configuram centralização de logs. `promtail` coleta `./logs` montado pelo serviço Mosaic e envia para Loki.
- `docker-compose.yml`: orquestra containers `mosaic`, `redis`, `prometheus`, `grafana`, `loki`, `promtail`. Integrações principais:
  - Monta `observability/prometheus/*.yml` dentro do container Prometheus.
  - Provisiona dashboards/datasources no Grafana.
  - Liga Promtail a Loki e monta volume de logs compartilhado com o app.
  - Configura healthcheck HTTP em `http://localhost:8000/healthz` para o container Mosaic.

---

## 4. Estratégia de testes (`tests/`)

### 4.1 Filosofia e camadas de testes

- **Unitários**: validam componentes isolados (`builder`, `formatter`, `extractors`, `registry`, `settings`). Exemplos: `test_builder_sql_basic`, `test_formatter_br.py`, `test_suffix_formatters.py`.
- **Integração**: exercitam múltiplas camadas sem depender de Postgres real (stub do executor). Arquivo chave: `test_end_to_end.py`, `test_integration_pg.py` (usa stub para rows, mas valida pipeline completo inclusive formatter e métricas).
- **Ponta-a-ponta (E2E)**: `test_integration_pg.py::test_e2e_ask_real_db_and_formatter` simula o fluxo NL→SQL completo e verifica formatação, metadados e métricas. `test_ask_route_multi_intent` garante múltiplas intenções.

`tests_catalog.json` e `tests_catalog_hardening.json` não estão presentes no repositório atual; a referência histórica indica que, quando utilizados, listam cenários NL→SQL para serem reproduzidos contra ambientes reais e de hardening. O pipeline atual confia diretamente nos YAMLs e no `registry_service`, e esses catálogos podem ser adicionados futuramente para ampliar a cobertura.

### 4.2 Testes de API e NL→SQL

- `test_end_to_end.py`:
  - Usa `TestClient(app)` e fixture `stub_executor` (monkeypatch em `executor_service.run`) para simular respostas previsíveis.
  - `test_ask_route_basic`: garante que `/ask` retorna `status.ok`, ecoa dados do cliente e entrega resultados formatados.
  - `test_ask_route_fallback_message`: valida mensagem de fallback quando não há match de intenção (usa `messages.yaml`).
  - `test_ask_route_multi_intent`: assegura que múltiplas intenções são retornadas quando `ask_top_k` > 1, simulando respostas para dividendos/notícias.
- `test_integration_pg.py`:
  - Fixture substitui `executor_service.run` e `columns_for` para usar colunas do `registry_service` (mantendo coerência YAML).
  - `test_e2e_ask_real_db_and_formatter`: valida pipeline completo, incluindo formatação BR de datas.
  - `test_yaml_db_consistency_subset`: chama `/admin/validate-schema` e compara colunas YAML vs DB (simulado).
  - `test_prometheus_metrics_series_exist` e `test_ask_metrics_exposed`: confirmam exposição de métricas em `/metrics` após execuções.
- `test_ask_errors.py`: garante que `/views/run` responde erro apropriado quando entidade não existe.

### 4.3 Testes de infraestrutura e utilitários

- `test_builder.py`: valida SQL gerado, limites e rejeição de colunas desconhecidas.
- `test_formatter_br.py`, `test_suffix_formatters.py`: cobrem formatação monetária, percentuais, datas.
- `test_cache_parity.py`: compara comportamento de caches local vs redis (quando mockado).
- `test_executor_real.py`: pode exigir Postgres real para validar `columns_for` e `run` (normalmente marcado para execução condicional).
- `test_registry.py`, `test_registry_validator.py`: asseguram que YAMLs são carregados e validados corretamente.
- `test_extractors_isolation.py`: verifica que normalizações não vazam estado entre instâncias.
- `test_settings_env.py`: confirma carregamento de variáveis de ambiente padrão (`.env` e defaults).

### 4.4 Catálogo de testes automatizados

Estrutura padronizada:

```text
tests/
├── conftest.py          # carrega .env e define defaults (EXECUTOR_MODE, DATABASE_URL)
├── test_end_to_end.py   # integração NL→SQL com TestClient
├── test_integration_pg.py
├── test_builder.py
├── test_formatter_br.py
├── ... (demais testes unitários)
```

Os testes fazem uso intensivo de `monkeypatch` para substituir `executor_service`, garantindo determinismo sem tocar no banco real. A ausência atual de `tests_catalog*.json` significa que cenários NL adicionais podem ser gerenciados diretamente nos YAMLs e nos testes parametrizados quando introduzidos.

---

## 5. Ferramentas de catálogo (`tools/`)

### 5.1 Snapshot do banco → YAML

`tools/snapshot_views_from_db.py`:

- Usa `executor_service.columns_for(entity)` para introspectar views predefinidas em `VIEWS` (dicionário hardcoded com `identifiers` e `default_date_field`).
- Gera YAMLs em `VIEWS_DIR` (default `data/views`) com `order_by_whitelist` deduzido (`ORDER_BY_GUESSES`).
- Requer `EXECUTOR_MODE != dummy` e `DATABASE_URL` configurado.

### 5.2 Enriquecimento com comentários/ASK

`tools/augment_yaml_from_db_comments.py`:

- Conecta ao Postgres (`psycopg.connect`), lê `COMMENT ON MATERIALIZED VIEW` e `COMMENT ON COLUMN`.
- `parse_view_comment` separa descrição da view e bloco `ask` (`||ask:key=v1,v2;`), produzindo dict de intents/keywords/synonyms.
- `apply_view_comment` e `apply_col_comments` atualizam YAML com descrições e aliases (quando presentes no COMMENT `Descrição | Alias`).
- Suporta `--entity`, `--write`, `--overwrite-view-desc`, `--overwrite-columns` para controle fino. Dry-run padrão.

### 5.3 Diferença YAML × banco

`tools/diff_yaml_db.py`:

- Recarrega `registry_service` para garantir leitura dos YAMLs atuais.
- Para cada entity (ou filtrado via `--entity`), compara colunas do YAML (`yaml_colnames`) com `executor_service.columns_for`.
- Gera resumo/detalhes no terminal ou JSON (`--json`). Útil para detectar drift de schema.

### 5.4 Higienização e prune

- `tools/prune_yaml_by_db.py`: identifica YAMLs sem view correspondente (`columns_for` vazio ou erro) e oferece remoção interativa.
- `tools/cleanup_alias_redundant.py`: remove aliases redundantes (iguais ao nome) das colunas YAML, mantendo arquivos enxutos.

### 5.5 Pipeline de sincronização

Fluxo recomendado (ver também seção 2.15):

```bash
# 1. Gera snapshot inicial das views
python tools/snapshot_views_from_db.py

# 2. Enriquecer com comentários e blocos ASK
python tools/augment_yaml_from_db_comments.py --write

# 3. Revisar diferenças em relação ao banco
python tools/diff_yaml_db.py --only-mismatch

# 4. Limpar aliases redundantes ou YAMLs órfãos
python tools/cleanup_alias_redundant.py
python tools/prune_yaml_by_db.py

# 5. Recarregar catálogo no app
curl -X POST http://localhost:8000/admin/views/reload
```

Esse pipeline garante que `registry_service` reflita fielmente o banco e que o orquestrador disponha de intents atualizadas.

---

## 6. Apêndice — Integrações, configuração e endpoints

### 6.1 Variáveis de ambiente críticas

Principais variáveis (.env / Settings):

- `EXECUTOR_MODE`: `read-only` ou `dummy`. Define se o executor aplica `SET TRANSACTION READ ONLY`.
- `DATABASE_URL`: DSN Postgres para execução real.
- `DB_SCHEMA`: schema base usado pelos tools (`augment_yaml_from_db_comments`).
- `PROMETHEUS_URL` / `GRAFANA_URL`: usados em `healthz_full()`.
- `ASK_MIN_SCORE`, `ASK_TOP_K`: limites de seleção de entidades no orquestrador.
- `ASK_DEFAULT_LIMIT`, `ASK_MAX_LIMIT`: limites do builder para `LIMIT`.
- `NLP_RELATIVE_DATES`: habilita interpretação automática de datas relativas.
- `CACHE_BACKEND`, `REDIS_URL`, `CACHE_NAMESPACE`: configuram caching para catálogo e tickers.
- `VIEWS_CACHE_TTL`, `TICKERS_CACHE_TTL`: TTL em segundos para caches.
- `PROMETHEUS_URL`, `GRAFANA_URL`: health-checks externos.
- `LOG_FORMAT`, `LOG_LEVEL`, `LOG_FILE`, `LOG_MAX_MB`, `LOG_BACKUPS`: logging estruturado.
- `MOSAIC_VERSION`, `GIT_SHA`: expostos em `APP_INFO` para dashboards.

### 6.2 Endpoints FastAPI expostos

- `GET /healthz`: health check leve.
- `GET /healthz/full`: verifica DB, Prometheus, Grafana e atualiza métricas `HEALTH_OK`.
- `GET /views`: lista catálogo (entity, colunas, identificadores).
- `GET /views/{entity}`: metadados completos do YAML (colunas com descrição, ask, etc.).
- `GET /views/{entity}/columns`: apenas nomes de colunas.
- `POST /views/run`: executa view com filtros explícitos (usa normalização/builder/executor/formatter).
- `POST /ask`: pergunta NL → múltiplas intents/entidades; resposta inclui planner, resultados formatados, metadados e métricas atualizadas.
- `POST /admin/views/reload`: força reload dos YAMLs para o `registry_service`.
- `GET /admin/validate-schema`: compara YAML vs DB e retorna diffs.
- `GET /metrics`: endpoint Prometheus servido por `prometheus_client.make_asgi_app()`.

### 6.3 Interação dos testes automatizados

- Testes usam `fastapi.testclient.TestClient` (`test_end_to_end.py`, `test_integration_pg.py`, `test_ask_errors.py`) para emitir requisições HTTP reais contra o app configurado com os middlewares e métricas.
- `monkeypatch` injeta `stub_executor` (substituindo `executor_service.run` e `columns_for`) para cenários determinísticos.
- Após chamadas a `/ask` ou `/views/run`, testes consultam `/metrics` para garantir exposição de séries (`mosaic_api_latency_ms`, `mosaic_db_latency_ms`, etc.).
- `conftest.py` pré-carrega `.env` e define defaults (`EXECUTOR_MODE=read-only`, `DATABASE_URL` fake) para isolar ambiente de CI.

---

✅ Esta visão detalhada permite navegar pelas camadas do Sirios Mosaic, compreender dependências e estender o sistema com segurança.

