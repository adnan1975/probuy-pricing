import unittest

from app.models.normalized_result import SearchResponse
from app.routers.search import search as search_handler
from main import app


class AppSmokeTests(unittest.IsolatedAsyncioTestCase):
    async def test_search_handler_returns_contract(self):
        response = await search_handler(product="DEWALT DCG418B")

        self.assertIsInstance(response, SearchResponse)
        self.assertEqual(response.query, "DEWALT DCG418B")
        self.assertIsInstance(response.results, list)
        self.assertIsInstance(response.per_source_errors, dict)

    def test_fastapi_routes_are_registered(self):
        route_paths = {route.path for route in app.routes}

        self.assertIn("/", route_paths)
        self.assertIn("/search", route_paths)


if __name__ == "__main__":
    unittest.main()
