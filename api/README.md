# PriceSense Backend

FastAPI backend for SCN-based price discovery.

## Structure

- `app/connectors/`: connector implementations
- `app/services/`: aggregation, analysis, and SCN catalog logic
- `app/models/`: normalized API response models
- `app/routers/`: API route definitions
- `db/supabase_pricing_schema.sql`: Supabase schema + table for SCN pricing
- `../pipeline/ingest_scn_to_supabase.py`: separate SCN batch ingestion job

## Connector

- `app/connectors/scn_connector.py` (Supabase-backed SCN pricing connector)

## Endpoints

### `GET /search?product=<query>`

Returns:

- `results`: normalized list of SCN source results
- `analysis`: lowest/highest/average/total_results/priced_results summary
- `per_source_errors`: source errors keyed by source label (if any)

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
python pipeline/ingest_scn_to_supabase.py --csv pipeline/input/scn_pricing.csv
```

If `--csv` is omitted, the job uses `SCN_PRICING_CSV` env var and then falls back to `pipeline/input/scn_pricing.csv`.

## Run locally

```bash
cd api
uvicorn main:app --reload
```

to put back playwright in render && PLAYWRIGHT_BROWSERS_PATH=/opt/render/project/.playwright-browsers python -m playwright install chromium

## Shopify Publish SQL Diagnostics

Inspect SKU fields:

```sql
select id, source_product_key, source_model_no
from probuy.source_products
where id = '0030ebf3-6013-4729-8256-c052db5cee19';
```

Inspect all price rows in selection order:

```sql
select source_product_id, list_price, effective_at, pricing_update_date, updated_at
from probuy.source_product_prices
where source_product_id = '0030ebf3-6013-4729-8256-c052db5cee19'
order by coalesce(effective_at, pricing_update_date, updated_at) desc;
```

Reproduce latest selected price row:

```sql
select source_product_id, list_price, effective_at, pricing_update_date, updated_at
from probuy.source_product_prices
where source_product_id = '0030ebf3-6013-4729-8256-c052db5cee19'
order by coalesce(effective_at, pricing_update_date, updated_at) desc
limit 1;
```

Inspect Shopify publication status:

```sql
select source_product_id, channel_code, publication_status, last_error, metadata, updated_at
from probuy.product_channel_publications
where source_product_id = '0030ebf3-6013-4729-8256-c052db5cee19'
  and upper(channel_code) = 'SHOPIFY';
```
