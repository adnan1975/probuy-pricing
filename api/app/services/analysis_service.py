from __future__ import annotations

from statistics import mean

from app.models.normalized_result import NormalizedResult, SearchAnalysis


class AnalysisService:
    def build(
        self,
        results: list[NormalizedResult],
        per_source_errors: dict[str, str] | None = None,
    ) -> SearchAnalysis:
        priced_values = [item.price_value for item in results if item.price_value is not None]

        return SearchAnalysis(
            lowest_price=min(priced_values) if priced_values else None,
            highest_price=max(priced_values) if priced_values else None,
            average_price=round(mean(priced_values), 2) if priced_values else None,
            total_results=len(results),
            priced_results=len(priced_values),
            per_source_errors=per_source_errors or {},
        )
