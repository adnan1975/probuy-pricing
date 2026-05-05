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
        self.assertEqual(result.price_text, "$199.99")

    def test_uses_regular_price_when_sale_missing(self):
        payload = self._payload({"regular_price": 89.5, "msrp": 99.99})
        result = self.connector.extract_results("test", payload)[0]
        self.assertEqual(result.price_value, 89.5)
        self.assertEqual(result.price_text, "$89.50")

    def test_handles_malformed_text_and_falls_back_to_next_valid_candidate(self):
        payload = self._payload({"sale_price": "Call for price", "regular_price": "$149.25 CAD"})
        result = self.connector.extract_results("test", payload)[0]
        self.assertEqual(result.price_value, 149.25)
        self.assertEqual(result.price_text, "$149.25")

    def test_rejects_zero_and_negative_values(self):
        payload = self._payload({"sale_price": 0, "regular_price": -4.0, "msrp": 79.0})
        result = self.connector.extract_results("test", payload)[0]
        self.assertEqual(result.price_value, 79.0)
        self.assertEqual(result.price_text, "$79.00")

    def test_accepts_lowercase_finalprice_field(self):
        result = self.connector.extract_results("test", self._payload({"finalprice": "$199.99"}))[0]
        self.assertEqual(result.price_value, 199.99)
        self.assertEqual(result.price_text, "$199.99")

    def test_accepts_lowercase_saleprice_field(self):
        result = self.connector.extract_results("test", self._payload({"saleprice": "$149.50"}))[0]
        self.assertEqual(result.price_value, 149.5)
        self.assertEqual(result.price_text, "$149.50")

    def test_accepts_lowercase_regularprice_field(self):
        result = self.connector.extract_results("test", self._payload({"regularprice": "$89.00"}))[0]
        self.assertEqual(result.price_value, 89.0)
        self.assertEqual(result.price_text, "$89.00")

    def test_extracts_results_from_products_key(self):
        payload = {"products": [{"name": "KMS Test Product", "url": "/products/test-product", "brand": "KMS", "finalprice": "$99.99"}]}
        result = self.connector.extract_results("test", payload)[0]
        self.assertEqual(result.title, "KMS Test Product")
        self.assertEqual(result.price_value, 99.99)

    def test_returns_empty_results_for_missing_results_and_products(self):
        self.assertEqual(self.connector.extract_results("test", {"pagination": {"totalResults": 0}}), [])

    def test_skips_item_missing_title(self):
        payload = {"results": [{"url": "/products/test-product", "brand": "KMS", "finalprice": "$99.99"}]}
        self.assertEqual(self.connector.extract_results("test", payload), [])

    def test_skips_item_missing_url(self):
        payload = {"results": [{"name": "KMS Test Product", "brand": "KMS", "finalprice": "$99.99"}]}
        self.assertEqual(self.connector.extract_results("test", payload), [])

    def test_extracts_model_from_nested_attributes_modelnumber(self):
        payload = {"results": [{"name": "DEWALT FLEXVOLT Grinder", "url": "/products/dcg418b", "brand": "DEWALT", "finalprice": "$299.99", "attributes": {"modelNumber": "DCG418B", "manufacturerPartNumber": "DCG418B-CA"}}]}
        result = self.connector.extract_results("dcg418b", payload)[0]
        self.assertEqual(result.model, "DCG418B")
        self.assertEqual(result.manufacturer_model, "DCG418B-CA")

    def test_extracts_model_from_mappings_core(self):
        payload = {"results": [{"name": "DEWALT FLEXVOLT Grinder", "url": "/products/dcg418b", "brand": "DEWALT", "finalprice": "$299.99", "mappings": {"core": {"modelnumber": "DCG418B", "manufacturerpartnumber": "DCG418B-CA"}}}]}
        result = self.connector.extract_results("dcg418b", payload)[0]
        self.assertEqual(result.model, "DCG418B")
        self.assertEqual(result.manufacturer_model, "DCG418B-CA")

    def test_extracts_image_from_image_url(self):
        payload = {"results": [{"name": "KMS Test Product", "url": "/products/test-product", "brand": "KMS", "finalprice": "$99.99", "imageUrl": "//cdn.example.com/test.jpg"}]}
        result = self.connector.extract_results("test", payload)[0]
        self.assertEqual(result.image_url, "https://cdn.example.com/test.jpg")

    def test_extracts_image_from_images_list(self):
        payload = {"results": [{"name": "KMS Test Product", "url": "/products/test-product", "brand": "KMS", "finalprice": "$99.99", "images": [{"url": "https://cdn.example.com/test.jpg"}]}]}
        result = self.connector.extract_results("test", payload)[0]
        self.assertEqual(result.image_url, "https://cdn.example.com/test.jpg")


if __name__ == "__main__":
    unittest.main()
