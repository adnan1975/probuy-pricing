import unittest

from app.models.normalized_result import SearchResponse
from app.routers.search import catalog_health as catalog_health_handler
from app.routers.search import search as search_handler
from main import app


class AppSmokeTests(unittest.IsolatedAsyncioTestCase):
    async def test_search_handler_returns_contract(self):
        response = await search_handler(product="DEWALT DCG418B")

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

    def test_fastapi_routes_are_registered(self):
        route_paths = {route.path for route in app.routes}

        self.assertIn("/", route_paths)
        self.assertIn("/search", route_paths)
        self.assertIn("/catalog/health", route_paths)


if __name__ == "__main__":
    unittest.main()
