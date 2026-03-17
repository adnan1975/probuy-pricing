from pydantic import BaseModel, Field, computed_field


class SearchResult(BaseModel):
    source: str
    source_type: str
    title: str
    price_text: str | None = None
    price_value: float
    currency: str = "CAD"
    sku: str | None = None
    brand: str | None = None
    availability: str = "Unknown"
    product_url: str | None = None
    image_url: str | None = None
    confidence: str = "High"
    score: int = 95

    @computed_field
    @property
    def source_label(self) -> str:
        return self.source

    @computed_field
    @property
    def price(self) -> str:
        return f"${self.price_value:,.2f}"

    @computed_field
    @property
    def stock(self) -> str:
        return self.availability

    @computed_field
    @property
    def link(self) -> str | None:
        return self.product_url


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
