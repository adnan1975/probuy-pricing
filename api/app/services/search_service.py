from __future__ import annotations

import logging
from collections.abc import Iterable

from app.connectors.amazonca_connector import AmazonCAConnector
from app.connectors.base import BaseConnector
from app.connectors.canadiantire_connector import CanadianTireConnector
from app.connectors.homedepot_connector import HomeDepotConnector
from app.connectors.kms_connector import KMSConnector
from app.connectors.scn_connector import SCNConnector
from app.connectors.whitecap_connector import WhiteCapConnector
from app.models.normalized_result import NormalizedResult, SearchResponse
from app.services.analysis_service import AnalysisService
from app.services.matching_service import MatchingService
from app.services.scn_catalog_service import SCNCatalogService, SCNItem


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
        self.logger.info("Running two-step search", extra={"query": query})

        per_source_errors: dict[str, str] = {}
        per_source_warnings: dict[str, str] = {}

        step1_results: list[NormalizedResult] = []
        scn_items: list[SCNItem] = []

        scn_connector = next((connector for connector in self.connectors if isinstance(connector, SCNConnector)), None)
        if scn_connector is not None:
            try:
                step1_results = await scn_connector.search(query)
                scn_items = self.scn_catalog_service.search(query)
                if scn_connector.last_warning:
                    per_source_warnings[scn_connector.source_label] = scn_connector.last_warning
            except Exception as exc:
                per_source_errors[scn_connector.source_label] = str(exc)
                self.logger.error("SCN step failed", extra={"query": query}, exc_info=True)

        non_scn_connectors = [connector for connector in self.connectors if not isinstance(connector, SCNConnector)]
        step2_results, step2_errors, step2_warnings = await self.collect_live_results(
            query,
            scn_items=scn_items,
            connectors=non_scn_connectors,
        )
        per_source_errors.update(step2_errors)
        per_source_warnings.update(step2_warnings)

        all_results = [*step1_results, *step2_results]
        ranked_results = self.matching_service.apply(query, all_results)
        ranked_results = self._enforce_scn_priority(ranked_results)
        analysis = self.analysis_service.build(
            ranked_results,
            per_source_errors=per_source_errors,
            per_source_warnings=per_source_warnings,
        )

        total_results = len(ranked_results)
        total_pages = (total_results + page_size - 1) // page_size if total_results else 0
        start = max(page - 1, 0) * page_size
        end = start + page_size

        return SearchResponse(
            query=query,
            results=ranked_results[start:end],
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
        scn_items: list[SCNItem] | None = None,
        connectors: list[BaseConnector] | None = None,
    ) -> tuple[list[NormalizedResult], dict[str, str], dict[str, str]]:
        connector_list = connectors or self.connectors
        results: list[NormalizedResult] = []
        per_source_errors: dict[str, str] = {}
        per_source_warnings: dict[str, str] = {}

        for connector in connector_list:
            try:
                connector_results = await self.search_connector_with_scn_variants(
                    connector,
                    query,
                    scn_items=scn_items,
                )
                results.extend(connector_results)
            except Exception as exc:
                per_source_errors[connector.source_label] = str(exc)
                self.logger.error(
                    "Connector search failed",
                    extra={"source": connector.source_label, "query": query},
                    exc_info=True,
                )

            connector_warning = getattr(connector, "last_warning", None)
            if connector_warning:
                per_source_warnings[connector.source_label] = connector_warning

        return results, per_source_errors, per_source_warnings

    def scn_query_variants(self, query: str, scn_items: list[SCNItem] | None = None) -> list[str]:
        """Build SCN-derived lookup queries in required sequence.

        Sequence: model -> manufacturer_model -> description.
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

        rows = scn_items
        if rows is None:
            try:
                rows = self.scn_catalog_service.search(base_query)
            except Exception:
                self.logger.exception("Failed generating SCN query variants", extra={"query": base_query})
                rows = []

        for item in rows:
            _push(item.model)
        for item in rows:
            _push(item.manufacturer_model)
        for item in rows:
            _push(item.description)

        if not variants:
            _push(base_query)

        return variants

    async def search_connector_with_scn_variants(
        self,
        connector: BaseConnector,
        query: str,
        scn_items: list[SCNItem] | None = None,
    ) -> list[NormalizedResult]:
        """Search one connector using SCN-derived alternatives."""
        if isinstance(connector, SCNConnector):
            return await connector.search(query)

        queries = self.scn_query_variants(query, scn_items=scn_items)
        if not queries:
            return []

        merged_results: list[NormalizedResult] = []
        seen_result_keys: set[tuple[str, str, str]] = set()

        for candidate_query in queries:
            connector_results = await connector.search(candidate_query)
            if not connector_results:
                continue

            priced_results = [result for result in connector_results if result.price_value is not None]
            if not priced_results:
                continue

            for result in priced_results:
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
