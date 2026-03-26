# QuoteSense Pipeline

Data ingestion project for loading source files into Supabase.

## Structure

- `ingest_scn_to_supabase.py`: batch job that ingests SCN pricing CSV data into Supabase
- `input/`: place ingestion input files here (for example `input/scn_pricing.csv`)

## Usage

From the repository root:

```bash
python pipeline/ingest_scn_to_supabase.py --csv pipeline/input/scn_pricing.csv
```

If `--csv` is omitted, the script uses:
1. `SCN_PRICING_CSV` env var (if set)
2. `pipeline/input/scn_pricing.csv`

The script imports backend ingestion services from `api/app/services`.
