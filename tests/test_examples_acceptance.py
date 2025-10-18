from __future__ import annotations

from typing import Set

import pytest
from fastapi.testclient import TestClient

from app.main import app

GROUP_INTENT = {
    "cadastro": "cadastro",
    "dividendos": "dividends",
    "historico_dividendos": "historico",
    "precos": "precos",
    "processos": "judicial",
    "ativos": "ativos",
    "indicadores": "indicadores",
}

EQUIV: dict[str, Set[str]] = {
    "cadastro": {"cadastro"},
    "dividends": {"dividends", "historico"},
    "historico": {"historico", "dividends"},
    "precos": {"precos"},
    "judicial": {"judicial", "processos"},
    "ativos": {"ativos", "imoveis"},
    "indicadores": {"indicadores", "mercado", "taxas"},
    "mercado": {"indicadores", "mercado", "taxas"},
    "taxas": {"indicadores", "mercado", "taxas"},
}


CADASTRO = [
    "me mostra o cadastro do VINO11",
    "qual o CNPJ do HGLG11?",
    "quem é o administrador do KNRI11?",
    "o XPML11 é de gestão ativa ou passiva?",
    "qual o público-alvo do GGRC11?",
    "quando foi o IPO do HCTR11?",
    "o FII PVBI11 é listado em qual segmento?",
    "quem é o custodiante do CPTS11?",
    "qual o tipo de fundo do TRXF11?",
    "qual o website oficial do BTLG11?",
    "o VISC11 é um fundo exclusivo?",
    "me dá o código ISIN do HGRU11",
    "qual o setor e classificação do XPLG11?",
    "o VILG11 tem data de constituição de quando?",
    "qual o nome B3 do HFOF11?",
    "qual o valor de mercado do HGLG11?",
    "me mostra o P/VP do KNRI11",
    "qual o dividend payout do MXRF11?",
    "qual o cap rate do PVBI11?",
    "o XPLG11 tem alta volatilidade?",
    "mostra o Sharpe Ratio do HCTR11",
    "qual a taxa de crescimento do VISC11?",
    "qual o enterprise value do GGRC11?",
    "o HFOF11 tem bom retorno por cota?",
    "quanto é o equity per share do CPTS11?",
    "o TRXF11 tem alta relação preço/patrimônio?",
    "mostra o revenue per share do VILG11",
    "qual o índice de payout do BTLG11?",
    "o KNCR11 tem cap rate acima de 9%?",
    "me dá o market cap e o EV do XPML11",
]


DIVIDENDOS = [
    "qual foi o último dividendo pago pelo HGLG11?",
    "quanto o KNRI11 pagou no último mês?",
    "qual o yield atual do CPTS11?",
    "o XPLG11 pagou dividendo em agosto?",
    "me mostra o dividendo mais recente do PVBI11",
    "quanto o HCTR11 distribuiu em setembro de 2025?",
    "qual o DY médio dos últimos 12 meses do VISC11?",
    "o MXRF11 pagou dividendo em dezembro passado?",
    "qual a data de pagamento mais recente do RECR11?",
    "quanto o VGIR11 pagou por cota em janeiro de 2025?",
    "me dá o último valor pago pelo HFOF11",
    "qual foi o yield do GGRC11 no mês passado?",
    "mostra o histórico resumido de dividendos do XPML11",
    "o KNCR11 distribuiu proventos em abril?",
    "quanto o BTLG11 pagou no último repasse?",
]


HIST_DIV = [
    "mostra o histórico de dividendos do HGLG11",
    "quanto o KNRI11 pagou em cada mês de 2024?",
    "qual foi o total de dividendos do PVBI11 no último ano?",
    "lista os pagamentos do MXRF11 em 2023",
    "me dá o histórico anual de dividendos do CPTS11",
    "quanto o VISC11 distribuiu mês a mês?",
    "o HCTR11 pagou mais em 2023 ou 2024?",
    "qual o mês de maior pagamento do XPLG11?",
    "quanto o BTLG11 pagou em março de 2024?",
    "traz o histórico de dividendos do GGRC11",
    "o HFOF11 reduziu o pagamento recentemente?",
    "mostra a média mensal de dividendos do KNCR11",
    "qual o menor dividendo já pago pelo VILG11?",
    "quando o TRXF11 começou a pagar dividendos?",
    "histórico completo de dividendos do XPML11",
]


PRECOS = [
    "qual o preço atual do HGLG11?",
    "quanto o KNRI11 fechou hoje?",
    "me mostra o preço do PVBI11 na última cotação",
    "o MXRF11 subiu nos últimos dias?",
    "qual a média móvel de 30 dias do HCTR11?",
    "mostra o preço do XPLG11 ontem",
    "o VISC11 está em tendência de alta?",
    "quanto o GGRC11 valeu em 1º de setembro de 2025?",
    "qual o preço médio do BTLG11 em agosto?",
    "o HFOF11 caiu este mês?",
    "mostra a evolução de preços do CPTS11",
    "quanto o TRXF11 estava valendo no começo do ano?",
    "o KNCR11 teve maior preço em qual dia?",
    "gráfico diário do VGIR11",
    "qual o preço atual e a variação mensal do XPML11?",
]


PROCESSOS = [
    "o HGLG11 tem algum processo ativo?",
    "quantas ações judiciais o KNRI11 possui?",
    "o MXRF11 está envolvido em algum processo?",
    "lista os processos em andamento do PVBI11",
    "o XPLG11 tem processo na CVM?",
    "mostra os processos administrativos do HCTR11",
    "o GGRC11 tem alguma causa trabalhista?",
    "há litígios envolvendo o CPTS11?",
    "o BTLG11 está sendo processado por algum motivo?",
    "me dá o resumo dos processos do VISC11",
    "o HFOF11 tem ações cíveis?",
    "o TRXF11 teve algum processo finalizado?",
    "quantos processos o KNCR11 possui atualmente?",
    "mostra o total de processos ativos do VGIR11",
    "há processos judiciais em nome do XPML11?",
]


ATIVOS = [
    "quais imóveis o HGLG11 possui?",
    "me mostra os ativos do KNRI11",
    "o PVBI11 tem imóveis em São Paulo?",
    "o XPLG11 tem galpões logísticos?",
    "onde ficam os ativos do GGRC11?",
    "o VISC11 possui shoppings?",
    "quais são os empreendimentos do HCTR11?",
    "o CPTS11 investe em CRIs ou imóveis físicos?",
    "me lista os imóveis do BTLG11",
    "o HFOF11 tem cotas de outros fundos?",
    "o TRXF11 é dono de qual ativo principal?",
    "o KNCR11 possui imóveis ou papéis?",
    "mostra o portfólio de ativos do VGIR11",
    "o XPML11 tem lojas ancoradas?",
    "onde ficam os ativos do VILG11?",
]


INDICADORES = [
    "qual foi o IPCA em março de 2025?",
    "quanto está a taxa Selic hoje?",
    "me mostra o CDI atual",
    "qual foi o IGPM acumulado no ano?",
    "o IPCA subiu em setembro?",
    "quanto está a inflação acumulada em 12 meses?",
    "mostra a variação do INCC em 2024",
    "qual o IPCA do último mês?",
    "o CDI anual está acima da Selic?",
    "qual o valor do IPCA em junho de 2025?",
    "quanto foi o IGPM de janeiro de 2024?",
    "o IPCA fechou em alta ou baixa?",
    "mostra o histórico mensal do IPCA em 2025",
    "quanto rendeu o CDI em 2024?",
    "qual é a projeção da Selic para este mês?",
]


ALL_CASES = (
    [(q, GROUP_INTENT["cadastro"]) for q in CADASTRO]
    + [(q, GROUP_INTENT["dividendos"]) for q in DIVIDENDOS]
    + [(q, GROUP_INTENT["historico_dividendos"]) for q in HIST_DIV]
    + [(q, GROUP_INTENT["precos"]) for q in PRECOS]
    + [(q, GROUP_INTENT["processos"]) for q in PROCESSOS]
    + [(q, GROUP_INTENT["ativos"]) for q in ATIVOS]
    + [(q, GROUP_INTENT["indicadores"]) for q in INDICADORES]
)


@pytest.fixture
def ask_client(stub_routing_dependencies):
    return TestClient(app)


@pytest.mark.parametrize("question,expected_intent", ALL_CASES)
def test_examples_acceptance(question, expected_intent, ask_client):
    response = ask_client.post("/ask", json={"question": question})
    assert response.status_code == 200, response.text

    payload = response.json()
    assert payload["status"]["reason"] == "ok", f"NL falhou: {question}"

    intents = payload.get("planner", {}).get("intents", []) or []
    normalized = set(intents)

    expected_set = EQUIV.get(expected_intent, {expected_intent})
    assert (
        normalized & expected_set
    ), f"Intent não detectada para: {question} → {intents}"
