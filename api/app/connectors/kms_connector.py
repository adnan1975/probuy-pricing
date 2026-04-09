from __future__ import annotations

import asyncio
import uuid
from urllib.parse import quote_plus

import requests

from app.connectors.secondary_scrapy_connector import SecondaryScrapyConnector
from app.models.normalized_result import NormalizedResult


class KMSToolsConnector(SecondaryScrapyConnector):
    source = "kms_tools"
    source_label = "KMS Tools"
    source_type = "retail"
    currency = "CAD"
    site_id = "skg4w4"
    base_domain = "https://www.kmstools.com"

    async def search(self, query: str) -> list[NormalizedResult]:
        normalized_query = self.normalize_ws(query)
        if not normalized_query:
            self.last_warning = "Empty query supplied."
            self.logger.warning("KMS search skipped because query is empty")
            return []

        self.last_warning = None
        url = self._build_searchspring_url(normalized_query)

        self.logger.info("KMS Searchspring search started query=%s url=%s", normalized_query, url)

        try:
            payload = await asyncio.to_thread(self._download_json, url)

            self.logger.debug(
                "KMS Searchspring response keys=%s",
                sorted(payload.keys()) if isinstance(payload, dict) else type(payload).__name__,
            )

            results = self._extract_results_from_json(normalized_query, payload)

            if results:
                self.persist_results(normalized_query, results)
                self.logger.info(
                    "KMS Searchspring search completed query=%s results=%s",
                    normalized_query,
                    len(results),
                )
            else:
                self.last_warning = (
                    f"No results parsed from Searchspring response for query '{normalized_query}'."
                )
                self.logger.warning(
                    "KMS Searchspring search completed with no parsed results query=%s",
                    normalized_query,
                )

            return results

        except requests.RequestException as exc:
            self.last_warning = f"Network error while fetching KMS Searchspring API: {exc}"
            self.logger.exception(
                "KMS Searchspring network error query=%s error=%s",
                normalized_query,
                exc,
            )
            return []

        except Exception as exc:  # noqa: BLE001
            self.last_warning = f"Unexpected KMS Searchspring parse error: {exc}"
            self.logger.exception(
                "KMS Searchspring unexpected error query=%s error=%s",
                normalized_query,
                exc,
            )
            return []

    def _build_searchspring_url(self, query: str) -> str:
        user_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())
        page_load_id = str(uuid.uuid4())
        domain = f"{self.base_domain}/shop.html?q={quote_plus(query)}"

        return (
            f"https://{self.site_id}.a.searchspring.io/api/search/search.json"
            f"?userId={user_id}"
            f"&domain={quote_plus(domain)}"
            f"&sessionId={session_id}"
            f"&pageLoadId={page_load_id}"
            f"&siteId={self.site_id}"
            f"&bgfilter.visibility=Search"
            f"&q={quote_plus(query)}"
            f"&beacon=true"
            f"&ajaxCatalog=Snap"
            f"&resultsFormat=native"
        )

    def _download_json(self, url: str) -> dict:
        self.logger.debug("Downloading KMS Searchspring JSON url=%s", url)

        response = requests.get(
            url,
            headers={
                "User-Agent": self.user_agent,
                "Accept": "application/json, text/plain, */*",
                "Referer": self.base_domain + "/",
                "Origin": self.base_domain,
                "Accept-Language": "en-CA,en-US;q=0.9,en;q=0.8",
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()

        self.logger.debug(
            "Downloaded KMS Searchspring JSON status=%s bytes=%s",
            response.status_code,
            len(response.text),
        )

        return response.json()

    def _extract_results_from_json(self, query: str, payload: dict) -> list[NormalizedResult]:
        raw_items = payload.get("results") or payload.get("products") or []

        self.logger.debug(
            "KMS Searchspring parse query=%s raw_item_count=%s",
            query,
            len(raw_items),
        )

        results: list[NormalizedResult] = []
        seen_urls: set[str] = set()

        for idx, item in enumerate(raw_items[:20], start=1):
            title = self.normalize_ws(
                item.get("name")
                or item.get("title")
                or item.get("product_name")
            )

            product_url = self.make_absolute_url(
                self.base_domain,
                item.get("url")
                or item.get("link")
                or item.get("product_url"),
            )

            image_url = self.make_absolute_url(
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

            brand = self.normalize_ws(
                item.get("brand")
                or item.get("manufacturer")
            ) or self.default_brand_from_title(title)

            price_value = self._extract_price_value(item)
            price_text = f"${price_value:.2f}" if price_value is not None else "Price unavailable"

            self.logger.debug(
                "KMS item idx=%s title=%r sku=%r brand=%r price_value=%r product_url=%r",
                idx,
                title,
                sku,
                brand,
                price_value,
                product_url,
            )

            if not title or not product_url:
                self.logger.debug(
                    "KMS item idx=%s skipped title=%r product_url=%r",
                    idx,
                    title,
                    product_url,
                )
                continue

            if product_url in seen_urls:
                self.logger.debug("KMS item idx=%s skipped duplicate url=%s", idx, product_url)
                continue

            seen_urls.add(product_url)

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
                    availability=item.get("listing_page_text") or item.get("stockStatus") or item.get("availability") or "See product page",
                    product_url=product_url,
                    image_url=image_url,
                    confidence="High" if price_value is not None else "Medium",
                    score=88 if price_value is not None else 72,
                    why="Parsed from KMS Searchspring search API.",
                )
            )

        return results

    def _extract_price_value(self, item: dict) -> float | None:
        candidate_fields = [
            "final_price",
            "price",
            "regular_price",
            "msrp",
            "sale_price",
            "salePrice",
            "map_price",
            "mapPrice",
            "finalPrice",
            "actual_price",
            "price_value",
        ]

        for field in candidate_fields:
            raw_value = item.get(field)
            parsed = self._coerce_price(raw_value)
            if parsed is not None:
                self.logger.debug(
                    "KMS price extracted field=%s raw_value=%r parsed=%r",
                    field,
                    raw_value,
                    parsed,
                )
                return parsed

        self.logger.debug("KMS price not found for item keys=%s", sorted(item.keys()))
        return None

    def _coerce_price(self, value) -> float | None:
        if value is None or value == "":
            return None

        if isinstance(value, (int, float)):
            return float(value)

        if isinstance(value, str):
            cleaned = value.strip().replace(",", "")
            if not cleaned:
                return None

            try:
                return float(cleaned)
            except ValueError:
                return self.parse_price(cleaned)

        return None
    search_url_template = "https://www.kmstools.com/shop.html?q={query}"

    def base_url(self) -> str:
        return self.base_domain

    def listing_selector(self) -> str:
        return ""

    def title_selector(self) -> str:
        return ""

    def price_selector(self) -> str:
        return ""

    def url_selector(self) -> str:
        return ""