import unittest

from app.connectors.canadiantire_connector import CanadianTireConnector
from app.connectors.homedepot_connector import HomeDepotConnector
from app.connectors.kms_connector import KMSConnector
from app.connectors.whitecap_connector import WhiteCapConnector


class ConnectorSmokeTests(unittest.IsolatedAsyncioTestCase):
    async def test_home_depot_connector_empty_query(self):
        results = await HomeDepotConnector().search("")
        self.assertEqual(results, [])

    async def test_canadian_tire_connector_empty_query(self):
        results = await CanadianTireConnector().search("")
        self.assertEqual(results, [])

    async def test_whitecap_connector_fallback(self):
        results = await WhiteCapConnector().search("sf201af")
        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0].source, "White Cap")

    async def test_kms_connector_fallback(self):
        results = await KMSConnector().search("sf201af")
        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0].source, "KMS Tools")


class HomeDepotHelperTests(unittest.TestCase):
    def test_extract_sku_and_absolute_url(self):
        connector = HomeDepotConnector()
        self.assertEqual(connector._extract_sku("SKU # 1234-ABCD"), "1234-ABCD")
        self.assertEqual(
            connector._absolute_url("/en/home/p.sample.html"),
            "https://www.homedepot.ca/en/home/p.sample.html",
        )

class ParsePriceTests(unittest.TestCase):
    def test_parse_price_extracts_float(self):
        text, value = HomeDepotConnector().parse_price("Now $1,234.50")
        self.assertEqual(text, "Now $1,234.50")
        self.assertEqual(value, 1234.5)


if __name__ == "__main__":
    unittest.main()
