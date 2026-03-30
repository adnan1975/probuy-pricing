from __future__ import annotations

import asyncio
import re
from abc import abstractmethod
from urllib.parse import quote_plus

from app.connectors.base import BaseConnector
from app.models.normalized_result import NormalizedResult

try:
    from playwright.async_api import Error as PlaywrightError
    from playwright.async_api import TimeoutError as PlaywrightTimeoutError
    from playwright.async_api import async_playwright
except Exception:  # pragma: no cover - exercised in environments without playwright
    async_playwright = None
    PlaywrightError = Exception
    PlaywrightTimeoutError = TimeoutError


class PlaywrightConnector(BaseConnector):
    search_url_template: str = ""
    source_type: str = "retail"
    max_results: int = 8
    timeout_ms: int = 30000
    retries: int = 2
    selectors: dict[str, list[str] | str] = {}

    async def search(self, query: str) -> list[NormalizedResult]:
        if not query.strip() or async_playwright is None:
            fallback = self.fallback_results(query)
            self.persist_results(query, fallback)
            return fallback

        for _ in range(self.retries):
            try:
                async with async_playwright() as playwright:
                    browser = await playwright.chromium.launch(headless=True)
                    try:
                        page = await browser.new_page()
                        await self.open_search_page(page, query)
                        cards = await self.extract_result_cards(page)
                        results: list[NormalizedResult] = []
                        for card in cards[: self.max_results]:
                            normalized = await self.normalize_result(page, card)
                            if normalized:
                                results.append(normalized)
                        self.persist_results(query, results)
                        return results
                    finally:
                        await browser.close()
            except (PlaywrightError, PlaywrightTimeoutError, TimeoutError, OSError):
                await asyncio.sleep(0.4)

        fallback = self.fallback_results(query)
        self.persist_results(query, fallback)
        return fallback

    async def open_search_page(self, page, query: str) -> None:
        target = self.search_url_template.format(query=quote_plus(query))
        await page.goto(target, wait_until="domcontentloaded", timeout=self.timeout_ms)
        await page.wait_for_timeout(1200)

    async def extract_result_cards(self, page):
        # Support both legacy `card` and current `cards` selector naming.
        selector_or_selectors = self.selectors.get("cards") or self.selectors["card"]
        selectors = (
            selector_or_selectors
            if isinstance(selector_or_selectors, list)
            else [selector_or_selectors]
        )

        for selector in selectors:
            locator = page.locator(selector)
            try:
                await locator.first.wait_for(state="visible", timeout=self.timeout_ms)
                count = await locator.count()
                if count:
                    return [locator.nth(i) for i in range(count)]
            except Exception:
                continue
        return []

    def parse_price(self, price_text: str | None) -> tuple[str | None, float | None]:
        if not price_text:
            return None, None
        compact = " ".join(price_text.split())
        match = re.search(r"(?:C\$|\$|CAD)?\s*([0-9][0-9,]*(?:\.[0-9]{2})?)", compact)
        if not match:
            return compact, None
        value = float(match.group(1).replace(",", ""))
        return compact, value

    @abstractmethod
    async def normalize_result(self, page, card) -> NormalizedResult | None:
        raise NotImplementedError

    def fallback_results(self, query: str) -> list[NormalizedResult]:
        return []
