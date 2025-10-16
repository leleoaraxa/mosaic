from datetime import datetime

import pytest

from app.formatter.serializer import to_human


@pytest.mark.parametrize(
    "key,value,expected",
    [
        ("payment_date", "2024-05-01", "01/05/2024"),
        ("traded_until_date", datetime(2024, 5, 1, 13, 45), "01/05/2024"),
        ("created_at", "2024-05-01T10:30:00Z", "01/05/2024"),
        ("total_cash_amt", 1234.5, "R$ 1.234,50"),
        ("dividend_amt", 321, "R$ 321,00"),
        ("close_price", "9876.54", "R$ 9.876,54"),
        ("dividend_payout_pct", 0.1578, "15,78 %"),
        ("dy_pct", 0.789, "78,90 %"),
        ("total_area", 10_000.0, "10.000,00 m²"),
        ("market_cap_value", 1234567.8, "1.234.567,80"),
        ("sharpe_ratio", 1.23456, "1,2346"),
        ("growth_rate", 0.4567, "0,457"),
        ("equity_per_share", 12.3456, "12,346"),
        ("beta_index", -0.9876, "-0,988"),
        ("shareholders_count", 123456, "123.456"),
    ],
)
def test_suffix_formatter_positive(key, value, expected):
    rows = [{key: value}]
    formatted = to_human(rows)[0][key]
    assert formatted == expected


def test_suffix_formatter_unknown_passthrough():
    rows = [{"ticker": "HGLG11"}]
    assert to_human(rows)[0]["ticker"] == "HGLG11"


@pytest.mark.parametrize(
    "key,value",
    [
        ("total_cash_amt", "abc"),
        ("dy_pct", "n/a"),
        ("market_cap_value", None),
        ("shareholders_count", ""),
    ],
)
def test_suffix_formatter_invalid_inputs_return_original(key, value):
    rows = [{key: value}]
    formatted = to_human(rows)[0][key]
    assert formatted == value
