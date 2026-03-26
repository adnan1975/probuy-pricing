from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

API_ROOT = Path(__file__).resolve().parents[1] / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.services.scn_catalog_service import SCNBatchIngestService


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch ingest SCN pricing CSV into Supabase")
    default_csv = Path(__file__).resolve().parent / "input" / "scn_pricing.csv"
    parser.add_argument(
        "--csv",
        dest="csv_path",
        default=None,
        help=(
            "Path to SCN CSV file. Defaults to SCN_PRICING_CSV or "
            f"{default_csv}"
        ),
    )
    args = parser.parse_args()

    selected_csv = args.csv_path or os.getenv("SCN_PRICING_CSV") or str(default_csv)

    service = SCNBatchIngestService()
    result = service.ingest_csv_to_supabase(csv_path=selected_csv)
    print(f"Read {result['read']} rows and upserted {result['upserted']} rows into Supabase.")


if __name__ == "__main__":
    main()
