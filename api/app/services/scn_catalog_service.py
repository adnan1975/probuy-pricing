from __future__ import annotations

import csv
import os
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SCNItem:
    model: str
    description: str
    list_price: float | None
    distributor_cost: float | None
    unit: str | None
    manufacturer: str | None


class SCNCatalogService:
    """Loads a compact SCN pricing extract from CSV.

    Expected columns (case-insensitive):
    - model
    - description
    - list_price
    - distributor_cost
    - unit
    - manufacturer (optional)

    By default reads SCN_PRICING_CSV from env or api/data/scn_pricing.csv.
    """

    def __init__(self, csv_path: str | None = None) -> None:
        root_dir = Path(__file__).resolve().parents[2]
        default_path = root_dir / "data" / "scn_pricing.csv"
        configured_path = csv_path or os.getenv("SCN_PRICING_CSV", str(default_path))
        self.csv_path = Path(configured_path)
        self._items: list[SCNItem] | None = None

    def load_items(self) -> list[SCNItem]:
        if self._items is not None:
            return self._items

        if not self.csv_path.exists():
            self._items = []
            return self._items

        rows: list[SCNItem] = []
        with self.csv_path.open("r", newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            for raw_row in reader:
                row = {self._normalize_key(key): (value or "").strip() for key, value in raw_row.items() if key}
                model = row.get("model")
                description = row.get("description")
                if not model and not description:
                    continue

                rows.append(
                    SCNItem(
                        model=model or "",
                        description=description or model or "",
                        list_price=self._parse_decimal(row.get("list_price")),
                        distributor_cost=self._parse_decimal(row.get("distributor_cost")),
                        unit=row.get("unit") or None,
                        manufacturer=row.get("manufacturer") or None,
                    )
                )

        self._items = rows
        return rows

    def search(self, query: str) -> list[SCNItem]:
        items = self.load_items()
        normalized = query.strip().lower()
        if not normalized:
            return items

        query_tokens = self._tokenize(normalized)
        if not query_tokens:
            return items

        matches: list[SCNItem] = []
        for item in items:
            haystack = f"{item.model} {item.description} {item.manufacturer or ''}".lower()
            if all(token in haystack for token in query_tokens):
                matches.append(item)
        return matches

    @staticmethod
    def _normalize_key(value: str) -> str:
        compact = re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")
        aliases = {
            "model_no_no_modele": "model",
            "mfg_model_no_no_fab": "model",
            "english_description_description_anglais": "description",
            "list_price_prix_liste": "list_price",
            "distributor_cost_cout_distributeur": "distributor_cost",
            "unit_of_sale": "unit",
            "unite_de_vente": "unit",
            "manufacturer": "manufacturer",
            "fabricant": "manufacturer",
        }
        return aliases.get(compact, compact)

    @staticmethod
    def _parse_decimal(value: str | None) -> float | None:
        if not value:
            return None
        cleaned = re.sub(r"[^0-9.,-]", "", value)
        if "," in cleaned and "." in cleaned:
            cleaned = cleaned.replace(",", "")
        elif cleaned.count(",") == 1 and cleaned.count(".") == 0:
            cleaned = cleaned.replace(",", ".")
        try:
            return float(cleaned)
        except ValueError:
            return None

    @staticmethod
    def _tokenize(value: str) -> list[str]:
        return [token for token in re.split(r"[^a-z0-9]+", value) if token]
