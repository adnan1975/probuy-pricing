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
    model: str | None = None
    manufacturer_model: str | None = None
    brand: str | None = None
    distributor_cost: float | None = None
    availability: str = "Unknown"
    location: str | None = None
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
    per_source_warnings: dict[str, str] = Field(default_factory=dict)


class SearchResponse(BaseModel):
    query: str
    results: list[NormalizedResult] = Field(default_factory=list)
    analysis: SearchAnalysis
    page: int = 1
    page_size: int = 25
    total_pages: int = 0
    total_results: int = 0
    # Kept for backward compatibility while frontend consumers migrate to analysis.per_source_errors.
    per_source_errors: dict[str, str] = Field(default_factory=dict)
    # Kept for backward compatibility while frontend consumers migrate to analysis.per_source_warnings.
    per_source_warnings: dict[str, str] = Field(default_factory=dict)


class ConnectorSearchRequest(BaseModel):
    query: str = ""


class ConnectorSearchResponse(BaseModel):
    connector: str
    query: str
    results: list[NormalizedResult] = Field(default_factory=list)
    error: str | None = None
    warning: str | None = None


class CatalogItem(BaseModel):
    model: str
    manufacturer_model: str | None = None
    description: str
    list_price: float | None = None
    distributor_cost: float | None = None
    unit: str | None = None
    manufacturer: str | None = None
