import unittest

from app.connectors.kms_connector import KMSConnector


class KMSConnectorPriceSelectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connector = KMSConnector()

    def _payload(self, price_fields: dict) -> dict:
        return {
            "results": [
                {
                    "name": "KMS Test Product",
                    "url": "/products/test-product",
                    "brand": "KMS",
                    **price_fields,
                }
            ]
        }

    def test_prefers_sale_or_live_over_msrp(self):
        payload = self._payload({"sale_price": 199.99, "msrp": 299.99, "regular_price": 249.99})

        result = self.connector.extract_results("test", payload)[0]

        self.assertEqual(result.price_value, 199.99)
        self.assertEqual(result.price_text, "199.99")

    def test_uses_regular_price_when_sale_missing(self):
        payload = self._payload({"regular_price": 89.5, "msrp": 99.99})

        result = self.connector.extract_results("test", payload)[0]

        self.assertEqual(result.price_value, 89.5)
        self.assertEqual(result.price_text, "89.5")

    def test_handles_malformed_text_and_falls_back_to_next_valid_candidate(self):
        payload = self._payload({"sale_price": "Call for price", "regular_price": "$149.25 CAD"})

        result = self.connector.extract_results("test", payload)[0]

        self.assertEqual(result.price_value, 149.25)
        self.assertEqual(result.price_text, "$149.25 CAD")

    def test_rejects_zero_and_negative_values(self):
        payload = self._payload({"sale_price": 0, "regular_price": -4.0, "msrp": 79.0})

        result = self.connector.extract_results("test", payload)[0]

        self.assertEqual(result.price_value, 79.0)
        self.assertEqual(result.price_text, "79.0")

    def test_extracts_model_and_manufacturer_model_from_search_payload(self):
        payload = {
            "results": [
                {
                    "name": "DEWALT FLEXVOLT Grinder",
                    "url": "/products/dcg418b",
                    "brand": "DEWALT",
                    "sale_price": 299.0,
                    "model_number": "DCG418B",
                    "attributes": {
                        "manufacturer_model": "DCG418B-CA",
                    },
                }
            ]
        }

        result = self.connector.extract_results("dcg418b", payload)[0]

        self.assertEqual(result.model, "DCG418B")
        self.assertEqual(result.manufacturer_model, "DCG418B-CA")


if __name__ == "__main__":
    unittest.main()
