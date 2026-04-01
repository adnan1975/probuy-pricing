from __future__ import annotations

import asyncio
import logging
import re
from urllib.parse import quote_plus, urljoin

from app.connectors.playwright_connector import (
    PlaywrightConnector,
    PlaywrightError,
    PlaywrightTimeoutError,
)
from app.connectors.playwright_lifecycle import playwright_lifecycle
from app.models.normalized_result import NormalizedResult

logger = logging.getLogger(__name__)


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
        normalized_query = query.strip()
        logger.debug(
            "kms_search_started",
            extra={
                "source": self.source,
                "query": normalized_query,
                "playwright_available": playwright_lifecycle.available,
            },
        )

        if not normalized_query:
            logger.info(
                "kms_search_skipped_empty_query",
                extra={"source": self.source, "query": query},
            )
            return []

        if not playwright_lifecycle.available:
            logger.info(
                "kms_search_skipped_playwright_unavailable",
                extra={
                    "source": self.source,
                    "query": normalized_query,
                    "reason": "playwright_unavailable",
                },
            )
            return []

        for _ in range(self.retries):
            try:
                browser = await playwright_lifecycle.get_browser()
                context = await browser.new_context()
                page = await context.new_page()
                try:
                    await self.open_search_page(page, normalized_query)
                    logger.debug(
                        "kms_search_page_opened",
                        extra={"source": self.source, "query": normalized_query, "page_url": page.url},
                    )

                    cards = await self.extract_result_cards(page)
                    logger.debug(
                        "kms_result_cards_extracted",
                        extra={"source": self.source, "query": normalized_query, "card_count": len(cards)},
                    )

                    results: list[NormalizedResult] = []
                    for card in cards[: self.max_results]:
                        normalized = await self.normalize_result(page, card)
                        if normalized:
                            results.append(normalized)
                            logger.debug(
                                "kms_result_candidate_parsed",
                                extra={
                                    "source": self.source,
                                    "query": normalized_query,
                                    "title": normalized.title,
                                    "sku": normalized.sku,
                                    "price_value": normalized.price_value,
                                },
                            )

                    if not results:
                        pdp_result = await self.normalize_product_page(page)
                        if pdp_result is not None:
                            results.append(pdp_result)
                            logger.debug(
                                "kms_result_candidate_from_pdp",
                                extra={
                                    "source": self.source,
                                    "query": normalized_query,
                                    "title": pdp_result.title,
                                    "sku": pdp_result.sku,
                                    "price_value": pdp_result.price_value,
                                },
                            )

                    priced_results = [result for result in results if result.price_value is not None]
                    if not priced_results:
                        logger.info(
                            "kms_search_no_priced_results_for_query",
                            extra={
                                "source": self.source,
                                "query": normalized_query,
                                "result_count": len(results),
                            },
                        )
                        return []

                    logger.info(
                        "kms_search_completed",
                        extra={
                            "source": self.source,
                            "query": normalized_query,
                            "result_count": len(priced_results),
                        },
                    )
                    self.persist_results(normalized_query, priced_results)
                    return priced_results
                finally:
                    await page.close()
                    await context.close()
            except (PlaywrightError, PlaywrightTimeoutError, TimeoutError, OSError) as exc:
                logger.info(
                    "kms_search_retrying_after_error",
                    extra={"source": self.source, "query": normalized_query, "error": str(exc)},
                )
                await asyncio.sleep(0.4)

        logger.info(
            "kms_search_exhausted_retries_no_results",
            extra={"source": self.source, "query": normalized_query},
        )
        return []

    async def open_search_page(self, page, query: str) -> None:
        target = self.search_url_template.format(query=quote_plus(query))
        await page.goto(target, wait_until="domcontentloaded", timeout=self.timeout_ms)

    async def extract_result_cards(self, page):
        last_error: Exception | None = None

        for selector in self.selectors["cards"]:
            locator = page.locator(selector)
            try:
                count = await locator.count()
                logger.debug(
                    "kms_selector_count",
                    extra={"source": self.source, "selector": selector, "count": count},
                )

                if count:
                    await locator.first.wait_for(state="visible", timeout=6000)
                    return [locator.nth(i) for i in range(count)]
            except Exception as exc:
                last_error = exc
                logger.debug(
                    "kms_selector_failed",
                    extra={"source": self.source, "selector": selector, "error": str(exc)},
                )
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
            logger.debug(
                "kms_normalize_result_failed",
                extra={"source": self.source, "error": str(exc)},
            )
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
            logger.debug(
                "kms_normalize_product_page_failed",
                extra={"source": self.source, "error": str(exc)},
            )
            return None

    def fallback_results(self, query: str) -> list[NormalizedResult]:
        return []

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
