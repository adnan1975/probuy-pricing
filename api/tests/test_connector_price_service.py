import unittest

from app.services.connector_price_service import ConnectorPriceService


class ConnectorPriceServiceTests(unittest.TestCase):
    def test_dedupe_latest_rows_keeps_first_latest_per_connector_product(self):
        rows = [
            {
                "source": "KMS Tools",
                "sku": "SKU-1",
                "manufacturer_model": "MODEL-1",
                "title": "Sample Item",
                "price": 20.0,
                "date_created": "2026-03-31T10:00:00Z",
            },
            {
                "source": "KMS Tools",
                "sku": "SKU-1",
                "manufacturer_model": "MODEL-1",
                "title": "Sample Item",
                "price": 21.0,
                "date_created": "2026-03-31T09:00:00Z",
            },
            {
                "source": "Home Depot",
                "sku": "SKU-1",
                "manufacturer_model": "MODEL-1",
                "title": "Sample Item",
                "price": 19.0,
                "date_created": "2026-03-31T08:00:00Z",
            },
        ]

        deduped = ConnectorPriceService._dedupe_latest_rows(rows)

        self.assertEqual(len(deduped), 2)
        self.assertEqual(deduped[0]["source"], "KMS Tools")
        self.assertEqual(deduped[0]["price"], 20.0)
        self.assertEqual(deduped[1]["source"], "Home Depot")


if __name__ == "__main__":
    unittest.main()
