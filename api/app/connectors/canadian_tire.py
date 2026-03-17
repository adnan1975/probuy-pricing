from app.connectors.base import BaseConnector
from app.connectors.mock_catalog import build_mock_result
from app.models.search import SearchResult


class CanadianTireConnector(BaseConnector):
    source = "canadian_tire"
    source_label = "Canadian Tire"

    def search(self, query: str) -> list[SearchResult]:
        return build_mock_result(query, self.source, self.source_label)
