from __future__ import annotations

import csv
import logging
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlparse

import requests

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SCNItem:
    model: str
    description: str
    list_price: float | None
    distributor_cost: float | None
    unit: str | None
    manufacturer: str | None
    warehouse: str | None


class SCNCatalogService:
    """Loads SCN pricing from Supabase."""

    def __init__(self, csv_path: str | None = None) -> None:
        root_dir = Path(__file__).resolve().parents[2]
        default_path = root_dir / "data" / "scn_pricing.csv"
        configured_path = csv_path or os.getenv("SCN_PRICING_CSV", str(default_path))
        # CSV path is kept only for the batch ingest utility below. Search paths
        # in this service always read from Supabase.
        self.csv_path = Path(configured_path)
        self._items: list[SCNItem] | None = None
        self.last_load_warning: str | None = None
        self._supabase_attempted = False
        self._supabase_fallback_reason: str | None = None
        self._last_load_source: str = "supabase"

    def load_items(self, force_reload: bool = False) -> list[SCNItem]:
        if self._items is not None and not force_reload:
            return self._items

        self.last_load_warning = None
        db_items = self._load_from_supabase()
        self._items = db_items
        self._last_load_source = "supabase"
        if not db_items:
            fallback_reason = self._supabase_fallback_reason or "Supabase returned no rows."
            self.last_load_warning = f"SCN catalog unavailable from Supabase ({fallback_reason})."
        return db_items

    @property
    def last_load_source(self) -> str:
        return self._last_load_source

    @property
    def supabase_configured(self) -> bool:
        return bool(settings.supabase_url and settings.supabase_service_role_key)

    @property
    def table_ref(self) -> str:
        return f"{settings.supabase_schema}.{settings.scn_table}"

    def health(self) -> dict[str, str | int | bool]:
        items = self.load_items()
        return {
            "catalog_source": self.last_load_source,
            "loaded_items_count": len(items),
            "supabase_configured": self.supabase_configured,
            "table_ref": self.table_ref,
        }

    def search(self, query: str) -> list[SCNItem]:
        normalized_query = query.strip().lower()
        self.last_load_warning = None
        items = self._load_from_supabase(query=query)
        if normalized_query:
            query_tokens = self._tokenize(normalized_query)
            if query_tokens:
                items = [
                    item
                    for item in items
                    if all(
                        token in f"{item.model} {item.description} {item.manufacturer or ''}".lower()
                        for token in query_tokens
                    )
                ]
        self._items = items
        self._last_load_source = "supabase"
        if not items:
            fallback_reason = self._supabase_fallback_reason or "Supabase returned no rows."
            self.last_load_warning = f"SCN catalog unavailable from Supabase ({fallback_reason})."
        return items

    def list_distinct_queries(self, limit: int = 100) -> list[str]:
        items = self.load_items()
        seen: set[str] = set()
        values: list[str] = []

        for item in items:
            for candidate in (item.model, item.description):
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
                    return values

        return values

    def _load_from_supabase(self, query: str | None = None) -> list[SCNItem]:
        self._supabase_attempted = False
        self._supabase_fallback_reason = None
        if not settings.supabase_url or not settings.supabase_service_role_key:
            self._supabase_fallback_reason = "Supabase credentials are not configured."
            return []

        self._supabase_attempted = True
        endpoint = f"{settings.supabase_url}/rest/v1/{settings.scn_table}"
        timeout_seconds = 15
        params = {
            "select": "model,description,list_price,distributor_cost,unit,manufacturer,warehouse",
            "order": "model.asc",
            "limit": "5000",
        }
        normalized_query = (query or "").strip()
        if normalized_query:
            escaped = normalized_query.replace("*", "").replace(",", " ")
            params["or"] = (
                f"(model.ilike.*{escaped}*,description.ilike.*{escaped}*,manufacturer.ilike.*{escaped}*)"
            )
        headers = {
            "apikey": settings.supabase_service_role_key,
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
            "Accept-Profile": settings.supabase_schema,
        }

        try:
            response = requests.get(endpoint, params=params, headers=headers, timeout=timeout_seconds)
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            self._supabase_fallback_reason = str(exc)
            return []

        if not isinstance(payload, list):
            self._supabase_fallback_reason = "Supabase returned an unexpected payload."
            logger.warning(
                "Unexpected SCN catalog payload type from Supabase (host=%s schema=%s table=%s payload_type=%s)",
                urlparse(settings.supabase_url).netloc or "unknown-host",
                settings.supabase_schema,
                settings.scn_table,
                type(payload).__name__,
            )
            return []
        if not payload:
            self._supabase_fallback_reason = "Supabase returned no rows."
            logger.warning(
                "Supabase returned no SCN rows (host=%s schema=%s table=%s timeout=%ss).",
                urlparse(settings.supabase_url).netloc or "unknown-host",
                settings.supabase_schema,
                settings.scn_table,
                timeout_seconds,
            )
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
                    warehouse=(
                        str(row.get("warehouse") or row.get("warhouse"))
                        if (row.get("warehouse") or row.get("warhouse"))
                        else None
                    ),
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
                        warehouse=row.get("warehouse") or None,
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
            "warehouse_location": "warehouse",
            "warhouse_location": "warehouse",
            "warhouse": "warehouse",
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

        table_ref = f"{settings.scn_table}"
        endpoint = f"{settings.supabase_url}/rest/v1/{table_ref}"
        headers = {
            "apikey": settings.supabase_service_role_key,
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=minimal",
            # POST requires Content-Profile (not Accept-Profile) to target non-public schemas
            "Content-Profile": settings.supabase_schema,
        }

        payload = [asdict(item) for item in items]
        if not payload:
            return {"read": 0, "upserted": 0}

        for idx in range(0, len(payload), settings.scn_batch_size):
            batch = payload[idx : idx + settings.scn_batch_size]
            response = requests.post(
                endpoint,
                params={"on_conflict": "model,manufacturer,warehouse"},
                headers=headers,
                json=batch,
                timeout=30,
            )
            response.raise_for_status()

        self.catalog_service.load_items(force_reload=True)
        return {"read": len(payload), "upserted": len(payload)}
