from app.services.shopify.product_mapper import map_product_to_product_set_input, validate_product_for_shopify


def _variant(payload):
    return payload["variants"][0]


def test_case_a_source_product_key_preferred():
    payload, errs = map_product_to_product_set_input({"source_product_key": "UQ497", "source_model_no": "493X", "list_price": 2.82, "title": "A"})
    assert not errs
    assert _variant(payload)["sku"] == "UQ497"
    assert _variant(payload)["price"] == "2.82"
    assert validate_product_for_shopify(payload) == []


def test_case_b_fallback_source_model_no():
    payload, _ = map_product_to_product_set_input({"source_product_key": "", "source_model_no": "493X", "list_price": 2.82, "title": "A"})
    assert _variant(payload)["sku"] == "493X"
    assert validate_product_for_shopify(payload) == []


def test_case_c_price_only_error_when_zero():
    payload, _ = map_product_to_product_set_input({"source_product_key": "UQ497", "list_price": 0, "title": "A"})
    assert validate_product_for_shopify(payload) == ["Missing valid non-zero price"]


def test_case_d_whitespace_sku_invalid():
    payload, _ = map_product_to_product_set_input({"source_product_key": "   ", "source_model_no": "   ", "list_price": 2.82, "title": "A"})
    assert "Missing required SKU" in validate_product_for_shopify(payload)


def test_case_f_payload_matches_validator_values():
    payload, _ = map_product_to_product_set_input({"source_product_key": "AB12", "list_price": "3.40", "title": "A"})
    variant = _variant(payload)
    assert variant["sku"] == "AB12"
    assert variant["price"] == "3.40"
    assert validate_product_for_shopify(payload) == []
