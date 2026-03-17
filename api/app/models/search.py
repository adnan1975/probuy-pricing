from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    source: str
    source_label: str
    title: str
    sku: str | None = None
    price: str
    price_value: float
    currency: str = "CAD"
    stock: str = "Unknown"
    link: str | None = None


class SearchAnalysis(BaseModel):
    lowest: float | None = None
    highest: float | None = None
    average: float | None = None
    source_count: int = 0


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult] = Field(default_factory=list)
    analysis: SearchAnalysis
    source_labels: list[str] = Field(default_factory=list)
