from __future__ import annotations

import logging
from datetime import datetime

import requests

from app.config import settings
from app.models.normalized_result import NormalizedResult

logger = logging.getLogger(__name__)


class ConnectorPriceService:
    """Persist and query connector prices in Supabase."""

    def __init__(self) -> None:
        self.table = settings.connector_prices_table

    @property
    def configured(self) -> bool:
        return bool(settings.supabase_url and settings.supabase_service_role_key)

    @property
    def endpoint(self) -> str | None:
        if not settings.supabase_url:
            return None
        return f"{settings.supabase_url}/rest/v1/{self.table}"

    def save_results(self, query: str, results: list[NormalizedResult]) -> int:
        if not self.configured or not results:
            return 0

        payload = []
        for item in results:
            payload.append(
                {
                    "search_query": query.strip(),
                    "source": item.source,
                    "sku": item.sku,
                    "manufacturer_model": item.manufacturer_model,
                    "title": item.title,
                    "price": item.price_value,
                    "available": item.availability,
                    "location": item.location,
                    "source_type": item.source_type,
                    "price_text": item.price_text,
                    "currency": item.currency,
                    "product_url": item.product_url,
                    "image_url": item.image_url,
                    "confidence": item.confidence,
                    "why": item.why,
                }
            )

        headers = {
            "apikey": settings.supabase_service_role_key,
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
            "Accept-Profile": settings.supabase_schema,
            "Content-Profile": settings.supabase_schema,
        }
        response = requests.post(self.endpoint, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        return len(payload)

    def search(self, query: str, page: int, page_size: int) -> tuple[list[NormalizedResult], int]:
        if not self.configured:
            return [], 0

        normalized_query = query.strip()
        headers = {
            "apikey": settings.supabase_service_role_key,
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
            "Accept": "application/json",
            "Prefer": "count=exact",
            "Accept-Profile": settings.supabase_schema,
        }

        params = {
            "select": "source,source_type,title,price_text,price,sku,manufacturer_model,available,location,currency,product_url,image_url,confidence,why,date_created",
            "order": "date_created.desc",
            # Pull a larger window, then dedupe + paginate locally so each connector row is the latest snapshot.
            "limit": "1000",
        }
        if normalized_query:
            escaped = normalized_query.replace("*", "").replace(",", " ")
            params["or"] = f"(title.ilike.*{escaped}*,sku.ilike.*{escaped}*,search_query.ilike.*{escaped}*)"

        response = requests.get(self.endpoint, headers=headers, params=params, timeout=20)
        response.raise_for_status()
        payload = response.json()
        total = self._extract_total(response.headers.get("Content-Range"))

        deduped_payload = self._dedupe_latest_rows(payload)
        total = len(deduped_payload)
        start = max(page - 1, 0) * page_size
        end = start + page_size
        page_rows = deduped_payload[start:end]

        results: list[NormalizedResult] = []
        for row in page_rows:
            results.append(
                NormalizedResult(
                    source=str(row.get("source") or "Unknown"),
                    source_type=str(row.get("source_type") or "retail"),
                    title=str(row.get("title") or "Untitled"),
                    price_text=row.get("price_text") or (f"${float(row['price']):,.2f}" if row.get("price") is not None else "Price unavailable"),
                    price_value=float(row["price"]) if row.get("price") is not None else None,
                    currency=str(row.get("currency") or "CAD"),
                    sku=row.get("sku"),
                    manufacturer_model=row.get("manufacturer_model"),
                    availability=str(row.get("available") or "Unknown"),
                    location=row.get("location"),
                    product_url=row.get("product_url"),
                    image_url=row.get("image_url"),
                    confidence=str(row.get("confidence") or "Medium"),
                    why=str(row.get("why") or "Stored connector result"),
                )
            )

        return results, total

    @staticmethod
    def _dedupe_latest_rows(rows: list[dict]) -> list[dict]:
        """
        Keep only the latest row for each connector + product tuple.
        Input rows are expected in date_created DESC order.
        """
        seen: set[tuple[str, str, str, str]] = set()
        deduped: list[dict] = []
        for row in rows:
            key = (
                str(row.get("source") or "").strip().lower(),
                str(row.get("sku") or "").strip().lower(),
                str(row.get("manufacturer_model") or "").strip().lower(),
                str(row.get("title") or "").strip().lower(),
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(row)
        return deduped

    @staticmethod
    def _extract_total(content_range: str | None) -> int:
        if not content_range or "/" not in content_range:
            return 0
        _, raw_total = content_range.split("/", 1)
        try:
            return int(raw_total)
        except ValueError:
            return 0

    def latest_snapshot_time(self) -> datetime | None:
        if not self.configured:
            return None

        headers = {
            "apikey": settings.supabase_service_role_key,
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
            "Accept": "application/json",
            "Accept-Profile": settings.supabase_schema,
        }
        response = requests.get(
            self.endpoint,
            headers=headers,
            params={"select": "date_created", "order": "date_created.desc", "limit": "1"},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        if not payload:
            return None
        raw_value = payload[0].get("date_created")
        if not raw_value:
            return None
        try:
            return datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
        except ValueError:
            return None
