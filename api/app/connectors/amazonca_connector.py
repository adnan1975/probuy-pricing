from __future__ import annotations

from app.connectors.secondary_scrapy_connector import SecondaryScrapyConnector


class AmazonCAConnector(SecondaryScrapyConnector):
    source = "amazon_ca"
    source_label = "Amazon.ca"
    search_url_template = "https://www.amazon.ca/s?k={query}"

    def base_url(self) -> str:
        return "https://www.amazon.ca"

    def listing_selector(self) -> str:
        return "div.s-result-item[data-component-type='s-search-result']"

    def title_selector(self) -> str:
        return "h2 a span::text"

    def price_selector(self) -> str:
        return ".a-price .a-offscreen::text, .a-price-whole::text"

    def url_selector(self) -> str:
        return "h2 a::attr(href)"

    def image_selector(self) -> str | None:
        return "img.s-image::attr(src)"
