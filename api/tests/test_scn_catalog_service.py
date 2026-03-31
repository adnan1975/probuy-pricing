import unittest
from unittest.mock import Mock, patch

from app.connectors.scn_connector import SCNConnector
from app.config import settings
from app.services.scn_catalog_service import SCNBatchIngestService, SCNCatalogService, SCNItem


class SCNCatalogServiceTests(unittest.TestCase):
    @patch("app.services.scn_catalog_service.requests.get")
    def test_search_matches_model_and_description(self, mock_get: Mock):
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = [
            {
                "model": "DCG418B",
                "description": "DEWALT FLEXVOLT Grinder",
                "list_price": 339.0,
                "distributor_cost": 295.0,
                "unit": "EA",
                "manufacturer": "DEWALT",
            },
            {
                "model": "SF201AF",
                "description": "3M Safety Glasses",
                "list_price": 14.25,
                "distributor_cost": 10.75,
                "unit": "EA",
                "manufacturer": "3M",
            },
        ]
        mock_get.return_value = mock_response
        old_url = settings.supabase_url
        old_key = settings.supabase_service_role_key
        try:
            settings.supabase_url = "https://example.supabase.co"
            settings.supabase_service_role_key = "test-key"
            service = SCNCatalogService()

            model_match = service.search("DCG418B")
            desc_match = service.search("safety glasses")

            self.assertEqual(len(model_match), 1)
            self.assertEqual(model_match[0].model, "DCG418B")
            self.assertEqual(len(desc_match), 1)
            self.assertEqual(desc_match[0].model, "SF201AF")
        finally:
            settings.supabase_url = old_url
            settings.supabase_service_role_key = old_key

    @patch("app.services.scn_catalog_service.requests.get")
    def test_search_with_empty_query_returns_early(self, mock_get: Mock):
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = [
            {"model": "A1", "description": "Item A", "list_price": 10.0},
            {"model": "B1", "description": "Item B", "list_price": None},
        ]
        mock_get.return_value = mock_response
        old_url = settings.supabase_url
        old_key = settings.supabase_service_role_key
        try:
            settings.supabase_url = "https://example.supabase.co"
            settings.supabase_service_role_key = "test-key"
            service = SCNCatalogService()
            results = service.search("")
            self.assertEqual(len(results), 0)
            mock_get.assert_not_called()
        finally:
            settings.supabase_url = old_url
            settings.supabase_service_role_key = old_key

    @patch("app.services.scn_catalog_service.requests.get")
    def test_health_reports_supabase_source_metadata(self, mock_get: Mock):
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = [{"model": "A1", "description": "Item A", "list_price": 10.0}]
        mock_get.return_value = mock_response
        old_url = settings.supabase_url
        old_key = settings.supabase_service_role_key
        try:
            settings.supabase_url = "https://example.supabase.co"
            settings.supabase_service_role_key = "test-key"
            service = SCNCatalogService()

            health = service.health()

            self.assertEqual(health["catalog_source"], "supabase")
            self.assertEqual(health["loaded_items_count"], 1)
            self.assertIn("supabase_configured", health)
            self.assertIn("table_ref", health)
        finally:
            settings.supabase_url = old_url
            settings.supabase_service_role_key = old_key

    @patch("app.services.scn_catalog_service.requests.get")
    def test_list_distinct_queries_includes_model_and_description(self, mock_get: Mock):
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = [
            {"model": "A1", "description": "Hydraulic Pump Model A", "list_price": 10.0},
            {"model": "B1", "description": "Hydraulic Pump Model B", "list_price": 12.0},
        ]
        mock_get.return_value = mock_response
        old_url = settings.supabase_url
        old_key = settings.supabase_service_role_key
        try:
            settings.supabase_url = "https://example.supabase.co"
            settings.supabase_service_role_key = "test-key"
            service = SCNCatalogService()

            suggestions = service.list_distinct_queries(limit=10)

            self.assertIn("A1", suggestions)
            self.assertIn("Hydraulic Pump Model A", suggestions)
            self.assertIn("B1", suggestions)
            self.assertIn("Hydraulic Pump Model B", suggestions)
        finally:
            settings.supabase_url = old_url
            settings.supabase_service_role_key = old_key

    @patch("app.services.scn_catalog_service.requests.get")
    def test_supabase_load_uses_schema_profile_header(self, mock_get: Mock):
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = [
            {"model": "A1", "description": "Hydraulic Pump Model A", "list_price": 10.0}
        ]
        mock_get.return_value = mock_response

        old_url = settings.supabase_url
        old_key = settings.supabase_service_role_key
        old_schema = settings.supabase_schema
        old_table = settings.scn_table
        try:
            settings.supabase_url = "https://example.supabase.co"
            settings.supabase_service_role_key = "test-key"
            settings.supabase_schema = "pricing"
            settings.scn_table = "scn_pricing"

            service = SCNCatalogService(csv_path="/tmp/does-not-matter.csv")
            rows = service.load_items(force_reload=True)

            self.assertEqual(len(rows), 1)
            self.assertEqual(service.last_load_source, "supabase")
            mock_get.assert_called_once()
            called_endpoint = mock_get.call_args.args[0]
            called_headers = mock_get.call_args.kwargs["headers"]
            self.assertEqual(called_endpoint, "https://example.supabase.co/rest/v1/scn_pricing")
            self.assertEqual(called_headers["Accept-Profile"], "pricing")
        finally:
            settings.supabase_url = old_url
            settings.supabase_service_role_key = old_key
            settings.supabase_schema = old_schema
            settings.scn_table = old_table


class SCNConnectorTests(unittest.IsolatedAsyncioTestCase):
    @patch("app.services.scn_catalog_service.requests.get")
    async def test_connector_maps_scn_rows_to_normalized_results(self, mock_get: Mock):
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = [
            {
                "model": "B1",
                "description": "Item B",
                "list_price": None,
                "distributor_cost": 5.0,
                "unit": "EA",
                "manufacturer": "BrandX",
                "warehouse": "Warehouse 7",
            }
        ]
        mock_get.return_value = mock_response
        old_url = settings.supabase_url
        old_key = settings.supabase_service_role_key
        try:
            settings.supabase_url = "https://example.supabase.co"
            settings.supabase_service_role_key = "test-key"
            connector = SCNConnector(catalog_service=SCNCatalogService())
            rows = await connector.search("item")

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].source, "SCN Pricing")
            self.assertIsNone(rows[0].price_value)
            self.assertEqual(rows[0].price_text, "Price unavailable from SCN list")
            self.assertEqual(rows[0].location, "Warehouse 7")
        finally:
            settings.supabase_url = old_url
            settings.supabase_service_role_key = old_key


class SCNBatchIngestServiceTests(unittest.TestCase):
    def test_normalize_ingest_payload_fills_nullable_pk_components(self):
        service = SCNBatchIngestService()
        rows = [
            SCNItem(
                model=" DCG418B ",
                manufacturer_model=None,
                description="DEWALT grinder",
                list_price=339.0,
                distributor_cost=299.0,
                unit="EA",
                manufacturer=None,
                warehouse=None,
            ),
        ]

        payload = service._normalize_ingest_payload(rows)

        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["model"], "DCG418B")
        self.assertEqual(payload[0]["manufacturer"], "")
        self.assertEqual(payload[0]["warehouse"], "")
        self.assertEqual(payload[0]["manufacturer_model"], "")

    def test_normalize_ingest_payload_skips_rows_without_model(self):
        service = SCNBatchIngestService()
        rows = [
            SCNItem(
                model="",
                manufacturer_model=None,
                description="Description only row",
                list_price=None,
                distributor_cost=None,
                unit=None,
                manufacturer="Acme",
                warehouse="Main",
            ),
        ]

        payload = service._normalize_ingest_payload(rows)

        self.assertEqual(payload, [])


if __name__ == "__main__":
    unittest.main()
