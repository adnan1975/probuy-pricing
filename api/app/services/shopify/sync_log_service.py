from __future__ import annotations

from typing import Any

import requests

from app.config import settings

ALLOWED_ACTIONS = {
    "SHOPIFY_PRODUCT_SET",
    "SHOPIFY_PUBLISH",
    "SHOPIFY_INVENTORY_SYNC",
    "SHOPIFY_PRICE_SYNC",
    "SHOPIFY_PRODUCT_FETCH",
    "SHOPIFY_PUBLICATION_FETCH",
}

ALLOWED_STATUSES = {"SUCCESS", "FAILED", "SKIPPED"}


class ShopifySyncLogService:
    def __init__(self, schema: str = "probuy", table: str = "channel_sync_logs") -> None:
        self.schema = schema
        self.table = table

    def log(
        self,
        *,
        action: str,
        status: str,
        source_product_id: str | None = None,
        channel_code: str = "shopify",
        request_payload: dict[str, Any] | None = None,
        response_payload: dict[str, Any] | None = None,
        error_message: str | None = None,
        triggered_by_user_id: str | None = None,
    ) -> dict[str, Any]:
        normalized_action = action.strip().upper()
        normalized_status = status.strip().upper()
        if normalized_action not in ALLOWED_ACTIONS:
            raise ValueError(f"Unsupported sync log action: {action}")
        if normalized_status not in ALLOWED_STATUSES:
            raise ValueError(f"Unsupported sync log status: {status}")

        if not settings.supabase_url or not settings.supabase_service_role_key:
            return {"ok": False, "error": "Supabase credentials are not configured."}

        endpoint = f"{settings.supabase_url}/rest/v1/{self.table}"
        headers = {
            "apikey": settings.supabase_service_role_key,
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
            "Content-Type": "application/json",
            "Accept-Profile": self.schema,
            "Content-Profile": self.schema,
            "Prefer": "return=representation",
        }
        payload = {
            "source_product_id": source_product_id,
            "channel_code": channel_code,
            "action": normalized_action,
            "status": normalized_status,
            "request_payload": request_payload,
            "response_payload": response_payload,
            "error_message": error_message,
            "triggered_by_user_id": triggered_by_user_id,
        }

        response = requests.post(endpoint, headers=headers, json=payload, timeout=15)
        if not response.ok:
            return {
                "ok": False,
                "status_code": response.status_code,
                "error": response.text,
                "payload": payload,
            }
        body = response.json()
        return {"ok": True, "row": body[0] if isinstance(body, list) and body else body}
