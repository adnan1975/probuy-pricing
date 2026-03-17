from abc import ABC, abstractmethod

from app.models.search import SearchResult


class BaseConnector(ABC):
    source: str
    source_label: str

    @abstractmethod
    def search(self, query: str) -> list[SearchResult]:
        """Return normalized search results for the provided query."""
