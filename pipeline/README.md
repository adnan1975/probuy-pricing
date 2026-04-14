# PriceSense Pipeline

Data ingestion utilities for preparing SCN pricing data and loading it into Supabase.

## Project structure

- `ingest_scn_to_supabase.py`: generates a matched SCN CSV (optional) and upserts rows to Supabase.
- `ingest_price_content_step.py`: validates/matches pricing workbook rows against content licensing data.
- `input/`: place source files here (for example `contentlicensing.csv`, `pricing.xlsx`, `scn_pricing.csv`).

## Prerequisites

- Python 3.11+
- Access to a Supabase project with the target schema/table already created
- Input files in `pipeline/input/` (or pass custom paths via CLI flags)

## Local setup

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r api/requirements.txt
```

> The pipeline scripts import backend services from `api/app`, so they share the backend dependency set.

## Environment variables

Set these before running the Supabase ingest script:

```bash
export SUPABASE_URL="https://<project-ref>.supabase.co"
export SUPABASE_SERVICE_ROLE_KEY="<service-role-key>"
```ps
$env:SUPABASE_URL="https://<project-ref>.supabase.co"
$env:SUPABASE_SERVICE_ROLE_KEY="https://<project-ref>.supabase.co"
 =""

```

Optional variables:

```bash
export SUPABASE_SCHEMA="pricing"          # default: pricing
export SUPABASE_SCN_TABLE="scn_pricing"   # default: scn_pricing
export SCN_BATCH_SIZE="500"               # default: 500
export SCN_PRICING_CSV="pipeline/input/scn_pricing.csv"
```

## Run locally

### 1) Check pricing/content match coverage

```bash
python pipeline/ingest_price_content_step.py \
  --content-csv pipeline/input/contentlicensing.csv \
  --pricing-xlsx pipeline/input/pricing.xlsx
```

This prints:
- total pricing rows processed
- matching rows found

### 2) Generate matched SCN CSV and ingest to Supabase

```bash
python pipeline/ingest_scn_to_supabase.py \
  --content-csv pipeline/input/contentlicensing.csv \
  --pricing-xlsx pipeline/input/pricing.xlsx \
  --csv pipeline/input/scn_pricing.csv
```

If `--csv` is omitted, the script uses:
1. `SCN_PRICING_CSV` env var (if set)
2. `pipeline/input/scn_pricing.csv`

### 3) Ingest an existing CSV without regenerating

```bash
python pipeline/ingest_scn_to_supabase.py \
  --skip-generate \
  --csv pipeline/input/scn_pricing.csv
```

## Notes

- The ingest step requires `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`; it fails fast if either is missing.
- `contentLicensingnew.csv` is supported as a legacy fallback when `contentlicensing.csv` is not found.
