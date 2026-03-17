from __future__ import annotations

from app.connectors.playwright_connector import PlaywrightConnector
from app.models.search import SearchResult


class CanadianTireConnector(PlaywrightConnector):
    source = "canadian_tire"
    source_label = "Canadian Tire"
    search_url_template = "https://www.canadiantire.ca/en/search-results.html?q={query}"
    selectors = {
        # Assumption: product cards keep this e2e id pattern.
        "card": '[data-testid="product-card"]',
        "title": '[data-testid="product-name"] a, a[data-testid="product-link"]',
        "price": '[data-testid="product-price"], [data-testid="sale-price"]',
        "sku": '[data-testid="product-part-number"]',
        "image": 'img[data-testid="product-image"]',
        "availability": '[data-testid="stock-status"]',
    }

    async def normalize_result(self, page, card) -> SearchResult | None:
        title_node = card.locator(self.selectors["title"]).first
        title = (await title_node.inner_text()).strip() if await title_node.count() else None
        if not title:
            return None

        href = await title_node.get_attribute("href") if await title_node.count() else None
        price_node = card.locator(self.selectors["price"]).first
        price_text = (await price_node.inner_text()).strip() if await price_node.count() else None
        normalized_price, price_value = self.parse_price(price_text)
        if price_value is None:
            return None

        sku_node = card.locator(self.selectors["sku"]).first
        sku_text = (await sku_node.inner_text()).strip() if await sku_node.count() else None
        availability_node = card.locator(self.selectors["availability"]).first
        availability = (
            (await availability_node.inner_text()).strip() if await availability_node.count() else "Unknown"
        )
        image_node = card.locator(self.selectors["image"]).first
        image_url = await image_node.get_attribute("src") if await image_node.count() else None

        return SearchResult(
            source=self.source_label,
            source_type=self.source_type,
            title=title,
            price_text=normalized_price,
            price_value=price_value,
            currency="CAD",
            sku=sku_text,
            availability=availability,
            product_url=href,
            image_url=image_url,
        )
