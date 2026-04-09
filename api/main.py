import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings

from app.routers.search import router as search_router
from app.utils.memory import get_rss_mb

logging.basicConfig(
    level=getattr(logging, settings.app_log_level, logging.INFO),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("pricesense.api")
RSS_WARNING_THRESHOLD_MB = 400.0


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield


app = FastAPI(title="PriceSense API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://probuy-frontend.onrender.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_request_memory(request: Request, call_next):
    start_ts = time.perf_counter()
    rss_start_mb = get_rss_mb()
    logger.info(
        "http_request_started",
        extra={"path": request.url.path, "method": request.method, "rss_mb": round(rss_start_mb, 2)},
    )
    if rss_start_mb >= RSS_WARNING_THRESHOLD_MB:
        logger.warning(
            "rss_threshold_exceeded_at_request_start",
            extra={"path": request.url.path, "rss_mb": round(rss_start_mb, 2), "threshold_mb": RSS_WARNING_THRESHOLD_MB},
        )

    try:
        response = await call_next(request)
    except Exception:
        rss_error_mb = get_rss_mb()
        elapsed_ms = (time.perf_counter() - start_ts) * 1000
        logger.exception(
            "http_request_failed",
            extra={
                "path": request.url.path,
                "method": request.method,
                "elapsed_ms": round(elapsed_ms, 2),
                "rss_start_mb": round(rss_start_mb, 2),
                "rss_end_mb": round(rss_error_mb, 2),
            },
        )
        if rss_error_mb >= RSS_WARNING_THRESHOLD_MB:
            logger.warning(
                "rss_threshold_exceeded_on_request_failure",
                extra={"path": request.url.path, "rss_mb": round(rss_error_mb, 2), "threshold_mb": RSS_WARNING_THRESHOLD_MB},
            )
        raise

    rss_end_mb = get_rss_mb()
    elapsed_ms = (time.perf_counter() - start_ts) * 1000
    logger.info(
        "http_request_completed",
        extra={
            "path": request.url.path,
            "method": request.method,
            "status_code": response.status_code,
            "elapsed_ms": round(elapsed_ms, 2),
            "rss_start_mb": round(rss_start_mb, 2),
            "rss_end_mb": round(rss_end_mb, 2),
        },
    )
    if rss_end_mb >= RSS_WARNING_THRESHOLD_MB:
        logger.warning(
            "rss_threshold_exceeded_at_request_end",
            extra={"path": request.url.path, "rss_mb": round(rss_end_mb, 2), "threshold_mb": RSS_WARNING_THRESHOLD_MB},
        )

    return response


@app.get("/")
def home() -> dict[str, str]:
    logger.info("Home endpoint called")
    return {"message": "PriceSense API running"}


app.include_router(search_router)
