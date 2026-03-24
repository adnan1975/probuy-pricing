from __future__ import annotations

import argparse

from app.services.scn_catalog_service import SCNBatchIngestService


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch ingest SCN pricing CSV into Supabase")
    parser.add_argument(
        "--csv",
        dest="csv_path",
        default=None,
        help="Path to SCN CSV file. Defaults to SCN_PRICING_CSV or api/data/scn_pricing.csv",
    )
    args = parser.parse_args()

    service = SCNBatchIngestService()
    result = service.ingest_csv_to_supabase(csv_path=args.csv_path)
    print(f"Read {result['read']} rows and upserted {result['upserted']} rows into Supabase.")


if __name__ == "__main__":
    main()
