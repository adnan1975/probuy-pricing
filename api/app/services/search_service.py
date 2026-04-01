from __future__ import annotations

import asyncio
import logging
from time import perf_counter
from collections.abc import Iterable

from app.config import settings
from app.connectors.base import BaseConnector
from app.connectors.amazonca_connector import AmazonCAConnector
from app.connectors.canadiantire_connector import CanadianTireConnector
from app.connectors.homedepot_connector import HomeDepotConnector
from app.connectors.kms_connector import KMSConnector
from app.connectors.playwright_connector import PlaywrightConnector
from app.connectors.scn_connector import SCNConnector
from app.connectors.whitecap_connector import WhiteCapConnector
from app.models.normalized_result import NormalizedResult, SearchResponse
from app.services.analysis_service import AnalysisService
from app.services.connector_price_service import ConnectorPriceService
from app.services.matching_service import MatchingService
from app.services.scn_catalog_service import SCNCatalogService


class SearchService:
    def __init__(self, connectors: list[BaseConnector] | None = None) -> None:
        self.connectors = connectors or [
            SCNConnector(),
            WhiteCapConnector(),
            KMSConnector(),
            CanadianTireConnector(),
            HomeDepotConnector(),
            AmazonCAConnector(),
        ]
        self.matching_service = MatchingService()
        self.analysis_service = AnalysisService()
        self.connector_price_service = ConnectorPriceService()
        self.scn_catalog_service = SCNCatalogService()
        self.logger = logging.getLogger(__name__)
        self._connector_lookup = self._build_connector_lookup(self.connectors)

    @staticmethod
    def _build_connector_lookup(connectors: Iterable[BaseConnector]) -> dict[str, BaseConnector]:
        lookup: dict[str, BaseConnector] = {}
        for connector in connectors:
            aliases = {
                connector.source,
                connector.source.replace("_", ""),
                connector.source_label.lower(),
                connector.source_label.lower().replace(" ", ""),
                connector.source_label.lower().replace(" ", "_"),
            }
            for alias in aliases:
                lookup[alias] = connector
        return lookup

    def resolve_connector(self, connector_name: str) -> BaseConnector | None:
        normalized = connector_name.strip().lower()
        if not normalized:
            return None
        return self._connector_lookup.get(normalized) or self._connector_lookup.get(normalized.replace("-", "_"))

    async def search(self, query: str, page: int = 1, page_size: int = 25) -> SearchResponse:
        self.logger.info("Loading connector results from Supabase", extra={"query": query})

        per_source_errors: dict[str, str] = {}
        per_source_warnings: dict[str, str] = {}

        stored_results: list[NormalizedResult] = []
        total_results = 0
        try:
            stored_results, total_results = self.connector_price_service.search(query, page=page, page_size=page_size)
        except Exception as exc:
            per_source_errors["Supabase connector_prices"] = str(exc)
            self.logger.error("Failed to load connector prices from Supabase", exc_info=True)

        if not stored_results:
            self.logger.info("No stored connector results found, running live connectors", extra={"query": query})
            settled_results, live_errors, live_warnings = await self.collect_live_results(query)
            per_source_errors.update(live_errors)
            per_source_warnings.update(live_warnings)

            if settled_results:
                stored_results = settled_results
                total_results = len(stored_results)

        ranked_results = self.matching_service.apply(query, stored_results)
        ranked_results = self._enforce_scn_priority(ranked_results)
        analysis = self.analysis_service.build(
            ranked_results,
            per_source_errors=per_source_errors,
            per_source_warnings=per_source_warnings,
        )

        if total_results == 0:
            total_results = len(ranked_results)
        total_pages = (total_results + page_size - 1) // page_size if total_results else 0

        return SearchResponse(
            query=query,
            results=ranked_results,
            analysis=analysis,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            total_results=total_results,
            per_source_errors=per_source_errors,
            per_source_warnings=per_source_warnings,
        )

    @staticmethod
    def _is_scn_result(result: NormalizedResult) -> bool:
        normalized_source = (result.source or "").strip().lower().replace("_", " ")
        return normalized_source in {"scn pricing", "scn"}

    def _enforce_scn_priority(self, results: list[NormalizedResult]) -> list[NormalizedResult]:
        if not results:
            return []

        has_scn_match = any(self._is_scn_result(item) for item in results)
        if not has_scn_match:
            self.logger.info("No SCN match found; suppressing non-SCN results per pricing rule")
            return []

        return sorted(
            results,
            key=lambda item: (
                1 if self._is_scn_result(item) else 0,
                item.score,
                1 if item.price_value is not None else 0,
            ),
            reverse=True,
        )

    async def collect_live_results(
        self,
        query: str,
        connectors: list[BaseConnector] | None = None,
    ) -> tuple[list[NormalizedResult], dict[str, str], dict[str, str]]:
        connector_list = connectors or self.connectors
        max_concurrency = max(1, settings.connector_max_concurrency)
        semaphore = asyncio.Semaphore(max_concurrency)

        lightweight_connectors = [connector for connector in connector_list if not isinstance(connector, PlaywrightConnector)]
        heavy_connectors = [connector for connector in connector_list if isinstance(connector, PlaywrightConnector)]

        async def _run_connector(
            connector: BaseConnector,
            *,
            use_semaphore: bool,
        ) -> tuple[BaseConnector, list[NormalizedResult] | Exception]:
            source = connector.source_label
            started_at = perf_counter()
            self.logger.info(
                "Connector search started",
                extra={"source": source, "query": query, "throttled": use_semaphore},
            )

            try:
                if use_semaphore:
                    async with semaphore:
                        results = await connector.search(query)
                else:
                    results = await connector.search(query)

                elapsed_ms = round((perf_counter() - started_at) * 1000, 2)
                self.logger.info(
                    "Connector search succeeded",
                    extra={"source": source, "query": query, "elapsed_ms": elapsed_ms, "status": "success"},
                )
                return connector, results
            except Exception as exc:
                elapsed_ms = round((perf_counter() - started_at) * 1000, 2)
                self.logger.error(
                    "Connector search failed",
                    extra={"source": source, "query": query, "elapsed_ms": elapsed_ms, "status": "failed"},
                    exc_info=(type(exc), exc, exc.__traceback__),
                )
                return connector, exc

        tasks: list[asyncio.Task[tuple[BaseConnector, list[NormalizedResult] | Exception]]] = []
        tasks.extend(asyncio.create_task(_run_connector(connector, use_semaphore=False)) for connector in lightweight_connectors)
        tasks.extend(asyncio.create_task(_run_connector(connector, use_semaphore=True)) for connector in heavy_connectors)
        settled = await asyncio.gather(*tasks)

        all_results: list[NormalizedResult] = []
        per_source_errors: dict[str, str] = {}
        per_source_warnings: dict[str, str] = {}

        for connector, item in settled:
            if isinstance(item, Exception):
                per_source_errors[connector.source_label] = str(item)
                continue
            all_results.extend(item)
            connector_warning = getattr(connector, "last_warning", None)
            if connector_warning:
                per_source_warnings[connector.source_label] = connector_warning

        return all_results, per_source_errors, per_source_warnings

    def scn_query_variants(self, query: str) -> list[str]:
        """Build alternative lookup queries from SCN catalog matches.

        When searching an individual connector we start from the original query,
        then append SCN-enriched terms (model, manufacturer model, description,
        manufacturer) so retail connectors get multiple attempts for the same item.
        """

        base_query = query.strip()
        if not base_query:
            return []

        variants: list[str] = []
        seen: set[str] = set()

        def _push(value: str | None) -> None:
            if not value:
                return
            normalized = value.strip()
            if not normalized:
                return
            key = normalized.lower()
            if key in seen:
                return
            seen.add(key)
            variants.append(normalized)

        _push(base_query)

        try:
            scn_items = self.scn_catalog_service.search(base_query)
        except Exception:
            self.logger.exception("Failed generating SCN query variants", extra={"query": base_query})
            return variants

        for item in scn_items:
            _push(item.model)
            _push(item.manufacturer_model)
            _push(item.description)
            _push(item.manufacturer)

        return variants

    async def search_connector_with_scn_variants(self, connector: BaseConnector, query: str) -> list[NormalizedResult]:
        """Search one connector with original query + SCN-derived alternatives."""
        if isinstance(connector, SCNConnector):
            return await connector.search(query)

        queries = self.scn_query_variants(query)
        if not queries:
            return []

        merged_results: list[NormalizedResult] = []
        seen_result_keys: set[tuple[str, str, str]] = set()

        for candidate_query in queries:
            connector_results = await connector.search(candidate_query)
            for result in connector_results:
                dedupe_key = (
                    (result.product_url or "").strip().lower(),
                    (result.sku or "").strip().lower(),
                    (result.title or "").strip().lower(),
                )
                if dedupe_key in seen_result_keys:
                    continue
                seen_result_keys.add(dedupe_key)
                merged_results.append(result)

        return merged_results
