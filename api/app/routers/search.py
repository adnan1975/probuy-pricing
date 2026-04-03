import logging

from fastapi import APIRouter, HTTPException, Path, Query

from app.models.normalized_result import (
    CatalogItem,
    ConnectorSearchRequest,
    ConnectorSearchResponse,
    SearchResponse,
)
from app.services.scn_catalog_service import SCNCatalogService
from app.services.search_service import SearchService

router = APIRouter()
search_service = SearchService()
scn_catalog_service = SCNCatalogService()
logger = logging.getLogger(__name__)


@router.get("/search", response_model=SearchResponse)
async def search(
    product: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
) -> SearchResponse:
    logger.info("Received /search request", extra={"product": product, "page": page, "page_size": page_size})
    return await search_service.search(product, page=page, page_size=page_size)


@router.get("/search/step1", response_model=SearchResponse)
async def search_step1(
    product: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
) -> SearchResponse:
    logger.info("Received /search/step1 request", extra={"product": product, "page": page, "page_size": page_size})
    response, _ = await search_service.search_step1(product, page=page, page_size=page_size)
    return response


@router.get("/search/step2", response_model=SearchResponse)
async def search_step2(product: str = Query(default="")) -> SearchResponse:
    logger.info("Received /search/step2 request", extra={"product": product})
    return await search_service.search_step2(product)


@router.post("/search/{connector_name}", response_model=ConnectorSearchResponse)
async def search_by_connector(
    payload: ConnectorSearchRequest,
    connector_name: str = Path(..., min_length=1),
) -> ConnectorSearchResponse:
    query = payload.query.strip()
    logger.info("Received /search/{connector_name} request", extra={"connector_name": connector_name, "query": query})

    connector = search_service.resolve_connector(connector_name)
    if connector is None:
        raise HTTPException(status_code=404, detail=f"Unknown connector: {connector_name}")

    try:
        results = await search_service.search_connector_with_scn_variants(connector, query)
    except Exception as exc:
        logger.error(
            "Connector search failed",
            extra={"connector": connector.source_label, "query": query},
            exc_info=(type(exc), exc, exc.__traceback__),
        )
        return ConnectorSearchResponse(
            connector=connector.source,
            query=query,
            results=[],
            error=str(exc),
            warning=getattr(connector, "last_warning", None),
        )

    return ConnectorSearchResponse(
        connector=connector.source,
        query=query,
        results=results,
        warning=getattr(connector, "last_warning", None),
    )


@router.get("/catalog/items", response_model=list[str])
async def catalog_items(limit: int = Query(default=100, ge=1, le=1000)) -> list[str]:
    logger.info("Received /catalog/items request", extra={"limit": limit})
    return scn_catalog_service.list_distinct_queries(limit=limit)


@router.get("/catalog/all-items", response_model=list[CatalogItem])
async def catalog_all_items() -> list[CatalogItem]:
    logger.info("Received /catalog/all-items request")
    items = scn_catalog_service.load_items()
    return [CatalogItem(**item.__dict__) for item in items]


@router.get("/catalog/health")
async def catalog_health() -> dict[str, str | int | bool]:
    logger.info("Received /catalog/health request")
    return scn_catalog_service.health()
