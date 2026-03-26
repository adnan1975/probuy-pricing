import unittest

from app.connectors.base import BaseConnector
from app.models.normalized_result import ConnectorSearchRequest, NormalizedResult
from app.models.normalized_result import SearchResponse
from app.routers.search import search_by_connector as search_by_connector_handler
from app.routers.search import search_service
from app.routers.search import catalog_health as catalog_health_handler
from app.routers.search import search as search_handler
from main import app


class StubConnector(BaseConnector):
    source = "stub_source"
    source_label = "Stub Source"
    source_type = "retail"

    async def search(self, query: str) -> list[NormalizedResult]:
        return [
            NormalizedResult(
                source=self.source_label,
                source_type=self.source_type,
                title=f"Result for {query}",
                price_text="$1.00",
                price_value=1.0,
                why="Stub result",
            )
        ]


class AppSmokeTests(unittest.IsolatedAsyncioTestCase):
    async def test_search_handler_returns_contract(self):
        response = await search_handler(product="DEWALT DCG418B", page=1, page_size=25)

        self.assertIsInstance(response, SearchResponse)
        self.assertEqual(response.query, "DEWALT DCG418B")
        self.assertIsInstance(response.results, list)
        self.assertIsInstance(response.per_source_errors, dict)

    async def test_catalog_health_handler_returns_metadata(self):
        response = await catalog_health_handler()

        self.assertIn("catalog_source", response)
        self.assertIn("loaded_items_count", response)
        self.assertIn("supabase_configured", response)
        self.assertIn("table_ref", response)

    async def test_search_by_connector_handler_returns_results(self):
        original_connectors = search_service.connectors
        original_lookup = search_service._connector_lookup
        try:
            stub = StubConnector()
            search_service.connectors = [stub]
            search_service._connector_lookup = search_service._build_connector_lookup(search_service.connectors)

            response = await search_by_connector_handler(
                payload=ConnectorSearchRequest(query="hammer"),
                connector_name="stubsource",
            )

            self.assertEqual(response.connector, "stub_source")
            self.assertEqual(response.query, "hammer")
            self.assertEqual(len(response.results), 1)
            self.assertEqual(response.results[0].title, "Result for hammer")
        finally:
            search_service.connectors = original_connectors
            search_service._connector_lookup = original_lookup

    def test_fastapi_routes_are_registered(self):
        route_paths = {route.path for route in app.routes}

        self.assertIn("/", route_paths)
        self.assertIn("/search", route_paths)
        self.assertIn("/search/{connector_name}", route_paths)
        self.assertIn("/catalog/health", route_paths)
        self.assertIn("/catalog/all-items", route_paths)


if __name__ == "__main__":
    unittest.main()
