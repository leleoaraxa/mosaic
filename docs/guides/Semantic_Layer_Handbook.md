# 📘 Guia de Governança e Criação de Views — SIRIOS Semantic Layer

> **Versão 2025.10 – Padrão de metadados e ontologia do SIRIOS**

---

## 1. Propósito do Diretório

O SIRIOS utiliza **dois pilares semânticos principais**:

| Diretório                | Papel                          | Descrição                                                                                                                                                |
| ------------------------ | ------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `data/views/`            | **Fonte de Verdade das Views** | Contém um arquivo YAML por view (ex.: `view_fiis_history_dividends.yaml`), descrevendo colunas, chaves, campo temporal padrão e o bloco semântico `ask`. |
| `data/ask/ontology.yaml` | **Ontologia Global**           | Define a gramática universal de intenções, sinônimos e pesos do orquestrador NL→SQL.                                                                     |

Esses arquivos alimentam o **orquestrador semântico**, responsável por transformar perguntas em português natural em consultas SQL corretas e seguras.

---

## 2. Estrutura de um Arquivo YAML de View

Cada view é descrita em um arquivo com esta estrutura mínima:

```yaml
entity: view_fiis_history_dividends
description: "Histórico de proventos pagos por fundo imobiliário"
identifiers: ["ticker"]
default_date_field: payment_date
order_by_whitelist: ["payment_date"]

columns:
  - name: dividend_amt
    description: "Valor do dividendo pago por cota"
    ask:
      intents: ["dividends"]
      synonyms:
        dividends: ["dividendo", "rendimento", "provento"]
      weights:
        synonyms: 2.5

ask:
  intents: ["dividends", "historico"]
  keywords: ["dividendo", "rendimento", "pagamento"]
  synonyms:
    dividends: ["provento", "dy", "yield"]
  latest_words: ["último", "recente", "hoje"]
  timewords: ["janeiro","fevereiro","março","..."]
  weights:
    keywords: 1.0
    synonyms: 2.0
  intent_tokens:
    dividends: ["dividendo","provento","dy","yield"]
```

---

## 3. Relação entre Ontologia e Views

O modelo de metadados do SIRIOS é **híbrido**:

| Nível                        | Responsabilidade                    | Fonte                    | Escopo                             |
| ---------------------------- | ----------------------------------- | ------------------------ | ---------------------------------- |
| **Global (ontologia)**       | Vocabulário base e pesos padrão     | `data/ask/ontology.yaml` | Compartilhado entre todas as views |
| **View**                     | Vocabulário e intenções específicas | `data/views/*.yaml`      | Contexto da view                   |
| **Coluna (`columns[].ask`)** | Termos técnicos e aliases da coluna | Dentro da própria view   | Contexto granular                  |

O **orquestrador** faz o merge dinâmico destas três camadas:

> `vocabulário_global (ontology)` + `vocabulário_view (ask)` + `vocabulário_coluna (columns[].ask)`

---

## 4. Como Manter e Atualizar

### 🔄 Atualizações de rotina

* Revisar sinônimos e intenções conforme surgirem novas perguntas dos usuários.
* Validar consistência com a ontologia global (`ontology.yaml`).
* Após editar:

  ```bash
  python -m tools.validate_views --path data/views/
  pytest -q
  ```

### 🧩 Revisão semântica

* Toda inclusão de `ask.intent_tokens` ou `columns[].ask` deve ter base em perguntas reais (logs de uso).
* Documente alterações relevantes no PR.

---

## 5. Como Criar uma Nova View

1. **Copiar o template:**

   ```bash
   cp data/views/_template.yaml data/views/view_nova_view.yaml
   ```

2. **Preencher campos obrigatórios:**

   * `entity`, `description`, `identifiers`
   * `default_date_field`
   * `order_by_whitelist`
   * `columns`
   * `ask`

3. **Definir bloco `ask` (nível da view):**

   * `intents`: nome(s) da intenção (ex.: `precos`, `dividends`, `cadastro`, etc.)
   * `keywords`: termos literais que o usuário pode usar
   * `synonyms`: mapa `{ intent: [sinônimos] }`
   * `weights`: numéricos (`keywords: 1.0`, `synonyms: 2.0`)
   * `intent_tokens`: opcional, se a view introduz intenções próprias

4. **Adicionar `columns[].ask` para campos relevantes:**

   ```yaml
   - name: close_price
     ask:
       intents: ["precos"]
       synonyms:
         precos: ["fechou", "fechamento", "close", "preço de fechamento"]
       weights:
         synonyms: 2.5
   ```

5. **Validar:**

   ```bash
   python -m tools.validate_views
   curl -X POST http://localhost:8000/admin/views/reload
   pytest -q
   ```

---

## 6. Boas Práticas

✅ Use **português completo e com acentos** nos sinônimos.
✅ Prefira `keywords=1.0` e `synonyms=2.0` (ajuste apenas quando houver ambiguidade).
✅ Evite duplicar sinônimos entre `ask` (view) e `columns[].ask`.
✅ Inclua sempre um `default_date_field`.
✅ O `order_by_whitelist` deve conter apenas colunas existentes.
✅ Valide antes de fazer merge.

---

## 7. Governança e Papéis

| Papel                  | Responsabilidades                                                                      |
| ---------------------- | -------------------------------------------------------------------------------------- |
| **Curadores**          | Definem e revisam intenções (`ask.intents`, `intent_tokens`) e consistência semântica. |
| **Analistas de Dados** | Garantem integridade técnica das colunas, tipos e chaves.                              |
| **Desenvolvedores**    | Validam integração NL→SQL e execução dos testes (`pytest`).                            |
| **Auditoria**          | PRs devem conter diff YAML legível e todos os testes verdes.                           |

---

## 8. Validação Automática

O validador (`tools.validate_views`) verifica:

* Presença das chaves obrigatórias.
* `weights` numéricos.
* `order_by_whitelist` consistente.
* `intent_tokens` como mapa `{intent: [strings...]}`.
* `columns[].ask` válido.
* Gera um bundle final:

  ```bash
  python -m tools.validate_views
  # cria data_views_final_bundle.zip
  ```

---

## 9. Ciclo de Vida de uma View

1. **Analista** propõe nova view (cria o YAML).
2. **Curador** ajusta intenções e sinônimos.
3. **Desenvolvedor** valida e roda testes.
4. **CI** executa `pytest` e valida schema.
5. **Merge** → `/admin/views/reload` recarrega em produção.

---

## 10. Resumo Conceitual

| Componente           | Função                                         |
| -------------------- | ---------------------------------------------- |
| **Ontologia global** | Vocabulário-base do SIRIOS                     |
| **Views YAML**       | Manifestos semânticos das entidades            |
| **Column.ask**       | Pistas granulares para compreensão de contexto |
| **Orquestrador**     | Motor que interpreta a linguagem natural       |
| **Governança**       | Garante clareza, consistência e auditabilidade |

---

## 11. Exemplos de Uso Prático

| Pergunta do usuário                            | Intent detectada | View escolhida               | Coluna-chave       |
| ---------------------------------------------- | ---------------- | ---------------------------- | ------------------ |
| “Quanto o KNRI11 fechou hoje?”                 | `precos`         | `view_fiis_history_prices`   | `close_price`      |
| “Mostra o total de processos ativos do VGIR11” | `judicial`       | `view_fiis_history_judicial` | `cause_amt`        |
| “Qual o P/VP do VINO11?”                       | `cadastro`       | `view_fiis_info`             | `price_book_ratio` |
| “Qual o cap rate do HGLG11?”                   | `cadastro`       | `view_fiis_info`             | `cap_rate`         |
| “Última notícia do XPML11”                     | `noticias`       | `view_fiis_history_news`     | `news_date`        |

---

## 12. Checklist Rápido (antes de abrir PR)

* [ ] YAML válido e identado corretamente
* [ ] `default_date_field` presente
* [ ] `order_by_whitelist` coerente
* [ ] `ask.weights` numéricos
* [ ] Nenhum sinônimo redundante
* [ ] Todos os testes (`pytest`) passaram
* [ ] `tools.validate_views` sem erros

---

## 13. Filosofia do SIRIOS

> “Clareza não vem de simplificar demais, mas de **organizar o complexo com rigor**.”
>
> — Padrão SIRIOS para Inteligência Semântica de Dados, 2025
