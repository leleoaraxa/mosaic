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


## 🟦 **Intent: cadastro/financeiro FIIs**

1. me mostra o cadastro do VINO11
2. qual o CNPJ do HGLG11?
3. quem é o administrador do KNRI11?
4. o XPML11 é de gestão ativa ou passiva?
5. qual o público-alvo do GGRC11?
6. quando foi o IPO do HCTR11?
7. o FII PVBI11 é listado em qual segmento?
8. quem é o custodiante do CPTS11?
9. qual o tipo de fundo do TRXF11?
10. qual o website oficial do BTLG11?
11. o VISC11 é um fundo exclusivo?
12. me dá o código ISIN do HGRU11
13. qual o setor e classificação do XPLG11?
14. o VILG11 tem data de constituição de quando?
15. qual o nome B3 do HFOF11?
16. qual o valor de mercado do HGLG11?
17. me mostra o P/VP do KNRI11
18. qual o dividend payout do MXRF11?
19. qual o cap rate do PVBI11?
20. o XPLG11 tem alta volatilidade?
21. mostra o Sharpe Ratio do HCTR11
22. qual a taxa de crescimento do VISC11?
23. qual o enterprise value do GGRC11?
24. o HFOF11 tem bom retorno por cota?
25. quanto é o equity per share do CPTS11?
26. o TRXF11 tem alta relação preço/patrimônio?
27. mostra o revenue per share do VILG11
28. qual o índice de payout do BTLG11?
29. o KNCR11 tem cap rate acima de 9%?
30. me dá o market cap e o EV do XPML11

---

## 🟩 **Intent: dividendos**

1. qual foi o último dividendo pago pelo HGLG11?
2. quanto o KNRI11 pagou no último mês?
3. qual o yield atual do CPTS11?
4. o XPLG11 pagou dividendo em agosto?
5. me mostra o dividendo mais recente do PVBI11
6. quanto o HCTR11 distribuiu em setembro de 2025?
7. qual o DY médio dos últimos 12 meses do VISC11?
8. o MXRF11 pagou dividendo em dezembro passado?
9. qual a data de pagamento mais recente do RECR11?
10. quanto o VGIR11 pagou por cota em janeiro de 2025?
11. me dá o último valor pago pelo HFOF11
12. qual foi o yield do GGRC11 no mês passado?
13. mostra o histórico resumido de dividendos do XPML11
14. o KNCR11 distribuiu proventos em abril?
15. quanto o BTLG11 pagou no último repasse?

---

## 🟨 **Intent: historico dividendos**

1. mostra o histórico de dividendos do HGLG11
2. quanto o KNRI11 pagou em cada mês de 2024?
3. qual foi o total de dividendos do PVBI11 no último ano?
4. lista os pagamentos do MXRF11 em 2023
5. me dá o histórico anual de dividendos do CPTS11
6. quanto o VISC11 distribuiu mês a mês?
7. o HCTR11 pagou mais em 2023 ou 2024?
8. qual o mês de maior pagamento do XPLG11?
9. quanto o BTLG11 pagou em março de 2024?
10. traz o histórico de dividendos do GGRC11
11. o HFOF11 reduziu o pagamento recentemente?
12. mostra a média mensal de dividendos do KNCR11
13. qual o menor dividendo já pago pelo VILG11?
14. quando o TRXF11 começou a pagar dividendos?
15. histórico completo de dividendos do XPML11

---

## 🟧 **Intent: precos**

1. qual o preço atual do HGLG11?
2. quanto o KNRI11 fechou hoje?
3. me mostra o preço do PVBI11 na última cotação
4. o MXRF11 subiu nos últimos dias?
5. qual a média móvel de 30 dias do HCTR11?
6. mostra o preço do XPLG11 ontem
7. o VISC11 está em tendência de alta?
8. quanto o GGRC11 valeu em 1º de setembro de 2025?
9. qual o preço médio do BTLG11 em agosto?
10. o HFOF11 caiu este mês?
11. mostra a evolução de preços do CPTS11
12. quanto o TRXF11 estava valendo no começo do ano?
13. o KNCR11 teve maior preço em qual dia?
14. gráfico diário do VGIR11 (se disponível)
15. qual o preço atual e a variação mensal do XPML11?


---


## 🟪 **Intent: processos**

1. o HGLG11 tem algum processo ativo?
2. quantas ações judiciais o KNRI11 possui?
3. o MXRF11 está envolvido em algum processo?
4. lista os processos em andamento do PVBI11
5. o XPLG11 tem processo na CVM?
6. mostra os processos administrativos do HCTR11
7. o GGRC11 tem alguma causa trabalhista?
8. há litígios envolvendo o CPTS11?
9. o BTLG11 está sendo processado por algum motivo?
10. me dá o resumo dos processos do VISC11
11. o HFOF11 tem ações cíveis?
12. o TRXF11 teve algum processo finalizado?
13. quantos processos o KNCR11 possui atualmente?
14. mostra o total de processos ativos do VGIR11
15. há processos judiciais em nome do XPML11?

---

## 🟫 **Intent: ativos/imoveis**


1. quais imóveis o HGLG11 possui?
2. me mostra os ativos do KNRI11
3. o PVBI11 tem imóveis em São Paulo?
4. o XPLG11 tem galpões logísticos?
5. onde ficam os ativos do GGRC11?
6. o VISC11 possui shoppings?
7. quais são os empreendimentos do HCTR11?
8. o CPTS11 investe em CRIs ou imóveis físicos?
9. me lista os imóveis do BTLG11
10. o HFOF11 tem cotas de outros fundos?
11. o TRXF11 é dono de qual ativo principal?
12. o KNCR11 possui imóveis ou papéis?
13. mostra o portfólio de ativos do VGIR11
14. o XPML11 tem lojas ancoradas?
15. onde ficam os ativos do VILG11?

---

## 🩵 **Intent: indicadores macro**

1. qual foi o IPCA em março de 2025?
2. quanto está a taxa Selic hoje?
3. me mostra o CDI atual
4. qual foi o IGPM acumulado no ano?
5. o IPCA subiu em setembro?
6. quanto está a inflação acumulada em 12 meses?
7. mostra a variação do INCC em 2024
8. qual o IPCA do último mês?
9. o CDI anual está acima da Selic?
10. qual o valor do IPCA em junho de 2025?
11. quanto foi o IGPM de janeiro de 2024?
12. o IPCA fechou em alta ou baixa?
13. mostra o histórico mensal do IPCA em 2025
14. quanto rendeu o CDI em 2024?
15. qual é a projeção da Selic para este mês?

---
