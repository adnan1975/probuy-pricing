from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod

from app.models.normalized_result import NormalizedResult
from app.services.connector_price_service import ConnectorPriceService
from app.services.semantic_match_service import SemanticMatchService


class BaseConnector(ABC):
    source: str
    source_label: str
    _price_service = ConnectorPriceService()
    _logger = logging.getLogger(__name__)
    minimum_match_percent = 60
    lexical_semantic_floor = 35

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
        semantic_enabled = SemanticMatchService.is_enabled()
        semantic_threshold = SemanticMatchService.threshold()
        for result in results:
            matched_tokens = self._match_count(query_tokens, result)
            match_percent = int(round((matched_tokens / len(query_tokens)) * 100))

            if match_percent < self.lexical_semantic_floor:
                dropped += 1
                continue

            confidence = "High" if match_percent >= 85 else "Medium"
            adjusted_score = max(result.score, match_percent)
            decision = "keep"
            decision_notes = [
                f"Lexical token match {match_percent}% ({matched_tokens}/{len(query_tokens)} tokens).",
            ]

            semantic_similarity = None
            if semantic_enabled and match_percent >= self.minimum_match_percent:
                comparison_text = SemanticMatchService.build_comparison_text(result)
                semantic_similarity = self.compute_semantic_similarity(query, comparison_text)
                semantic_percent = int(round(semantic_similarity * 100))
                decision_notes.append(
                    f"Semantic similarity {semantic_percent}% (threshold {int(round(semantic_threshold * 100))}%)."
                )

                if semantic_similarity >= semantic_threshold:
                    adjusted_score = max(adjusted_score, int(round(semantic_similarity * 100)))
                    confidence = "High" if semantic_similarity >= 0.75 else confidence
                    decision_notes.append("Semantic check boosted ranking.")
                else:
                    adjusted_score = max(0, adjusted_score - 20)
                    confidence = "Low"
                    decision = "demote"
                    decision_notes.append("Semantic check demoted candidate.")
            elif semantic_enabled:
                decision_notes.append(
                    "Semantic check skipped (lexical below semantic floor for scoring)."
                )
            else:
                decision_notes.append("Semantic check disabled by config.")

            if match_percent < self.minimum_match_percent and (semantic_similarity is None or semantic_similarity < semantic_threshold):
                decision = "drop"

            if decision == "drop":
                dropped += 1
                continue

            base_why = (result.why or "").strip()
            why_prefix = f"Connector-level query filter decision: {decision}. {' '.join(decision_notes)}"
            filtered.append(
                result.model_copy(
                    update={
                        "score": adjusted_score,
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

    def compute_semantic_similarity(self, query: str, result_text: str) -> float:
        return SemanticMatchService.compute_semantic_similarity(query, result_text)
