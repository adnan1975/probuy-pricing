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
        request = self.build_request(normalized_query)

        self.logger.info(
            "%s api search started query=%s request=%s",
            self.__class__.__name__,
            normalized_query,
            self._loggable_request(request),
        )

        try:
            payload = await asyncio.to_thread(self.download_payload, request)
            results = self._extract_results(normalized_query, payload)

            if results:
                self.persist_results(normalized_query, results)
                self.logger.info(
                    "%s api search completed query=%s results=%s",
                    self.__class__.__name__,
                    normalized_query,
                    len(results),
                )
            else:
                self.last_warning = "No API results were parsed from response payload."
                self.logger.warning(
                    "%s api search completed with no results query=%s",
                    self.__class__.__name__,
                    normalized_query,
                )

            return results

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
