import asyncio
import time
import unittest

from app.connectors.scn_connector import SCNConnector
from app.models.normalized_result import NormalizedResult
from app.services.search_service import SearchService


class DelayedConnector(SCNConnector):
    def __init__(self, source_label: str, delay_seconds: float, price_value: float, source_type: str = "retail") -> None:
        self.source = source_label.lower().replace(" ", "_")
        self.source_label = source_label
        self.delay_seconds = delay_seconds
        self.price_value = price_value
        self.source_type = source_type
        self.last_warning = None

    async def search(self, query: str) -> list[NormalizedResult]:
        await asyncio.sleep(self.delay_seconds)
        return [
            NormalizedResult(
                source=self.source_label,
                source_type=self.source_type,
                title=f"{query} result from {self.source_label}",
                price_text=f"${self.price_value:.2f}",
                price_value=self.price_value,
                currency="CAD",
                sku=f"SKU-{self.source_label[:3].upper()}",
                brand="TestBrand",
                availability="In Stock",
                product_url=f"https://example.com/{self.source}",
                image_url="https://example.com/image.jpg",
                confidence="High",
                score=80,
                why="Connector test result",
            )
        ]


class SearchServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_scn_only_connector_execute(self):
        service = SearchService(
            connectors=[
                DelayedConnector("SCN Pricing", delay_seconds=0.15, price_value=10, source_type="distributor"),
            ]
        )

        started = time.perf_counter()
        response = await service.search("dewalt grinder")
        elapsed = time.perf_counter() - started

        self.assertEqual(len(response.results), 1)
        self.assertEqual(response.results[0].source, "SCN Pricing")
        self.assertGreater(elapsed, 0.10)

    async def test_response_shape_analysis_and_normalized_schema(self):
        service = SearchService(
            connectors=[
                DelayedConnector("SCN Pricing", delay_seconds=0.01, price_value=12.0, source_type="distributor"),
            ]
        )

        response = await service.search("3m sf201af")

        self.assertEqual(response.query, "3m sf201af")
        self.assertIsInstance(response.results, list)
        self.assertEqual(response.analysis.lowest_price, 12.0)
        self.assertEqual(response.analysis.highest_price, 12.0)
        self.assertEqual(response.analysis.average_price, 12.0)
        self.assertEqual(response.analysis.total_results, 1)
        self.assertEqual(response.analysis.priced_results, 1)
        self.assertEqual(response.per_source_errors, {})

        expected_fields = {
            "source",
            "source_type",
            "title",
            "price_text",
            "price_value",
            "currency",
            "sku",
            "manufacturer_model",
            "brand",
            "availability",
            "location",
            "product_url",
            "image_url",
            "confidence",
            "score",
            "why",
        }

        for result in response.results:
            self.assertEqual(set(result.model_dump().keys()), expected_fields)

    async def test_search_step2_returns_empty_results(self):
        service = SearchService(connectors=[SCNConnector()])
        response = await service.search_step2("dcbl722b")
        self.assertEqual(response.results, [])
        self.assertEqual(response.analysis.total_results, 0)


if __name__ == "__main__":
    unittest.main()
