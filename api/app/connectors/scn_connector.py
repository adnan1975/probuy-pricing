from __future__ import annotations

from app.connectors.base import BaseConnector
from app.models.normalized_result import NormalizedResult
from app.services.scn_catalog_service import SCNCatalogService


class SCNConnector(BaseConnector):
    source = "scn"
    source_label = "SCN Pricing"
    source_type = "distributor"

    def __init__(self, catalog_service: SCNCatalogService | None = None) -> None:
        self.catalog_service = catalog_service or SCNCatalogService()
        self.last_warning: str | None = None

    async def search(self, query: str) -> list[NormalizedResult]:
        items = self.catalog_service.search(query)
        self.last_warning = self.catalog_service.last_load_warning
        results: list[NormalizedResult] = []

        for item in items:
            price_value = item.list_price
            price_text = f"${price_value:,.2f}" if price_value is not None else "Price unavailable from SCN list"
            why = "Matched SCN model/description catalog."
            if price_value is None:
                why = "Matched SCN model/description catalog, but no list price value was present."

            results.append(
                NormalizedResult(
                    source=self.source_label,
                    source_type=self.source_type,
                    title=item.description,
                    price_text=price_text,
                    price_value=price_value,
                    currency="CAD",
                    sku=item.model or None,
                    brand=item.manufacturer,
                    availability="Catalog Item",
                    product_url=None,
                    image_url=None,
                    confidence="High",
                    score=88 if price_value is not None else 72,
                    why=why,
                )
            )

        self.persist_results(query, results)
        return results
