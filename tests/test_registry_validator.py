from app.registry.validator import validate_yaml_structure


def test_validator_accepts_valid_yaml():
    data = {
        "entity": "view_fiis_info",
        "columns": ["ticker", "sector"],
        "identifiers": ["ticker"],
        "ask": {"keywords": ["cadastro"], "intents": ["info"], "latest_words": []},
    }
    assert validate_yaml_structure(data) == []


def test_validator_rejects_invalid_yaml():
    data = {
        "entity": "broken_view",
        "columns": ["ticker"],
        # faltando identifiers e ask
    }
    errs = validate_yaml_structure(data)
    assert any("identifiers" in e or "ask" in e for e in errs)
