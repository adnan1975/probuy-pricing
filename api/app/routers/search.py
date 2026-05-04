import asyncio
import json
import logging

from fastapi import APIRouter, HTTPException, Path, Query
from fastapi.responses import StreamingResponse

from app.models.normalized_result import (
    AutomatedPricingJobStartResponse,
    AutomatedPricingJobStatusResponse,
    CatalogItem,
    ConnectorSearchRequest,
    ConnectorSearchResponse,
    SearchResponse,
)
from app.services.automated_pricing_service import AutomatedPricingService
from app.services.scn_catalog_service import SCNCatalogService
from app.services.search_service import SearchService

router = APIRouter()
search_service = SearchService()
scn_catalog_service = SCNCatalogService()
automated_pricing_service = AutomatedPricingService()
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




@router.get("/catalog/dashboard-stats")
async def catalog_dashboard_stats() -> dict[str, object]:
    logger.info("Received /catalog/dashboard-stats request")
    return scn_catalog_service.fetch_dashboard_stats()

@router.get("/catalog/health")
async def catalog_health() -> dict[str, str | int | bool]:
    logger.info("Received /catalog/health request")
    return scn_catalog_service.health()


@router.post("/automated-pricing/start", response_model=AutomatedPricingJobStartResponse)
async def automated_pricing_start(limit: int = Query(default=100, ge=1, le=100)) -> AutomatedPricingJobStartResponse:
    logger.info("Received /automated-pricing/start request", extra={"limit": limit})
    job = automated_pricing_service.start_job(limit=limit)
    return AutomatedPricingJobStartResponse(job_id=job.job_id, status=job.status, total_items=job.total_items)


@router.get("/automated-pricing/{job_id}", response_model=AutomatedPricingJobStatusResponse)
async def automated_pricing_status(job_id: str = Path(..., min_length=1)) -> AutomatedPricingJobStatusResponse:
    logger.info("Received /automated-pricing/{job_id} request", extra={"job_id": job_id})
    job = automated_pricing_service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return AutomatedPricingJobStatusResponse(
        job_id=job.job_id,
        status=job.status,
        total_items=job.total_items,
        processed_items=job.processed_items,
        rows=[row.__dict__ for row in job.rows],
        errors=job.errors,
    )


@router.get("/automated-pricing/{job_id}/stream")
async def automated_pricing_stream(job_id: str = Path(..., min_length=1)) -> StreamingResponse:
    logger.info("Received /automated-pricing/{job_id}/stream request", extra={"job_id": job_id})
    job = automated_pricing_service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_generator():
        last_index = 0
        while True:
            live_job = automated_pricing_service.get_job(job_id)
            if live_job is None:
                yield "event: error\ndata: Job not found\n\n"
                break

            while last_index < len(live_job.rows):
                row = live_job.rows[last_index]
                payload = json.dumps(
                    {
                        "type": "row",
                        "processed_items": live_job.processed_items,
                        "total_items": live_job.total_items,
                        "row": row.__dict__,
                    }
                )
                yield f"event: row\ndata: {payload}\n\n"
                last_index += 1

            if live_job.status == "completed":
                final_payload = json.dumps(
                    {
                        "type": "done",
                        "processed_items": live_job.processed_items,
                        "total_items": live_job.total_items,
                        "errors": live_job.errors,
                    }
                )
                yield f"event: done\ndata: {final_payload}\n\n"
                break

            await asyncio.sleep(0.4)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
