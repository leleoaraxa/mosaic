# tests/test_extractors_isolation.py
from app.extractors.normalizers import normalize_request


def test_filters_isolation_between_calls():
    req1 = {
        "entity": "view_fiis_info",
        "filters": {"ticker": "HGLG"},
        "limit": 10,
    }
    req2 = {
        "entity": "view_fiis_info",
        "filters": {"ticker": "VINO11"},
        "limit": 10,
    }

    out1 = normalize_request(req1)
    out2 = normalize_request(req2)

    # Normaliza HGLG -> HGLG11 sem afetar a próxima chamada
    assert out1.filters["ticker"] == "HGLG11"
    assert out2.filters["ticker"] == "VINO11"

    # E não muta o dicionário original
    assert req1["filters"]["ticker"] == "HGLG"
    assert req2["filters"]["ticker"] == "VINO11"


def test_date_filters_accept_br_formats():
    req = {
        "entity": "view_fiis_history_dividends",
        "filters": {
            "date_from": "01/05/2024",
            "date_to": "31/05/2024",
            "payment_date": "15/05/2024",
            "created_at": "16/05/2024",
            "traded_until_date": "10/05/2024",
        },
    }

    out = normalize_request(req)
    assert out.filters["date_from"] == "2024-05-01"
    assert out.filters["date_to"] == "2024-05-31"
    assert out.filters["payment_date"] == "2024-05-15"
    assert out.filters["created_at"] == "2024-05-16"
    assert out.filters["traded_until_date"] == "2024-05-10"
