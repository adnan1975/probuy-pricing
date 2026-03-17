# Project: QuoteSense

## Goal
Build an AI-powered pricing comparison tool for industrial products.

The system should:
- Search products across multiple retailers
- Compare prices
- Identify best source for quoting
- Provide analysis (lowest, highest, average price)

---

## Architecture

Frontend:
- React (Vite)

Backend:
- FastAPI

Deployment:
- Render

---

## Data Sources (IMPORTANT)

We DO NOT use Google SERP.

We ONLY use direct retailer connectors:

- White Cap (primary distributor)
- KMS Tools
- Canadian Tire
- Home Depot

---

## Connector Design

Each source must have its own connector:

app/connectors/
- whitecap_connector.py
- kms_connector.py
- canadiantire_connector.py
- homedepot_connector.py

Each connector must:
- accept a search query
- return normalized results

---

## Normalized Result Format

```json
{
  "source": "White Cap",
  "source_type": "distributor",
  "title": "...",
  "price_value": 329.00,
  "currency": "CAD",
  "sku": "...",
  "brand": "...",
  "availability": "...",
  "product_url": "...",
  "confidence": "High",
  "score": 98
}
