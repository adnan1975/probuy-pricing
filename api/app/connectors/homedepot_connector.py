from __future__ import annotations

from app.connectors.secondary_scrapy_connector import SecondaryScrapyConnector


class HomeDepotConnector(SecondaryScrapyConnector):
    source = "home_depot"
    source_label = "Home Depot"
    search_url_template = "https://www.homedepot.ca/search?q={query}"

    def base_url(self) -> str:
        return "https://www.homedepot.ca"

    def listing_selector(self) -> str:
        return "article.product-tile, .product-list__item, [data-testid='product-tile']"

    def title_selector(self) -> str:
        return "[data-testid='product-title']::text, h2 a::text, h3 a::text"

    def price_selector(self) -> str:
        return "[data-testid='product-price'] ::text, .price ::text"

    def url_selector(self) -> str:
        return "[data-testid='product-title']::attr(href), h2 a::attr(href), h3 a::attr(href)"

    def image_selector(self) -> str | None:
        return "img::attr(src), img::attr(data-src)"
