import logging

from fastapi import APIRouter, Query

from app.models.normalized_result import SearchResponse
from app.services.scn_catalog_service import SCNCatalogService
from app.services.search_service import SearchService

router = APIRouter()
search_service = SearchService()
scn_catalog_service = SCNCatalogService()
logger = logging.getLogger(__name__)


@router.get("/search", response_model=SearchResponse)
async def search(product: str = Query(default="")) -> SearchResponse:
    logger.info("Received /search request", extra={"product": product})
    return await search_service.search(product)


@router.get("/catalog/items", response_model=list[str])
async def catalog_items(limit: int = Query(default=100, ge=1, le=1000)) -> list[str]:
    logger.info("Received /catalog/items request", extra={"limit": limit})
    return scn_catalog_service.list_distinct_queries(limit=limit)


@router.get("/catalog/health")
async def catalog_health() -> dict[str, str | int | bool]:
    logger.info("Received /catalog/health request")
    return scn_catalog_service.health()
