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
