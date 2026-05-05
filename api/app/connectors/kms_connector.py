from __future__ import annotations

import uuid
from collections import Counter
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote_plus

from app.connectors.http_client import get_shared_http_client
from app.connectors.secondary_api_connector import SecondaryAPIConnector
from app.models.normalized_result import NormalizedResult


@dataclass
class KMSParseStats:
    skipped_missing_title: int = 0
    skipped_missing_url: int = 0
    skipped_invalid_item_type: int = 0
    missing_price: int = 0
    missing_model: int = 0
    missing_image: int = 0
    selected_price_fields: Counter[str] = field(default_factory=Counter)
    rejected_price_fields: Counter[str] = field(default_factory=Counter)
    sample_missing_price_titles: list[str] = field(default_factory=list)
    sample_skipped_items: list[dict[str, Any]] = field(default_factory=list)

    def add_missing_price_title(self, title: str | None) -> None:
        if title and len(self.sample_missing_price_titles) < 5:
            self.sample_missing_price_titles.append(title)

    def add_skipped_item_sample(self, index: int, reason: str, item: Any) -> None:
        if len(self.sample_skipped_items) >= 5:
            return

        if isinstance(item, dict):
            sample = {
                "index": index,
                "reason": reason,
                "keys": list(item.keys())[:30],
                "title": item.get("name") or item.get("title"),
                "url": item.get("url") or item.get("link"),
                "sku": item.get("sku"),
            }
        else:
            sample = {
                "index": index,
                "reason": reason,
                "type": type(item).__name__,
            }
        self.sample_skipped_items.append(sample)


class KMSConnector(SecondaryAPIConnector):
    source = "kms_tools"
    source_label = "KMS Tools"
    source_type = "retail"
    currency = "CAD"
    site_id = "skg4w4"
    base_domain = "https://www.kmstools.com"
    min_reasonable_price = 0.01
    max_reasonable_price = 100000.0

    price_field_precedence: tuple[str, ...] = (
        "final_price",
        "finalPrice",
        "finalprice",
        "sale_price",
        "salePrice",
        "saleprice",
        "actual_price",
        "actualPrice",
        "actualprice",
        "price",
        "regular_price",
        "regularPrice",
        "regularprice",
        "price_value",
        "priceValue",
        "pricevalue",
        "map_price",
        "mapPrice",
        "mapprice",
        "msrp",
        "list_price",
        "listPrice",
        "listprice",
    )

    def build_request(self, query: str) -> dict[str, Any]:
        user_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())
        page_load_id = str(uuid.uuid4())
        domain = f"{self.base_domain}/shop.html?q={quote_plus(query)}"

        request = {
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

        self.logger.info(
            "KMS Searchspring request prepared query=%r endpoint=%s site_id=%s domain=%s",
            query,
            request["url"],
            self.site_id,
            self.base_domain,
        )
        self.logger.debug(
            "KMS Searchspring request params query=%r params=%s",
            query,
            request.get("params"),
        )

        return request

    def download_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        url = request["url"]
        return get_shared_http_client().get_json(
            url,
            params=request.get("params"),
            headers=request.get("headers"),
            timeout=request.get("timeout", self.timeout_seconds),
        )

    def extract_results(self, query: str, payload: Any) -> list[NormalizedResult]:
        items = self._extract_items(payload)
        stats = KMSParseStats()
        results: list[NormalizedResult] = []

        for index, item in enumerate(items):
            result = self._parse_item(query=query, item=item, index=index, stats=stats)
            if result is not None:
                results.append(result)

        self._log_parse_summary(query=query, item_count=len(items), results=results, stats=stats)
        return results

    def _extract_items(self, payload: Any) -> list[dict[str, Any]]:
        if not isinstance(payload, dict):
            self.logger.warning("KMS payload is not a JSON object payload_type=%s", type(payload).__name__)
            return []

        raw_items = payload.get("results")
        source_key = "results"
        if raw_items is None:
            raw_items = payload.get("products")
            source_key = "products"
        if raw_items is None:
            self.logger.warning("KMS payload missing results/products keys available_keys=%s", list(payload.keys()))
            return []
        if not isinstance(raw_items, list):
            self.logger.warning(
                "KMS payload field is not a list source_key=%s field_type=%s",
                source_key,
                type(raw_items).__name__,
            )
            return []

        items = [item for item in raw_items if isinstance(item, dict)]
        invalid_count = len(raw_items) - len(items)
        if invalid_count:
            self.logger.warning(
                "KMS payload contains non-object result items source_key=%s invalid_count=%s total_count=%s",
                source_key,
                invalid_count,
                len(raw_items),
            )

        self.logger.info("KMS Searchspring payload extracted source_key=%s item_count=%s", source_key, len(items))
        return items

    def _extract_title(self, item: dict[str, Any]) -> str | None:
        return self.normalize_ws(item.get("name") or item.get("title") or item.get("product_name") or item.get("productName"))

    def _extract_product_url(self, item: dict[str, Any]) -> str | None:
        raw_url = self.normalize_ws(item.get("url") or item.get("link") or item.get("product_url") or item.get("productUrl"))
        if not raw_url:
            return None
        if raw_url.startswith("http://") or raw_url.startswith("https://"):
            return raw_url
        if raw_url.startswith("/"):
            return f"{self.base_domain}{raw_url}"
        return f"{self.base_domain}/{raw_url}"

    def _extract_image_url(self, item: dict[str, Any]) -> str | None:
        image = self.normalize_ws(
            item.get("imageUrl")
            or item.get("image_url")
            or item.get("image")
            or item.get("thumbnail")
            or item.get("thumbnailImageUrl")
            or item.get("thumbnail_image_url")
            or item.get("largeImageUrl")
            or item.get("large_image_url")
        )
        if not image:
            images = item.get("images")
            if isinstance(images, list) and images:
                first = images[0]
                if isinstance(first, str):
                    image = self.normalize_ws(first)
                elif isinstance(first, dict):
                    image = self.normalize_ws(first.get("url") or first.get("src") or first.get("imageUrl") or first.get("image_url"))
        if not image:
            return None
        if image.startswith("//"):
            return f"https:{image}"
        if image.startswith("http://") or image.startswith("https://"):
            return image
        if image.startswith("/"):
            return f"{self.base_domain}{image}"
        return image

    def _extract_sku(self, item: dict[str, Any]) -> str | None:
        return self.normalize_ws(item.get("sku") or item.get("id") or item.get("product_id") or item.get("productId") or item.get("uid") or item.get("code") or item.get("mpn") or item.get("partNumber"))

    def _extract_brand(self, item: dict[str, Any], title: str | None) -> str | None:
        brand = self.normalize_ws(item.get("brand") or item.get("manufacturer") or item.get("vendor"))
        if brand:
            return brand
        return self.default_brand_from_title(title or "")

    def _extract_availability(self, item: dict[str, Any]) -> str | None:
        return self.normalize_ws(item.get("listing_page_text") or item.get("stockStatus") or item.get("stock_status") or item.get("availability") or item.get("inventory_status") or item.get("inventoryStatus"))

    def _format_price_text(self, price_value: float | None) -> str | None:
        if price_value is None:
            return None
        return f"${price_value:,.2f}"

    def _parse_item(self, query: str, item: dict[str, Any], index: int, stats: KMSParseStats) -> NormalizedResult | None:
        title = self._extract_title(item)
        product_url = self._extract_product_url(item)
        if not title:
            stats.skipped_missing_title += 1
            stats.add_skipped_item_sample(index=index, reason="missing_title", item=item)
            self.logger.debug("KMS item skipped missing title index=%s keys=%s", index, list(item.keys()))
            return None
        if not product_url:
            stats.skipped_missing_url += 1
            stats.add_skipped_item_sample(index=index, reason="missing_url", item=item)
            self.logger.debug("KMS item skipped missing URL index=%s title=%r keys=%s", index, title, list(item.keys()))
            return None

        sku = self._extract_sku(item)
        brand = self._extract_brand(item, title)
        image_url = self._extract_image_url(item)
        availability = self._extract_availability(item)
        model, manufacturer_model = self._extract_model_details(item)

        if not image_url:
            stats.missing_image += 1
        if not model and not manufacturer_model:
            stats.missing_model += 1

        price_decision = self._select_best_price_candidate(item)
        price_value = price_decision["price_value"]
        price_text = price_decision["price_text"] or "Price unavailable"
        raw_field = price_decision.get("raw_field")

        if raw_field:
            stats.selected_price_fields[raw_field] += 1
        else:
            stats.missing_price += 1
            stats.add_missing_price_title(title)
        for rejected_field in price_decision.get("rejected_fields") or []:
            stats.rejected_price_fields[rejected_field] += 1

        return NormalizedResult(
            source=self.source_label,
            source_type=self.source_type,
            title=title,
            price_text=price_text,
            price_value=price_value,
            currency=self.currency,
            sku=sku or None,
            model=model,
            manufacturer_model=manufacturer_model,
            brand=brand or None,
            availability=availability or "See product page",
            product_url=product_url,
            image_url=image_url,
            confidence="High" if price_value is not None else "Medium",
            score=88 if price_value is not None else 72,
            why=(
                "Parsed from KMS Searchspring search API with "
                f"price_field={raw_field or 'none'}, "
                f"model={'yes' if model else 'no'}, "
                f"manufacturer_model={'yes' if manufacturer_model else 'no'}."
            ),
        )

    def _select_best_price_candidate(self, item: dict[str, Any]) -> dict[str, Any]:
        best: dict[str, Any] | None = None
        rejected_fields: list[str] = []
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
                rejected_fields.append(field)
                self.logger.debug("KMS price candidate rejected field=%s raw=%r parsed=%r", field, raw_value, parsed_value)
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
                "price_text": self._format_price_text(best["parsed_value"]),
                "raw_field": best["field"],
                "rejected_fields": rejected_fields,
            }

        self.logger.debug(
            "KMS price unavailable no_valid_candidates payload_keys=%s rejected_fields=%s",
            list(item.keys()),
            rejected_fields,
        )
        return {"price_value": None, "price_text": None, "raw_field": None, "rejected_fields": rejected_fields}

    def _is_reasonable_price(self, value: float | None) -> bool:
        if value is None:
            return False
        return self.min_reasonable_price <= value <= self.max_reasonable_price

    def _extract_model_details(self, item: dict[str, Any]) -> tuple[str | None, str | None]:
        def _pick(*candidates: Any) -> str | None:
            for candidate in candidates:
                value = self.normalize_ws(candidate)
                if value:
                    return value
            return None

        attrs = item.get("attributes")
        if not isinstance(attrs, dict):
            attrs = {}
        mappings = item.get("mappings")
        if not isinstance(mappings, dict):
            mappings = {}
        mapping_core = mappings.get("core")
        if not isinstance(mapping_core, dict):
            mapping_core = {}

        model = _pick(
            item.get("model"), item.get("model_number"), item.get("modelNumber"), item.get("modelnumber"),
            item.get("partNumber"), item.get("part_number"), item.get("partnumber"), item.get("mpn"),
            item.get("mfg_model"), item.get("mfgModel"), item.get("manufacturerPartNumber"), item.get("manufacturer_part_number"),
            attrs.get("model"), attrs.get("model_number"), attrs.get("modelNumber"), attrs.get("modelnumber"),
            attrs.get("part_number"), attrs.get("partNumber"), attrs.get("partnumber"), attrs.get("mpn"),
            attrs.get("mfg_model"), attrs.get("mfgModel"),
            mapping_core.get("model"), mapping_core.get("model_number"), mapping_core.get("modelNumber"), mapping_core.get("modelnumber"),
        )
        manufacturer_model = _pick(
            item.get("manufacturer_model"), item.get("manufacturerModel"), item.get("manufacturer_part_number"), item.get("manufacturerPartNumber"),
            item.get("manufacturerpartnumber"), item.get("mfr_model"), item.get("mfrModel"), item.get("mfg_model"), item.get("mfgModel"),
            attrs.get("manufacturer_model"), attrs.get("manufacturerModel"), attrs.get("manufacturer_part_number"), attrs.get("manufacturerPartNumber"),
            attrs.get("manufacturerpartnumber"), attrs.get("mfr_model"), attrs.get("mfrModel"), attrs.get("mfg_model"), attrs.get("mfgModel"),
            mapping_core.get("manufacturer_model"), mapping_core.get("manufacturerModel"), mapping_core.get("manufacturer_part_number"), mapping_core.get("manufacturerPartNumber"), mapping_core.get("manufacturerpartnumber"),
        )
        return model, manufacturer_model

    def _log_parse_summary(self, query: str, item_count: int, results: list[NormalizedResult], stats: KMSParseStats) -> None:
        priced_count = sum(1 for result in results if result.price_value is not None)
        unpriced_count = len(results) - priced_count
        self.logger.info(
            "KMS parse complete query=%r payload_items=%s normalized_results=%s priced=%s unpriced=%s "
            "missing_model=%s missing_image=%s skipped_missing_title=%s skipped_missing_url=%s "
            "selected_price_fields=%s rejected_price_fields=%s sample_missing_price_titles=%s sample_skipped_items=%s",
            query,
            item_count,
            len(results),
            priced_count,
            unpriced_count,
            stats.missing_model,
            stats.missing_image,
            stats.skipped_missing_title,
            stats.skipped_missing_url,
            dict(stats.selected_price_fields),
            dict(stats.rejected_price_fields),
            stats.sample_missing_price_titles,
            stats.sample_skipped_items,
        )
