from app.models.search import SearchResult


MOCK_PRODUCTS = {
    "grinder": {
        "match_tokens": ["grinder", "dcg418b", "flexvolt"],
        "title": "DEWALT FLEXVOLT 60V MAX Grinder (Tool Only)",
        "sku": "DCG418B",
        "links": {
            "white_cap": "https://www.whitecap.com/p/dewalt-flexvolt-grinder-dcg418b",
            "kms_tools": "https://www.kmstools.com/dewalt-flexvolt-60v-grinder-dcg418b",
            "canadian_tire": "https://www.canadiantire.ca/en/pdp/dewalt-flexvolt-grinder-dcg418b.html",
            "home_depot": "https://www.homedepot.ca/product/dewalt-flexvolt-60v-grinder/1000000001",
        },
        "prices": {
            "white_cap": 339.0,
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
            "white_cap": "https://www.whitecap.com/p/3m-securefit-sf201af",
            "kms_tools": "https://www.kmstools.com/3m-securefit-sf201af",
            "canadian_tire": "https://www.canadiantire.ca/en/pdp/3m-securefit-sf201af.html",
            "home_depot": "https://www.homedepot.ca/product/3m-securefit-sf201af/1000000002",
        },
        "prices": {
            "white_cap": 14.25,
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


def build_mock_result(query: str, source: str, source_label: str) -> list[SearchResult]:
    product = resolve_product(query)
    if product is None:
        return []

    price_value = product["prices"][source]
    return [
        SearchResult(
            source=source,
            source_label=source_label,
            title=product["title"],
            sku=product["sku"],
            price=f"${price_value:,.2f}",
            price_value=price_value,
            stock="In Stock",
            link=product["links"][source],
        )
    ]
