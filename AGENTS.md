# QuoteSense Engineering Instructions

## Goal
Implement retailer connectors for:
- White Cap
- KMS Tools
- Canadian Tire
- Home Depot

## Architecture
- Backend: FastAPI
- One connector per retailer in `app/connectors/`
- Frontend must never scrape directly
- `/search` endpoint aggregates connector results

## Scraping Requirements
- Use Playwright Python
- Prefer Playwright `locator` APIs and user-perceived selectors
- Avoid long brittle CSS/XPath selector chains
- Use headless browser by default
- Extract:
  - source
  - title
  - price_text
  - price_value
  - currency
  - sku if available
  - brand if available
  - availability if available
  - product_url
  - image_url if available

## Connector Design
Create:
- `whitecap_connector.py`
- `kms_connector.py`
- `canadiantire_connector.py`
- `homedepot_connector.py`

Each connector must expose:
- `async def search(self, query: str) -> list[NormalizedResult]`

## Result Normalization
All connectors must return the same normalized schema.

## Implementation Strategy
- Start with Home Depot and Canadian Tire using live Playwright scraping
- If White Cap or KMS selectors are unstable, implement a guarded fallback with clear TODOs
- Add timeouts, retries, and graceful error handling
- Never crash the whole search because one connector fails

## Quality Requirements
- Add small helper methods for:
  - open_search_page
  - extract_result_cards
  - parse_price
  - normalize_result
- Keep selectors centralized per connector
- Add comments for assumptions and fragile selectors
- Add at least one test or smoke-check per connector
