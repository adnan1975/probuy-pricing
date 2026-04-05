from __future__ import annotations

import asyncio
import re
from abc import ABC, abstractmethod
from urllib.parse import quote_plus

import requests
from scrapy import Selector

from app.connectors.base import BaseConnector
from app.models.normalized_result import NormalizedResult


class SecondaryScrapyConnector(BaseConnector, ABC):
    """Base connector for secondary sources parsed with Scrapy Selector APIs."""

    source_type = "retail"
    currency = "CAD"
    timeout_seconds = 10
    user_agent = (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )

    def __init__(self) -> None:
        self.last_warning: str | None = None

    @property
    @abstractmethod
    def search_url_template(self) -> str:
        ...

    @property
    def search_url(self) -> str:
        return self.search_url_template

    async def search(self, query: str) -> list[NormalizedResult]:
        normalized_query = query.strip()
        if not normalized_query:
            self.last_warning = "Empty query supplied."
            return []

        self.last_warning = None
        try:
            html = await asyncio.to_thread(self._download_html, normalized_query)
            results = self._extract_results(normalized_query, html)
            if not results:
                self.last_warning = "No visible priced listings were parsed from search page."
            else:
                self.persist_results(normalized_query, results)
            return results
        except requests.RequestException as exc:
            self.last_warning = f"Network error while fetching source page: {exc}"
            return []
        except Exception as exc:  # noqa: BLE001
            self.last_warning = f"Unexpected parse error: {exc}"
            return []

    def _download_html(self, query: str) -> str:
        url = self.search_url.format(query=quote_plus(query))
        response = requests.get(
            url,
            headers={"User-Agent": self.user_agent, "Accept-Language": "en-CA,en-US;q=0.9,en;q=0.8"},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return response.text

    def _extract_results(self, query: str, html: str) -> list[NormalizedResult]:
        selector = Selector(text=html)
        rows = selector.css(self.listing_selector())[:5]
        results: list[NormalizedResult] = []

        for row in rows:
            title = row.css(self.title_selector()).get()
            if not title:
                continue
            price_text = row.css(self.price_selector()).get()
            price_value = self._parse_price(price_text)
            product_url = row.css(self.url_selector()).get()
            if product_url and product_url.startswith("/"):
                product_url = f"{self.base_url().rstrip('/')}{product_url}"

            results.append(
                NormalizedResult(
                    source=self.source_label,
                    source_type=self.source_type,
                    title=self._normalize_ws(title),
                    price_text=self._normalize_ws(price_text) if price_text else "Price unavailable",
                    price_value=price_value,
                    currency=self.currency,
                    sku=self._normalize_ws(row.css(self.sku_selector()).get()) if self.sku_selector() else None,
                    brand=self.default_brand_from_title(title),
                    availability="See product page",
                    product_url=product_url,
                    image_url=row.css(self.image_selector()).get() if self.image_selector() else None,
                    confidence="Medium" if price_value is not None else "Low",
                    score=70 if price_value is not None else 55,
                    why="Parsed from secondary connector search page using Scrapy Selector.",
                )
            )

        return results

    @staticmethod
    def _normalize_ws(value: str | None) -> str:
        if not value:
            return ""
        return re.sub(r"\s+", " ", value).strip()

    @staticmethod
    def _parse_price(price_text: str | None) -> float | None:
        if not price_text:
            return None
        match = re.search(r"\$\s*([0-9][0-9,]*(?:\.[0-9]{2})?)", price_text)
        if not match:
            return None
        try:
            return float(match.group(1).replace(",", ""))
        except ValueError:
            return None

    @staticmethod
    def default_brand_from_title(title: str) -> str | None:
        parts = title.split()
        return parts[0] if parts else None

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
