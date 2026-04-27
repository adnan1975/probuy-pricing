from __future__ import annotations

import uuid
from typing import Any
from urllib.parse import quote_plus

import requests

from app.connectors.http_client import get_shared_http_client
from app.connectors.secondary_api_connector import SecondaryAPIConnector
from app.models.normalized_result import NormalizedResult


class KMSConnector(SecondaryAPIConnector):
    source = "kms_tools"
    source_label = "KMS Tools"
    source_type = "retail"
    currency = "CAD"
    site_id = "skg4w4"
    base_domain = "https://www.kmstools.com"
    min_reasonable_price = 0.01
    max_reasonable_price = 100000.0

    # Searchspring payloads can include multiple price-like fields at once.
    # We prefer live/sale values over merchandising MSRP/list anchors.
    price_field_precedence: tuple[str, ...] = (
        "final_price",
        "finalPrice",
        "sale_price",
        "salePrice",
        "actual_price",
        "price",
        "regular_price",
        "price_value",
        "map_price",
        "mapPrice",
        "msrp",
    )

    def build_request(self, query: str) -> dict[str, Any]:
        user_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())
        page_load_id = str(uuid.uuid4())
        domain = f"{self.base_domain}/shop.html?q={quote_plus(query)}"

        return {
            "url": f"https://{self.site_id}.a.searchspring.io/api/search/search.json",
            "params": {
                "userId": user_id,
                "domain": domain,
                "sessionId": session_id,
                "pageLoadId": page_load_id,
                "siteId": self.site_id,
                "bgfilter.visibility": "Search",
                "q": query,
                "beacon": "true",
                "ajaxCatalog": "Snap",
                "resultsFormat": "native",
            },
            "headers": {
                "User-Agent": self.user_agent,
                "Accept": "application/json, text/plain, */*",
                "Referer": self.base_domain + "/",
                "Origin": self.base_domain,
                "Accept-Language": "en-CA,en-US;q=0.9,en;q=0.8",
            },
            "timeout": self.timeout_seconds,
        }

    def download_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        url = request["url"]
        return get_shared_http_client().get_json(
            url,
            params=request.get("params"),
            headers=request.get("headers"),
            timeout=request.get("timeout", self.timeout_seconds),
        )

    def extract_results(self, query: str, payload: Any) -> list[NormalizedResult]:
        if not isinstance(payload, dict):
            return []

        raw_items = payload.get("results") or payload.get("products") or []
        results: list[NormalizedResult] = []

        for item in raw_items:
            if not isinstance(item, dict):
                continue

            title = self.normalize_ws(item.get("name") or item.get("title") or item.get("product_name"))
            product_url = self.normalize_url(
                self.base_domain,
                item.get("url") or item.get("link") or item.get("product_url"),
            )
            image_url = self.normalize_url(
                self.base_domain,
                item.get("imageUrl")
                or item.get("image")
                or item.get("thumbnailImageUrl")
                or item.get("thumbnail"),
            )
            sku = self.normalize_ws(
                item.get("sku")
                or item.get("code")
                or item.get("mpn")
                or item.get("partNumber")
            )
            brand = self.normalize_ws(item.get("brand") or item.get("manufacturer")) or self.default_brand_from_title(
                title
            )
            price_decision = self._select_best_price_candidate(item)
            price_value = price_decision["price_value"]
            price_text = price_decision["price_text"] or (
                f"${price_value:.2f}" if price_value is not None else "Price unavailable"
            )

            if not title or not product_url:
                continue

            results.append(
                NormalizedResult(
                    source=self.source_label,
                    source_type=self.source_type,
                    title=title,
                    price_text=price_text,
                    price_value=price_value,
                    currency=self.currency,
                    sku=sku or None,
                    brand=brand or None,
                    availability=item.get("listing_page_text")
                    or item.get("stockStatus")
                    or item.get("availability")
                    or "See product page",
                    product_url=product_url,
                    image_url=image_url,
                    confidence="High" if price_value is not None else "Medium",
                    score=88 if price_value is not None else 72,
                    why="Parsed from KMS Searchspring search API.",
                )
            )

        return results

    def _select_best_price_candidate(self, item: dict[str, Any]) -> dict[str, Any]:
        best: dict[str, Any] | None = None
        for precedence, field in enumerate(self.price_field_precedence):
            raw_value = item.get(field)
            if raw_value in (None, ""):
                continue

            parsed_value = self.coerce_price(raw_value)
            is_valid = self._is_reasonable_price(parsed_value)
            candidate = {
                "field": field,
                "precedence": precedence,
                "raw_value": raw_value,
                "parsed_value": parsed_value,
                "is_valid": is_valid,
            }

            if not is_valid:
                self.logger.debug(
                    "KMS price candidate rejected field=%s raw=%r parsed=%r",
                    field,
                    raw_value,
                    parsed_value,
                )
                continue

            if best is None or precedence < best["precedence"]:
                best = candidate

        if best is not None:
            self.logger.debug(
                "KMS selected price field=%s raw=%r parsed=%s currency=%s",
                best["field"],
                best["raw_value"],
                best["parsed_value"],
                self.currency,
            )
            return {
                "price_value": best["parsed_value"],
                "price_text": self._raw_price_text(best["raw_value"]),
                "raw_field": best["field"],
            }

        self.logger.debug("KMS price unavailable; no valid candidates in payload keys=%s", list(item.keys()))
        return {"price_value": None, "price_text": None, "raw_field": None}

    def _raw_price_text(self, raw_value: Any) -> str | None:
        if raw_value in (None, ""):
            return None
        if isinstance(raw_value, str):
            return raw_value.strip() or None
        return str(raw_value)

    def _is_reasonable_price(self, value: float | None) -> bool:
        if value is None:
            return False
        return self.min_reasonable_price <= value <= self.max_reasonable_price
