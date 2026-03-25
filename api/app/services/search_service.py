from __future__ import annotations

import asyncio
import logging

from app.connectors.base import BaseConnector
from app.connectors.canadiantire_connector import CanadianTireConnector
from app.connectors.homedepot_connector import HomeDepotConnector
from app.connectors.kms_connector import KMSConnector
from app.connectors.scn_connector import SCNConnector
from app.connectors.whitecap_connector import WhiteCapConnector
from app.models.normalized_result import NormalizedResult, SearchResponse
from app.services.analysis_service import AnalysisService
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
        self.logger = logging.getLogger(__name__)

    async def search(self, query: str, page: int = 1, page_size: int = 25) -> SearchResponse:
        self.logger.info("Starting aggregated search", extra={"query": query})
        tasks = [connector.search(query) for connector in self.connectors]
        settled = await asyncio.gather(*tasks, return_exceptions=True)

        all_results: list[NormalizedResult] = []
        per_source_errors: dict[str, str] = {}
        per_source_warnings: dict[str, str] = {}

        for connector, item in zip(self.connectors, settled, strict=True):
            if isinstance(item, Exception):
                per_source_errors[connector.source_label] = str(item)
                self.logger.error(
                    "Connector search failed",
                    extra={"source": connector.source_label, "query": query},
                    exc_info=(type(item), item, item.__traceback__),
                )
                continue
            all_results.extend(item)
            self.logger.info(
                "Connector returned results",
                extra={"source": connector.source_label, "count": len(item)},
            )
            connector_warning = getattr(connector, "last_warning", None)
            if connector_warning:
                per_source_warnings[connector.source_label] = connector_warning
                self.logger.warning(
                    "Connector warning",
                    extra={"source": connector.source_label, "warning": connector_warning},
                )

        ranked_results = self.matching_service.apply(query, all_results)
        analysis = self.analysis_service.build(
            ranked_results,
            per_source_errors=per_source_errors,
            per_source_warnings=per_source_warnings,
        )
        self.logger.info(
            "Aggregated search completed",
            extra={
                "query": query,
                "total_results": len(ranked_results),
                "error_sources": len(per_source_errors),
                "warning_sources": len(per_source_warnings),
            },
        )

        total_results = len(ranked_results)
        total_pages = (total_results + page_size - 1) // page_size if total_results else 0
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_results = ranked_results[start_idx:end_idx]

        return SearchResponse(
            query=query,
            results=paginated_results,
            analysis=analysis,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            total_results=total_results,
            per_source_errors=per_source_errors,
            per_source_warnings=per_source_warnings,
        )
