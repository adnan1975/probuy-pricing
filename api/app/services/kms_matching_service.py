from __future__ import annotations

from app.models.normalized_result import ConnectorSearchRequest


def norm(value: str | None) -> str:
    return " ".join((value or "").strip().lower().split())


def token_overlap(left: str | None, right: str | None) -> float:
    l_tokens = set(norm(left).split())
    r_tokens = set(norm(right).split())
    if not l_tokens or not r_tokens:
        return 0.0
    common = len(l_tokens & r_tokens)
    return common / max(len(l_tokens), len(r_tokens))


def kms_match_percentage(payload: ConnectorSearchRequest, candidate) -> float:
    # source_product_id and source_code are intentionally excluded from matching as requested.
    model_expected = payload.model_number
    model_actual = max(
        token_overlap(model_expected, getattr(candidate, "model", None)),
        token_overlap(model_expected, getattr(candidate, "manufacturer_model", None)),
        token_overlap(model_expected, getattr(candidate, "sku", None)),
    )

    weighted_attributes = [
        (payload.title, getattr(candidate, "title", None), 0.35),
        (payload.brand or payload.manufacturer, getattr(candidate, "brand", None), 0.25),
        # model_number can map to model/manufacturer_model/sku depending on source catalog conventions.
        (model_expected, model_actual, 0.40),
    ]

    score = 0.0
    total_weight = 0.0
    for expected, actual, weight in weighted_attributes:
        if not norm(expected):
            continue
        total_weight += weight
        overlap = actual if isinstance(actual, float) else token_overlap(expected, actual)
        score += overlap * weight

    if total_weight == 0:
        return 0.0
    return round((score / total_weight) * 100, 2)


def kms_match_details(payload: ConnectorSearchRequest, candidate) -> tuple[float, dict[str, float]]:
    title_overlap = token_overlap(payload.title, getattr(candidate, "title", None))
    brand_overlap = token_overlap(payload.brand or payload.manufacturer, getattr(candidate, "brand", None))
    model_overlap = max(
        token_overlap(payload.model_number, getattr(candidate, "model", None)),
        token_overlap(payload.model_number, getattr(candidate, "manufacturer_model", None)),
        token_overlap(payload.model_number, getattr(candidate, "sku", None)),
    )

    weighted_score = (title_overlap * 0.35) + (brand_overlap * 0.25) + (model_overlap * 0.40)
    return round(weighted_score * 100, 2), {
        "title": round(title_overlap * 100, 2),
        "brand": round(brand_overlap * 100, 2),
        "model": round(model_overlap * 100, 2),
    }


def kms_search_queries(payload: ConnectorSearchRequest) -> list[str]:
    candidates = [
        payload.title,
        payload.brand,
        payload.manufacturer,
        payload.model_number,
        payload.query,
    ]
    deduped: list[str] = []
    seen = set()
    for value in candidates:
        normalized = (value or "").strip()
        if normalized and normalized.lower() not in seen:
            deduped.append(normalized)
            seen.add(normalized.lower())
    return deduped
