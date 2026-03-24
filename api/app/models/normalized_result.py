from __future__ import annotations

from pydantic import BaseModel, Field


class NormalizedResult(BaseModel):
    source: str
    source_type: str
    title: str
    price_text: str | None = None
    price_value: float | None = None
    currency: str = "CAD"
    sku: str | None = None
    brand: str | None = None
    availability: str = "Unknown"
    product_url: str | None = None
    image_url: str | None = None
    confidence: str = "Medium"
    score: int = 0
    why: str = "Base connector match"


class SearchAnalysis(BaseModel):
    lowest_price: float | None = None
    highest_price: float | None = None
    average_price: float | None = None
    total_results: int = 0
    priced_results: int = 0
    per_source_errors: dict[str, str] = Field(default_factory=dict)


class SearchResponse(BaseModel):
    query: str
    results: list[NormalizedResult] = Field(default_factory=list)
    analysis: SearchAnalysis
    # Kept for backward compatibility while frontend consumers migrate to analysis.per_source_errors.
    per_source_errors: dict[str, str] = Field(default_factory=dict)
