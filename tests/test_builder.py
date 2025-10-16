from app.builder.service import builder_service
from app.extractors.normalizers import ExtractedRunRequest

def test_builder_sql_basic():
    req = ExtractedRunRequest(entity="view_fiis_info", filters={"ticker":"VINO11"}, limit=10)
    sql, params = builder_service.build_sql(req)
    assert "FROM view_fiis_info" in sql
    assert "LIMIT 10" in sql
    assert params["ticker"] == "VINO11"


def test_builder_rejects_unknown_columns():
    req = ExtractedRunRequest(
        entity="view_fiis_info",
        select=["ticker", "non_existing_pct"],
        filters={},
    )
    try:
        builder_service.build_sql(req)
    except ValueError as exc:
        assert "non_existing_pct" in str(exc)
    else:
        raise AssertionError("Builder aceitou coluna inexistente")
