from __future__ import annotations

from app.connectors.mock_catalog import build_mock_result
from app.connectors.playwright_connector import PlaywrightConnector
from app.models.search import SearchResult


class KMSConnector(PlaywrightConnector):
    source = "kms_tools"
    source_label = "KMS Tools"
    search_url_template = "https://www.kmstools.com/catalogsearch/result/?q={query}"
    selectors = {
        # TODO: Re-verify in browser; Magento themes can vary per deployment.
        "card": "li.product-item, .product-item-info",
        "title": "a.product-item-link, a[href*='product']",
        "price": ".price, [data-price-type='finalPrice']",
        "sku": ".sku, [data-role='sku']",
        "image": "img.product-image-photo, img",
    }

    async def normalize_result(self, page, card) -> SearchResult | None:
        title_node = card.locator(self.selectors["title"]).first
        title = (await title_node.inner_text()).strip() if await title_node.count() else None
        if not title:
            return None

        price_node = card.locator(self.selectors["price"]).first
        price_text = (await price_node.inner_text()).strip() if await price_node.count() else None
        normalized_price, price_value = self.parse_price(price_text)
        if price_value is None:
            return None

        sku_node = card.locator(self.selectors["sku"]).first
        sku = (await sku_node.inner_text()).strip() if await sku_node.count() else None
        href = await title_node.get_attribute("href")
        image_node = card.locator(self.selectors["image"]).first
        image_url = await image_node.get_attribute("src") if await image_node.count() else None

        return SearchResult(
            source=self.source_label,
            source_type=self.source_type,
            title=title,
            price_text=normalized_price,
            price_value=price_value,
            currency="CAD",
            sku=sku,
            product_url=href,
            image_url=image_url,
            availability="Unknown",
            confidence="Medium",
            score=82,
        )

    def fallback_results(self, query: str) -> list[SearchResult]:
        # Guarded fallback while KMS selectors are validated against live HTML.
        return build_mock_result(query, self.source, self.source_label)
