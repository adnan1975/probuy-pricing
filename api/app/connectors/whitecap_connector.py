import re

from app.connectors.base import BaseConnector
from app.connectors.mock_catalog import build_mock_result
from app.models.search import NormalizedResult


class WhiteCapConnector(BaseConnector):
    source = "white_cap"
    source_label = "White Cap"

    async def search(self, query: str) -> list[NormalizedResult]:
        # TODO: Live scraping selectors for White Cap require account/session context.
        # Keep fallback stable until selector strategy is validated in production-like traffic.
        return build_mock_result(query, self.source, self.source_label)

    async def open_search_page(self, query: str) -> str:
        return f"https://www.whitecap.com/search?q={query}"

    async def extract_result_cards(self, _query: str) -> list[dict]:
        return []

    def parse_price(self, price_text: str) -> float:
        matched = re.search(r"(\d+(?:\.\d{2})?)", price_text)
        return float(matched.group(1)) if matched else 0.0

    def normalize_result(self, payload: dict) -> NormalizedResult:
        return NormalizedResult(
            source=self.source_label,
            source_type="distributor",
            title=payload.get("title", ""),
            price_text=payload.get("price_text", "$0.00"),
            price_value=self.parse_price(payload.get("price_text", "")),
            currency="CAD",
            sku=payload.get("sku"),
            brand=payload.get("brand"),
            availability=payload.get("availability", "Unknown"),
            product_url=payload.get("product_url"),
            image_url=payload.get("image_url"),
            confidence="Low",
            score=70,
        )
