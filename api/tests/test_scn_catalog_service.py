from pathlib import Path
import tempfile
import unittest

from app.connectors.scn_connector import SCNConnector
from app.services.scn_catalog_service import SCNCatalogService


class SCNCatalogServiceTests(unittest.TestCase):
    def test_search_matches_model_and_description(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "scn.csv"
            csv_path.write_text(
                "model,description,list_price,distributor_cost,unit,manufacturer\n"
                "DCG418B,DEWALT FLEXVOLT Grinder,339,295,EA,DEWALT\n"
                "SF201AF,3M Safety Glasses,14.25,10.75,EA,3M\n",
                encoding="utf-8",
            )
            service = SCNCatalogService(csv_path=str(csv_path))

            model_match = service.search("DCG418B")
            desc_match = service.search("safety glasses")

            self.assertEqual(len(model_match), 1)
            self.assertEqual(model_match[0].model, "DCG418B")
            self.assertEqual(len(desc_match), 1)
            self.assertEqual(desc_match[0].model, "SF201AF")

    def test_search_with_empty_query_returns_all_rows(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "scn.csv"
            csv_path.write_text(
                "model,description,list_price,distributor_cost,unit\n"
                "A1,Item A,10.00,8.00,EA\n"
                "B1,Item B,,5.00,EA\n",
                encoding="utf-8",
            )
            service = SCNCatalogService(csv_path=str(csv_path))
            results = service.search("")
            self.assertEqual(len(results), 2)

    def test_health_reports_csv_source_metadata(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "scn.csv"
            csv_path.write_text(
                "model,description,list_price,distributor_cost,unit\n"
                "A1,Item A,10.00,8.00,EA\n",
                encoding="utf-8",
            )
            service = SCNCatalogService(csv_path=str(csv_path))

            health = service.health()

            self.assertEqual(health["catalog_source"], "csv")
            self.assertEqual(health["loaded_items_count"], 1)
            self.assertIn("supabase_configured", health)
            self.assertIn("table_ref", health)


class SCNConnectorTests(unittest.IsolatedAsyncioTestCase):
    async def test_connector_maps_scn_rows_to_normalized_results(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "scn.csv"
            csv_path.write_text(
                "model,description,list_price,distributor_cost,unit,manufacturer\n"
                "B1,Item B,,5.00,EA,BrandX\n",
                encoding="utf-8",
            )
            connector = SCNConnector(catalog_service=SCNCatalogService(csv_path=str(csv_path)))
            rows = await connector.search("item")

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].source, "SCN Pricing")
            self.assertIsNone(rows[0].price_value)
            self.assertEqual(rows[0].price_text, "Price unavailable from SCN list")


if __name__ == "__main__":
    unittest.main()
