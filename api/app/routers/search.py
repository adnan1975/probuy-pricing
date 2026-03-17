from fastapi import APIRouter, Query

from app.models.search import SearchResponse
from app.services.search_service import SearchService

router = APIRouter()
search_service = SearchService()


@router.get("/search", response_model=SearchResponse)
async def search(product: str = Query(default="")) -> SearchResponse:
    return await search_service.search(product)
