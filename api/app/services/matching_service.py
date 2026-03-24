from __future__ import annotations

import re

from app.models.normalized_result import NormalizedResult


class MatchingService:
    def apply(self, query: str, results: list[NormalizedResult]) -> list[NormalizedResult]:
        query_tokens = self._tokenize(query)

        ranked: list[NormalizedResult] = []
        for result in results:
            title_tokens = self._tokenize(result.title)
            overlap = len(query_tokens & title_tokens)
            score = min(100, max(result.score, 60 + overlap * 10))

            why_parts: list[str] = []
            if overlap:
                why_parts.append(f"{overlap} query token(s) matched title")
            if result.brand and result.brand.lower() in query.lower():
                score = min(100, score + 8)
                why_parts.append("brand matched query")
            if result.sku and result.sku.lower() in query.lower():
                score = min(100, score + 12)
                why_parts.append("part number matched query")
            if result.source_type == "distributor":
                score = min(100, score + 3)
                why_parts.append("distributor source preference")

            ranked.append(
                result.model_copy(
                    update={
                        "score": score,
                        "why": "; ".join(why_parts) if why_parts else "General text match",
                    }
                )
            )

        ranked.sort(key=lambda item: (item.score, item.price_value is not None), reverse=True)
        return ranked

    @staticmethod
    def _tokenize(value: str) -> set[str]:
        return {token for token in re.split(r"[^a-zA-Z0-9]+", value.lower()) if token}
