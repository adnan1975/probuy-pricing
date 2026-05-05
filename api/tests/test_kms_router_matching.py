import unittest
from types import SimpleNamespace

from app.models.normalized_result import ConnectorSearchRequest
from app.services.kms_matching_service import kms_match_percentage, kms_search_queries


class KMSRouterMatchingTests(unittest.TestCase):
    def test_model_number_matches_candidate_model_fields(self):
        payload = ConnectorSearchRequest(
            query="",
            title="DEWALT FLEXVOLT grinder",
            brand="DEWALT",
            model_number="DCG418B",
            category="power tools",
        )
        candidate = SimpleNamespace(
            title="DEWALT FLEXVOLT Grinder Bare Tool",
            brand="DEWALT",
            sku="NA",
            model="DCG418B",
            manufacturer_model="DCG418B-CA",
        )

        score = kms_match_percentage(payload, candidate)
        self.assertGreaterEqual(score, 85.0)

    def test_category_is_not_used_as_kms_query_candidate(self):
        payload = ConnectorSearchRequest(
            query="grinder",
            title="DEWALT FLEXVOLT grinder",
            brand="DEWALT",
            model_number="DCG418B",
            category="power tools",
        )

        queries = kms_search_queries(payload)

        self.assertNotIn("power tools", queries)
        self.assertIn("DCG418B", queries)


if __name__ == "__main__":
    unittest.main()
