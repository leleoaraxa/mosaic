# tools/snapshot_views_from_db.py
import os, yaml
from app.executor.service import executor_service

VIEWS = {
    "view_fiis_info": {
        "identifiers": ["ticker"],
        "default_date_field": "updated_at",
    },
    "view_fiis_history_dividends": {
        "identifiers": ["ticker", "traded_until_date", "payment_date"],
        "default_date_field": "payment_date",
    },
    "view_fiis_history_assets": {
        "identifiers": [
            "ticker",
            "asset_class",
            "asset_name",
            "asset_address",
            "assets_status",
        ],
        "default_date_field": "created_at",
    },
    "view_fiis_history_judicial": {
        "identifiers": ["ticker", "process_number"],
        "default_date_field": "initiation_date",
    },
    "view_fiis_history_prices": {
        "identifiers": ["ticker", "price_date"],
        "default_date_field": "price_date",
    },
    "view_fiis_history_news": {
        "identifiers": ["ticker", "news_url"],
        "default_date_field": "news_date",
    },
    "view_market_indicators": {
        "identifiers": ["indicator_date", "indicator_name"],
        "default_date_field": "indicator_date",
    },
    "view_history_taxes": {
        "identifiers": ["tax_date"],
        "default_date_field": "tax_date",
    },
}

ORDER_BY_GUESSES = [
    "payment_date",
    "price_date",
    "news_date",
    "indicator_date",
    "tax_date",
    "created_at",
    "updated_at",
    "ticker",
    "asset_name",
]


def main():
    out_dir = os.environ.get("VIEWS_DIR", os.path.abspath("data/views"))
    os.makedirs(out_dir, exist_ok=True)

    for entity, meta in VIEWS.items():
        cols = executor_service.columns_for(entity)
        if not cols:
            print(f"[warn] sem colunas (modo dummy?) → {entity}")
            continue

        order_by_whitelist = [c for c in ORDER_BY_GUESSES if c in cols] or cols

        doc = {
            "entity": entity,
            "description": f"Snapshot gerado do DB para {entity}",
            "identifiers": meta["identifiers"],
            "default_date_field": meta["default_date_field"],
            "order_by_whitelist": order_by_whitelist,
            "columns": [{"name": c} for c in cols],
        }

        path = os.path.join(out_dir, f"{entity}.yaml")
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(doc, f, allow_unicode=True, sort_keys=False)
        print(f"[ok] wrote {path}")


if __name__ == "__main__":
    # Precisa EXECUTOR_MODE != dummy e DATABASE_URL configurado
    if os.environ.get("EXECUTOR_MODE", "dummy") == "dummy":
        print("ERROR: EXECUTOR_MODE=dummy — aponte para Postgres real.")
        raise SystemExit(1)
    main()
