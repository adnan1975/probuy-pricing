from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Path
from pydantic import BaseModel

from app.config import settings
from app.services.shopify.product_service import ShopifyProductService

router = APIRouter(tags=["shopify"])
service = ShopifyProductService()


class ShopifyPublishRequest(BaseModel):
    publish: bool = False
    status: str = "DRAFT"
    forceUpdate: bool = False




@router.get("/api/channels/shopify/products/{sourceProductId}/publish")
@router.get("/channels/shopify/products/{sourceProductId}/publish")
@router.get("/api/api/channels/shopify/products/{sourceProductId}/publish")
def publish_product_help(sourceProductId: str = Path(..., min_length=1)) -> dict[str, str]:
    return {
        "detail": "Use POST with JSON body to publish product to Shopify",
        "source_product_id": sourceProductId,
    }


@router.post("/api/channels/shopify/products/{sourceProductId}/publish")
@router.post("/channels/shopify/products/{sourceProductId}/publish")
@router.post("/api/api/channels/shopify/products/{sourceProductId}/publish")
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
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Shopify publish failed: {exc}") from exc

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
