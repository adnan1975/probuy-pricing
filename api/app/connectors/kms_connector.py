from __future__ import annotations

import asyncio
import re
from urllib.parse import quote_plus, urljoin

from app.connectors.mock_catalog import build_mock_result
from app.connectors.playwright_connector import (
    PlaywrightConnector,
    PlaywrightTimeoutError,
    async_playwright,
)
from app.models.normalized_result import NormalizedResult


class KMSConnector(PlaywrightConnector):
    source = "kms_tools"
    source_label = "KMS Tools"
    source_type = "retail"
    search_url_template = "https://www.kmstools.com/catalogsearch/result/?q={query}"

    selectors = {
        # Search result cards
        "cards": [
            "#product-list div.product-item.card",
            ".products.wrapper .product-item.card",
            "ul[role='list'] > li > div.product-item",
        ],

        # Listing card fields
        "title": [
            "a.product-item-link",
            "a.product.photo.product-item-photo",
        ],
        "price": [
            ".price-box .price",
            "[data-price-type='finalPrice'] .price",
            "span.price",
        ],
        "sku": [
            ".text-xs.text-slate-500",
            ".text-xs",
        ],
        "image": [
            "img.product-image-photo",
            "img[alt][src]",
        ],
        "availability": [
            "div[title='Availability'] span",
            "div[title='Availability']",
        ],

        # PDP fallback
        "pdp_title": [
            "h1.page-title .base",
            "h1.page-title span",
            "h1.page-title",
            "h1",
        ],
        "pdp_price": [
            ".price-box .price",
            "[data-price-type='finalPrice'] .price",
            "span.price",
        ],
        "pdp_sku": [
            ".product.attribute.sku .value",
            "[data-th='SKU']",
            #"text=/\\bSKU\\b|model\\b/i",
        ],
        "pdp_image": [
            "img.fotorama__img",
            "img.gallery-placeholder__image",
            "img[alt][src]",
        ],
        "pdp_availability": [
            ".stock.available",
            ".stock.unavailable",
            #"text=/in stock|out of stock|backorder/i",
        ],
    }

    async def search(self, query: str) -> list[NormalizedResult]:
        print(f"KMSConnector searching for: {query}")
        print(f"KMSConnector async_playwright available: {async_playwright is not None}")
        print(f"KMSConnector search URL template: {self.search_url_template}")

        if not query.strip() or async_playwright is None:
            print("KMSConnector missing query or Playwright; returning fallback results.")
            fallback = self.fallback_results(query)
            self.persist_results(query, fallback)
            return fallback

        print("KMSConnector initializing Playwright search...")

        for _ in range(self.retries):
            try:
                async with async_playwright() as playwright:
                    browser = await playwright.chromium.launch(headless=True)
                    try:
                        page = await browser.new_page()
                        await self.open_search_page(page, query)

                        print(f"KMSConnector opened search page for: {query}")
                        print(f"KMSConnector page URL after load: {page.url}")
                        print(f"KMSConnector page content length: {len(await page.content())}")
                        print(f"KMSConnector looking for result cards with selectors: {self.selectors['cards']}")

                        cards = await self.extract_result_cards(page)
                        print(f"KMSConnector found {len(cards)} result cards for: {query}")

                        results: list[NormalizedResult] = []
                        for card in cards[: self.max_results]:
                            normalized = await self.normalize_result(page, card)
                            if normalized:
                                results.append(normalized)

                        if not results:
                            pdp_result = await self.normalize_product_page(page)
                            if pdp_result is not None:
                                results.append(pdp_result)

                        print(f"KMSConnector extracted {len(results)} normalized results for: {query}")
                        self.persist_results(query, results)
                        return results
                    finally:
                        await browser.close()
            except (PlaywrightTimeoutError, TimeoutError, OSError) as exc:
                print(f"KMSConnector retrying after error: {exc}")
                await asyncio.sleep(0.4)

        fallback = self.fallback_results(query)
        self.persist_results(query, fallback)
        return fallback

    async def open_search_page(self, page, query: str) -> None:
        target = self.search_url_template.format(query=quote_plus(query))
        await page.goto(target, wait_until="domcontentloaded", timeout=self.timeout_ms)

    async def extract_result_cards(self, page):
        last_error: Exception | None = None

        for selector in self.selectors["cards"]:
            locator = page.locator(selector)
            try:
                count = await locator.count()
                print(f"KMS selector '{selector}' count={count}")

                if count:
                    await locator.first.wait_for(state="visible", timeout=6000)
                    return [locator.nth(i) for i in range(count)]
            except Exception as exc:
                last_error = exc
                print(f"KMS selector failed '{selector}': {exc}")
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
        except Exception as exc:
            print(f"KMSConnector normalize_result failed: {exc}")
            return None

    async def normalize_product_page(self, page) -> NormalizedResult | None:
        try:
            title_node = page.locator(self._selector_union("pdp_title")).first
            if not await title_node.count():
                return None

            title = self._clean(await title_node.inner_text())
            if not title:
                return None

            price_node = page.locator(self._selector_union("pdp_price")).first
            price_text = self._clean(await price_node.inner_text()) if await price_node.count() else None
            normalized_price, price_value = self.parse_price(price_text)

            sku_node = page.locator(self._selector_union("pdp_sku")).first
            raw_sku = self._clean(await sku_node.inner_text()) if await sku_node.count() else None
            sku = self._extract_sku(raw_sku)

            image_node = page.locator(self._selector_union("pdp_image")).first
            image_src = await image_node.get_attribute("src") if await image_node.count() else None
            image_url = self._absolute_url(image_src)

            availability_node = page.locator(self._selector_union("pdp_availability")).first
            availability = self._clean(await availability_node.inner_text()) if await availability_node.count() else None

            confidence = "Medium" if price_value is not None else "Low"
            why = (
                "Matched on KMS Tools product page fallback (exact/single result redirect)."
                if price_value is not None
                else "Matched on KMS Tools product page fallback, but no visible price was found."
            )

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
                product_url=page.url,
                image_url=image_url,
                confidence=confidence,
                score=76 if price_value is not None else 58,
                why=why,
            )
        except Exception as exc:
            print(f"KMSConnector normalize_product_page failed: {exc}")
            return None

    def fallback_results(self, query: str) -> list[NormalizedResult]:
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
        first = title.split(" ", 1)[0].strip("-_/ ")
        if not first:
            return None
        return first.title()

    @staticmethod
    def _absolute_url(value: str | None) -> str | None:
        if not value:
            return None
        return urljoin("https://www.kmstools.com", value)