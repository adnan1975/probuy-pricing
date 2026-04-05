from __future__ import annotations

from app.connectors.secondary_scrapy_connector import SecondaryScrapyConnector


class WhiteCapConnector(SecondaryScrapyConnector):
    source = "white_cap"
    source_label = "White Cap"
    source_type = "distributor"
    search_url_template = "https://www.whitecap.com/search?q={query}"

    def base_url(self) -> str:
        return "https://www.whitecap.com"

    def listing_selector(self) -> str:
        return "article, .product-tile, .productGridItem"

    def title_selector(self) -> str:
        return "a[title]::attr(title), h2 a::text, h3 a::text"

    def price_selector(self) -> str:
        return ".price ::text, .product-price ::text"

    def url_selector(self) -> str:
        return "a[href*='/p/']::attr(href), h2 a::attr(href), h3 a::attr(href)"

    def sku_selector(self) -> str | None:
        return "[data-testid='sku']::text, .sku::text"

    def image_selector(self) -> str | None:
        return "img::attr(src), img::attr(data-src)"
