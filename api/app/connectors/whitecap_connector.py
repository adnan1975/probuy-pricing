from app.connectors.base import BaseConnector
from app.connectors.mock_catalog import build_mock_result
from app.models.search import SearchResult


class WhiteCapConnector(BaseConnector):
    source = "white_cap"
    source_label = "White Cap"

    def search(self, query: str) -> list[SearchResult]:
        return build_mock_result(query, self.source, self.source_label)
