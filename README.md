# Sirios Mosaic

> **Arquitetura Modular do Projeto Sirios (v1.0 – Outubro/2025)**
> “Pequenas peças, grandes respostas.”

---

## 🌌 Visão Geral

**Sirios Mosaic** é a arquitetura modular do ecossistema **Sirios**, criada para transformar perguntas em português em consultas SQL seguras e auditáveis — sobre dados financeiros estruturados.

O núcleo do Mosaic é **100% dinâmico**: o sistema descobre automaticamente os *views* disponíveis em `data/views/*.yaml` (atualmente **8 views oficiais**), sem qualquer referência fixa no código.
Cada módulo é independente e se comunica via contratos simples, formando a pipeline:

```
Usuário → Gateway/API → Orchestrator NL → Extractors → Registry (YAMLs)
→ Query Builder → Executor RO → Formatter → Resposta
```

---

## 🎯 Objetivo

Oferecer uma experiência **segura, modular e evolutiva** de NL→SQL:

* Execução **read-only** em Postgres (sem DML/DDLs);
* **Separação de responsabilidades** entre módulos;
* **Catálogo centralizado e autodetectável** (`data/views/*.yaml`);
* **Formatos 100% brasileiros** (datas, moeda, percentuais);
* **Observabilidade nativa** (Prometheus + Grafana + logs estruturados);
* **Evolução incremental** (cada módulo pode ser adicionado, sem quebrar o todo).

---

## 🧩 Módulos Principais

| Módulo              | Função                                                           | Pasta / Serviço     |
| ------------------- | ---------------------------------------------------------------- | ------------------- |
| **Gateway/API**     | Entrada pública (FastAPI): autenticação, roteamento, rate-limit. | `app/gateway`       |
| **Orchestrator NL** | Interpreta perguntas e define a *view* e filtros adequados.      | `app/orchestrator`  |
| **Extractors**      | Normalizam ticker, datas BR, períodos e filtros.                 | `app/extractors`    |
| **Views Registry**  | Carrega e valida YAMLs de views dinâmicos.                       | `app/registry`      |
| **Query Builder**   | Gera SQL seguro e parametrizado a partir dos metadados.          | `app/builder`       |
| **Executor RO**     | Executa SQL em Postgres (read-only).                             | `app/executor`      |
| **Formatter**       | Formata datas, moeda (BRL) e percentuais para exibição.          | `app/formatter`     |
| **Observability**   | Métricas, logs e tracing estruturado.                            | `app/observability` |

---

## 🗂️ Estrutura Atual de Diretórios

```
sirios-mosaic/
├── app/
│   ├── gateway/          # FastAPI principal
│   ├── orchestrator/     # Regras NL→View (em implantação)
│   ├── registry/         # Leitor/validador dinâmico de YAMLs
│   ├── builder/          # SQL seguro e parametrizado
│   ├── executor/         # Execução read-only no Postgres
│   ├── formatter/        # Datas, moedas e percentuais BR
│   ├── extractors/       # Normalização e parsing
│   ├── observability/    # Métricas e logs Prometheus/Loki
│   └── main.py
├── data/views/           # Catálogo dinâmico (8 YAMLs)
├── tests/                # Casos NL→SQL e smoke-tests
├── docker-compose.yml
├── README.md
└── pyproject.toml
```

---

## 📅 Convenções (Brasil)

* **Datas:** entrada e saída `DD/MM/AAAA` (internamente ISO `YYYY-MM-DD`);
* **Moeda:** `R$ 12.345,67`;
* **Percentuais:** `7,25%`;
* **Ticker:** normalizado apenas na entrada (`HGLG` → `HGLG11`).

---

## 🔐 Segurança e Validação

* SQL gerado exclusivamente pelo **Query Builder** (sem concatenação livre).
* **Whitelist de colunas e ordenações** por view (via YAML).
* **Proteções básicas**: nega `;`, `COPY`, `DROP`, `--`, `/* */`, `WITH` não autorizado.
* **Role Postgres read-only** e `SET default_transaction_read_only = on`.
* **Logs auditáveis** com `request_id` e `sql_hash`.

---

## 📊 Observabilidade

* **Métricas Prometheus:** `mosaic_ask_latency_ms`, `mosaic_db_latency_ms`, `mosaic_db_rows_total`, `mosaic_ask_errors_total`, `mosaic_health_ok`.
* **Grafana:** dashboards “Mosaic Gateway” e “Mosaic Builder”.
* **Logs:** formato JSON, com `request_id` propagado.

---

## 🚀 Roadmap

**Fase 0** – Skeleton com 2 views (`fiis_info`, `fiis_history_dividends`).
**Fase 1** – Catálogo dinâmico completo (8 views) + observabilidade.
**Fase 2** – LLM seguro (fallback inteligente via Orchestrator).
**Fase 3** – SDK + OpenAPI + exportações (CSV, Parquet, API externa).

---

## 🧠 Filosofia

O **Sirios Mosaic** é feito para crescer sem perder integridade.
Cada peça sabe o que é — e o que não é —, e o todo se adapta à medida que novas peças surgem.

> “Arquitetura é quando cada parte sabe o que é — e o que não é.”
> — *Leleo & Sirius, 2025*

---

## ⚙️ Licença e Contribuição

* Licença: MIT
* Versionamento: `YYYYMMDDHHMM` + alias `current`
* Toda alteração de view ou contrato requer PR com **testes e changelog**

---

**Sirios Mosaic**
© 2025 – Projeto de Pesquisa e Desenvolvimento **Sirios / Knowledge AI**
