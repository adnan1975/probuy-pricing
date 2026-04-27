from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod

from app.models.normalized_result import NormalizedResult
from app.services.connector_price_service import ConnectorPriceService


class BaseConnector(ABC):
    source: str
    source_label: str
    _price_service = ConnectorPriceService()
    _logger = logging.getLogger(__name__)
    minimum_match_percent = 60

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

    def apply_query_match_filter(self, query: str, results: list[NormalizedResult]) -> tuple[list[NormalizedResult], int]:
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return results, 0

        filtered: list[NormalizedResult] = []
        dropped = 0
        for result in results:
            matched_tokens = self._match_count(query_tokens, result)
            match_percent = int(round((matched_tokens / len(query_tokens)) * 100))
            if match_percent < self.minimum_match_percent:
                dropped += 1
                continue

            confidence = "High" if match_percent >= 85 else "Medium"
            why_prefix = f"Connector-level query match {match_percent}% ({matched_tokens}/{len(query_tokens)} tokens)."
            base_why = (result.why or "").strip()
            filtered.append(
                result.model_copy(
                    update={
                        "score": max(result.score, match_percent),
                        "confidence": confidence if result.confidence != "High" else result.confidence,
                        "why": f"{why_prefix} {base_why}".strip(),
                    }
                )
            )
        return filtered, dropped

    @staticmethod
    def _tokenize(value: str) -> set[str]:
        return {token for token in re.split(r"[^a-zA-Z0-9]+", value.lower()) if token}

    def _match_count(self, query_tokens: set[str], result: NormalizedResult) -> int:
        blob = " ".join(
            [
                result.title or "",
                result.brand or "",
                result.sku or "",
                result.model or "",
                result.manufacturer_model or "",
            ]
        ).lower()
        return sum(1 for token in query_tokens if token in blob)
