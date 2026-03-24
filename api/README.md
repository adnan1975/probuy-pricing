# QuoteSense Backend

FastAPI backend for connector-based price discovery.

## Structure

- `app/connectors/`: retailer connectors (live scraping + guarded fallback)
- `app/services/`: aggregation, analysis, and SCN catalog logic
- `app/models/`: normalized API response models
- `app/routers/`: API route definitions
- `db/supabase_pricing_schema.sql`: Supabase schema + table for SCN pricing
- `scripts/ingest_scn_to_supabase.py`: separate SCN batch ingestion job

## Connectors

Implemented direct connectors:

- `app/connectors/scn_connector.py` (Supabase-backed SCN catalog, CSV fallback)
- `app/connectors/whitecap_connector.py` (guarded fallback)
- `app/connectors/kms_connector.py` (guarded fallback)
- `app/connectors/canadiantire_connector.py` (Playwright + fallback)
- `app/connectors/homedepot_connector.py` (Playwright + fallback)

## Endpoints

### `GET /search?product=<query>`

Returns:

- `results`: normalized list of source results
- `analysis`: lowest/highest/average/total_results/priced_results summary
- `per_source_errors`: connector errors keyed by source label (if any)

### `GET /catalog/items?limit=250`

Returns distinct SCN catalog entries (model-first) to populate frontend dropdowns/autocomplete.

## Supabase setup (pricing schema)

1. Open Supabase SQL editor.
2. Run SQL from `api/db/supabase_pricing_schema.sql`.
3. Configure backend env vars (see `api/.env.example`):
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_ROLE_KEY`
   - optional `SUPABASE_SCHEMA` (`pricing` by default)
   - optional `SUPABASE_SCN_TABLE` (`scn_pricing` by default)

## Batch ingestion job

Ingest the spreadsheet extract into Supabase as a separate job:

```bash
cd api
python scripts/ingest_scn_to_supabase.py --csv data/scn_pricing.csv
```

If `--csv` is omitted, the job uses `SCN_PRICING_CSV` env var and then falls back to `api/data/scn_pricing.csv`.

## Run locally

```bash
cd api
uvicorn main:app --reload
```

## Notes

- Supabase is preferred for SCN reads.
- If Supabase credentials are not set or unavailable, SCN data automatically falls back to the CSV loader.
