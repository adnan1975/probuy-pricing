from __future__ import annotations

import re
from urllib.parse import quote_plus, urljoin

from app.connectors.mock_catalog import build_mock_result
from app.connectors.playwright_connector import PlaywrightConnector
from app.models.normalized_result import NormalizedResult


class KMSConnector(PlaywrightConnector):
    source = "kms_tools"
    source_label = "KMS Tools"
    source_type = "retail"
    search_url_template = "https://www.kmstools.com/catalogsearch/result/?q={query}"
    selectors = {
        # Keep KMS selectors centralized in case their Magento theme changes.
        # TODO: Re-verify these selectors against live HTML periodically.
        "cards": [
            "li.product-item",
            ".products.list.items.product-items li.item.product",
            ".product-item-info",
        ],
        # Prefer user-facing anchors and titles over brittle nested selectors.
        "title": [
            "a.product-item-link",
            "a[title][href*='.html']",
            "a[href*='/product/']",
        ],
        "price": [
            "span.price",
            "[data-price-type='finalPrice'] .price",
            "[data-price-amount]",
            r"text=/\$\s*[0-9]/",
        ],
        "sku": [
            ".product-item-sku",
            "[data-role='sku']",
            "text=/\bSKU\b|model\b/i",
        ],
        "image": [
            "img.product-image-photo",
            "img[alt][src]",
        ],
        "availability": [
            ".stock.available",
            ".stock.unavailable",
            "text=/in stock|out of stock|backorder/i",
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

            sku_node = card.locator(self._selector_union("sku")).first
            raw_sku = self._clean(await sku_node.inner_text()) if await sku_node.count() else None
            sku = self._extract_sku(raw_sku)

            image_node = card.locator(self._selector_union("image")).first
            image_src = await image_node.get_attribute("src") if await image_node.count() else None
            image_url = self._absolute_url(image_src)

            availability_node = card.locator(self._selector_union("availability")).first
            availability = self._clean(await availability_node.inner_text()) if await availability_node.count() else None

            confidence = "Medium" if price_value is not None else "Low"
            why = "Matched on KMS Tools search card title + visible price."
            if price_value is None:
                # TODO: KMS occasionally renders price in script/config payloads; add parser if needed.
                why = "Matched on KMS Tools search card title; price not reliably visible on this card."

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
                confidence=confidence,
                score=78 if price_value is not None else 60,
                why=why,
            )
        except Exception:
            # One malformed card should never fail the whole connector.
            return None

    def fallback_results(self, query: str) -> list[NormalizedResult]:
        # Guarded fallback while live KMS HTML can vary by anti-bot and theme changes.
        return build_mock_result(query, self.source, self.source_label)

    @staticmethod
    def _selector_union(name: str) -> str:
        return ", ".join(KMSConnector.selectors[name])

    @staticmethod
    def _clean(value: str | None) -> str | None:
        if value is None:
            return None
        compact = " ".join(value.split())
        return compact if compact else None

    @staticmethod
    def _extract_sku(raw: str | None) -> str | None:
        if not raw:
            return None
        match = re.search(r"(?:sku|model)\s*[:#]?\s*([A-Z0-9-]{4,})", raw, re.IGNORECASE)
        if match:
            return match.group(1)
        fallback = re.search(r"\b([A-Z0-9-]{5,})\b", raw)
        return fallback.group(1) if fallback else None

    @staticmethod
    def _extract_brand(title: str) -> str | None:
        # Fragile assumption: first token is usually the display brand on listing cards.
        first = title.split(" ", 1)[0].strip("-_/ ")
        if not first:
            return None
        return first.title()

    @staticmethod
    def _absolute_url(value: str | None) -> str | None:
        if not value:
            return None
        return urljoin("https://www.kmstools.com", value)
