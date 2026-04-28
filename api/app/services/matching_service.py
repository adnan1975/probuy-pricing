from __future__ import annotations

import math
import re
from collections import Counter

from app.models.normalized_result import NormalizedResult


class MatchingService:
    LEXICAL_WEIGHT = 0.60
    SEMANTIC_WEIGHT = 0.40

    def apply(self, query: str, results: list[NormalizedResult]) -> list[NormalizedResult]:
        query_tokens = self._tokenize(query)
        query_model_tokens = self._extract_model_like_tokens(query)

        ranked: list[NormalizedResult] = []
        for result in results:
            comparison_text = self._build_product_text(result)
            title_tokens = self._tokenize(result.title)

            lexical_score, lexical_overlap = self._compute_lexical_score(
                query_tokens=query_tokens,
                title_tokens=title_tokens,
                query_model_tokens=query_model_tokens,
                result=result,
            )
            semantic_similarity = self._compute_embedding_similarity(query, comparison_text)
            semantic_score = int(round(semantic_similarity * 100))

            weighted_score = int(
                round((lexical_score * self.LEXICAL_WEIGHT) + (semantic_score * self.SEMANTIC_WEIGHT))
            )

            override_score, exact_match_field = self._exact_part_number_override(query_model_tokens, result)
            final_score = self._clamp_score(max(result.score, weighted_score, override_score))

            why_parts = [
                f"lexical overlap {lexical_overlap}/{max(1, len(query_tokens))} ({lexical_score}%)",
                f"semantic {self._semantic_bucket(semantic_similarity)} ({semantic_score}%)",
            ]
            if exact_match_field:
                why_parts.append(f"exact {exact_match_field} match override")
            if result.source_type == "distributor":
                final_score = self._clamp_score(final_score + 2)
                why_parts.append("distributor source preference")

            ranked.append(
                result.model_copy(
                    update={
                        "score": final_score,
                        "why": "; ".join(why_parts),
                    }
                )
            )

        ranked.sort(key=lambda item: (item.score, item.price_value is not None), reverse=True)
        return ranked

    def _compute_lexical_score(
        self,
        query_tokens: set[str],
        title_tokens: set[str],
        query_model_tokens: set[str],
        result: NormalizedResult,
    ) -> tuple[int, int]:
        overlap = len(query_tokens & title_tokens)
        overlap_ratio = overlap / max(1, len(query_tokens))
        score = int(round(overlap_ratio * 70))

        for part_number in self._result_part_numbers(result):
            if part_number in query_model_tokens:
                score += 30
                break

        return self._clamp_score(score), overlap

    @staticmethod
    def _build_product_text(result: NormalizedResult) -> str:
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

    def _compute_embedding_similarity(self, query: str, comparison_text: str) -> float:
        query_embedding = self._embed_text(query)
        product_embedding = self._embed_text(comparison_text)
        if not query_embedding or not product_embedding:
            return 0.0

        dot = sum(query_embedding[key] * product_embedding.get(key, 0.0) for key in query_embedding)
        query_norm = math.sqrt(sum(value * value for value in query_embedding.values()))
        product_norm = math.sqrt(sum(value * value for value in product_embedding.values()))
        if query_norm == 0.0 or product_norm == 0.0:
            return 0.0
        return max(0.0, min(1.0, dot / (query_norm * product_norm)))

    def _exact_part_number_override(
        self,
        query_model_tokens: set[str],
        result: NormalizedResult,
    ) -> tuple[int, str | None]:
        for field_name, part_number in [
            ("sku", result.sku),
            ("model", result.model),
            ("manufacturer_model", result.manufacturer_model),
        ]:
            normalized = self._normalize_model_token(part_number)
            if normalized and normalized in query_model_tokens:
                return 95, field_name
        return 0, None

    def _result_part_numbers(self, result: NormalizedResult) -> set[str]:
        part_numbers: set[str] = set()
        for value in [result.sku, result.model, result.manufacturer_model]:
            normalized = self._normalize_model_token(value)
            if normalized:
                part_numbers.add(normalized)
        return part_numbers

    @staticmethod
    def _tokenize(value: str) -> set[str]:
        return {token for token in re.split(r"[^a-zA-Z0-9]+", value.lower()) if token}

    def _extract_model_like_tokens(self, value: str) -> set[str]:
        raw_tokens = re.findall(r"[a-zA-Z0-9-]+", value.lower())
        normalized_tokens = {self._normalize_model_token(token) for token in raw_tokens}
        return {token for token in normalized_tokens if token and len(token) >= 3}

    @staticmethod
    def _normalize_model_token(value: str | None) -> str:
        if not value:
            return ""
        return re.sub(r"[^a-z0-9]", "", value.lower())

    def _embed_text(self, value: str) -> dict[str, float]:
        tokens = [token for token in self._tokenize(value) if len(token) >= 2]
        if not tokens:
            return {}

        # Lightweight token-ngram embedding. Keeps implementation dependency-free while
        # capturing semantic closeness for phrasing variants.
        grams = Counter[str]()
        for token in tokens:
            padded = f"_{token}_"
            for index in range(len(padded) - 2):
                grams[padded[index : index + 3]] += 1

        norm = math.sqrt(sum(count * count for count in grams.values()))
        if norm == 0.0:
            return {}
        return {gram: count / norm for gram, count in grams.items()}

    @staticmethod
    def _semantic_bucket(similarity: float) -> str:
        if similarity >= 0.8:
            return "high"
        if similarity >= 0.55:
            return "medium"
        return "low"

    @staticmethod
    def _clamp_score(value: int) -> int:
        return max(0, min(100, value))
