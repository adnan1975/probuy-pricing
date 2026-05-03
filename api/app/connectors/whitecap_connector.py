from __future__ import annotations

import re
from urllib.parse import quote_plus, urljoin

from app.connectors.mock_catalog import build_mock_result
from app.connectors.playwright_connector import PlaywrightConnector
from app.models.normalized_result import NormalizedResult


class WhiteCapConnector(PlaywrightConnector):
    source = "white_cap"
    source_label = "White Cap"
    source_type = "distributor"
    search_url_template = "https://www.whitecap.com/search?query={query}"
    selectors = {
        # Keep selectors centralized so DOM updates stay isolated to this connector.
        # NOTE: White Cap frequently ships SPA/layout updates; fallbacks below are intentional.
        "cards": [
            '[data-testid="product-card"]',
            'article[data-product-id]',
            'li[data-product-id]',
            'article:has(a[href*="/p/"])',
            'li:has(a[href*="/p/"])',
        ],
        "title": [
            'a[data-testid="product-link"]',
            'a[title][href*="/p/"]',
            'a[href*="/p/"]',
        ],
        "price": [
            '[data-testid="product-price"]',
            '[aria-label*="price" i]',
            '.price',
            r'text=/\$\s*[0-9]/',
        ],
        "sku": [
            '[data-testid*="sku"]',
            '[aria-label*="sku" i]',
            r'text=/\bSKU\b|item\s*#/i',
        ],
        "availability": [
            '[data-testid*="stock"]',
            '[aria-label*="stock" i]',
            'text=/in stock|out of stock|available/i',
        ],
        "image": [
            'img[data-testid="product-image"]',
            'img[alt][src]',
        ],
    }

    async def open_search_page(self, page, query: str) -> None:
        target = self.search_url_template.format(query=quote_plus(query))
        self._logger.info(
            "White Cap: opening search page",
            extra={"source": self.source_label, "query": query, "url": target},
        )
        await page.goto(target, wait_until="domcontentloaded", timeout=self.timeout_ms)
        self._logger.info(
            "White Cap: search page loaded",
            extra={"source": self.source_label, "query": query, "url": target},
        )

    async def extract_result_cards(self, page):
        last_error: Exception | None = None
        for selector in self.selectors["cards"]:
            locator = page.locator(selector)
            try:
                self._logger.info(
                    "White Cap: trying card selector",
                    extra={"source": self.source_label, "selector": selector},
                )
                await locator.first.wait_for(state="visible", timeout=7000)
                count = await locator.count()
                self._logger.info(
                    "White Cap: selector matched cards",
                    extra={"source": self.source_label, "selector": selector, "count": count},
                )
                if count:
                    return [locator.nth(i) for i in range(count)]
            except Exception as exc:  # pragma: no cover - depends on live DOM
                self._logger.warning(
                    "White Cap: selector failed while extracting cards",
                    extra={"source": self.source_label, "selector": selector},
                    exc_info=True,
                )
                last_error = exc
                continue

        if last_error is not None:
            self._logger.error(
                "White Cap: all card selectors failed",
                extra={"source": self.source_label},
                exc_info=True,
            )
            raise last_error
        self._logger.warning(
            "White Cap: no cards found with available selectors",
            extra={"source": self.source_label},
        )
        return []

    async def normalize_result(self, page, card) -> NormalizedResult | None:
        try:
            title_node = card.locator(self._selector_union("title")).first
            if not await title_node.count():
                self._logger.info(
                    "White Cap: skipping card missing title node",
                    extra={"source": self.source_label},
                )
                return None

            title = self._clean(await title_node.inner_text())
            if not title:
                self._logger.info(
                    "White Cap: skipping card with empty title",
                    extra={"source": self.source_label},
                )
                return None

            href = await title_node.get_attribute("href")
            product_url = self._absolute_url(href)

            price_node = card.locator(self._selector_union("price")).first
            raw_price = self._clean(await price_node.inner_text()) if await price_node.count() else None
            price_text, price_value = self.parse_price(raw_price)
            default_price_text = "Price unavailable from source listing"
            price_text = price_text or default_price_text

            sku_node = card.locator(self._selector_union("sku")).first
            raw_sku = self._clean(await sku_node.inner_text()) if await sku_node.count() else None
            sku = self._extract_sku(raw_sku)

            availability_node = card.locator(self._selector_union("availability")).first
            availability = self._clean(await availability_node.inner_text()) if await availability_node.count() else None

            image_node = card.locator(self._selector_union("image")).first
            image_src = await image_node.get_attribute("src") if await image_node.count() else None
            image_url = self._absolute_url(image_src)

            self._logger.info(
                "White Cap: normalized card",
                extra={
                    "source": self.source_label,
                    "title": title,
                    "sku": sku,
                    "price_text": price_text,
                    "has_price": price_value is not None,
                    "product_url": product_url,
                },
            )
            return NormalizedResult(
                source=self.source_label,
                source_type=self.source_type,
                title=title,
                price_text=price_text,
                price_value=price_value,
                currency="CAD",
                sku=sku,
                brand=self._extract_brand(title),
                availability=availability or "Unknown",
                product_url=product_url,
                image_url=image_url,
                is_published=None,
                publication_channel=None,
                confidence="Medium" if price_value is not None else "Low",
                why=(
                    "Matched on White Cap search card title + visible price."
                    if price_value is not None
                    else "Matched on White Cap search card title, but no visible price was found."
                ),
            )
        except Exception:
            self._logger.warning(
                "White Cap: failed to normalize card",
                extra={"source": self.source_label},
                exc_info=True,
            )
            # Never let a malformed White Cap card break the connector.
            return None

    def fallback_results(self, query: str) -> list[NormalizedResult]:
        # Best-effort fallback: return curated mock benchmark rows for known demo queries.
        # TODO: Replace with production-safe fallback once White Cap anti-bot/geo behavior is profiled.
        fallback = build_mock_result(query, self.source, self.source_label)
        self._logger.warning(
            "White Cap: using fallback results",
            extra={"source": self.source_label, "query": query, "count": len(fallback)},
        )
        return fallback

    @staticmethod
    def _selector_union(name: str) -> str:
        return ", ".join(WhiteCapConnector.selectors[name])

    @staticmethod
    def _clean(value: str | None) -> str | None:
        if value is None:
            return None
        compact = " ".join(value.split())
        return compact if compact else None

    @staticmethod
    def _extract_brand(title: str) -> str | None:
        # Fragile assumption: first token is often the brand in White Cap listing titles.
        first = title.split(" ", 1)[0].strip("-_/ ")
        if not first:
            return None
        return first.title()

    @staticmethod
    def _extract_sku(raw: str | None) -> str | None:
        if not raw:
            return None
        match = re.search(r"(?:SKU|item\s*#?)\s*[:#]?\s*([A-Z0-9-]{4,})", raw, re.IGNORECASE)
        if match:
            return match.group(1)
        fallback = re.search(r"\b([A-Z0-9-]{5,})\b", raw)
        return fallback.group(1) if fallback else None

    @staticmethod
    def _absolute_url(value: str | None) -> str | None:
        if not value:
            return None
        return urljoin("https://www.whitecap.com", value)
