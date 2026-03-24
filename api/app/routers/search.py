from fastapi import APIRouter, Query

from app.models.normalized_result import SearchResponse
from app.services.scn_catalog_service import SCNCatalogService
from app.services.search_service import SearchService

router = APIRouter()
search_service = SearchService()
scn_catalog_service = SCNCatalogService()


@router.get("/search", response_model=SearchResponse)
async def search(product: str = Query(default="")) -> SearchResponse:
    return await search_service.search(product)


@router.get("/catalog/items", response_model=list[str])
async def catalog_items(limit: int = Query(default=100, ge=1, le=1000)) -> list[str]:
    return scn_catalog_service.list_distinct_queries(limit=limit)
