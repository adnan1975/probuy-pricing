from __future__ import annotations

import asyncio
import logging
import re
from abc import ABC, abstractmethod
from typing import Any
from urllib.parse import urljoin

import requests

from app.connectors.base import BaseConnector
from app.models.normalized_result import NormalizedResult


class SecondaryAPIConnector(BaseConnector, ABC):
    """Template-method base connector for JSON API secondary sources."""

    source_type = "retail"
    currency = "CAD"
    timeout_seconds = 10
    max_results = 20
    max_query_variants = 3

    user_agent = (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )

    def __init__(self) -> None:
        self.last_warning: str | None = None
        self.last_error: str | None = None
        self.logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")

    async def search(self, query: str) -> list[NormalizedResult]:
        normalized_query = self.normalize_ws(query)
        if not normalized_query:
            self.last_warning = "Empty query supplied."
            self.last_error = None
            self.logger.warning("%s search skipped because query is empty", self.__class__.__name__)
            return []

        self.last_warning = None
        self.last_error = None
        variants = self.build_query_variants(normalized_query)[: self.max_query_variants]
        if not variants:
            variants = [("fallback", normalized_query)]

        try:
            variant_attempt_summaries: list[str] = []
            aggregated_results: list[NormalizedResult] = []
            total_dropped = 0

            for strategy_name, variant_query in variants:
                results, dropped_low_match = await self._run_single_attempt(strategy_name, variant_query)
                total_dropped += dropped_low_match
                variant_attempt_summaries.append(
                    f"{strategy_name}:{len(results)} result(s)"
                    if results
                    else f"{strategy_name}:0 result(s)"
                )
                aggregated_results.extend(results)

                if self.should_stop_after_variant(strategy_name, results):
                    break

            deduped_results = self.dedupe_results(aggregated_results)
            limited_results = deduped_results[: self.max_results]
            final_results, dropped_against_original = self.apply_query_match_filter(normalized_query, limited_results)
            total_dropped += dropped_against_original

            if final_results:
                partial_count = self._count_partial_price_results(final_results)
                warning_parts: list[str] = []
                if partial_count > 0:
                    warning_parts.append(f"Partial parse: {partial_count} result(s) had no numeric price value.")
                if total_dropped > 0:
                    warning_parts.append(
                        f"Filtered {total_dropped} result(s) below {self.minimum_match_percent}% query match."
                    )
                if len(variants) > 1:
                    warning_parts.append(f"Query strategies: {', '.join(variant_attempt_summaries)}.")
                if warning_parts:
                    self.last_warning = " ".join(warning_parts)
                self.persist_results(normalized_query, final_results)
                self.logger.info(
                    "%s api search completed query=%s results=%s strategies=%s",
                    self.__class__.__name__,
                    normalized_query,
                    len(final_results),
                    ", ".join(variant_attempt_summaries),
                )
            else:
                self.last_warning = (
                    "No API results met connector-level match threshold "
                    f"({self.minimum_match_percent}%+ required)."
                    if total_dropped > 0
                    else "No API results were parsed from response payload."
                )
                if len(variants) > 1:
                    self.last_warning = f"{self.last_warning} Query strategies: {', '.join(variant_attempt_summaries)}."
                self.logger.warning(
                    "%s api search completed with no results query=%s strategies=%s",
                    self.__class__.__name__,
                    normalized_query,
                    ", ".join(variant_attempt_summaries),
                )

            return final_results

        except requests.RequestException as exc:
            self.last_error = f"Network error while fetching source API: {exc}"
            self.last_warning = self.last_error
            self.logger.exception(
                "%s network error query=%s error=%s",
                self.__class__.__name__,
                normalized_query,
                exc,
            )
            return []

        except Exception as exc:  # noqa: BLE001
            self.last_error = f"Unexpected API parse error: {exc}"
            self.last_warning = self.last_error
            self.logger.exception(
                "%s unexpected error query=%s error=%s",
                self.__class__.__name__,
                normalized_query,
                exc,
            )
            return []

    async def _run_single_attempt(self, strategy_name: str, query: str) -> tuple[list[NormalizedResult], int]:
        request = self.build_request(query)
        self.logger.info(
            "%s api search attempt strategy=%s query=%s request=%s",
            self.__class__.__name__,
            strategy_name,
            query,
            self._loggable_request(request),
        )
        payload = await asyncio.to_thread(self.download_payload, request)
        results = self._extract_results(query, payload)
        annotated = self._annotate_results_for_strategy(strategy_name, query, results)
        return self.apply_query_match_filter(query, annotated)

    def build_query_variants(self, query: str) -> list[tuple[str, str]]:
        normalized = self.normalize_ws(query)
        if not normalized:
            return []

        tokens = [token for token in re.split(r"\s+", normalized) if token]
        model_token = self._detect_model_token(tokens)
        brand_token = tokens[0] if tokens else ""
        keyword_tokens = [token for token in tokens if token.lower() != model_token.lower()] if model_token else tokens
        keyword_phrase = " ".join(keyword_tokens[:4]).strip()

        candidates: list[tuple[str, str]] = []
        if model_token:
            candidates.append(("model_number", model_token))
        if brand_token and model_token:
            candidates.append(("brand_model", f"{brand_token} {model_token}"))
        if brand_token and keyword_phrase:
            candidates.append(("brand_keywords", f"{brand_token} {keyword_phrase}"))
        candidates.append(("fallback", normalized))

        seen: set[str] = set()
        ordered: list[tuple[str, str]] = []
        for strategy_name, text in candidates:
            cleaned = self.normalize_ws(text)
            key = cleaned.lower()
            if not cleaned or key in seen:
                continue
            seen.add(key)
            ordered.append((strategy_name, cleaned))
        return ordered

    @staticmethod
    def _detect_model_token(tokens: list[str]) -> str | None:
        for token in tokens:
            compact = token.strip()
            if not compact:
                continue
            if re.search(r"[0-9]", compact) and len(compact) >= 3:
                return compact
        return None

    def should_stop_after_variant(self, strategy_name: str, results: list[NormalizedResult]) -> bool:
        return strategy_name == "model_number" and len(results) >= 3

    def _annotate_results_for_strategy(
        self, strategy_name: str, query: str, results: list[NormalizedResult]
    ) -> list[NormalizedResult]:
        strategy_score_boost = {
            "model_number": 8,
            "brand_model": 5,
            "brand_keywords": 3,
            "fallback": 0,
        }.get(strategy_name, 0)

        enriched: list[NormalizedResult] = []
        for result in results:
            why = (result.why or "").strip()
            strategy_why = f"Strategy {strategy_name} query '{query}'."
            enriched.append(
                result.model_copy(
                    update={
                        "score": min(100, result.score + strategy_score_boost),
                        "why": f"{strategy_why} {why}".strip(),
                    }
                )
            )
        return enriched

    def _extract_results(self, query: str, payload: Any) -> list[NormalizedResult]:
        raw_results = self.extract_results(query, payload)
        limited = raw_results[: self.max_results]
        return self.dedupe_results(limited)

    @abstractmethod
    def build_request(self, query: str) -> dict[str, Any]:
        """Return request config (url/params/headers/etc.) for the query."""

    @abstractmethod
    def download_payload(self, request: dict[str, Any]) -> Any:
        """Fetch and return decoded JSON payload."""

    @abstractmethod
    def extract_results(self, query: str, payload: Any) -> list[NormalizedResult]:
        """Convert payload rows to normalized results."""

    @staticmethod
    def _loggable_request(request: dict[str, Any]) -> dict[str, Any]:
        clone = dict(request)
        headers = dict(clone.get("headers") or {})
        if "Authorization" in headers:
            headers["Authorization"] = "***"
        if headers:
            clone["headers"] = headers
        return clone

    @staticmethod
    def normalize_ws(value: str | None) -> str:
        if not value:
            return ""
        return re.sub(r"\s+", " ", value).strip()

    @classmethod
    def coerce_price(cls, value: Any) -> float | None:
        if value is None or value == "":
            return None

        if isinstance(value, (int, float)):
            return float(value)

        if isinstance(value, str):
            cleaned = value.strip().replace(",", "")
            if not cleaned:
                return None
            try:
                return float(cleaned)
            except ValueError:
                return cls.parse_price(cleaned)

        return None

    @staticmethod
    def parse_price(price_text: str | None) -> float | None:
        if not price_text:
            return None

        cleaned = str(price_text).strip().replace(",", "")
        if not cleaned:
            return None

        try:
            return float(cleaned)
        except ValueError:
            pass

        match = re.search(r"([0-9]+(?:\.[0-9]{1,2})?)", cleaned)
        if not match:
            return None

        try:
            return float(match.group(1))
        except ValueError:
            return None

    @classmethod
    def normalize_url(cls, base_url: str, maybe_relative_url: str | None) -> str | None:
        cleaned = cls.normalize_ws(maybe_relative_url)
        if not cleaned:
            return None
        return urljoin(base_url.rstrip("/") + "/", cleaned)

    @staticmethod
    def default_brand_from_title(title: str) -> str | None:
        parts = title.split()
        return parts[0] if parts else None

    @classmethod
    def dedupe_results(cls, results: list[NormalizedResult]) -> list[NormalizedResult]:
        deduped: list[NormalizedResult] = []
        seen_urls: set[str] = set()
        seen_titles: set[str] = set()

        for result in results:
            url_key = cls.normalize_ws(result.product_url or "")
            title_key = cls.normalize_ws(result.title).lower()

            if url_key and url_key in seen_urls:
                continue
            if title_key and title_key in seen_titles:
                continue

            if url_key:
                seen_urls.add(url_key)
            if title_key:
                seen_titles.add(title_key)

            deduped.append(result)

        return deduped

    @staticmethod
    def _count_partial_price_results(results: list[NormalizedResult]) -> int:
        count = 0
        for result in results:
            if result.price_value is not None:
                continue
            price_text = (result.price_text or "").strip().lower()
            if not price_text or price_text == "price unavailable":
                continue
            count += 1
        return count
