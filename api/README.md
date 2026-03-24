# QuoteSense Backend

FastAPI backend for connector-based price discovery.

## Structure

- `app/connectors/`: retailer connectors (live scraping + guarded fallback)
- `app/services/`: aggregation and analysis business logic
- `app/models/`: normalized API response models
- `app/routers/`: API route definitions

## Connectors

Implemented direct connectors:

- `app/connectors/whitecap_connector.py` (guarded fallback)
- `app/connectors/kms_connector.py` (guarded fallback)
- `app/connectors/canadiantire_connector.py` (Playwright + fallback)
- `app/connectors/homedepot_connector.py` (Playwright + fallback)

All connectors return a normalized schema with:

- `source`
- `title`
- `price_text`
- `price_value`
- `currency`
- `sku`
- `brand`
- `availability`
- `product_url`
- `image_url`

## Endpoint

### `GET /search?product=<query>`

Returns:

- `results`: normalized list of source results
- `analysis`: lowest/highest/average/total_results/priced_results summary
- `per_source_errors`: connector errors keyed by source label (if any)

## Run locally

```bash
cd api
uvicorn main:app --reload
```

## SCN pricing spreadsheet integration

To keep repository size small, do **not** commit large Excel files.

1. In Excel, save the SCN workbook as UTF-8 CSV with only required fields:
   - `model`
   - `description`
   - `list_price`
   - `distributor_cost`
   - `unit`
   - `manufacturer` (optional)
2. Place the compact CSV at `api/data/scn_pricing.csv` (or set `SCN_PRICING_CSV=/absolute/path/to/file.csv`).
3. The backend now exposes this data through the `SCN Pricing` connector and includes it in `/search` responses.

The loader also accepts SCN bilingual column headers and maps them automatically when present.
