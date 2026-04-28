from __future__ import annotations

import difflib
import re

from app.config import settings
from app.models.normalized_result import NormalizedResult


class SemanticMatchService:
    @staticmethod
    def build_comparison_text(result: NormalizedResult) -> str:
        return " ".join(
            part.strip()
            for part in [
                result.title or "",
                result.brand or "",
                result.sku or "",
                result.model or "",
                result.manufacturer_model or "",
            ]
            if part and part.strip()
        )

    @staticmethod
    def compute_semantic_similarity(query: str, result_text: str) -> float:
        query_tokens = SemanticMatchService._tokenize(query)
        result_tokens = SemanticMatchService._tokenize(result_text)
        if not query_tokens or not result_tokens:
            return 0.0

        intersection = len(query_tokens.intersection(result_tokens))
        lexical_component = intersection / len(query_tokens)

        sequence_component = difflib.SequenceMatcher(
            None,
            " ".join(sorted(query_tokens)),
            " ".join(sorted(result_tokens)),
        ).ratio()

        score = (0.65 * lexical_component) + (0.35 * sequence_component)
        return max(0.0, min(1.0, round(score, 4)))

    @staticmethod
    def is_enabled() -> bool:
        return settings.semantic_match_enabled

    @staticmethod
    def threshold() -> float:
        return max(0.0, min(1.0, settings.semantic_match_threshold))

    @staticmethod
    def _tokenize(value: str) -> set[str]:
        return {token for token in re.split(r"[^a-zA-Z0-9]+", value.lower()) if token}
