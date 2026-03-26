from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from app.models.normalized_result import NormalizedResult
from app.services.connector_price_service import ConnectorPriceService


class BaseConnector(ABC):
    source: str
    source_label: str
    _price_service = ConnectorPriceService()
    _logger = logging.getLogger(__name__)

    @abstractmethod
    async def search(self, query: str) -> list[NormalizedResult]:
        """Return normalized search results for the provided query."""

    def persist_results(self, query: str, results: list[NormalizedResult]) -> None:
        if not results:
            return
        try:
            self._price_service.save_results(query, results)
        except Exception:
            self._logger.warning("Failed to persist connector results", extra={"source": self.source_label}, exc_info=True)
