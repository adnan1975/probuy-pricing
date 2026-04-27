from __future__ import annotations

import asyncio
import logging
import re
from abc import ABC, abstractmethod
from urllib.parse import quote_plus

import requests
from scrapy import Selector

from app.connectors.base import BaseConnector
from app.connectors.http_client import get_shared_http_client
from app.models.normalized_result import NormalizedResult


class SecondaryScrapyConnector(BaseConnector, ABC):
    """Base connector for selector-based secondary sources."""

    source_type = "retail"
    currency = "CAD"
    timeout_seconds = 10
    max_results = 10

    user_agent = (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )

    def __init__(self) -> None:
        self.last_warning: str | None = None
        self.logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")

    @property
    @abstractmethod
    def search_url_template(self) -> str:
        ...

    @property
    def search_url(self) -> str:
        return self.search_url_template

    async def search(self, query: str) -> list[NormalizedResult]:
        normalized_query = self.normalize_ws(query)
        if not normalized_query:
            self.last_warning = "Empty query supplied."
            self.logger.warning("%s search skipped because query is empty", self.__class__.__name__)
            return []

        self.last_warning = None
        url = self.build_search_url(self.search_url_template, normalized_query)

        self.logger.info(
            "%s search started query=%s url=%s",
            self.__class__.__name__,
            normalized_query,
            url,
        )

        try:
            html = await asyncio.to_thread(self.download_html, url)
            self.logger.debug(
                "%s downloaded html query=%s html_length=%s",
                self.__class__.__name__,
                normalized_query,
                len(html),
            )

            results = self._extract_results(normalized_query, html)
            results, dropped_low_match = self.apply_query_match_filter(normalized_query, results)

            if results:
                partial_count = self._count_partial_price_results(results)
                warning_parts: list[str] = []
                if partial_count > 0:
                    warning_parts.append(f"Partial parse: {partial_count} result(s) had no numeric price value.")
                if dropped_low_match > 0:
                    warning_parts.append(
                        f"Filtered {dropped_low_match} result(s) below {self.minimum_match_percent}% query match."
                    )
                if warning_parts:
                    self.last_warning = " ".join(warning_parts)
                self.persist_results(normalized_query, results)
                self.logger.info(
                    "%s search completed query=%s results=%s",
                    self.__class__.__name__,
                    normalized_query,
                    len(results),
                )
            else:
                if dropped_low_match > 0:
                    self.last_warning = (
                        "No listings met connector-level match threshold "
                        f"({self.minimum_match_percent}%+ required)."
                    )
                else:
                    self.last_warning = "No visible listings were parsed from search page."
                self.logger.warning(
                    "%s search completed with no results query=%s url=%s",
                    self.__class__.__name__,
                    normalized_query,
                    url,
                )

            return results

        except requests.RequestException as exc:
            self.last_warning = f"Network error while fetching source page: {exc}"
            self.logger.exception(
                "%s network error query=%s url=%s error=%s",
                self.__class__.__name__,
                normalized_query,
                url,
                exc,
            )
            return []

        except Exception as exc:  # noqa: BLE001
            self.last_warning = f"Unexpected parse error: {exc}"
            self.logger.exception(
                "%s unexpected error query=%s url=%s error=%s",
                self.__class__.__name__,
                normalized_query,
                url,
                exc,
            )
            return []

    def build_search_url(self, template: str, query: str) -> str:
        return template.format(query=quote_plus(query.strip()))

    def download_html(self, url: str) -> str:
        self.logger.debug("Downloading HTML from url=%s", url)
        html = get_shared_http_client().get_text(
            url,
            headers={"User-Agent": self.user_agent},
            timeout=self.timeout_seconds,
        )
        self.logger.debug("Downloaded HTML successfully url=%s", url)
        return html

    def _extract_results(self, query: str, html: str) -> list[NormalizedResult]:
        selector = Selector(text=html)
        rows = selector.css(self.listing_selector())[: self.max_results]

        self.logger.debug(
            "%s extract_results query=%s listing_selector=%s row_count=%s",
            self.__class__.__name__,
            query,
            self.listing_selector(),
            len(rows),
        )

        results: list[NormalizedResult] = []
        seen_urls: set[str] = set()
        seen_titles: set[str] = set()

        for idx, row in enumerate(rows, start=1):
            title_parts = row.css(self.title_selector()).getall()
            price_parts = row.css(self.price_selector()).getall()
            url_parts = row.css(self.url_selector()).getall()
            image_parts = row.css(self.image_selector()).getall() if self.image_selector() else []
            sku_parts = row.css(self.sku_selector()).getall() if self.sku_selector() else []

            title = self.join_text_parts(title_parts)
            price_text = self.join_text_parts(price_parts)
            raw_url = self.first_non_empty(url_parts)
            raw_image = self.first_non_empty(image_parts)
            raw_sku = self.first_non_empty(sku_parts)

            product_url = self.make_absolute_url(self.base_url(), raw_url)
            image_url = self.make_absolute_url(self.base_url(), raw_image)
            sku = self.normalize_ws(raw_sku)
            price_value = self.parse_price(price_text)

            self.logger.debug(
                "%s row idx=%s title_parts=%r price_parts=%r url_parts=%r sku_parts=%r",
                self.__class__.__name__,
                idx,
                title_parts,
                price_parts,
                url_parts,
                sku_parts,
            )
            self.logger.debug(
                "%s row idx=%s title=%r price_text=%r parsed_price=%r product_url=%r image_url=%r sku=%r",
                self.__class__.__name__,
                idx,
                title,
                price_text,
                price_value,
                product_url,
                image_url,
                sku,
            )

            if not title:
                self.logger.debug("%s row idx=%s skipped because title missing", self.__class__.__name__, idx)
                continue

            if not product_url:
                self.logger.debug(
                    "%s row idx=%s skipped because product_url missing title=%r",
                    self.__class__.__name__,
                    idx,
                    title,
                )
                continue

            if product_url in seen_urls:
                self.logger.debug(
                    "%s row idx=%s skipped duplicate url=%s",
                    self.__class__.__name__,
                    idx,
                    product_url,
                )
                continue

            normalized_title_key = title.lower()
            if normalized_title_key in seen_titles:
                self.logger.debug(
                    "%s row idx=%s skipped duplicate title=%r",
                    self.__class__.__name__,
                    idx,
                    title,
                )
                continue

            seen_urls.add(product_url)
            seen_titles.add(normalized_title_key)

            if price_text and price_value is None:
                self.logger.warning(
                    "%s price parse failed idx=%s title=%r raw_price_text=%r",
                    self.__class__.__name__,
                    idx,
                    title,
                    price_text,
                )

            results.append(
                NormalizedResult(
                    source=self.source_label,
                    source_type=self.source_type,
                    title=title,
                    price_text=price_text or "Price unavailable",
                    price_value=price_value,
                    currency=self.currency,
                    sku=sku or None,
                    brand=self.default_brand_from_title(title),
                    availability="See product page",
                    product_url=product_url,
                    image_url=image_url,
                    confidence="Medium" if price_value is not None else "Low",
                    score=70 if price_value is not None else 55,
                    why="Parsed from secondary connector search page using selector-based scraping.",
                )
            )

        self.logger.debug(
            "%s extraction finished query=%s normalized_results=%s",
            self.__class__.__name__,
            query,
            len(results),
        )
        return results

    @staticmethod
    def normalize_ws(value: str | None) -> str:
        if not value:
            return ""
        return re.sub(r"\s+", " ", value).strip()

    @classmethod
    def join_text_parts(cls, values: list[str] | tuple[str, ...]) -> str:
        cleaned = [cls.normalize_ws(v) for v in values if cls.normalize_ws(v)]
        return cls.normalize_ws(" ".join(cleaned))

    @classmethod
    def first_non_empty(cls, values: list[str] | tuple[str, ...]) -> str | None:
        for value in values:
            cleaned = cls.normalize_ws(value)
            if cleaned:
                return cleaned
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

    @staticmethod
    def default_brand_from_title(title: str) -> str | None:
        parts = title.split()
        return parts[0] if parts else None

    @staticmethod
    def make_absolute_url(base_url: str, maybe_relative_url: str | None) -> str | None:
        if not maybe_relative_url:
            return None
        if maybe_relative_url.startswith(("http://", "https://")):
            return maybe_relative_url
        if maybe_relative_url.startswith("/"):
            return f"{base_url.rstrip('/')}{maybe_relative_url}"
        return f"{base_url.rstrip('/')}/{maybe_relative_url.lstrip('/')}"

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

    @abstractmethod
    def base_url(self) -> str:
        ...

    @abstractmethod
    def listing_selector(self) -> str:
        ...

    @abstractmethod
    def title_selector(self) -> str:
        ...

    @abstractmethod
    def price_selector(self) -> str:
        ...

    @abstractmethod
    def url_selector(self) -> str:
        ...

    def sku_selector(self) -> str | None:
        return None

    def image_selector(self) -> str | None:
        return None
