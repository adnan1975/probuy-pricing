from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path
import re
import sys
from typing import Iterable

from openpyxl import load_workbook

API_ROOT = Path(__file__).resolve().parents[1] / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.services.scn_catalog_service import SCNBatchIngestService

DEFAULT_INPUT_DIR = Path(__file__).resolve().parent / "input"
DEFAULT_SCN_CSV = DEFAULT_INPUT_DIR / "scn_pricing.csv"
DEFAULT_CONTENT_CSV = DEFAULT_INPUT_DIR / "contentlicensing.csv"
DEFAULT_PRICING_XLSX = DEFAULT_INPUT_DIR / "pricing.xlsx"

OUTPUT_COLUMNS = ["model", "description", "list_price", "distributor_cost", "unit", "manufacturer"]


def normalize_key(value: object) -> str:
    if value is None:
        return ""
    return re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")


def normalize_model(value: object) -> str:
    return str(value or "").strip().upper()


def _sheet_rows_with_headers(worksheet) -> Iterable[dict[str, object]]:
    rows = worksheet.iter_rows(values_only=True)
    try:
        headers = [str(cell).strip() if cell is not None else "" for cell in next(rows)]
    except StopIteration:
        return

    for row in rows:
        yield {headers[idx]: row[idx] if idx < len(row) else None for idx in range(len(headers))}


def _find_column(fieldnames: list[str], aliases: tuple[str, ...], file_path: Path) -> str:
    by_normalized = {normalize_key(name): name for name in fieldnames if name}
    for alias in aliases:
        if alias in by_normalized:
            return by_normalized[alias]
    raise ValueError(
        f"Could not find any of columns {aliases} in {file_path}. Available columns: {fieldnames}"
    )


def _resolve_content_csv(content_csv: Path) -> Path:
    if content_csv.exists():
        return content_csv

    legacy_path = content_csv.with_name("contentLicensingnew.csv")
    if content_csv.name.lower() == "contentlicensing.csv" and legacy_path.exists():
        return legacy_path

    raise FileNotFoundError(f"Content CSV not found: {content_csv}")


def read_content_manufacturer_map(content_csv: Path) -> dict[str, str]:
    with content_csv.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        if not reader.fieldnames:
            raise ValueError(f"Content licensing CSV has no header row: {content_csv}")

        prod_column = _find_column(reader.fieldnames, ("prod",), content_csv)
        manufacturer_column = _find_column(
            reader.fieldnames,
            (
                "manufacturernumber",
                "manufacturer_number",
                "manufacturer",
                "fabricant",
                "mfr",
                "mfg",
                "brand",
                "marque",
            ),
            content_csv,
        )

        manufacturer_map: dict[str, str] = {}
        for row in reader:
            model = normalize_model(row.get(prod_column))
            manufacturer = str(row.get(manufacturer_column) or "").strip()
            if not model:
                continue
            if model not in manufacturer_map or (not manufacturer_map[model] and manufacturer):
                manufacturer_map[model] = manufacturer

    return manufacturer_map


def _coerce_text(value: object) -> str:
    return str(value or "").strip()


def generate_matched_scn_csv(content_csv: Path, pricing_xlsx: Path, output_csv: Path) -> dict[str, int]:
    resolved_content_csv = _resolve_content_csv(content_csv)
    manufacturer_by_model = read_content_manufacturer_map(resolved_content_csv)

    workbook = load_workbook(pricing_xlsx, data_only=True, read_only=True)
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    total_rows = 0
    matched_rows = 0

    with output_csv.open("w", encoding="utf-8", newline="") as out_file:
        writer = csv.DictWriter(out_file, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()

        for sheet_name in workbook.sheetnames:
            worksheet = workbook[sheet_name]
            for row in _sheet_rows_with_headers(worksheet):
                total_rows += 1
                normalized_row = {normalize_key(k): v for k, v in row.items() if k}
                model = _coerce_text(normalized_row.get("model_no_no_modele") or normalized_row.get("mfg_model_no_no_fab"))
                model_key = normalize_model(model)

                if not model_key or model_key not in manufacturer_by_model:
                    continue

                description = _coerce_text(
                    normalized_row.get("english_description_description_anglais")
                    or normalized_row.get("description")
                    or model
                )
                list_price = _coerce_text(normalized_row.get("list_price_prix_liste") or normalized_row.get("list_price"))
                distributor_cost = _coerce_text(
                    normalized_row.get("distributor_cost_cout_distributeur")
                    or normalized_row.get("distributor_cost")
                )
                unit = _coerce_text(
                    normalized_row.get("unit_of_sale")
                    or normalized_row.get("unite_de_vente")
                    or normalized_row.get("unit")
                )
                manufacturer = manufacturer_by_model.get(model_key, "")

                writer.writerow(
                    {
                        "model": model,
                        "description": description,
                        "list_price": list_price,
                        "distributor_cost": distributor_cost,
                        "unit": unit,
                        "manufacturer": manufacturer,
                    }
                )
                matched_rows += 1

    return {"processed": total_rows, "matched": matched_rows}


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Generate scn_pricing.csv from pricing/content licensing matched rows and ingest into Supabase"
        )
    )
    parser.add_argument(
        "--csv",
        dest="csv_path",
        default=None,
        help=(
            "Path to SCN CSV output/input. Defaults to SCN_PRICING_CSV or "
            f"{DEFAULT_SCN_CSV}"
        ),
    )
    parser.add_argument(
        "--content-csv",
        default=str(DEFAULT_CONTENT_CSV),
        help=f"Path to content licensing CSV. Default: {DEFAULT_CONTENT_CSV}",
    )
    parser.add_argument(
        "--pricing-xlsx",
        default=str(DEFAULT_PRICING_XLSX),
        help=f"Path to pricing workbook. Default: {DEFAULT_PRICING_XLSX}",
    )
    parser.add_argument(
        "--skip-generate",
        action="store_true",
        help="Skip generating scn_pricing.csv and ingest the selected CSV directly.",
    )
    args = parser.parse_args()

    selected_csv = Path(args.csv_path or os.getenv("SCN_PRICING_CSV") or str(DEFAULT_SCN_CSV))

    if not args.skip_generate:
        content_csv = Path(args.content_csv)
        pricing_xlsx = Path(args.pricing_xlsx)
        content_csv = _resolve_content_csv(content_csv)
        if not pricing_xlsx.exists():
            raise FileNotFoundError(f"Pricing workbook not found: {pricing_xlsx}")

        stats = generate_matched_scn_csv(content_csv, pricing_xlsx, selected_csv)
        print(
            f"Generated {selected_csv} with {stats['matched']} matched rows "
            f"from {stats['processed']} processed pricing rows."
        )

    service = SCNBatchIngestService()
    result = service.ingest_csv_to_supabase(csv_path=str(selected_csv))
    print(f"Read {result['read']} rows and upserted {result['upserted']} rows into Supabase.")


if __name__ == "__main__":
    main()
