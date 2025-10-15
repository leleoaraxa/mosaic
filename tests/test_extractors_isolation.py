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
