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

## Render + Supabase setup (recommended)

If you ingest data with a local batch job and want the hosted app on Render to read from Supabase, use this pattern:

1. **Create/verify your Supabase project**
   - In Supabase, open **Project Settings → Database**.
   - Copy the connection details for:
     - host
     - database name
     - user
     - password
   - Prefer the **pooler** connection string for application traffic.

2. **Set environment variables in Render (API service)**
   - In Render, open `quotesense-api` → **Environment**.
   - Add:
     - `SUPABASE_URL` = your project URL
     - `SUPABASE_ANON_KEY` = anon/public key (if you need Supabase client API access)
     - `DATABASE_URL` = PostgreSQL connection string (pooler, SSL required)
   - Recommended `DATABASE_URL` shape:

```bash
postgresql://<USER>:<PASSWORD>@<POOLER_HOST>:6543/<DB_NAME>?sslmode=require
```

3. **Deploy API and frontend with Render Blueprint**
   - Keep using `render.yaml` at repo root.
   - In Render, create a Blueprint from this repo so API + frontend deploy together.
   - Ensure frontend `VITE_API_URL` points at your deployed API service URL.

4. **Keep writes local, reads in Render**
   - Run your batch ingestor locally with a **service role key** (never expose this key to frontend).
   - Batch job writes to Supabase tables.
   - Render-hosted API uses read-only queries (or least-privilege DB role) against the same Supabase project.

5. **Security + reliability checklist**
   - Never commit keys in git.
   - Restrict CORS to your Render frontend domain.
   - Use Row Level Security policies for tables accessed via Supabase APIs.
   - Add connection pooling (Supabase pooler) to avoid exhausting Postgres connections.
   - Set query timeouts and fail gracefully so `/search` still returns partial results.

### Quick verification commands

From your local machine after deployment:

```bash
curl "https://<your-api>.onrender.com/health"
curl "https://<your-api>.onrender.com/search?product=DEWALT%20DCG418B"
```

If `/search` returns data and analysis plus no DB auth errors in Render logs, your Render↔Supabase read path is working.
