from __future__ import annotations

import csv
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path

import requests

from app.config import settings


@dataclass(frozen=True)
class SCNItem:
    model: str
    description: str
    list_price: float | None
    distributor_cost: float | None
    unit: str | None
    manufacturer: str | None


class SCNCatalogService:
    """Loads SCN pricing from Supabase (preferred) with CSV fallback for local use."""

    def __init__(self, csv_path: str | None = None) -> None:
        root_dir = Path(__file__).resolve().parents[2]
        default_path = root_dir / "data" / "scn_pricing.csv"
        configured_path = csv_path or os.getenv("SCN_PRICING_CSV", str(default_path))
        self.csv_path = Path(configured_path)
        self._items: list[SCNItem] | None = None

    def load_items(self, force_reload: bool = False) -> list[SCNItem]:
        if self._items is not None and not force_reload:
            return self._items

        db_items = self._load_from_supabase()
        if db_items:
            self._items = db_items
            return db_items

        csv_items = self._load_from_csv()
        self._items = csv_items
        return csv_items

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

    def list_distinct_queries(self, limit: int = 100) -> list[str]:
        items = self.load_items()
        seen: set[str] = set()
        values: list[str] = []

        for item in items:
            candidate = item.model or item.description
            if not candidate:
                continue
            normalized = candidate.strip()
            if not normalized:
                continue
            key = normalized.lower()
            if key in seen:
                continue
            seen.add(key)
            values.append(normalized)
            if len(values) >= limit:
                break

        return values

    def _load_from_supabase(self) -> list[SCNItem]:
        if not settings.supabase_url or not settings.supabase_service_role_key:
            return []

        table_ref = f"{settings.supabase_schema}.{settings.scn_table}"
        endpoint = f"{settings.supabase_url}/rest/v1/{table_ref}"
        params = {
            "select": "model,description,list_price,distributor_cost,unit,manufacturer",
            "order": "model.asc",
            "limit": "5000",
        }
        headers = {
            "apikey": settings.supabase_service_role_key,
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
        }

        try:
            response = requests.get(endpoint, params=params, headers=headers, timeout=15)
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException:
            return []

        if not isinstance(payload, list):
            return []

        rows: list[SCNItem] = []
        for row in payload:
            rows.append(
                SCNItem(
                    model=str(row.get("model") or ""),
                    description=str(row.get("description") or ""),
                    list_price=self._parse_decimal(row.get("list_price")),
                    distributor_cost=self._parse_decimal(row.get("distributor_cost")),
                    unit=str(row.get("unit")) if row.get("unit") else None,
                    manufacturer=str(row.get("manufacturer")) if row.get("manufacturer") else None,
                )
            )
        return rows

    def _load_from_csv(self) -> list[SCNItem]:
        if not self.csv_path.exists():
            return []

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

        return rows

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
    def _parse_decimal(value: str | float | int | None) -> float | None:
        if value is None:
            return None
        if isinstance(value, int | float):
            return float(value)
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


class SCNBatchIngestService:
    """Batch job service that upserts SCN pricing records into Supabase."""

    def __init__(self) -> None:
        self.catalog_service = SCNCatalogService()

    def ingest_csv_to_supabase(self, csv_path: str | None = None) -> dict[str, int]:
        if csv_path:
            self.catalog_service = SCNCatalogService(csv_path=csv_path)

        items = self.catalog_service._load_from_csv()
        if not settings.supabase_url or not settings.supabase_service_role_key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required for ingestion")

        table_ref = f"{settings.supabase_schema}.{settings.scn_table}"
        endpoint = f"{settings.supabase_url}/rest/v1/{table_ref}"
        headers = {
            "apikey": settings.supabase_service_role_key,
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=minimal",
        }

        payload = [asdict(item) for item in items]
        if not payload:
            return {"read": 0, "upserted": 0}

        for idx in range(0, len(payload), settings.scn_batch_size):
            batch = payload[idx : idx + settings.scn_batch_size]
            response = requests.post(
                endpoint,
                params={"on_conflict": "model"},
                headers=headers,
                json=batch,
                timeout=30,
            )
            response.raise_for_status()

        self.catalog_service.load_items(force_reload=True)
        return {"read": len(payload), "upserted": len(payload)}
