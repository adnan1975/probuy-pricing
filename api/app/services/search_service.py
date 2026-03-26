from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable

from app.connectors.base import BaseConnector
from app.connectors.canadiantire_connector import CanadianTireConnector
from app.connectors.homedepot_connector import HomeDepotConnector
from app.connectors.kms_connector import KMSConnector
from app.connectors.scn_connector import SCNConnector
from app.connectors.whitecap_connector import WhiteCapConnector
from app.models.normalized_result import NormalizedResult, SearchResponse
from app.services.analysis_service import AnalysisService
from app.services.connector_price_service import ConnectorPriceService
from app.services.matching_service import MatchingService


class SearchService:
    def __init__(self, connectors: list[BaseConnector] | None = None) -> None:
        self.connectors = connectors or [
            SCNConnector(),
            WhiteCapConnector(),
            KMSConnector(),
            CanadianTireConnector(),
            HomeDepotConnector(),
        ]
        self.matching_service = MatchingService()
        self.analysis_service = AnalysisService()
        self.connector_price_service = ConnectorPriceService()
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

    async def collect_live_results(
        self,
        query: str,
        connectors: list[BaseConnector] | None = None,
    ) -> tuple[list[NormalizedResult], dict[str, str], dict[str, str]]:
        connector_list = connectors or self.connectors
        tasks = [connector.search(query) for connector in connector_list]
        settled = await asyncio.gather(*tasks, return_exceptions=True)

        all_results: list[NormalizedResult] = []
        per_source_errors: dict[str, str] = {}
        per_source_warnings: dict[str, str] = {}

        for connector, item in zip(connector_list, settled, strict=True):
            if isinstance(item, Exception):
                per_source_errors[connector.source_label] = str(item)
                self.logger.error(
                    "Connector search failed",
                    extra={"source": connector.source_label, "query": query},
                    exc_info=(type(item), item, item.__traceback__),
                )
                continue
            all_results.extend(item)
            connector_warning = getattr(connector, "last_warning", None)
            if connector_warning:
                per_source_warnings[connector.source_label] = connector_warning

        return all_results, per_source_errors, per_source_warnings
