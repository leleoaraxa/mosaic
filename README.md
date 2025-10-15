# Sirios Mosaic

> **Arquitetura Modular do Projeto Sirios (v1.0 – Outubro/2025)**
> “Pequenas peças, grandes respostas.”

---

## 🌌 Visão Geral

**Sirios Mosaic** é a nova arquitetura modular do ecossistema **Sirios**, projetada para permitir que o usuário converse em linguagem natural sobre dados financeiros estruturados — transformando perguntas em português em consultas SQL seguras, baseadas nas 13 views oficiais.

Cada módulo do Mosaic é uma **peça independente** de um mosaico maior. Juntas, elas formam a pipeline:

```
Usuário → Gateway/API → Orquestrador NL → Extractors → Registry (YAMLs) → Query Builder → Executor RO → Formatter → Resposta
```

---

## 🎯 Objetivo

Garantir uma experiência **segura, modular e evolutiva** de NL→Views:

* 100% **read-only** (Postgres protegido, sem DML/DDLs);
* **Separação de responsabilidades** entre módulos;
* **Catálogo centralizado** via YAMLs (`view_fiis_*`, `view_history_*`, `view_market_*`);
* **Datas, moeda e linguagem 100% brasileiras**;
* **Observabilidade nativa** (Prometheus + Grafana + logs estruturados);
* **Expansão incremental** (adiciona-se um módulo por vez, sem quebrar o sistema).

---

## 🧩 Módulos Principais

| Módulo              | Função                                                       | Repositório / Pasta    |
| ------------------- | ------------------------------------------------------------ | ---------------------- |
| **Gateway/API**     | Entrada pública; autenticação, CORS, rate limit, roteamento. | `mosaic-gateway`       |
| **NL Orchestrator** | Interpreta perguntas e decide intent/view.                   | `mosaic-orchestrator`  |
| **Extractors**      | Normaliza ticker, datas BR, períodos e filtros.              | `mosaic-extractors`    |
| **Views Registry**  | Carrega e valida YAMLs de views.                             | `mosaic-registry`      |
| **Query Builder**   | Gera SQL seguro a partir dos metadados.                      | `mosaic-builder`       |
| **Executor RO**     | Executa SQL em Postgres com role de leitura.                 | `mosaic-executor`      |
| **Formatter**       | Formata a resposta (moeda BRL, %, datas BR).                 | `mosaic-formatter`     |
| **Observability**   | Métricas, logs, auditoria e tracing.                         | `mosaic-observability` |

---

## 🗂️ Estrutura Inicial de Diretórios

```
sirios-mosaic/
├── app/
│   ├── gateway/          # FastAPI principal
│   ├── orchestrator/     # Regras NL→View
│   ├── registry/         # Leitor/validador dos YAMLs
│   ├── builder/          # Geração de SQL seguro
│   ├── executor/         # Execução RO no Postgres
│   ├── formatter/        # Saída BR (datas, moedas, %)
│   ├── extractors/       # Normalizadores
│   ├── observability/    # Métricas e logs
│   └── main.py
├── data/views/           # 13 YAMLs do catálogo oficial
├── tests/                # Fixtures e casos NL→SQL
├── docker-compose.yml
├── README.md
└── pyproject.toml
```

---

## 📅 Convenções (BR)

* **Datas:** `DD/MM/AAAA` (exibição e entrada); internamente `YYYY-MM-DD`.
* **Moeda:** `R$ 12.345,67`.
* **Percentuais:** `7,25%`.
* **Ticker:** normalizado apenas na entrada (ex.: `HGLG` → `HGLG11`).

---

## 🔐 Segurança e Validação

* Queries geradas apenas pelo Builder (sem SQL dinâmico).
* Whitelist de colunas e ordenações por view.
* Denylist SQL: `;`, `COPY`, `DROP`, `--`, `/* */`, `WITH` não controlado.
* Role Postgres de leitura (`SELECT` only).
* Logs auditáveis com `request_id` e `sql_hash`.

---

## 📊 Observabilidade

* Prometheus: `ask_cost_total`, `ask_rows_returned`, `nl_router_latency_ms`, `db_latency_ms`.
* Grafana: painéis “Mosaic Gateway” e “Mosaic Builder”.
* Logs JSON estruturados.

---

## 🚀 Roadmap

**Fase 0** – Skeleton com 2 views (`view_fiis_info`, `view_fiis_history_dividends`).
**Fase 1** – Cobertura 13/13 + observabilidade.
**Fase 2** – LLM seguro com catálogo fechado.
**Fase 3** – SDK + OpenAPI + exportações (CSV, Parquet).

---

## 🧠 Filosofia

O Sirios Mosaic é projetado para **crescer mantendo o contexto**.
Cada módulo é uma peça que **encaixa sem depender internamente do outro**, e cada contrato é testável e auditável.

> “Arquitetura é quando cada parte sabe o que é — e o que não é.”
> — *Leleo & Sirius, 2025*

---

## ⚙️ Licença e Contribuição

* Licença: MIT.
* Regras de contribuição e versionamento: `YYYYMMDDHHMM` + alias `current`.
* Toda alteração de view ou contrato requer PR com testes e changelog.

---

**Sirios Mosaic**
© 2025 – Projeto de Pesquisa e Desenvolvimento **Sirios / Knowledge AI**
