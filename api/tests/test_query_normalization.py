import unittest
from unittest.mock import Mock, patch

from app.config import settings
from app.models.normalized_result import NormalizedResult
from app.services.matching_service import MatchingService
from app.services.scn_catalog_service import SCNCatalogService
from app.utils.query_normalization import expand_measurement_variants, normalize_measurements


class QueryNormalizationTests(unittest.TestCase):
    def test_normalize_measurements_handles_quote_variants(self):
        cases = {
            "14''": "14 in",
            '14""': "14 in",
            "14 inch": "14 in",
            "14 in": "14 in",
            '0.325""': "0.325 in",
            "3 ft": "3 ft",
        }

        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(normalize_measurements(raw), expected)

    def test_normalize_measurements_mixed_string(self):
        text = "DEWALT blade 14\"\" , arbor 0.325\"\" and frame 6 feet"
        self.assertEqual(
            normalize_measurements(text),
            "dewalt blade 14 in arbor 0.325 in and frame 6 ft",
        )

    def test_equivalent_inputs_return_consistent_normalized_tokens(self):
        equivalents = ["14'' grinder", "14\"\" grinder", "14 inch grinder", "14 in grinder"]
        normalized_tokens = [{token for token in normalize_measurements(item).split(" ") if token} for item in equivalents]
        first = normalized_tokens[0]
        for token_set in normalized_tokens[1:]:
            self.assertEqual(token_set, first)

    def test_expand_measurement_variants_dedupes_and_preserves_order(self):
        variants = expand_measurement_variants("14 in cutoff saw")
        self.assertGreaterEqual(len(variants), 4)
        self.assertEqual(variants[0], "14 in cutoff saw")
        self.assertIn('14" cutoff saw', variants)
        self.assertIn("14'' cutoff saw", variants)
        self.assertIn("14 inch cutoff saw", variants)
        self.assertEqual(len(variants), len(dict.fromkeys(variants)))


class SCNCatalogMeasurementQueryTests(unittest.TestCase):
    @patch("app.services.scn_catalog_service.requests.get")
    def test_scn_search_uses_normalized_and_expanded_measurement_queries(self, mock_get: Mock):
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = [{"model": "A1", "description": "14 in saw"}]
        mock_get.return_value = mock_response

        old_url = settings.supabase_url
        old_key = settings.supabase_service_role_key
        try:
            settings.supabase_url = "https://example.supabase.co"
            settings.supabase_service_role_key = "test-key"
            service = SCNCatalogService()
            service.search('14"" saw')

            called_params = mock_get.call_args.kwargs["params"]
            self.assertIn("14 in", called_params["or"])
            self.assertIn('14"', called_params["or"])
            self.assertIn("14''", called_params["or"])
            self.assertIn("14 inch", called_params["or"])
        finally:
            settings.supabase_url = old_url
            settings.supabase_service_role_key = old_key


class MatchingServiceMeasurementTests(unittest.TestCase):
    def test_matching_scores_equivalent_measurement_forms_consistently(self):
        service = MatchingService()
        results = [
            NormalizedResult(
                source="Home Depot",
                source_type="retail",
                title='DEWALT 14" cutoff saw',
                price_text="$10.00",
                price_value=10.0,
                currency="CAD",
                sku=None,
                brand="DEWALT",
                availability="In Stock",
                product_url="https://example.com/item",
                image_url=None,
                confidence="High",
                score=60,
                why="",
            )
        ]

        ranked_a = service.apply("dewalt 14 inch cutoff saw", results)
        ranked_b = service.apply("dewalt 14'' cutoff saw", results)

        self.assertEqual(ranked_a[0].score, ranked_b[0].score)


if __name__ == "__main__":
    unittest.main()
