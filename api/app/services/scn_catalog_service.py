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
    manufacturer_model: str | None
    description: str
    list_price: float | None
    distributor_cost: float | None
    scn_image: str | None
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
        if not normalized_query:
            self._items = []
            self._last_load_source = "supabase"
            return []

        search_max_rows = max(1, settings.scn_search_max_rows)
        items = self._load_from_supabase(query=normalized_query, row_cap=search_max_rows)
        query_tokens = self._tokenize(normalized_query)
        if query_tokens:
            items = [item for item in items if self._matches_all_tokens(item, query_tokens)]
        self._items = items
        self._last_load_source = "supabase"
        if not items:
            fallback_reason = self._supabase_fallback_reason or "Supabase returned no rows."
            self.last_load_warning = f"SCN catalog unavailable from Supabase ({fallback_reason})."
        return items

    @staticmethod
    def _searchable_blob(item: SCNItem) -> str:
        return " ".join(
            [
                item.model,
                item.manufacturer_model or "",
                item.description,
                item.manufacturer or "",
                item.unit or "",
                item.warehouse or "",
                str(item.list_price) if item.list_price is not None else "",
                str(item.distributor_cost) if item.distributor_cost is not None else "",
            ]
        ).lower()

    def _matches_all_tokens(self, item: SCNItem, query_tokens: list[str]) -> bool:
        blob = self._searchable_blob(item)
        return all(token in blob for token in query_tokens)

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


    def fetch_dashboard_stats(self) -> dict[str, object]:
        if not settings.supabase_url or not settings.supabase_service_role_key:
            return {
                "total_products": 0,
                "total_published_products": 0,
                "total_categories": 0,
                "channel_counts": {},
                "warning": "Supabase credentials are not configured.",
            }

        endpoint = f"{settings.supabase_url}/rest/v1/{settings.scn_table}"
        headers = {
            "apikey": settings.supabase_service_role_key,
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
            "Accept-Profile": settings.supabase_schema,
        }
        params = {
            "select": "publication_status,category,channel_code",
            "limit": "1000",
            "offset": "0",
        }

        rows: list[dict] = []
        while True:
            response = requests.get(endpoint, params=params, headers=headers, timeout=15)
            if not response.ok:
                return {
                    "total_products": 0,
                    "total_published_products": 0,
                    "total_categories": 0,
                    "channel_counts": {},
                    "warning": f"Supabase stats query failed with status {response.status_code}.",
                }
            payload = response.json()
            if not isinstance(payload, list):
                break
            if not payload:
                break
            rows.extend(payload)
            params["offset"] = str(int(params["offset"]) + int(params["limit"]))

        category_set: set[str] = set()
        channel_counts: dict[str, int] = {}
        published_count = 0

        for row in rows:
            publication_status = str(row.get("publication_status") or "").strip().lower()
            if publication_status == "published":
                published_count += 1

            category = str(row.get("category") or "").strip()
            if category:
                category_set.add(category)

            channel = str(row.get("channel_code") or "").strip().lower()
            if channel:
                channel_counts[channel] = channel_counts.get(channel, 0) + 1

        return {
            "total_products": len(rows),
            "total_published_products": published_count,
            "total_categories": len(category_set),
            "channel_counts": channel_counts,
            "warning": None,
        }

    def _load_from_supabase(self, query: str | None = None, row_cap: int | None = None) -> list[SCNItem]:
        self._supabase_attempted = False
        self._supabase_fallback_reason = None
        if not settings.supabase_url or not settings.supabase_service_role_key:
            self._supabase_fallback_reason = "Supabase credentials are not configured."
            return []

        self._supabase_attempted = True
        endpoint = f"{settings.supabase_url}/rest/v1/{settings.scn_table}"
        timeout_seconds = 15
        select_clause = (
            "model,manufacturer_model,description,list_price,distributor_cost,scn_image,"
            "unit,manufacturer,warehouse"
        )
        page_size = 1000
        params = {
            "select": select_clause,
            "order": "model.asc",
        }
        normalized_query = (query or "").strip()
        if normalized_query:
            escaped = normalized_query.replace("*", "").replace(",", " ")
            params["or"] = (
                f"(model.ilike.*{escaped}*,manufacturer_model.ilike.*{escaped}*,"
                f"description.ilike.*{escaped}*,manufacturer.ilike.*{escaped}*)"
            )
        headers = {
            "apikey": settings.supabase_service_role_key,
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
            "Accept-Profile": settings.supabase_schema,
        }

        effective_cap = max(1, row_cap) if row_cap is not None else None
        if effective_cap is not None:
            page_size = min(page_size, effective_cap)

        rows: list[SCNItem] = []
        page_index = 0
        truncation_logged = False
        while True:
            paged_params = {
                **params,
                "limit": str(page_size),
                "offset": str(page_index * page_size),
            }
            try:
                response = requests.get(endpoint, params=paged_params, headers=headers, timeout=timeout_seconds)
                response.raise_for_status()
                page_payload = response.json()
            except requests.RequestException as exc:
                self._supabase_fallback_reason = str(exc)
                return []

            if not isinstance(page_payload, list):
                self._supabase_fallback_reason = "Supabase returned an unexpected payload."
                logger.warning(
                    "Unexpected SCN catalog payload type from Supabase (host=%s schema=%s table=%s payload_type=%s)",
                    urlparse(settings.supabase_url).netloc or "unknown-host",
                    settings.supabase_schema,
                    settings.scn_table,
                    type(page_payload).__name__,
                )
                return []

            if not page_payload:
                break

            for row in page_payload:
                rows.append(
                    SCNItem(
                        model=str(row.get("model") or ""),
                        manufacturer_model=str(row.get("manufacturer_model")) if row.get("manufacturer_model") else None,
                        description=str(row.get("description") or ""),
                        list_price=self._parse_decimal(row.get("list_price")),
                        distributor_cost=self._parse_decimal(row.get("distributor_cost")),
                        scn_image=str(row.get("scn_image")) if row.get("scn_image") else None,
                        unit=str(row.get("unit")) if row.get("unit") else None,
                        manufacturer=str(row.get("manufacturer")) if row.get("manufacturer") else None,
                        warehouse=(
                            str(row.get("warehouse"))
                            if (row.get("warehouse") and str(row.get("warehouse")).strip())
                            else None
                        ),
                    )
                )
                if effective_cap is not None and len(rows) >= effective_cap:
                    truncation_logged = True
                    break

            if truncation_logged:
                logger.warning(
                    "SCN Supabase search results truncated (query=%r row_cap=%s).",
                    normalized_query,
                    effective_cap,
                )
                break

            if len(page_payload) < page_size or normalized_query:
                break
            page_index += 1

        if not rows:
            self._supabase_fallback_reason = "Supabase returned no rows."
            logger.warning(
                "Supabase returned no SCN rows (host=%s schema=%s table=%s timeout=%ss).",
                urlparse(settings.supabase_url).netloc or "unknown-host",
                settings.supabase_schema,
                settings.scn_table,
                timeout_seconds,
            )
            return []
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
                        manufacturer_model=row.get("manufacturer_model") or None,
                        description=description or model or "",
                        list_price=self._parse_decimal(row.get("list_price")),
                        distributor_cost=self._parse_decimal(row.get("distributor_cost")),
                        scn_image=row.get("scn_image") or None,
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
            "mfg_model_no_no_fab": "manufacturer_model",
            "manufacturernumber": "manufacturer_model",
            "manufacturer_number": "manufacturer_model",
            "english_description_description_anglais": "description",
            "list_price_prix_liste": "list_price",
            "distributor_cost_cout_distributeur": "distributor_cost",
            "unit_of_sale": "unit",
            "unite_de_vente": "unit",
            "scn_image": "scn_image",
            "image_url": "scn_image",
            "image": "scn_image",
            "manufacturer": "manufacturer",
            "fabricant": "manufacturer",
            "warehouse_location": "warehouse",
            
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

        payload = self._normalize_ingest_payload(items)
        if not payload:
            return {"read": 0, "upserted": 0}

        for idx in range(0, len(payload), settings.scn_batch_size):
            batch = payload[idx : idx + settings.scn_batch_size]
            try:
                response = requests.post(
                    endpoint,
                    params={"on_conflict": "model,manufacturer,warehouse"},
                    headers=headers,
                    json=batch,
                    timeout=30,
                )
                response.raise_for_status()
            except requests.HTTPError as exc:
                self._log_batch_http_error(exc=exc, batch=batch, batch_start_index=idx)
                raise

        self.catalog_service.load_items(force_reload=True)
        return {"read": len(payload), "upserted": len(payload)}

    def _log_batch_http_error(
        self,
        *,
        exc: requests.HTTPError,
        batch: list[dict[str, object]],
        batch_start_index: int,
    ) -> None:
        response = exc.response
        if response is None:
            logger.exception("SCN ingest batch failed without response metadata.")
            return
        error_details = self._extract_supabase_error_details(response)

        logger.error(
            (
                "SCN ingest batch failed with HTTP %s (batch_start_index=%s, batch_size=%s, "
                "error_code=%s, error_message=%s, error_hint=%s, error_details=%s, response=%s)"
            ),
            response.status_code,
            batch_start_index,
            len(batch),
            error_details["code"],
            error_details["message"],
            error_details["hint"],
            error_details["details"],
            response.text[:1000],
        )

        # 400 usually indicates row-level shape/constraint issues. Probe each row to
        # identify the exact offending model and CSV payload for faster remediation.
        if response.status_code != 400:
            return

        for offset, row in enumerate(batch):
            absolute_row = batch_start_index + offset + 2  # +2 accounts for 0-index + header row
            model = row.get("model")
            manufacturer = row.get("manufacturer")
            warehouse = row.get("warehouse")
            logger.error(
                "Potentially invalid SCN row at CSV line %s (model=%s, manufacturer=%s, warehouse=%s, row=%s)",
                absolute_row,
                model,
                manufacturer,
                warehouse,
                row,
            )

    def _normalize_ingest_payload(self, items: list[SCNItem]) -> list[dict[str, object]]:
        payload: list[dict[str, object]] = []
        skipped_missing_model = 0

        for item in items:
            row = asdict(item)
            model = str(row.get("model") or "").strip()
            if not model:
                skipped_missing_model += 1
                continue

            row["model"] = model
            row["manufacturer"] = str(row.get("manufacturer") or "").strip()
            row["warehouse"] = str(row.get("warehouse") or "").strip()
            row["manufacturer_model"] = str(row.get("manufacturer_model") or "").strip()
            payload.append(row)

        if skipped_missing_model:
            logger.warning(
                "Skipped %s SCN rows during ingest because `model` was empty.",
                skipped_missing_model,
            )

        return payload

    @staticmethod
    def _extract_supabase_error_details(response: requests.Response) -> dict[str, str]:
        try:
            payload = response.json()
        except ValueError:
            return {"code": "", "message": "", "hint": "", "details": ""}

        if not isinstance(payload, dict):
            return {"code": "", "message": "", "hint": "", "details": ""}

        return {
            "code": str(payload.get("code") or ""),
            "message": str(payload.get("message") or ""),
            "hint": str(payload.get("hint") or ""),
            "details": str(payload.get("details") or ""),
        }
