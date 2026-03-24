from __future__ import annotations

import re
from urllib.parse import quote_plus, urljoin

from app.connectors.playwright_connector import PlaywrightConnector
from app.models.normalized_result import NormalizedResult


class CanadianTireConnector(PlaywrightConnector):
    source = "canadian_tire"
    source_label = "Canadian Tire"
    source_type = "retail"
    search_url_template = "https://www.canadiantire.ca/en/search-results.html?q={query}"
    selectors = {
        # Keep selectors centralized in this connector so DOM updates are isolated.
        # Assumption: product list cards remain represented with article semantics or test ids.
        "cards": [
            '[data-testid="product-card"]',
            'article[data-testid*="product"]',
            'article:has(a[href*="/en/pdp/"])',
        ],
        # Prefer user-facing anchors with title semantics before generic links.
        "title": [
            '[data-testid="product-name"] a',
            'a[data-testid="product-link"]',
            'a[title][href*="/en/pdp/"]',
            'a[href*="/en/pdp/"]',
        ],
        "price": [
            '[data-testid="product-price"]',
            '[data-testid="sale-price"]',
            '[aria-label*="price" i]',
            r'text=/\$\s*[0-9]/',
        ],
        "sku": [
            '[data-testid="product-part-number"]',
            '[aria-label*="part number" i]',
            r'text=/part\s*number|model\s*#/i',
        ],
        "image": [
            'img[data-testid="product-image"]',
            'img[alt][src]'
        ],
        "availability": [
            '[data-testid="stock-status"]',
            '[aria-label*="stock" i]',
            'text=/in stock|out of stock|available/i',
        ],
    }

    async def open_search_page(self, page, query: str) -> None:
        target = self.search_url_template.format(query=quote_plus(query))
        await page.goto(target, wait_until="domcontentloaded", timeout=self.timeout_ms)

    async def extract_result_cards(self, page):
        last_error: Exception | None = None
        for selector in self.selectors["cards"]:
            locator = page.locator(selector)
            try:
                await locator.first.wait_for(state="visible", timeout=6000)
                count = await locator.count()
                if count:
                    return [locator.nth(i) for i in range(count)]
            except Exception as exc:  # pragma: no cover - depends on live DOM
                last_error = exc
                continue

        if last_error is not None:
            raise last_error
        return []

    async def normalize_result(self, page, card) -> NormalizedResult | None:
        try:
            title_node = card.locator(self._selector_union("title")).first
            if not await title_node.count():
                return None

            title = self._clean(await title_node.inner_text())
            if not title:
                return None

            href = await title_node.get_attribute("href")
            product_url = self._absolute_url(href)

            price_node = card.locator(self._selector_union("price")).first
            price_text = self._clean(await price_node.inner_text()) if await price_node.count() else None
            normalized_price, price_value = self.parse_price(price_text)
            if price_value is None:
                return None

            sku_node = card.locator(self._selector_union("sku")).first
            raw_sku = self._clean(await sku_node.inner_text()) if await sku_node.count() else None
            sku = self._extract_sku(raw_sku)

            availability_node = card.locator(self._selector_union("availability")).first
            availability = self._clean(await availability_node.inner_text()) if await availability_node.count() else None

            image_node = card.locator(self._selector_union("image")).first
            image_src = await image_node.get_attribute("src") if await image_node.count() else None
            image_url = self._absolute_url(image_src)

            return NormalizedResult(
                source=self.source_label,
                source_type=self.source_type,
                title=title,
                price_text=normalized_price,
                price_value=price_value,
                currency="CAD",
                sku=sku,
                brand=self._extract_brand(title),
                availability=availability or "Unknown",
                product_url=product_url,
                image_url=image_url,
                confidence="Medium",
                why="Matched on Canadian Tire search card title + visible price.",
            )
        except Exception:
            # A single malformed card should never fail the connector.
            return None

    @staticmethod
    def _selector_union(name: str) -> str:
        return ", ".join(CanadianTireConnector.selectors[name])

    @staticmethod
    def _clean(value: str | None) -> str | None:
        if value is None:
            return None
        compact = " ".join(value.split())
        return compact if compact else None

    @staticmethod
    def _extract_brand(title: str) -> str | None:
        # Fragile assumption: first token usually maps to the product brand.
        first = title.split(" ", 1)[0].strip("-_/ ")
        if not first:
            return None
        return first.title()

    @staticmethod
    def _extract_sku(raw: str | None) -> str | None:
        if not raw:
            return None
        match = re.search(r"(?:part\s*number|model\s*#?)\s*[:#]?\s*([A-Z0-9-]{4,})", raw, re.IGNORECASE)
        if match:
            return match.group(1)
        fallback = re.search(r"\b([A-Z0-9-]{5,})\b", raw)
        return fallback.group(1) if fallback else None

    @staticmethod
    def _absolute_url(value: str | None) -> str | None:
        if not value:
            return None
        return urljoin("https://www.canadiantire.ca", value)
