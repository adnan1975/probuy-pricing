from abc import ABC, abstractmethod

from app.models.search import NormalizedResult


class BaseConnector(ABC):
    source: str
    source_label: str

    @abstractmethod
    async def search(self, query: str) -> list[NormalizedResult]:
        """Return normalized search results for the provided query."""
