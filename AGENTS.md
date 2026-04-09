# PriceSense Engineering Instructions

## Project Goal
PriceSense is an AI-powered industrial pricing comparison tool.

It should:
- Search for a product across White Cap, KMS Tools, Canadian Tire, and Home Depot
- Extract visible prices and basic product details
- Normalize results into one shared schema
- Rank and analyze results for quoting
- Return structured JSON to the frontend

## Current Stack
- Frontend: React + Vite
- Backend: FastAPI
- Deployment: Render

## Critical Architecture Decisions
- DO NOT use Google SERP, SerpApi, or DataForSEO in the backend
- DO NOT scrape from the frontend
- All retailer access must happen through backend connectors
- One connector per retailer
- Connectors must be modular and independently fail-safe
- One source failing must not break the /search endpoint

## Retailer Sources
Implement connectors for:
- White Cap
- KMS Tools
- Canadian Tire
- Home Depot

## Scraping Requirements
- Use Scrapy Python for retailer scraping
- Prefer Scrapy Locator APIs
- Prefer user-facing selectors, visible text, titles, labels, stable data attributes
- Avoid long brittle CSS/XPath chains
- Avoid arbitrary sleeps; prefer locator-based waits
- Parse list/search pages first, then product pages only when necessary
- Keep selectors centralized inside each connector
- Add comments explaining fragile assumptions

## Connector Contract
Each connector must expose:
- async def search(self, query: str) -> list[NormalizedResult]

Each connector should:
- accept a product query
- return zero or more normalized results
- handle timeouts gracefully
- return partial results when possible
- never crash the whole app

## Normalized Result Schema
Every connector must return the same fields:

{
  "source": "White Cap",
  "source_type": "distributor" or "retail",
  "title": "...",
  "price_text": "$329.00",
  "price_value": 329.00,
  "currency": "CAD",
  "sku": "...",
  "brand": "...",
  "availability": "...",
  "product_url": "...",
  "image_url": "...",
  "confidence": "High|Medium|Low",
  "score": 0,
  "why": "..."
}

## Backend Responsibilities
/search endpoint must:
1. Call all retailer connectors in parallel
2. Normalize results
3. Apply simple matching / score improvements using query, brand, part number if available
4. Compute analysis:
   - lowest price
   - highest price
   - average price
   - total results
   - priced results
   - per-source errors
5. Return structured response

## Desired Folder Structure
app/
  main.py
  config.py
  routers/
    search.py
  models/
    normalized_result.py
  connectors/
    base.py
    whitecap_connector.py
    kms_connector.py
    canadiantire_connector.py
    homedepot_connector.py
  services/
    search_service.py
    analysis_service.py
    matching_service.py
  utils/
    price_parser.py
    text_utils.py

## Implementation Strategy
- Start with working live Scrapy implementations for Home Depot and Canadian Tire
- Implement White Cap and KMS Tools with the best reliable approach available
- If a live implementation is too brittle, return guarded partial support with clear TODOs
- Add source labels suitable for frontend display:
  - White Cap = distributor / primary quoting source
  - KMS Tools = retail benchmark
  - Canadian Tire = retail benchmark
  - Home Depot = retail benchmark

## Frontend Requirements
Update demo UI to:
- remove SERP/Google language
- show the four retailer/distributor sources clearly
- color-code source types
- display source labels and why-ranked explanations
- keep quote guidance panel
- support example products like:
  - DEWALT FLEXVOLT grinder DCG418B
  - 3M SecureFit SF201AF safety glasses

## Repo Hygiene
- Never include binary files in commits or PRs
- Exclude:
  - __pycache__/
  - *.pyc
  - venv/
  - node_modules/
  - dist/
  - build/
  - .DS_Store
- Respect .gitignore
- If binary/generated files are tracked, remove them from git

## Acceptance Criteria
- No SERP dependency remains in backend
- /search returns aggregated retailer results
- Home Depot and Canadian Tire return live results for sample queries
- White Cap and KMS are implemented with best effort and safe fallback behavior
- Frontend reflects retailer-based model
- No binary files included in PR
