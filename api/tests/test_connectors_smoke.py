import unittest

from app.connectors.canadiantire_connector import CanadianTireConnector
from app.connectors.homedepot_connector import HomeDepotConnector
from app.connectors.kms_connector import KMSConnector
from app.connectors.whitecap_connector import WhiteCapConnector


class ConnectorSmokeTests(unittest.IsolatedAsyncioTestCase):
    async def test_whitecap_smoke(self) -> None:
        results = await WhiteCapConnector().search("dewalt grinder")
        self.assertIsInstance(results, list)

    async def test_kms_smoke(self) -> None:
        results = await KMSConnector().search("dewalt grinder")
        self.assertIsInstance(results, list)

    async def test_canadian_tire_smoke(self) -> None:
        results = await CanadianTireConnector().search("dewalt grinder")
        self.assertIsInstance(results, list)

    async def test_home_depot_smoke(self) -> None:
        results = await HomeDepotConnector().search("dewalt grinder")
        self.assertIsInstance(results, list)


if __name__ == "__main__":
    unittest.main()
