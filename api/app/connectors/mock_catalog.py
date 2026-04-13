from app.models.normalized_result import NormalizedResult


MOCK_PRODUCTS = {
    "grinder": {
        "match_tokens": ["grinder", "dcg418b", "flexvolt"],
        "title": "DEWALT FLEXVOLT 60V MAX Grinder (Tool Only)",
        "sku": "DCG418B",
        "links": {
            "canada_welding_supply": "https://canadaweldingsupply.ca/products/dewalt-flexvolt-60v-max-angle-grinder-tool-only-dcg418b",
            "kms_tools": "https://www.kmstools.com/dewalt-flexvolt-60v-grinder-dcg418b",
            "canadian_tire": "https://www.canadiantire.ca/en/pdp/dewalt-flexvolt-grinder-dcg418b.html",
            "home_depot": "https://www.homedepot.ca/product/dewalt-flexvolt-60v-grinder/1000000001",
        },
        "prices": {
            "canada_welding_supply": 339.0,
            "kms_tools": 329.99,
            "canadian_tire": 349.99,
            "home_depot": 344.0,
        },
    },
    "glasses": {
        "match_tokens": ["sf201af", "securefit", "3m", "glasses"],
        "title": "3M SecureFit SF201AF Safety Glasses, Clear Anti-Fog",
        "sku": "SF201AF",
        "links": {
            "canada_welding_supply": "https://canadaweldingsupply.ca/products/3m-securefit-safety-glasses-sf201af",
            "kms_tools": "https://www.kmstools.com/3m-securefit-sf201af",
            "canadian_tire": "https://www.canadiantire.ca/en/pdp/3m-securefit-sf201af.html",
            "home_depot": "https://www.homedepot.ca/product/3m-securefit-sf201af/1000000002",
        },
        "prices": {
            "canada_welding_supply": 14.25,
            "kms_tools": 12.99,
            "canadian_tire": 15.49,
            "home_depot": 13.87,
        },
    },
}


def resolve_product(query: str) -> dict | None:
    normalized = query.lower()
    for product in MOCK_PRODUCTS.values():
        if any(token in normalized for token in product["match_tokens"]):
            return product
    return None


def build_mock_result(query: str, source: str, source_label: str) -> list[NormalizedResult]:
    product = resolve_product(query)
    if product is None:
        return []

    price_value = product["prices"][source]
    return [
        NormalizedResult(
            source=source_label,
            source_type="distributor" if source == "canada_welding_supply" else "retail",
            title=product["title"],
            price_text=f"${price_value:,.2f}",
            price_value=price_value,
            sku=product["sku"],
            brand=product["title"].split(" ")[0],
            availability="In Stock",
            product_url=product["links"][source],
            image_url=None,
            confidence="High",
            score=98 if source == "canada_welding_supply" else 95,
        )
    ]
