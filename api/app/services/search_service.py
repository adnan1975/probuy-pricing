import asyncio
from statistics import mean

from app.connectors.canadiantire_connector import CanadianTireConnector
from app.connectors.homedepot_connector import HomeDepotConnector
from app.connectors.kms_connector import KMSConnector
from app.connectors.whitecap_connector import WhiteCapConnector
from app.models.search import SearchAnalysis, SearchResponse


class SearchService:
    def __init__(self) -> None:
        self.connectors = [
            WhiteCapConnector(),
            KMSConnector(),
            CanadianTireConnector(),
            HomeDepotConnector(),
        ]

    async def search(self, query: str) -> SearchResponse:
        tasks = [connector.search(query) for connector in self.connectors]
        raw_results = await asyncio.gather(*tasks, return_exceptions=True)

        results = []
        for connector, item in zip(self.connectors, raw_results):
            if isinstance(item, Exception):
                # Never fail whole search due to one connector.
                continue
            results.extend(item)

        priced = [item.price_value for item in results]
        analysis = SearchAnalysis(
            lowest=min(priced) if priced else None,
            highest=max(priced) if priced else None,
            average=round(mean(priced), 2) if priced else None,
            source_count=len({item.source for item in results}),
        )

        source_labels = [connector.source_label for connector in self.connectors]

        return SearchResponse(
            query=query,
            results=results,
            analysis=analysis,
            source_labels=source_labels,
        )
