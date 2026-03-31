from __future__ import annotations

import re
from urllib.parse import quote_plus, urljoin

from app.connectors.playwright_connector import PlaywrightConnector
from app.models.normalized_result import NormalizedResult


class AmazonCAConnector(PlaywrightConnector):
    source = "amazon_ca"
    source_label = "Amazon.ca"
    source_type = "retail"
    search_url_template = "https://www.amazon.ca/s?k={query}"
    selectors = {
        # Keep selectors centralized in this connector.
        # Assumption: Amazon search cards continue exposing the `s-search-result` data-component-type.
        "cards": [
            'div[data-component-type="s-search-result"]',
            'div.s-result-item[data-asin]',
        ],
        "title": [
            "h2 a span",
            "h2 span[aria-label]",
            "h2",
        ],
        "title_link": [
            "h2 a",
            "a.a-link-normal[href*='/dp/']",
        ],
        "price_whole": [
            "span.a-price > span.a-offscreen",
            "span.a-price-whole",
        ],
        "price_fraction": [
            "span.a-price-fraction",
        ],
        "availability": [
            'span.a-color-price',
            'span.a-color-base',
            "text=/in stock|out of stock|usually ships/i",
        ],
        "image": [
            "img.s-image",
            "img[alt][src]",
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
                await locator.first.wait_for(state="visible", timeout=7000)
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

            link_node = card.locator(self._selector_union("title_link")).first
            href = await link_node.get_attribute("href") if await link_node.count() else None
            product_url = self._absolute_url(href)

            price_text = await self._extract_price_text(card)
            normalized_price, price_value = self.parse_price(price_text)
            default_price_text = "Price unavailable from source listing"
            normalized_price = normalized_price or default_price_text

            image_node = card.locator(self._selector_union("image")).first
            image_src = await image_node.get_attribute("src") if await image_node.count() else None
            image_url = self._absolute_url(image_src)

            availability_node = card.locator(self._selector_union("availability")).first
            availability = self._clean(await availability_node.inner_text()) if await availability_node.count() else None

            asin = await card.get_attribute("data-asin")
            sku = asin.strip() if asin and asin.strip() else self._extract_asin(product_url)

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
                confidence="Medium" if price_value is not None else "Low",
                why=(
                    "Matched on Amazon.ca search card title + visible price."
                    if price_value is not None
                    else "Matched on Amazon.ca search card title, but no visible price was found."
                ),
            )
        except Exception:
            # One malformed card should not fail the connector.
            return None

    async def _extract_price_text(self, card) -> str | None:
        offscreen_locator = card.locator(self._selector_union("price_whole")).first
        if await offscreen_locator.count():
            text = self._clean(await offscreen_locator.inner_text())
            if text:
                return text

        whole_locator = card.locator("span.a-price-whole").first
        fraction_locator = card.locator(self._selector_union("price_fraction")).first

        if await whole_locator.count():
            whole = self._clean(await whole_locator.inner_text()) or ""
            whole = whole.replace(".", "").replace(",", "")
            fraction = self._clean(await fraction_locator.inner_text()) if await fraction_locator.count() else None
            if fraction and re.fullmatch(r"\d{2}", fraction):
                return f"${whole}.{fraction}"
            if whole:
                return f"${whole}"

        return None

    @staticmethod
    def _selector_union(name: str) -> str:
        return ", ".join(AmazonCAConnector.selectors[name])

    @staticmethod
    def _clean(value: str | None) -> str | None:
        if value is None:
            return None
        compact = " ".join(value.split())
        return compact if compact else None

    @staticmethod
    def _extract_brand(title: str) -> str | None:
        # Fragile assumption: first token in Amazon catalog titles often maps to brand.
        first = title.split(" ", 1)[0].strip("-_/ ")
        if not first:
            return None
        return first.title()

    @staticmethod
    def _absolute_url(value: str | None) -> str | None:
        if not value:
            return None
        return urljoin("https://www.amazon.ca", value)

    @staticmethod
    def _extract_asin(value: str | None) -> str | None:
        if not value:
            return None
        match = re.search(r"/dp/([A-Z0-9]{10})", value)
        return match.group(1) if match else None
