# Estado Real do Mosaic – Outubro/2025

## 1. Escopo do diagnóstico
- Diretório `app/`: serviços de registro, builder, executor, extratores, formatter, gateway e observabilidade, além do bootstrap FastAPI em `main.py`.【F:app/registry/service.py†L1-L71】【F:app/builder/service.py†L1-L97】【F:app/executor/service.py†L1-L37】【F:app/extractors/normalizers.py†L1-L73】【F:app/formatter/serializer.py†L1-L20】【F:app/gateway/router.py†L41-L746】【F:app/observability/metrics.py†L1-L45】【F:app/main.py†L1-L58】
- Catálogo YAML em `data/views/` (8 arquivos) e DDL auxiliar em `data/ddl/views.sql`.【F:data/views/view_fiis_info.yaml†L1-L86】【F:data/views/view_fiis_history_dividends.yaml†L1-L31】【F:data/views/view_fiis_history_prices.yaml†L1-L40】【F:data/views/view_fiis_history_assets.yaml†L1-L48】【F:data/views/view_fiis_history_news.yaml†L1-L40】【F:data/views/view_fiis_history_judicial.yaml†L1-L48】【F:data/views/view_history_taxes.yaml†L1-L66】【F:data/views/view_market_indicators.yaml†L1-L38】【F:data/ddl/views.sql†L1-L120】
- Infraestrutura de observabilidade (`observability/*`), composição Docker e dependências do projeto.【F:observability/prometheus/prometheus.yml†L1-L16】【F:observability/promtail-config.yml†L1-L19】【F:observability/loki-config.yaml†L1-L37】【F:observability/grafana/provisioning/dashboards/dashboards.yml†L1-L11】【F:docker-compose.yml†L1-L74】【F:pyproject.toml†L1-L27】
- Testes automatizados atuais em `tests/` (3 arquivos).【F:tests/test_registry.py†L1-L6】【F:tests/test_builder.py†L1-L10】【F:tests/test_end_to_end.py†L1-L15】

## 2. Estrutura e modularidade
- **Gateway (`app/gateway`)**: concentra rotas HTTP, heurísticas NL→SQL, validações, métricas e caching de tickers. Importa diretamente registry, extractor, builder, executor, formatter e métricas, evidenciando forte acoplamento e ausência de um módulo `orchestrator` separado.【F:app/gateway/router.py†L41-L746】
- **Registry**: carrega YAML dinamicamente em cache, expõe colunas, identificadores e whitelist de ordenação.【F:app/registry/loader.py†L4-L17】【F:app/registry/service.py†L11-L68】
- **Builder**: gera SQL com validações de colunas/identificadores e suporte a filtros simples, ranges e heurística de datas.【F:app/builder/service.py†L6-L95】
- **Executor**: modo `dummy` ou Postgres real sem camada de abstração adicional; não há logs nem wrappers de segurança além do DSN fornecido.【F:app/executor/service.py†L7-L34】
- **Extractors**: normalizam ticker e datas, mas usam defaults mutáveis em `ExtractedRunRequest.filters`, arriscando compartilhamento de estado entre execuções.【F:app/extractors/normalizers.py†L7-L56】
- **Formatter**: apenas converte datas ISO para padrão brasileiro; não cobre moeda ou percentuais conforme design do README.【F:app/formatter/serializer.py†L10-L20】
- **Observability**: disponibiliza métricas Prometheus e middleware de logging JSON com `request_id` propagado.【F:app/observability/metrics.py†L8-L45】【F:app/observability/logging.py†L1-L109】
- **Bootstrap (`app/main.py`)**: monta FastAPI, middleware e /metrics, mas importa `healthz_full` diretamente do gateway, reforçando acoplamento e inexistência de camada orquestradora separada.【F:app/main.py†L13-L55】
- **Módulos ausentes ou stubs**: não há pastas `orchestrator` nem `builder` alternativo conforme blueprint do README; `app/orchestrator/` e `app/builder/__init__.py` são vazios ou inexistentes, mostrando desvio do design modular previsto.【F:README.md†L33-L70】

## 3. Registry e Views
- Existem 8 YAMLs no catálogo (`view_fiis_info`, `view_fiis_history_dividends`, `view_fiis_history_prices`, `view_fiis_history_assets`, `view_fiis_history_news`, `view_fiis_history_judicial`, `view_history_taxes`, `view_market_indicators`).【F:data/views/view_fiis_info.yaml†L1-L86】【F:data/views/view_fiis_history_dividends.yaml†L1-L31】【F:data/views/view_fiis_history_prices.yaml†L1-L40】【F:data/views/view_fiis_history_assets.yaml†L1-L48】【F:data/views/view_fiis_history_news.yaml†L1-L40】【F:data/views/view_fiis_history_judicial.yaml†L1-L48】【F:data/views/view_history_taxes.yaml†L1-L66】【F:data/views/view_market_indicators.yaml†L1-L38】 O README ainda fala em 13 views, logo o catálogo está incompleto.【F:README.md†L15-L26】
- O carregamento é dinâmico via `os.listdir`, atribuindo `entity` e origem do arquivo; qualquer novo YAML é incluído sem código adicional, embora sem validações de schema ou linting.【F:app/registry/loader.py†L4-L17】
- `RegistryService` disponibiliza colunas, identificadores e whitelist de `order_by`, mas não valida tipos nem garantias de consistência entre YAML e banco.【F:app/registry/service.py†L15-L68】
- Há hardcodes relevantes: `view_fiis_info` usado como fallback para cache de tickers, healthcheck, e fallback de intents, contrariando modularidade estrita.【F:app/gateway/router.py†L58-L66】【F:app/gateway/router.py†L379-L387】【F:app/gateway/router.py†L649-L669】
- Placeholders e validações implementadas: exemplos de blocos `ask` com `keywords`/`latest_words` (dividendos, taxas, etc.).【F:data/views/view_fiis_history_dividends.yaml†L1-L31】【F:data/views/view_history_taxes.yaml†L1-L66】 Não há validação automática desses campos além do consumo heurístico no gateway.

## 4. Query Builder
- Construção de SQL é baseada em metadados: seleção de colunas permitidas, checagem de filtros contra `columns`/`identifiers`, ranges `_from/_to` e heurística para `date_from/date_to`. Limit e order_by respeitam whitelist do registry.【F:app/builder/service.py†L6-L95】
- A montagem final é feita por interpolação direta (`f"SELECT ... FROM {req.entity}"`), embora `entity` tenha sido verificado no registry; não há uso de ORM ou query builder formal.【F:app/builder/service.py†L81-L95】
- `where` usa placeholders parametrizados `%()` mitigando injeção, porém não há normalização de nomes de coluna além do YAML, e não existe whitelist explícita para funções ou expressões agregadas.
- Não há mapeamento de `order_by` para direções customizadas além de `ASC/DESC`; colunas são whitelistadas pelo registry.【F:app/builder/service.py†L85-L94】

### Exemplo real do Builder
```python
sql = f"SELECT {', '.join(select_cols)} FROM {req.entity}"
if where:
    sql += " WHERE " + " AND ".join(where)
sql += f" LIMIT {int(req.limit)}"
```
【F:app/builder/service.py†L81-L95】

## 5. Executor
- `ExecutorService` aceita modo `dummy` (retorna eco do SQL) ou conecta via `psycopg` com `autocommit=True`; o Docker Compose define `EXECUTOR_MODE=read-only`, mas o código não distingue este valor e portanto executa queries sem forçar sessão read-only ou `readonly=True` na conexão.【F:app/executor/service.py†L7-L34】【F:docker-compose.yml†L3-L25】
- Parâmetros de conexão dependem apenas da variável `DATABASE_URL`; não há pooling, retry, TLS ou mascaramento de credenciais nos logs (não existem logs de executor).【F:app/executor/service.py†L16-L22】
- `columns_for` executa `SELECT * FROM {entity} LIMIT 0` sem parametrização extra, assumindo que o nome da view é seguro – novamente herdando o hardcode de entidades do registry.【F:app/executor/service.py†L24-L34】
- Logs estruturados não capturam `sql_hash`; `_execute_view` apenas registra erros e métricas, e o auditoria `/ask` gera `question_hash`, não hash do SQL executado.【F:app/gateway/router.py†L491-L504】【F:app/gateway/router.py†L689-L739】

## 6. Formatter e Extractors
- `to_human` converte apenas campos terminados em `date`/`data` de ISO para `DD/MM/AAAA`; não há formatação para moeda (`R$`) ou percentuais, apesar de requisitos do README.【F:app/formatter/serializer.py†L10-L20】【F:README.md†L76-L88】
- `normalize_request` impõe limite máximo 1000 linhas, normaliza ticker (`XXXX`→`XXXX11`) e datas BR para ISO, mas usa defaults mutáveis (`filters={}`) tanto no Pydantic Model quanto no dicionário retornado, o que pode vazar estado entre requisições sob carga multi-thread.【F:app/extractors/normalizers.py†L7-L56】
- Funções auxiliares `_normalize_ticker_or_guess` e `_normalize_dates_in_filters` existem, mas não são chamadas; sugerem plano de reutilização ainda não realizado.【F:app/extractors/normalizers.py†L58-L73】
- Não há padronização de tickers com fallback para lista oficial além do cache do gateway; o extractor não valida contra o registry.

## 7. NL Orchestrator (intents)
- A lógica de intents está embutida no gateway: seleção da view via `ask.keywords`, ranking de entidades, inferência de filtros (ticker, datas) e seleção de colunas por comentários, tudo antes de chamar `RunViewRequest`. Não existe módulo `orchestrator` dedicado.【F:app/gateway/router.py†L256-L336】【F:app/gateway/router.py†L531-L741】
- A expansão via YAML é suportada: novos `keywords`/`latest_words` entram no ranking sem alterar código, desde que o YAML seja atualizado.【F:app/gateway/router.py†L256-L336】
- Hardcodes persistem: fallback global para `view_fiis_info`, order heuristics por palavras como "último" e limites fixos (1 ou 500) diretamente no código.【F:app/gateway/router.py†L548-L579】【F:app/gateway/router.py†L649-L669】
- Não há fallback para LLM externo; todo fluxo é heurístico. Quando não encontra dados, gera metadados `not_found` ou busca fallback na view de cadastro.【F:app/gateway/router.py†L600-L669】
- O endpoint `/ask` retorna lista de seções e metadados, mas os testes assumem resposta plana (`{"entity": ...}`), mostrando desalinhamento de contrato.【F:app/gateway/router.py†L689-L741】【F:tests/test_end_to_end.py†L11-L15】

## 8. Observability
- Métricas Prometheus implementadas: `mosaic_app_info`, `mosaic_ask_latency_ms`, `mosaic_ask_rows_total`, `mosaic_ask_errors_total`, `mosaic_db_latency_ms`, `mosaic_db_queries_total`, `mosaic_db_rows_total`, `mosaic_app_up`, `mosaic_api_latency_ms`, `mosaic_api_errors_total`, `mosaic_health_ok`. Nenhuma métrica de custo (`ask_cost_total`) está presente, apesar do roadmap.【F:app/observability/metrics.py†L8-L45】
- Logging estruturado com `RequestIdMiddleware` garante `request_id` em todos os registros e oferece opção de arquivo com rotação.【F:app/observability/logging.py†L1-L109】
- `/metrics` exposto via `make_asgi_app`; healthchecks fornecem `/healthz` e `/healthz/full`, mas não existe `/__health/ping` conforme padrão citado pelo usuário.【F:app/main.py†L34-L55】【F:app/gateway/router.py†L356-L410】
- Integração com Loki/Grafana/Prometheus provisionada via Docker Compose e arquivos de provisioning (datasources, dashboards, playlists).【F:docker-compose.yml†L27-L74】【F:observability/grafana/provisioning/datasources/datasource.yml†L1-L20】【F:observability/grafana/provisioning/dashboards/dashboards.yml†L1-L11】【F:observability/prometheus/prometheus.yml†L1-L16】【F:observability/promtail-config.yml†L1-L19】

## 9. Testes
- `test_registry_loaded` apenas verifica que o registry retorna lista; não checa validade dos YAMLs.【F:tests/test_registry.py†L1-L6】
- `test_builder_sql_basic` cobre construção básica com ticker fixo `VINO11`; não testa validação de colunas, ranges ou order_by.【F:tests/test_builder.py†L1-L10】
- `test_end_to_end` chama `/ask`, mas a asserção espera chave `entity` na raiz – incompatível com o payload de seções, logo o teste falha atualmente. Não há simulação do executor real nem validação completa NL→SQL→DB→Formatter.【F:tests/test_end_to_end.py†L1-L15】【F:app/gateway/router.py†L689-L741】
- Não existem testes de integração com Postgres, validação do YAML vs DB, nem cobertura para observabilidade.

## 10. Código hardcoded e riscos
- **Views e intents fixas**: strings como `"view_fiis_info"` aparecem em cache de ticker, healthcheck, fallback de intents e testes, criando dependência forte dessa view.【F:app/gateway/router.py†L58-L66】【F:app/gateway/router.py†L379-L387】【F:app/gateway/router.py†L649-L669】【F:tests/test_end_to_end.py†L11-L15】
- **Limites e heurísticas estáticas**: limites `1`, `100`, `500` e TTL de 5 minutos codificados no gateway, sem configuração externa.【F:app/gateway/router.py†L42-L67】【F:app/gateway/router.py†L548-L579】【F:app/gateway/router.py†L584-L633】
- **Dependências externas**: URLs de Prometheus/Grafana fixos no código, embora sobrescrevíveis por variáveis de ambiente; Docker Compose impõe paths fixos (`/srv/data/views`, `/var/log/mosaic`).【F:app/gateway/router.py†L44-L45】【F:docker-compose.yml†L9-L23】
- **Dados sensíveis**: não há tokens/API keys no repositório. Contudo, `EXECUTOR_MODE=read-only` não tem efeito prático; recomenda-se implementar uso de roles read-only ou `SET default_transaction_read_only = on`.
- **Mutable defaults**: `ExtractedRunRequest.filters` com `{}` compartilhado e `normalize_request` mutando esse dict podem introduzir vazamento de filtros entre requisições – refatorar para `Field(default_factory=dict)` ou cópia defensiva.【F:app/extractors/normalizers.py†L7-L44】
- **Contratos desalinhados**: teste de `/ask` assume resposta antiga, indicando mudança de contrato sem atualização de consumidores ou documentação.【F:tests/test_end_to_end.py†L11-L15】
- **Ferramentas utilitárias** (`tools/*.py`) mencionam entidades específicas (`view_fiis_info`) para sincronizar YAML com DB, reforçando dependências manuais no catálogo.【F:tools/augment_yaml_from_db_comments.py†L23-L23】【F:tools/snapshot_views_from_db.py†L6-L6】

## 11. Resumo final – Estado Real do Mosaic
| Item | Situação | Observações |
| --- | --- | --- |
| ✅ Registry dinâmico | Carrega YAMLs automaticamente e expõe colunas/identificadores.【F:app/registry/loader.py†L4-L17】【F:app/registry/service.py†L28-L68】 |
| ✅ Métricas e logging | Prometheus e middleware JSON com `request_id` ativos; dashboards provisionados.【F:app/observability/metrics.py†L8-L45】【F:app/observability/logging.py†L1-L109】【F:observability/grafana/provisioning/datasources/datasource.yml†L1-L20】 |
| ⚙️ Query builder | Usa metadados e parâmetros, mas ainda monta SQL via f-string (risco residual).【F:app/builder/service.py†L6-L95】 |
| ⚙️ Executor | Conecta ao Postgres, porém sem enforcement de role read-only nem logs/`sql_hash`.【F:app/executor/service.py†L7-L34】 |
| ⚙️ NL heurístico | Fluxo `/ask` funciona com intents YAML, porém fortemente acoplado ao gateway e hardcodes de views/limites.【F:app/gateway/router.py†L256-L741】 |
| ⚙️ Formatter | Apenas datas BR; falta moeda/percentual conforme objetivo do projeto.【F:app/formatter/serializer.py†L10-L20】【F:README.md†L76-L88】 |
| ⚙️ Testes | Existem smoke tests, mas não cobrem contrato real nem pipeline completo; um teste falha devido a payload diferente.【F:tests/test_end_to_end.py†L11-L15】 |
| 🚧 Orchestrator modular | Pasta `orchestrator/` não existe; heurísticas NL estão no gateway, contrariando blueprint.【F:README.md†L33-L70】【F:app/gateway/router.py†L256-L741】 |
| 🚧 Catálogo completo | Apenas 8 views YAML; roadmap prevê 13 e ausência de validação formal do schema.【F:data/views/view_fiis_info.yaml†L1-L86】【F:README.md†L15-L26】 |
| 🚧 Hardcodes críticos | Dependência explícita em `view_fiis_info`, limites mágicos e defaults mutáveis exigem refatoração para config centralizada.【F:app/gateway/router.py†L58-L66】【F:app/gateway/router.py†L548-L669】【F:app/extractors/normalizers.py†L7-L56】 |

**Nível de prontidão estimado para Fase 2 (LLM seguro): 45%.** A base oferece registry dinâmico, builder parametrizado e observabilidade inicial, mas carece de separação de orquestração, endurecimento do executor read-only, catálogo completo/validado e testes end-to-end representativos.
