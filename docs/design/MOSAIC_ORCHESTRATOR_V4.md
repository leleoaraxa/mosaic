# 📘 `docs/design/MOSAIC_ORCHESTRATOR_V4.md`

> **Sirios Mosaic – Orquestrador NL→SQL (v4)**
> *Design funcional, contratos e sincronização de catálogo*

---

## 🌌 1. Visão Geral

O **orquestrador** é o núcleo semântico do Mosaic: interpreta perguntas em linguagem natural, identifica intenções e entidades (views), monta consultas SQL seguras e devolve respostas contextualizadas.

Versão **v4** introduz:

* fan-out de intenções (ex.: dividendos + notícias);
* múltiplos tickers (`IN`);
* intervalos de datas dinâmicos (“4 meses antes”, “mês anterior”);
* mensagens educativas configuráveis;
* padronização de acentuação e tokens;
* sincronização automática entre **PostgreSQL → YAMLs**;
* envelope rico de request/response (com cliente, status, planner, meta).

---

## ⚙️ 2. Fluxo NL→SQL Simplificado

```
Usuário → /ask → Gateway → Orchestrator
    → Extratores (tickers, datas, intenções)
        → Builder (gera SQL parametrizado)
            → Executor (Postgres read-only)
                → Serializer (to_human)
                    → Resposta enriquecida
```

---

## 🧩 3. Envelope JSON – Contratos

### 3.1 Request

```jsonc
{
  "question": "últimos dividendos e notícias do HGLG e KNRI",
  "top_k": 10,
  "date_range": {"from": "2024-01-01", "to": "2024-03-31"},
  "client": {
    "token": "opaque-or-jwt",
    "client_id": "cli_123",
    "nickname": "Leleo",
    "balance": 123.45
  },
  "trace": {"request_id": "external-correlation-id"}
}
```

**Notas**

* `question` obrigatório.
* `date_range` opcional; se ausente, NLP infere (inclui expressões relativas).
* `client` apenas ecoado, sem lógica financeira nesta versão.
* `top_k` limita por intenção (default em settings).

---

### 3.2 Response

```jsonc
{
  "request_id": "abcd-123",
  "original_question": "últimos dividendos e notícias do HGLG e KNRI",
  "client": {
    "client_id": "cli_123",
    "nickname": "Leleo",
    "balance_before": 123.45,
    "balance_after": 123.45
  },
  "status": {"reason": "ok", "message": "Tudo certo!"},
  "planner": {
    "intents": ["dividends", "news"],
    "entities": [
      {"intent": "dividends", "entity": "view_fiis_history_dividends"},
      {"intent": "news", "entity": "view_fiis_history_news"}
    ],
    "filters": {
      "tickers": ["HGLG11", "KNRI11"],
      "date_field": "payment_date",
      "date_from": "2024-01-01",
      "date_to": "2024-03-31"
    }
  },
  "results": {
    "dividends": [/* até top_k */],
    "news": [/* até top_k */]
  },
  "meta": {
    "elapsed_ms": 18,
    "rows_total": 6,
    "rows_by_intent": {"dividends": 3, "news": 3},
    "limits": {"top_k": 3}
  },
  "usage": {"tokens_prompt": 0, "tokens_completion": 0, "cost_estimated": 0.0}
}
```

**Valores possíveis de `status.reason`**

| Reason             | Significado                            |
| ------------------ | -------------------------------------- |
| `ok`               | Tudo resolvido normalmente             |
| `intent_unmatched` | Nenhuma intenção atingiu score mínimo  |
| `partial_fanout`   | Apenas parte das intenções respondidas |
| `error`            | Falha controlada (builder/DB/etc.)     |

---

## 🧠 4. NLP e Regras Semânticas

### 4.1 Extração

* **Tickers**: aceita múltiplos; gera `ticker__in` se >1.
* **Datas**: reconhece `entre ... e ...` e expressões relativas (“últimos 3 meses”, “mês anterior”).
* **Intenções**: tokens comparados com `ask.synonyms.*` e `ask.keywords`.
* **Últimos / mais recentes**: definidos em YAML (`ask.latest_words`).

### 4.2 Normalização

* Tudo processado em **minúsculo e sem acento**.
* Saídas e YAMLs mantêm acentuação original para exibição.

### 4.3 Fallback Educativo

* Removido fallback para `view_fiis_info`.
* Se nenhuma intenção aceita, retorna `intent_unmatched` com mensagem de ajuda vinda de `settings.messages.*`.

---

## 🗓️ 5. Intervalos Relativos

Exemplos (base = data atual):

| Expressão         | Intervalo derivado              |
| ----------------- | ------------------------------- |
| “últimos 3 meses” | from = hoje − 90d, to = hoje    |
| “4 meses antes”   | from = hoje − 120d, to = hoje   |
| “mês anterior”    | início e fim do mês anterior    |
| “ano atual”       | 01/01 até 31/12 do ano corrente |

Controlado por `settings.nlp.relative_dates = true`.

---

## 🗃️ 6. YAML por Entidade (`ask.synonyms + pesos`)

### Estrutura padrão

```yaml
entity: view_fiis_history_dividends
description: Snapshot de dividendos históricos
default_date_field: payment_date

ask:
  intents: [dividends, historico]
  keywords: [dividendos, rendimentos, proventos]
  synonyms:
    dividends: [dividendos, rendimentos, proventos, pagamentos]
    latest: [último, últimos, mais recente]
  weights:
    keywords: 1
    synonyms: 2
  top_k: 6
  latest_words: [último, mais recente, últimos]
```

### Convenções de escrita

* Evitar duplicações (“historico” vs “histórico”).
* Acentuação normal, mas preloader cria versão normalizada (`keywords_normalized`).
* `top_k` local substitui limite global.

---

## 🧾 7. Comentários SQL → YAML

### Sintaxe padrão

```sql
COMMENT ON MATERIALIZED VIEW view_fiis_info IS
'Descrição da view.||
ask:intents=cadastro,perfil,info;
keywords=cadastro,dados,ficha,cnpj,site,administrador;
synonyms.cadastro=cadastro,dados;
latest_words=último,últimos,mais recente;';
```

### Colunas

```sql
COMMENT ON COLUMN view_fiis_info.ticker IS
'Código do fundo na B3.|Código FII';
```

### Convenções

| Parte            | Significado                      |               |                                    |
| ---------------- | -------------------------------- | ------------- | ---------------------------------- |
| Texto antes de ` |                                  | `             | Descrição humana                   |
| Após `           |                                  | `             | Metadados (`chave=valor1,valor2;`) |
| Após `           | ` em coluna                      | Alias exibido |                                    |
| Prefixo `ask:`   | Bloco semântico copiado pro YAML |               |                                    |

---

## 🔄 8. Sincronização DB ↔ YAML

### Scripts disponíveis

| Comando                                                 | Ação                             |
| ------------------------------------------------------- | -------------------------------- |
| `python -m tools.snapshot_views_from_db`                | Gera YAMLs fiéis ao DB           |
| `python -m tools.diff_yaml_db`                          | Diff humano entre DB e YAML      |
| `python -m tools.diff_yaml_db --json`                   | Diff em JSON (CI/CD)             |
| `python -m tools.augment_yaml_from_db_comments --write` | Atualiza descrições e blocos ask |
| `--entity view_fiis_info`                               | Limita a uma view                |

### Automação no boot

O `preloader` pode verificar hash YAML x hash DB e:

* emitir log de divergência;
* opcionalmente atualizar YAMLs (`auto_sync_views: true`).

### Configs

```yaml
settings:
  auto_sync_views: true
  sync_views_on_startup: true
  sync_views_write: false
```

---

## 🛠️ 9. Endpoints Administrativos

| Método                       | Rota                                   | Função |
| ---------------------------- | -------------------------------------- | ------ |
| `POST /admin/views/reload`   | Recarrega catálogo em cache            |        |
| `POST /admin/views/sync`     | Sincroniza YAMLs com comentários do DB |        |
| `GET /admin/views/diff`      | Retorna diff YAML↔DB em JSON           |        |
| `GET /admin/validate-schema` | Valida schema de views (já existe)     |        |

Métricas associadas:

* `mosaic_views_reloaded_total`
* `mosaic_views_sync_total`
* `mosaic_views_diff_detected_total`

---

## 📊 10. Limites por Entidade

Controla o número de linhas retornadas por tipo de view.

### Configuração global

```yaml
limits:
  ask_default_limit: 100
  ask_max_limit: 1000
  top_k_default: 3
  rows_by_entity:
    view_fiis_history_dividends: 6
    view_fiis_history_news: 3
    view_fiis_info: 1
```

### Prioridade de aplicação

1. `YAML.ask.top_k`
2. `settings.limits.rows_by_entity[entity]`
3. `settings.limits.top_k_default`

---

## 🧱 11. Arquivos-alvo

| Caminho                                      | Papel                                                       |
| -------------------------------------------- | ----------------------------------------------------------- |
| `app/orchestrator/service.py`                | Core NL→SQL (intents, datas, tickers, planner)              |
| `app/registry/preloader.py`                  | Cache e sincronização YAML↔DB                               |
| `app/registry/service.py`                    | Registro central de views e metadados                       |
| `app/core/settings.py`                       | Novas chaves `messages`, `limits`, `nlp`, `auto_sync_views` |
| `app/gateway/router.py`                      | Delegação limpa para `route_question()`                     |
| `app/tools/augment_yaml_from_db_comments.py` | Parser de comentários SQL                                   |
| `app/tools/diff_yaml_db.py`                  | Comparação YAML↔DB                                          |
| `docs/design/MOSAIC_ORCHESTRATOR_V4.md`      | Este documento                                              |
| `data/views/*.yaml`                          | Catálogo de views (por entidade)                            |

---

## 🧭 12. Fases de Implementação

| Fase  | Escopo                                                  | Status esperado |
| ----- | ------------------------------------------------------- | --------------- |
| **1** | Vocabulários YAML, mensagens educativas, eco de cliente | ✅ sem quebra    |
| **2** | Multi-ticker + fan-out (dividends/news) + top_k         | 🔄 novos testes |
| **3** | Sincronização automática e endpoints admin              | 🔜              |
| **4** | Intervalos relativos + métricas de intent/fanout        | 🔜              |

---

## ✅ 13. Resultado Esperado

* Todas as 40 suítes antigas continuam verdes.
* Novos testes cobrindo:

  * `intent_unmatched` com mensagens educativas;
  * multi-ticker;
  * fan-out de intenções;
  * sync YAML↔DB dry-run;
  * limite por entidade (top_k).

> O **Sirios Mosaic v4** passa a ser semanticamente expansível, auditável e educativo — sem aumentar complexidade de código nem perder determinismo.

---

💾 **Fim do Documento — `docs/design/MOSAIC_ORCHESTRATOR_V4.md`**
