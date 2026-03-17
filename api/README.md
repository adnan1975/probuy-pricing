# QuoteSense Backend

FastAPI backend for connector-based price discovery.

## Structure

- `app/connectors/`: retailer connectors (currently mock implementations)
- `app/services/`: aggregation and analysis business logic
- `app/models/`: normalized API response models
- `app/routers/`: API route definitions

## Connectors

Implemented direct connectors:

- `app/connectors/whitecap_connector.py`
- `app/connectors/kms_connector.py`
- `app/connectors/canadiantire_connector.py`
- `app/connectors/homedepot_connector.py`

All connectors currently return mock data from a shared catalog to keep the API stable while live scraping integrations are developed.

## Endpoint

### `GET /search?product=<query>`

Returns:

- `results`: normalized list of source results
- `analysis`: lowest/highest/average/source_count summary
- `source_labels`: source names for frontend rendering

## Run locally

```bash
cd api
uvicorn main:app --reload
```
