import unittest

from app.connectors.amazonca_connector import AmazonCAConnector
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

    async def test_amazon_ca_connector_empty_query(self):
        results = await AmazonCAConnector().search("")
        self.assertEqual(results, [])

    async def test_whitecap_connector_fallback(self):
        results = await WhiteCapConnector().search("sf201af")
        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0].source, "White Cap")

    async def test_kms_connector_no_mock_fallback(self):
        results = await KMSConnector().search("sf201af")
        self.assertEqual(results, [])


class HomeDepotHelperTests(unittest.TestCase):
    def test_extract_sku_and_absolute_url(self):
        connector = HomeDepotConnector()
        self.assertEqual(connector._extract_sku("SKU # 1234-ABCD"), "1234-ABCD")
        self.assertEqual(
            connector._absolute_url("/en/home/p.sample.html"),
            "https://www.homedepot.ca/en/home/p.sample.html",
        )



class CanadianTireHelperTests(unittest.TestCase):
    def test_extract_sku_and_absolute_url(self):
        connector = CanadianTireConnector()
        self.assertEqual(connector._extract_sku("Part Number: SF201AF"), "SF201AF")
        self.assertEqual(
            connector._absolute_url("/en/pdp/sample-product.html"),
            "https://www.canadiantire.ca/en/pdp/sample-product.html",
        )

    def test_extract_brand(self):
        connector = CanadianTireConnector()
        self.assertEqual(connector._extract_brand("DEWALT FLEXVOLT Grinder"), "Dewalt")


class ParsePriceTests(unittest.TestCase):
    def test_parse_price_extracts_float(self):
        text, value = HomeDepotConnector().parse_price("Now $1,234.50")
        self.assertEqual(text, "Now $1,234.50")
        self.assertEqual(value, 1234.5)


if __name__ == "__main__":
    unittest.main()
