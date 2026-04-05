from __future__ import annotations

import logging

from app.connectors.base import BaseConnector
from app.connectors.scn_connector import SCNConnector
from app.models.normalized_result import NormalizedResult, SearchResponse
from app.services.analysis_service import AnalysisService
from app.services.matching_service import MatchingService
from app.services.scn_catalog_service import SCNCatalogService, SCNItem


class SearchService:
    def __init__(self, connectors: list[BaseConnector] | None = None) -> None:
        self.connectors = connectors or [SCNConnector()]
        self.matching_service = MatchingService()
        self.analysis_service = AnalysisService()
        self.scn_catalog_service = SCNCatalogService()
        self.logger = logging.getLogger(__name__)
        self._connector_lookup = self._build_connector_lookup(self.connectors)

    @staticmethod
    def _build_connector_lookup(connectors: list[BaseConnector]) -> dict[str, BaseConnector]:
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
        per_source_errors: dict[str, str] = {}
        per_source_warnings: dict[str, str] = {}

        connector = next((item for item in self.connectors if isinstance(item, SCNConnector)), None)
        if connector is None:
            return SearchResponse(
                query=query,
                results=[],
                analysis=self.analysis_service.build([], per_source_errors=per_source_errors, per_source_warnings=per_source_warnings),
                page=page,
                page_size=page_size,
                total_pages=0,
                total_results=0,
                per_source_errors=per_source_errors,
                per_source_warnings=per_source_warnings,
            )

        try:
            results = await connector.search(query)
            if connector.last_warning:
                per_source_warnings[connector.source_label] = connector.last_warning
        except Exception as exc:
            per_source_errors[connector.source_label] = str(exc)
            self.logger.error("SCN search failed", extra={"query": query}, exc_info=True)
            results = []

        ranked_results = self.matching_service.apply(query, results)
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

    async def search_step1(
        self,
        query: str,
        page: int = 1,
        page_size: int = 25,
    ) -> tuple[SearchResponse, list[SCNItem]]:
        response = await self.search(query=query, page=page, page_size=page_size)
        return response, self.scn_catalog_service.search(query)

    async def search_step2(self, query: str, scn_items: list[SCNItem] | None = None) -> SearchResponse:
        return SearchResponse(
            query=query,
            results=[],
            analysis=self.analysis_service.build([], per_source_errors={}, per_source_warnings={}),
            page=1,
            page_size=0,
            total_pages=0,
            total_results=0,
            per_source_errors={},
            per_source_warnings={},
        )

    async def search_connector_with_scn_variants(
        self,
        connector: BaseConnector,
        query: str,
        scn_items: list[SCNItem] | None = None,
    ) -> list[NormalizedResult]:
        return await connector.search(query)
