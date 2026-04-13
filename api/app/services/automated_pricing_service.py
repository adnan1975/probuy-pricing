from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.models.normalized_result import NormalizedResult
from app.services.scn_catalog_service import SCNItem, SCNCatalogService
from app.services.search_service import SearchService

logger = logging.getLogger(__name__)


@dataclass
class AutomatedPricingRow:
    item_name: str
    model: str
    description: str
    kms_tools_price: float | None
    other_connector_price: float | None
    final_price: float | None
    published_to_shopify: bool
    published_to_method: bool


@dataclass
class AutomatedPricingJob:
    job_id: str
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    total_items: int = 0
    processed_items: int = 0
    status: str = "pending"
    rows: list[AutomatedPricingRow] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class AutomatedPricingService:
    """Runs a connector fan-out job for the first catalog items and stores in-memory progress."""

    def __init__(self) -> None:
        self._catalog_service = SCNCatalogService()
        self._search_service = SearchService()
        self._jobs: dict[str, AutomatedPricingJob] = {}

    def start_job(self, limit: int = 100) -> AutomatedPricingJob:
        safe_limit = max(1, min(limit, 100))
        job = AutomatedPricingJob(
            job_id=str(uuid.uuid4()),
            created_at=datetime.now(timezone.utc),
            total_items=safe_limit,
            status="running",
            started_at=datetime.now(timezone.utc),
        )
        self._jobs[job.job_id] = job
        asyncio.create_task(self._run_job(job.job_id, safe_limit))
        return job

    def get_job(self, job_id: str) -> AutomatedPricingJob | None:
        return self._jobs.get(job_id)

    async def _run_job(self, job_id: str, limit: int) -> None:
        job = self._jobs[job_id]
        items = [
            item
            for item in self._catalog_service.load_items()
            if (item.warehouse or "").strip().upper() == "VAN"
        ][:limit]
        job.total_items = len(items)

        for item in items:
            try:
                row = await self._process_item(item)
                job.rows.append(row)
            except Exception as exc:  # noqa: BLE001
                message = f"{item.model or item.description}: {exc}"
                logger.exception("Automated pricing item processing failed", extra={"job_id": job_id, "model": item.model})
                job.errors.append(message)
            finally:
                job.processed_items += 1

        job.status = "completed"
        job.finished_at = datetime.now(timezone.utc)

    async def _process_item(self, item: SCNItem) -> AutomatedPricingRow:
        query = self._build_query(item)

        connector_tasks = [
            connector.search(query)
            for connector in self._search_service.secondary_connectors
        ]
        connector_results = await asyncio.gather(*connector_tasks, return_exceptions=True)

        per_source_prices: dict[str, float] = {}
        for connector, result in zip(self._search_service.secondary_connectors, connector_results):
            if isinstance(result, Exception):
                continue
            best = self._best_price(result)
            if best is not None:
                per_source_prices[connector.source_label] = best

        kms_price = per_source_prices.get("KMS Tools")
        other_prices = [
            value
            for source, value in per_source_prices.items()
            if source != "KMS Tools"
        ]
        other_price = min(other_prices) if other_prices else None
        final_price_candidates = [p for p in (kms_price, other_price) if p is not None]
        final_price = min(final_price_candidates) if final_price_candidates else item.list_price

        return AutomatedPricingRow(
            item_name=item.manufacturer_model or item.model,
            model=item.model,
            description=item.description,
            kms_tools_price=kms_price,
            other_connector_price=other_price,
            final_price=final_price,
            published_to_shopify=True,
            published_to_method=True,
        )

    @staticmethod
    def _build_query(item: SCNItem) -> str:
        for candidate in (item.manufacturer_model, item.model, item.description):
            if candidate and candidate.strip():
                return candidate.strip()
        return ""

    @staticmethod
    def _best_price(results: list[NormalizedResult]) -> float | None:
        prices = [row.price_value for row in results if isinstance(row.price_value, (int, float))]
        return min(prices) if prices else None
