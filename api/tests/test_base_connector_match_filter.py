from __future__ import annotations

import unittest

from app.connectors.base import BaseConnector
from app.models.normalized_result import NormalizedResult


class FakeConnector(BaseConnector):
    source = "fake"
    source_label = "Fake"
    source_type = "retail"

    async def search(self, query: str) -> list[NormalizedResult]:
        return []


class BaseConnectorMatchFilterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connector = FakeConnector()

    def test_apply_query_match_filter_keeps_only_sixty_percent_or_above(self):
        query = "dewalt flexvolt grinder"
        high_match = NormalizedResult(
            source="Fake",
            source_type="retail",
            title="DEWALT FLEXVOLT cordless grinder tool only",
            score=10,
            confidence="Low",
            why="fixture",
        )
        low_match = NormalizedResult(
            source="Fake",
            source_type="retail",
            title="Milwaukee drill combo kit",
            score=90,
            confidence="High",
            why="fixture",
        )

        kept, dropped = self.connector.apply_query_match_filter(query, [high_match, low_match])

        self.assertEqual(len(kept), 1)
        self.assertEqual(dropped, 1)
        self.assertIn("Connector-level query match", kept[0].why)
        self.assertGreaterEqual(kept[0].score, 60)


if __name__ == "__main__":
    unittest.main()
