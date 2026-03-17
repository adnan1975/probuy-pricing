import re
from urllib.parse import quote_plus

from app.connectors.base import BaseConnector
from app.connectors.mock_catalog import build_mock_result
from app.models.search import NormalizedResult

try:
    from playwright.async_api import Page, async_playwright
except ImportError:  # pragma: no cover
    async_playwright = None
    Page = object


class CanadianTireConnector(BaseConnector):
    source = "canadian_tire"
    source_label = "Canadian Tire"
    _base_url = "https://www.canadiantire.ca"
    _search_url_template = "https://www.canadiantire.ca/en/search-results.html?q={query}"
    _card_selector = '[data-testid="product-card"], article'
    _title_selector = "h3 a, h2 a, a[data-testid='product-title'], a"
    _price_selector = "[data-testid='price'], .price, [class*='price']"
    _sku_selector = "[data-testid='sku'], [class*='sku']"
    _image_selector = "img"

    async def search(self, query: str) -> list[NormalizedResult]:
        if not query.strip() or async_playwright is None:
            return build_mock_result(query, self.source, self.source_label)

        try:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=True)
                page = await browser.new_page()
                await self.open_search_page(page, query)
                results = await self.extract_result_cards(page)
                await browser.close()
                return results or build_mock_result(query, self.source, self.source_label)
        except Exception:
            return build_mock_result(query, self.source, self.source_label)

    async def open_search_page(self, page: Page, query: str) -> None:
        await page.goto(
            self._search_url_template.format(query=quote_plus(query)),
            timeout=30_000,
            wait_until="domcontentloaded",
        )
        await page.wait_for_timeout(1_500)

    async def extract_result_cards(self, page: Page) -> list[NormalizedResult]:
        cards = page.locator(self._card_selector)
        count = min(await cards.count(), 6)
        results: list[NormalizedResult] = []
        for index in range(count):
            card = cards.nth(index)
            title = ((await card.locator(self._title_selector).first.inner_text()) or "").strip()
            link = await card.locator(self._title_selector).first.get_attribute("href")
            price_text = ((await card.locator(self._price_selector).first.inner_text()) or "").strip()
            sku = await card.locator(self._sku_selector).first.inner_text() if await card.locator(self._sku_selector).count() else None
            image_url = await card.locator(self._image_selector).first.get_attribute("src") if await card.locator(self._image_selector).count() else None
            results.append(self.normalize_result(title=title, price_text=price_text, product_url=link, sku=sku, image_url=image_url))

        return results

    def parse_price(self, price_text: str) -> float:
        matched = re.search(r"(\d{1,3}(?:,\d{3})*(?:\.\d{2})|\d+(?:\.\d{2})?)", price_text)
        return float(matched.group(1).replace(",", "")) if matched else 0.0

    def normalize_result(
        self,
        *,
        title: str,
        price_text: str,
        product_url: str | None,
        sku: str | None,
        image_url: str | None,
    ) -> NormalizedResult:
        normalized_url = f"{self._base_url}{product_url}" if product_url and product_url.startswith("/") else product_url
        return NormalizedResult(
            source=self.source_label,
            source_type="retailer",
            title=title,
            price_text=price_text,
            price_value=self.parse_price(price_text),
            currency="CAD",
            sku=sku,
            brand=title.split(" ")[0] if title else None,
            availability="Unknown",
            product_url=normalized_url,
            image_url=image_url,
            confidence="Medium",
            score=88,
        )
