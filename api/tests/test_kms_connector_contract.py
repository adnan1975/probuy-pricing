import unittest

from app.connectors.kms_connector import KMSConnector


class KMSConnectorContractTests(unittest.TestCase):
    def test_kms_connector_exposes_only_api_contract_methods(self):
        connector = KMSConnector()

        self.assertTrue(callable(getattr(connector, "build_request", None)))
        self.assertTrue(callable(getattr(connector, "download_payload", None)))
        self.assertTrue(callable(getattr(connector, "extract_results", None)))

        # KMS now inherits from SecondaryAPIConnector and should not provide
        # HTML selector/search-template placeholders.
        for removed_attr in (
            "listing_selector",
            "title_selector",
            "price_selector",
            "url_selector",
            "search_url_template",
        ):
            self.assertFalse(hasattr(connector, removed_attr), f"{removed_attr} should not exist on KMSConnector")


if __name__ == "__main__":
    unittest.main()
