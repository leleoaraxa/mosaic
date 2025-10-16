from app.orchestrator.service import _default_date_field, build_run_request


def test_extract_dates_and_filter_dividends():
    q = "histórico de dividendos do KNRI entre 01/01/2024 e 30/06/2024"
    req = build_run_request(q)
    # 1) entidade correta
    assert req["entity"] == "view_fiis_history_dividends"
    # 2) datas extraídas
    assert req["filters"]["date_from"] == "01/01/2024"
    assert req["filters"]["date_to"] == "30/06/2024"
    # 3) campo de data escolhido sensato
    assert _default_date_field(req["entity"]) in ("traded_until_date", "payment_date")
