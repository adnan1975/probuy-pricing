from __future__ import annotations

from app.connectors.secondary_scrapy_connector import SecondaryScrapyConnector


class CanadaWeldingSupplyConnector(SecondaryScrapyConnector):
    source = "canada_welding_supply"
    source_label = "Canada Welding Supply"
    source_type = "distributor"
    search_url_template = "https://canadaweldingsupply.ca/search?q={query}"

    def base_url(self) -> str:
        return "https://canadaweldingsupply.ca"

    def listing_selector(self) -> str:
        return "article, .product-item, .grid-product, li.product"

    def title_selector(self) -> str:
        return "a[title]::attr(title), .product-title::text, h2 a::text, h3 a::text"

    def price_selector(self) -> str:
        return ".price ::text, .product-price ::text, [class*='price']::text"

    def url_selector(self) -> str:
        return "a[href*='/products/']::attr(href), .product-title::attr(href), h2 a::attr(href), h3 a::attr(href)"

    def sku_selector(self) -> str | None:
        return "[data-sku]::attr(data-sku), .sku::text"

    def image_selector(self) -> str | None:
        return "img::attr(src), img::attr(data-src), img::attr(data-srcset)"
