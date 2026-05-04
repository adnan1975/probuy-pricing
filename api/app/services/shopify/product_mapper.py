from __future__ import annotations

import html
import logging
import re
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _slugify(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-{2,}", "-", value)
    return value.strip("-")


def _first_non_empty(*values: Any) -> str:
    for value in values:
        text = _clean_text(value)
        if text:
            return text
    return ""


def normalize_price(value: Any) -> Decimal | None:
    if value is None:
        return None
    cleaned = str(value).replace("$", "").replace(",", "").strip()
    try:
        amount = Decimal(cleaned)
    except (InvalidOperation, TypeError, ValueError):
        return None
    if amount <= 0:
        return None
    return amount




def _valid_shopify_gid(value: str) -> bool:
    text = _clean_text(value)
    return text.startswith("gid://") and len(text) > len("gid://")


def normalize_sku(product: dict[str, Any]) -> str:
    canonical = _clean_text(product.get("source_product_key"))
    if canonical:
        return canonical
    return _clean_text(product.get("source_model_no"))


def _public_https_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme != "https" or not parsed.netloc:
        return False
    host = parsed.hostname or ""
    if host in {"localhost", "127.0.0.1"}:
        return False
    if host.endswith(".local"):
        return False
    return True


def map_product_to_product_set_input(product: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    sku = normalize_sku(product) or _first_non_empty(product.get("sku"), product.get("part_number"), product.get("mpn"))
    brand = _first_non_empty(product.get("brand"), product.get("manufacturer"), "Unknown")
    title = _first_non_empty(
        product.get("title"),
        product.get("name"),
        product.get("product_name"),
        product.get("description"),
        sku,
        "Untitled Product",
    )
    handle = _first_non_empty(
        product.get("shopify_handle"),
        product.get("slug"),
        product.get("handle"),
        _slugify(f"{brand}-{sku}"),
        _slugify(title),
    )
    details = _first_non_empty(product.get("details"), product.get("description"), product.get("long_description"))
    description_html = f"<p>{html.escape(details)}</p>" if details else "<p>No description provided.</p>"

    tags = [
        _clean_text(product.get("category")),
        _clean_text(brand),
        _clean_text(product.get("source")),
    ]
    tags = [tag for tag in tags if tag]

    normalized_price = normalize_price(product.get("normalized_list_price") or product.get("price") or product.get("price_value") or product.get("list_price"))
    price = f"{normalized_price:.2f}" if normalized_price is not None else None
    normalized_cost = normalize_price(product.get("cost") or product.get("cost_price"))
    cost = f"{normalized_cost:.2f}" if normalized_cost is not None else None

    default_option_name = "Title"
    default_option_value = _first_non_empty(product.get("variant_option_value"), "Default Title")

    variant = {
        "sku": sku,
        "price": price,
        "barcode": _first_non_empty(product.get("barcode"), product.get("upc"), product.get("ean")),
        # ProductSetInput variants use optionValues; omitting this can cause hard validation failures.
        "optionValues": [
            {
                "optionName": default_option_name,
                "name": default_option_value,
            }
        ],
        "inventoryItem": {
            "cost": cost,
            "measurement": {
                "weight": {
                    "unit": _first_non_empty(product.get("weight_unit"), "KILOGRAMS").upper(),
                    "value": float(product.get("weight") or 0),
                }
            },
        },
    }

    metafields = []
    for source_key, mf_key in (
        ("package_length", "package_length"),
        ("package_width", "package_width"),
        ("package_height", "package_height"),
        ("package_weight", "package_weight"),
    ):
        raw = product.get(source_key)
        if raw is None or str(raw).strip() == "":
            continue
        metafields.append({"namespace": "custom", "key": mf_key, "type": "single_line_text_field", "value": str(raw)})

    valid_images: list[dict[str, str]] = []
    errors: list[str] = []
    for image_url in product.get("image_urls") or ([product.get("image_url")] if product.get("image_url") else []):
        cleaned = _clean_text(image_url)
        if not cleaned:
            continue
        if not _public_https_url(cleaned):
            logger.warning("Skipping non-public or non-https image URL", extra={"image_url": cleaned, "sku": sku})
            errors.append(f"Invalid image URL skipped: {cleaned}")
            continue
        valid_images.append({"src": cleaned})

    product_input = {
        "handle": handle,
        "title": title,
        "descriptionHtml": description_html,
        "vendor": brand,
        "productType": _first_non_empty(product.get("product_type"), product.get("category"), "General"),
        "tags": tags,
        "status": _first_non_empty(product.get("shopify_status"), "DRAFT"),
        "productOptions": [{"name": default_option_name, "values": [{"name": default_option_value}]}],
        "variants": [variant],
        "metafields": metafields,
        "files": valid_images,
    }

    category_gid = _first_non_empty(product.get("shopify_category_gid"), product.get("shopify_category"))
    if _valid_shopify_gid(category_gid):
        product_input["category"] = category_gid

    return product_input, errors


def validate_product_for_shopify(product_input: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    title = _clean_text(product_input.get("title"))
    variant = (product_input.get("variants") or [{}])[0]
    sku = _clean_text(variant.get("sku"))
    normalized_price = normalize_price(variant.get("price"))

    if not title:
        errors.append("Missing required title")
    if not sku:
        errors.append("Missing required SKU")
    if normalized_price is None:
        errors.append("Missing valid non-zero price")

    return errors
