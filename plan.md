## 🧩 Etapa 6 — Validador YAML Dinâmico

**Objetivo:** validar estrutura mínima dos 8 YAMLs (sem fixar nomes).

### 🔹 Arquivos a solicitar

* `app/registry/loader.py`
* `app/registry/service.py`
* *(novo)* `app/registry/validator.py`
* 1 YAML de exemplo (`data/views/view_fiis_info.yaml`)

### 🔹 Ações previstas

1. Criar `validator.py` com Pydantic ou Yamale:
   Campos obrigatórios: `entity`, `columns`, `identifiers`, `ask`.
2. Integrar ao loader — apenas avisa via log/metric se inválido.
3. Adicionar `test_registry_validator.py`.

---

## 🧩 Etapa 7 — Config Centralizada

**Objetivo:** mover limites/URLs mágicos para `settings.py`.

### 🔹 Arquivos a solicitar

* `app/gateway/router.py`
* `app/main.py`
* *(novo)* `app/core/settings.py` se não existir

### 🔹 Ações previstas

1. Centralizar:

   * TTLs de cache, limites (`100`, `500`, etc.),
   * URLs Prometheus/Grafana,
   * executor mode default.
2. Usar `pydantic-settings` ou `os.getenv()`.
3. Testar override via `.env`.

---

## 🧩 Etapa 8 — Integração Docker PG e E2E

**Objetivo:** validar fluxo NL→SQL→DB→Formatter.

### 🔹 Arquivos a solicitar

* `docker-compose.yml`
* `tests/test_end_to_end.py`
* *(novo)* `tests/test_integration_pg.py`

### 🔹 Ações previstas

1. Adicionar container `postgres-test` (separado).
2. Executar queries via executor real (`read-only`).
3. Validar consistência entre YAML e DB (`columns_for`).
4. Coletar métricas (`db_latency_ms`, `rows_total`).

---

## 🚀 Ordem recomendada de envio dos arquivos

1. `app/extractors/normalizers.py`
2. `app/executor/service.py`
3. `app/gateway/router.py`
4. `app/formatter/serializer.py`
5. `app/registry/{loader.py,service.py}`
6. 1 YAML (ex.: `view_fiis_info.yaml`)
7. `app/main.py`
8. `docker-compose.yml`
9. `tests/test_end_to_end.py`

---

Se concordar, **começamos pela Etapa 1 (Extractor Seguro)**.
👉 Me envie o conteúdo atual de `app/extractors/normalizers.py` para eu gerar o patch limpo (refactor com `default_factory` e cópia defensiva).

Posso também já criar o *commit message* padrão (`fix(extractors): safer defaults and copy isolation`) se quiser deixar padronizado.
Confirmo e seguimos?
