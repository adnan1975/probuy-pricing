import re
from urllib.parse import quote_plus

from app.connectors.base import BaseConnector
from app.connectors.mock_catalog import build_mock_result
from app.models.search import NormalizedResult

try:
    from playwright.async_api import Page, async_playwright
except ImportError:  # pragma: no cover - exercised in smoke tests via fallback
    async_playwright = None
    Page = object


class HomeDepotConnector(BaseConnector):
    source = "home_depot"
    source_label = "Home Depot"
    _base_url = "https://www.homedepot.ca"
    _search_url_template = "https://www.homedepot.ca/search?q={query}"
    _card_selector = '[data-testid="product-tile"], article'
    _title_selector = "h2 a, h3 a, a[data-testid='product-title'], a"
    _price_selector = "[data-testid='product-price'], .price, [aria-label*='price']"
    _sku_selector = "[data-testid='product-sku'], [class*='sku']"
    _image_selector = "img"

    async def search(self, query: str) -> list[NormalizedResult]:
        if not query.strip() or async_playwright is None:
            return build_mock_result(query, self.source, self.source_label)

        for _ in range(2):
            try:
                async with async_playwright() as playwright:
                    browser = await playwright.chromium.launch(headless=True)
                    page = await browser.new_page()
                    await self.open_search_page(page, query)
                    cards = await self.extract_result_cards(page)
                    results = [r for r in cards if r]
                    await browser.close()
                    return results or build_mock_result(query, self.source, self.source_label)
            except Exception:
                # Fragile selectors or anti-bot behavior should not fail the full request.
                continue

        return build_mock_result(query, self.source, self.source_label)

    async def open_search_page(self, page: Page, query: str) -> None:
        search_url = self._search_url_template.format(query=quote_plus(query))
        await page.goto(search_url, timeout=30_000, wait_until="domcontentloaded")
        await page.wait_for_timeout(1_500)

    async def extract_result_cards(self, page: Page) -> list[NormalizedResult]:
        cards = page.locator(self._card_selector)
        count = min(await cards.count(), 6)
        results: list[NormalizedResult] = []

        for index in range(count):
            card = cards.nth(index)
            title = (await card.locator(self._title_selector).first.inner_text()).strip()
            product_url = await card.locator(self._title_selector).first.get_attribute("href")
            price_text = ((await card.locator(self._price_selector).first.inner_text()) or "").strip()
            sku_text = await card.locator(self._sku_selector).first.inner_text() if await card.locator(self._sku_selector).count() else None
            image_url = await card.locator(self._image_selector).first.get_attribute("src") if await card.locator(self._image_selector).count() else None
            results.append(
                self.normalize_result(
                    title=title,
                    price_text=price_text,
                    product_url=product_url,
                    sku=sku_text,
                    image_url=image_url,
                )
            )

        return results

    def parse_price(self, price_text: str) -> float:
        matched = re.search(r"(\d{1,3}(?:,\d{3})*(?:\.\d{2})|\d+(?:\.\d{2})?)", price_text.replace("\xa0", " "))
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
