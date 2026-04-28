from __future__ import annotations

import unittest

import pytest
import requests

pytest.importorskip("scrapy")

from app.connectors.amazonca_connector import AmazonCAConnector
from app.connectors.canadiantire_connector import CanadianTireConnector
from app.connectors.canadaweldingsupply_connector import CanadaWeldingSupplyConnector
from app.connectors.homedepot_connector import HomeDepotConnector
from app.connectors.kms_connector import KMSConnector
from app.connectors.secondary_api_connector import SecondaryAPIConnector
from app.connectors.secondary_scrapy_connector import SecondaryScrapyConnector
from app.models.normalized_result import NormalizedResult


class FakeAPIContractConnector(SecondaryAPIConnector):
    source = "fake_api"
    source_label = "Fake API"
    max_results = 2

    def __init__(
        self,
        payload: object = None,
        should_raise: bool = False,
        payload_by_query: dict[str, object] | None = None,
    ) -> None:
        super().__init__()
        self.payload = payload if payload is not None else {"items": []}
        self.should_raise = should_raise
        self.payload_by_query = payload_by_query or {}
        self.requested_queries: list[str] = []

    def build_request(self, query: str) -> dict[str, object]:
        return {"query": query}

    def download_payload(self, request: dict[str, object]) -> object:
        if self.should_raise:
            raise requests.RequestException("simulated api transport failure")
        query = str(request.get("query", ""))
        self.requested_queries.append(query)
        return self.payload_by_query.get(query, self.payload)

    def extract_results(self, query: str, payload: object) -> list[NormalizedResult]:
        if not isinstance(payload, dict):
            return []

        results: list[NormalizedResult] = []
        for item in payload.get("items", []):
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", "")).strip()
            url = str(item.get("url", "")).strip()
            if not title or not url:
                continue
            results.append(
                NormalizedResult(
                    source=self.source_label,
                    source_type=self.source_type,
                    title=title,
                    price_text=item.get("price_text") or "Price unavailable",
                    price_value=item.get("price_value"),
                    currency="CAD",
                    sku=item.get("sku"),
                    brand=item.get("brand"),
                    availability="See product page",
                    product_url=url,
                    image_url=item.get("image_url"),
                    confidence="High" if item.get("price_value") is not None else "Low",
                    score=80,
                    why="Fake API fixture",
                )
            )
        return results


class FakeScrapyContractConnector(SecondaryScrapyConnector):
    source = "fake_scrapy"
    source_label = "Fake Scrapy"
    max_results = 2
    search_url_template = "https://example.test/search?q={query}"

    def __init__(self, html: str = "", should_raise: bool = False) -> None:
        super().__init__()
        self.html = html
        self.should_raise = should_raise

    def download_html(self, url: str) -> str:
        if self.should_raise:
            raise requests.RequestException("simulated page fetch failure")
        return self.html

    def base_url(self) -> str:
        return "https://example.test"

    def listing_selector(self) -> str:
        return ".card"

    def title_selector(self) -> str:
        return ".title::text"

    def price_selector(self) -> str:
        return ".price::text"

    def url_selector(self) -> str:
        return "a::attr(href)"


class ConnectorContractTests(unittest.IsolatedAsyncioTestCase):
    def test_all_supported_connectors_expose_expected_source_labels(self):
        connectors = [
            (KMSConnector(), "KMS Tools", "retail"),
            (CanadianTireConnector(), "Canadian Tire", "retail"),
            (HomeDepotConnector(), "Home Depot", "retail"),
            (AmazonCAConnector(), "Amazon.ca", "retail"),
            (CanadaWeldingSupplyConnector(), "Canada Welding Supply", "distributor"),
        ]

        for connector, expected_label, expected_type in connectors:
            self.assertEqual(connector.source_label, expected_label)
            self.assertEqual(connector.source_type, expected_type)

    async def test_search_handles_recoverable_failures_without_raising(self):
        api_connector = FakeAPIContractConnector(should_raise=True)
        scrapy_connector = FakeScrapyContractConnector(should_raise=True)

        api_results = await api_connector.search("dewalt")
        scrapy_results = await scrapy_connector.search("dewalt")

        self.assertEqual(api_results, [])
        self.assertEqual(scrapy_results, [])
        self.assertIsNotNone(api_connector.last_warning)
        self.assertIsNotNone(scrapy_connector.last_warning)

    async def test_results_match_normalized_contract_required_fields(self):
        fixture = {
            "items": [
                {
                    "title": "DEWALT FLEXVOLT Grinder DCG418B",
                    "url": "https://example.test/p/dcg418b",
                    "price_text": "$329.00",
                    "price_value": 329.0,
                    "sku": "DCG418B",
                    "brand": "DEWALT",
                }
            ]
        }
        connector = FakeAPIContractConnector(payload=fixture)

        results = await connector.search("dcg418b")

        self.assertEqual(len(results), 1)
        result = results[0]
        self.assertIsInstance(result, NormalizedResult)
        self.assertTrue(result.source)
        self.assertTrue(result.source_type)
        self.assertTrue(result.title)
        self.assertTrue(result.why)

    async def test_last_warning_for_zero_results_and_partial_parse_is_consistent(self):
        zero_results_connector = FakeScrapyContractConnector(html="<html><body>No cards</body></html>")
        zero_results = await zero_results_connector.search("none")
        self.assertEqual(zero_results, [])
        self.assertEqual(
            zero_results_connector.last_warning,
            "No visible listings were parsed from search page.",
        )

        partial_html = """
        <div class='card'>
          <a href='/p/1'><span class='title'>Item One</span></a>
          <span class='price'>Call for price</span>
        </div>
        """
        partial_connector = FakeScrapyContractConnector(html=partial_html)
        partial_results = await partial_connector.search("partial")

        self.assertEqual(len(partial_results), 1)
        self.assertEqual(
            partial_connector.last_warning,
            "Partial parse: 1 result(s) had no numeric price value.",
        )

    async def test_duplicate_url_filtering_and_max_results_are_enforced(self):
        fixture = {
            "items": [
                {"title": "First", "url": "https://example.test/p/1", "price_text": "$10", "price_value": 10.0},
                {
                    "title": "Second duplicate url",
                    "url": "https://example.test/p/1",
                    "price_text": "$11",
                    "price_value": 11.0,
                },
                {"title": "Third", "url": "https://example.test/p/3", "price_text": "$12", "price_value": 12.0},
                {"title": "Fourth", "url": "https://example.test/p/4", "price_text": "$13", "price_value": 13.0},
            ]
        }
        connector = FakeAPIContractConnector(payload=fixture)

        results = await connector.search("fixture")

        # max_results=2 limits before de-duplication, leaving only one unique URL.
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].product_url, "https://example.test/p/1")

    async def test_base_scrapy_behavior_with_mocked_html_fixture(self):
        html = """
        <div class='card'>
          <a href='/p/1'><span class='title'>Valid One</span></a>
          <span class='price'>$20.00</span>
        </div>
        <div class='card'>
          <a href='/p/1'><span class='title'>Valid One Duplicate URL</span></a>
          <span class='price'>$20.00</span>
        </div>
        <div class='card'>
          <a href='/p/3'><span class='title'>Valid Three</span></a>
          <span class='price'>$30.00</span>
        </div>
        """
        connector = FakeScrapyContractConnector(html=html)

        results = await connector.search("fixture")

        # max_results=2 keeps first two rows; dedupe then removes the duplicate URL.
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "Valid One")

    async def test_api_connector_uses_multi_strategy_query_fallback_order(self):
        payload_by_query = {
            "2613-20": {"items": []},
            "Milwaukee 2613-20": {"items": []},
            "Milwaukee M18 SDS Hammer": {
                "items": [
                    {
                        "title": "Milwaukee M18 Brushless SDS 1in",
                        "url": "https://example.test/p/m18-sds",
                        "price_text": "$299.00",
                        "price_value": 299.0,
                        "brand": "Milwaukee",
                        "sku": "2613-20",
                    }
                ]
            },
        }
        connector = FakeAPIContractConnector(
            payload={"items": []},
            payload_by_query=payload_by_query,
        )

        results = await connector.search("Milwaukee 2613-20 M18 SDS Hammer")

        self.assertEqual(
            connector.requested_queries[:3],
            ["2613-20", "Milwaukee 2613-20", "Milwaukee M18 SDS Hammer"],
        )
        self.assertEqual(len(results), 1)
        self.assertIn("Strategy brand_keywords query 'Milwaukee M18 SDS Hammer'.", results[0].why)


if __name__ == "__main__":
    unittest.main()
