# 🧭 Sprint de Saneamento Mosaic – v1.0 (Outubro/2025)
> “Corrigir para crescer.” — *Sirios Core Engineering*

---

## 🧩 Objetivo Geral
Consolidar o **núcleo do Sirios Mosaic** (8 views dinâmicas) para operação estável, segura e modular, preparando terreno para a **Fase 2 (LLM seguro)**.

---

## 📅 Duração sugerida
**2 semanas (10 dias úteis)**
Cada sprint é incremental: fecha 1 módulo + 1 teste de regressão.
Finaliza com a suíte NL→SQL→DB→Formatter 100% verde.

---

## 🧱 Estrutura da Sprint (8 Etapas)

| Nº | Etapa / Módulo | Objetivo Técnico | Dependências | Entregáveis | Status Esperado |
|----|-----------------|------------------|---------------|--------------|-----------------|
| **1** | **Extractor Seguro** | Eliminar `defaults mutáveis` e vazamento de estado em `filters`. | Nenhuma | `extractors/normalizers.py` corrigido + teste unitário. | ✅ `Field(default_factory=dict)` e cópia defensiva aplicada. |
| **2** | **Executor Read-only Real** | Aplicar enforcement de `EXECUTOR_MODE=read-only`; logar `sql_hash`, tempo e linhas. | Etapa 1 (para E2E limpo) | Novo wrapper `execute_readonly()`, logs e métricas. | ✅ Queries com `SET default_transaction_read_only=on`. |
| **3** | **Orchestrator Modular** | Extrair heurísticas NL→SQL do gateway para `app/orchestrator/`. | Etapa 2 | Novo módulo `orchestrator/` + adaptador no gateway. | ✅ Gateway limpo; `route(question)` isolado. |
| **4** | **Contrato `/ask` & Testes** | Alinhar schema de resposta (seções) e atualizar `test_end_to_end.py`. | Etapa 3 | Testes E2E atualizados e doc `/ask_schema.json`. | ✅ Todos testes passam com payload novo. |
| **5** | **Formatter BR Completo** | Adicionar formatação de `BRL` e `percentuais`. | Independente | `formatter/serializer.py` ampliado + 3 testes novos. | ✅ Datas, moeda e `%` padronizados BR. |
| **6** | **Validador YAML Dinâmico** | Implementar validação leve (Pydantic/Yamale) para `data/views/*.yaml`. | Etapa 3 | `registry/validator.py` + testes `test_registry_validator.py`. | ✅ Schema mínimo garantido (entity, columns, identifiers, ask). |
| **7** | **Config Centralizada (Settings)** | Migrar limites, TTLs, URLs fixos do gateway para `settings.py`. | Etapa 3 | Novos env vars + remoção de mágicos. | ✅ Gateway limpo e parametrizável. |
| **8** | **Integração Docker PG / Tests E2E** | Reforçar pipeline NL→SQL→DB→Formatter usando container PG real. | Etapas 1–7 | Compose testado + `test_integration_pg.py`. | ✅ Suíte verde, logs e métricas auditáveis. |

---

## 🧩 Checkpoints e Dependências

```
(1) Extractor Seguro
       ↓
(2) Executor Read-only
       ↓
(3) Orchestrator Modular
       ↓
(4) Contrato /ask
    ↙       ↘
(5) Formatter BR     (6) Validador YAML
       ↓               ↓
       └── (7) Config Centralizada
                    ↓
             (8) Integração Docker PG
```

- **Dependência crítica:** Orchestrator modular (Etapa 3) é o pivot da arquitetura — o Gateway só será “limpo” após essa entrega.
- **Dependência suave:** Formatter e Validador podem caminhar em paralelo.

---

## 🧩 Critérios de Aceite (por módulo)

| Área | Critério |
|------|-----------|
| **Segurança** | Nenhum SQL concatenado; `EXECUTOR_MODE=read-only` funcional. |
| **Confiabilidade** | Testes unitários e E2E passando; logs estruturados por request. |
| **Manutenibilidade** | Nenhum valor mágico fora de `settings`; modularização completa. |
| **Compatibilidade** | `/ask` retorna payload documentado e testado. |
| **Conformidade BR** | Datas, moedas e percentuais formatados conforme padrão nacional. |

---

## 📦 Entrega Final

**Branch:** `chore/refactor-mosaic-harden-202510`
**Docs incluídos:**
- `SIRIOS_MOSAIC_REFACTOR_PLAN.md`
- `SIRIOS_MOSAIC_PATCH_NOTES.md`
- `ask_schema.json`
- `test_summary.log` (saída pytest final)

---

## ✅ Checklist de Implementação

| Etapa | Implementado | Testado | Revisado | Observações |
|-------|--------------|----------|-----------|--------------|
| 1 – Extractor Seguro | [ ] | [ ] | [ ] | |
| 2 – Executor Read-only | [ ] | [ ] | [ ] | |
| 3 – Orchestrator Modular | [ ] | [ ] | [ ] | |
| 4 – Contrato /ask | [ ] | [ ] | [ ] | |
| 5 – Formatter BR | [ ] | [ ] | [ ] | |
| 6 – Validador YAML | [ ] | [ ] | [ ] | |
| 7 – Config Centralizada | [ ] | [ ] | [ ] | |
| 8 – Integração Docker PG | [ ] | [ ] | [ ] | |

---

## 🔭 Pós-Sprint (Fase 2 Preparatória)

1. Introduzir *fallback heurístico + LLM seguro* no `orchestrator`.
2. Adicionar métrica `ask_cost_total` (para custos de inferência).
3. Ativar tracing distribuído (tempo NL→SQL→DB).
4. Revisar schema observability (`mosaic_db_latency_ms`, `ask_latency_ms`, `ask_rows_total`).

---

**Sirios Mosaic — Sprint de Saneamento v1.0**
© 2025 – Projeto de Pesquisa e Desenvolvimento **Sirios / Knowledge AI**
