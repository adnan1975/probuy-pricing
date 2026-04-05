from __future__ import annotations

from app.connectors.secondary_scrapy_connector import SecondaryScrapyConnector


class CanadianTireConnector(SecondaryScrapyConnector):
    source = "canadian_tire"
    source_label = "Canadian Tire"
    search_url_template = "https://www.canadiantire.ca/en/search-results.html?q={query}"

    def base_url(self) -> str:
        return "https://www.canadiantire.ca"

    def listing_selector(self) -> str:
        return "article.product-card, li.product-grid-item, div[data-testid='product-grid-item']"

    def title_selector(self) -> str:
        return "a[data-testid='product-card-link']::text, h3 a::text, .product-card__title::text"

    def price_selector(self) -> str:
        return "[data-testid='price'] ::text, .price ::text"

    def url_selector(self) -> str:
        return "a[data-testid='product-card-link']::attr(href), h3 a::attr(href), .product-card__title::attr(href)"

    def image_selector(self) -> str | None:
        return "img::attr(src), img::attr(data-src)"
