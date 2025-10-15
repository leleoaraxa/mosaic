from app.formatter.serializer import to_human


def test_formatter_suffix_based_rules():
    rows = [
        {
            "payment_date": "2025-10-15",
            "traded_until_date": "2025-10-14",
            "created_at": "2025-10-15T13:45:22",
            "dividend_amount": 0.57,  # *_amount -> R$
            "yield_pct": 0.0123,  # *_pct -> %
            "total_area": 1234.56,  # *_area -> m²
            "market_cap_value": 9876543.21,  # *_value -> número BR (sem símbolo)
            "sharpe_ratio": 1.2345,  # *_ratio -> número BR (sem símbolo)
        }
    ]
    out = to_human(rows)[0]

    # Datas
    assert out["payment_date"] == "15/10/2025"
    assert out["traded_until_date"] == "14/10/2025"
    assert out["created_at"] == "15/10/2025"

    # Preço (R$)
    assert isinstance(out["dividend_amount"], str) and out[
        "dividend_amount"
    ].startswith("R$ ")

    # Percentual
    assert out["yield_pct"].endswith("%")

    # Área
    assert out["total_area"].endswith(" m²")

    # Números sem símbolo
    assert "," in out["market_cap_value"]  # decimal BR
    assert "," in out["sharpe_ratio"]
