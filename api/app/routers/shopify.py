from __future__ import annotations

from typing import Any

import logging

from fastapi import APIRouter, Header, HTTPException, Path
from pydantic import BaseModel

from app.config import settings
from app.services.shopify.product_service import ShopifyProductService

router = APIRouter(tags=["shopify"])
logger = logging.getLogger(__name__)
service = ShopifyProductService()


class ShopifyPublishRequest(BaseModel):
    publish: bool = False
    status: str = "DRAFT"
    forceUpdate: bool = False


@router.post("/api/channels/shopify/products/{sourceProductId}/publish")
@router.post("/channels/shopify/products/{sourceProductId}/publish")
def publish_product(
    payload: ShopifyPublishRequest,
    sourceProductId: str = Path(..., min_length=1),
    x_admin_token: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
) -> dict[str, Any]:
    expected = settings.shopify_admin_token
    if expected and x_admin_token != expected:
        raise HTTPException(status_code=403, detail="Admin authorization required")

    try:
        result = service.publish_product_to_shopify(
            sourceProductId,
            publish=payload.publish,
            status=payload.status,
            force_update=payload.forceUpdate,
            triggered_by_user_id=x_user_id,
        )
    except ValueError as exc:
        logger.warning(
            "shopify_publish_not_found",
            extra={"source_product_id": sourceProductId, "status": payload.status, "publish": payload.publish},
        )
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception(
            "shopify_publish_failed",
            extra={
                "source_product_id": sourceProductId,
                "status": payload.status,
                "publish": payload.publish,
                "force_update": payload.forceUpdate,
                "triggered_by_user_id": x_user_id,
            },
        )
        raise HTTPException(status_code=500, detail="Shopify publish failed. See server logs for details.") from exc

    return {
        "source_product_id": sourceProductId,
        "status": result.get("status"),
        "ok": result.get("ok"),
        "shopify": {
            "product_id": result.get("shopify_product_id"),
            "variant_id": result.get("shopify_variant_id"),
            "handle": result.get("handle"),
        },
        "errors": result.get("errors") or [],
    }


@router.get("/api/products/{sourceProductId}")
@router.get("/products/{sourceProductId}")
def get_product(sourceProductId: str):
    service = ShopifyProductService()
    product = service._load_source_product(sourceProductId)
    return {
        **product,
        "model_number": product.get("source_model_no"),
        "source_product_key": product.get("source_product_key"),
        "sku": product.get("normalized_sku"),
        "list_price": product.get("list_price"),
    }
