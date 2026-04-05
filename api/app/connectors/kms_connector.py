from __future__ import annotations

from app.connectors.secondary_scrapy_connector import SecondaryScrapyConnector


class KMSToolsConnector(SecondaryScrapyConnector):
    source = "kms_tools"
    source_label = "KMS Tools"
    search_url_template = "https://www.kmstools.com/search?q={query}"

    def base_url(self) -> str:
        return "https://www.kmstools.com"

    def listing_selector(self) -> str:
        return "article.product-card, div.product-item, li.grid__item"

    def title_selector(self) -> str:
        return "h3 a::text, .product-item__title::text, .product-card__title::text"

    def price_selector(self) -> str:
        return ".price-item--sale::text, .price-item--regular::text, .price::text"

    def url_selector(self) -> str:
        return "h3 a::attr(href), .product-item__title::attr(href), .product-card__title::attr(href)"

    def image_selector(self) -> str | None:
        return "img::attr(src), img::attr(data-src)"
