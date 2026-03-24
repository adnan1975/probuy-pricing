from __future__ import annotations

from app.connectors.mock_catalog import build_mock_result
from app.connectors.playwright_connector import PlaywrightConnector
from app.models.normalized_result import NormalizedResult


class WhiteCapConnector(PlaywrightConnector):
    source = "white_cap"
    source_label = "White Cap"
    source_type = "distributor"
    search_url_template = "https://www.whitecap.com/search?q={query}"
    selectors = {
        # TODO: Re-verify against production DOM; this site often uses dynamic class names.
        "card": "article, li[data-product-id], .product-tile",
        "title": "a[href*='/p/'], a[data-testid='product-link']",
        "price": "[data-testid='product-price'], .price, .sales",
        "image": "img",
    }

    async def normalize_result(self, page, card) -> NormalizedResult | None:
        title_node = card.locator(self.selectors["title"]).first
        title = (await title_node.inner_text()).strip() if await title_node.count() else None
        if not title:
            return None

        price_node = card.locator(self.selectors["price"]).first
        price_text = (await price_node.inner_text()).strip() if await price_node.count() else None
        normalized_price, price_value = self.parse_price(price_text)
        if price_value is None:
            return None

        href = await title_node.get_attribute("href")
        image_node = card.locator(self.selectors["image"]).first
        image_url = await image_node.get_attribute("src") if await image_node.count() else None

        return NormalizedResult(
            source=self.source_label,
            source_type=self.source_type,
            title=title,
            price_text=normalized_price,
            price_value=price_value,
            currency="CAD",
            product_url=href,
            image_url=image_url,
            availability="Unknown",
            confidence="Medium",
            score=80,
        )

    def fallback_results(self, query: str) -> list[NormalizedResult]:
        # Guarded fallback while White Cap selectors are validated against live HTML.
        return build_mock_result(query, self.source, self.source_label)
