# Developing Notes

## Ask metadata pipeline

- View comments may include an `||ask:` suffix with fields such as `intents`, `keywords`, `synonyms.*`, `latest_words`, and the new `intent_tokens` map. The value of `intent_tokens` must be a JSON object mapping the global intent name to a list of anchor tokens. Example: `ask.intent_tokens={"precos":["preço","cotação"],"judicial":["processo","ação"]}`.
- Column comments accept the optional suffix `||col=<JSON>`. The JSON payload can contain:
  - `intents`: list of intents supported by that column.
  - `synonyms`: map `intent -> list[str]` with intent-specific synonyms.
  - `weights`: fine-tuning overrides (for example `{ "synonyms": 2.5 }`).
- The CLI `tools.snapshot_views_from_db` remains unchanged but preserves existing `ask` metadata.
- `tools.augment_yaml_from_db_comments` now parses `intent_tokens` and `||col` payloads. Run `python -m tools.augment_yaml_from_db_comments --write` after updating Postgres comments to sync `data/views/*.yaml`.
- The orchestrator consumes the enriched YAML. Intent detection, entity scoring, and ticker extraction no longer rely on hard-coded vocabularies; always keep the metadata up-to-date.
