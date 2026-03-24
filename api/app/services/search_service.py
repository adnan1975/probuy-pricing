from __future__ import annotations

import asyncio

from app.connectors.base import BaseConnector
from app.connectors.canadiantire_connector import CanadianTireConnector
from app.connectors.homedepot_connector import HomeDepotConnector
from app.connectors.kms_connector import KMSConnector
from app.connectors.whitecap_connector import WhiteCapConnector
from app.models.normalized_result import NormalizedResult, SearchResponse
from app.services.analysis_service import AnalysisService
from app.services.matching_service import MatchingService


class SearchService:
    def __init__(self, connectors: list[BaseConnector] | None = None) -> None:
        self.connectors = connectors or [
            WhiteCapConnector(),
            KMSConnector(),
            CanadianTireConnector(),
            HomeDepotConnector(),
        ]
        self.matching_service = MatchingService()
        self.analysis_service = AnalysisService()

    async def search(self, query: str) -> SearchResponse:
        tasks = [connector.search(query) for connector in self.connectors]
        settled = await asyncio.gather(*tasks, return_exceptions=True)

        all_results: list[NormalizedResult] = []
        per_source_errors: dict[str, str] = {}

        for connector, item in zip(self.connectors, settled, strict=True):
            if isinstance(item, Exception):
                per_source_errors[connector.source_label] = str(item)
                continue
            all_results.extend(item)

        ranked_results = self.matching_service.apply(query, all_results)
        analysis = self.analysis_service.build(ranked_results)

        return SearchResponse(
            query=query,
            results=ranked_results,
            analysis=analysis,
            per_source_errors=per_source_errors,
        )
