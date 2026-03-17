from app.connectors.base import BaseConnector
from app.connectors.mock_catalog import build_mock_result
from app.models.search import SearchResult


class KMSToolsConnector(BaseConnector):
    source = "kms_tools"
    source_label = "KMS Tools"

    def search(self, query: str) -> list[SearchResult]:
        return build_mock_result(query, self.source, self.source_label)
