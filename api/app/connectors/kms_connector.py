import re

from app.connectors.base import BaseConnector
from app.connectors.mock_catalog import build_mock_result
from app.models.search import NormalizedResult


class KMSConnector(BaseConnector):
    source = "kms_tools"
    source_label = "KMS Tools"

    async def search(self, query: str) -> list[NormalizedResult]:
        # TODO: KMS Tools pages are heavily dynamic and selector strategy still needs hardening.
        # Use fallback data while a stable Playwright workflow is finalized.
        return build_mock_result(query, self.source, self.source_label)

    async def open_search_page(self, query: str) -> str:
        return f"https://www.kmstools.com/search?q={query}"

    async def extract_result_cards(self, _query: str) -> list[dict]:
        return []

    def parse_price(self, price_text: str) -> float:
        matched = re.search(r"(\d+(?:\.\d{2})?)", price_text)
        return float(matched.group(1)) if matched else 0.0

    def normalize_result(self, payload: dict) -> NormalizedResult:
        return NormalizedResult(
            source=self.source_label,
            source_type="retailer",
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
