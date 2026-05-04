from __future__ import annotations

import logging
from typing import Any

import requests
from requests import Response

from app.config import settings
from app.services.shopify.client import ShopifyClient
from app.services.shopify.product_mapper import map_product_to_product_set_input, validate_product_for_shopify
from app.services.shopify.sync_log_service import ShopifySyncLogService

logger = logging.getLogger(__name__)


class ShopifyProductService:
    def __init__(self) -> None:
        self.client = ShopifyClient()
        self.sync_logs = ShopifySyncLogService(schema="probuy")

    def publish_product_to_shopify(
        self,
        source_product_id: str,
        *,
        publish: bool,
        status: str,
        force_update: bool,
        triggered_by_user_id: str | None = None,
    ) -> dict[str, Any]:
        product = self._load_source_product(source_product_id)
        publication = self._load_or_create_publication(source_product_id)

        product_input, mapper_errors = map_product_to_product_set_input(product)
        product_input["status"] = status
        validation_errors = mapper_errors + validate_product_for_shopify(product_input)

        if validation_errors:
            error_text = "; ".join(validation_errors)
            self._update_publication(publication["id"], "NEEDS_REVIEW", error_text, publication.get("metadata") or {})
            self.sync_logs.log(
                action="SHOPIFY_PRODUCT_SET",
                status="SKIPPED",
                source_product_id=source_product_id,
                request_payload={"publish": publish, "status": status, "force_update": force_update},
                error_message=error_text,
                triggered_by_user_id=triggered_by_user_id,
            )
            return {"ok": False, "status": "NEEDS_REVIEW", "errors": validation_errors}

        metadata = publication.get("metadata") or {}
        existing_product_id = metadata.get("shopify_product_id")
        existing_handle = metadata.get("shopify_handle")

        if existing_product_id and not force_update:
            product_input["id"] = existing_product_id
        elif existing_handle:
            product_input["handle"] = existing_handle

        mutation = """
        mutation ProductSet($input: ProductSetInput!, $synchronous: Boolean!) {
          productSet(input: $input, synchronous: $synchronous) {
            product {
              id
              handle
              title
              variants(first: 1) { nodes { id sku } }
            }
            userErrors { field message }
          }
        }
        """
        variables = {"input": product_input, "synchronous": True}
        self._update_publication(publication["id"], "QUEUED", None, metadata)

        result = self.client.graphql(mutation, variables, operation_name="ProductSet")
        if not result.ok:
            err = result.error or {"message": "Unknown Shopify error"}
            all_errors = [err.get("message", "Unknown error")] + [e.message for e in result.graphql_errors]
            all_errors.extend(str(e.get("message")) for e in result.user_errors if isinstance(e, dict))
            error_text = "; ".join([e for e in all_errors if e])
            self._update_publication(publication["id"], "FAILED", error_text, metadata)
            self.sync_logs.log(
                action="SHOPIFY_PRODUCT_SET",
                status="FAILED",
                source_product_id=source_product_id,
                request_payload=variables,
                response_payload={"error": result.error, "graphql_errors": [e.message for e in result.graphql_errors], "user_errors": result.user_errors},
                error_message=error_text,
                triggered_by_user_id=triggered_by_user_id,
            )
            return {"ok": False, "status": "FAILED", "errors": all_errors}

        payload = (result.data or {}).get("productSet") or {}
        shopify_product = payload.get("product") or {}
        new_metadata = dict(metadata)
        new_metadata.update(
            {
                "shopify_product_id": shopify_product.get("id"),
                "shopify_handle": shopify_product.get("handle"),
                "shopify_variant_id": (((shopify_product.get("variants") or {}).get("nodes") or [{}])[0]).get("id"),
            }
        )
        final_status = "PUBLISHED" if publish else "QUEUED"
        self._update_publication(publication["id"], final_status, None, new_metadata)
        self.sync_logs.log(
            action="SHOPIFY_PRODUCT_SET",
            status="SUCCESS",
            source_product_id=source_product_id,
            request_payload=variables,
            response_payload=payload,
            triggered_by_user_id=triggered_by_user_id,
        )
        return {
            "ok": True,
            "status": final_status,
            "shopify_product_id": new_metadata.get("shopify_product_id"),
            "shopify_variant_id": new_metadata.get("shopify_variant_id"),
            "handle": new_metadata.get("shopify_handle"),
            "errors": [],
        }

    def _headers(self) -> dict[str, str]:
        return {
            "apikey": settings.supabase_service_role_key or "",
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
            "Accept-Profile": "probuy",
            "Content-Profile": "probuy",
            "Content-Type": "application/json",
        }


    def _request_supabase(self, method: str, endpoint: str, **kwargs: Any) -> Response:
        request_headers = dict(self._headers())
        extra_headers = kwargs.pop("headers", None) or {}
        request_headers.update(extra_headers)

        response = requests.request(method, endpoint, headers=request_headers, timeout=20, **kwargs)
        if response.status_code != 406:
            response.raise_for_status()
            return response

        fallback_headers = dict(request_headers)
        fallback_headers["Accept-Profile"] = "public"
        fallback_headers["Content-Profile"] = "public"
        fallback_response = requests.request(method, endpoint, headers=fallback_headers, timeout=20, **kwargs)
        fallback_response.raise_for_status()
        return fallback_response

    def _load_source_product(self, source_product_id: str) -> dict[str, Any]:
        endpoint = f"{settings.supabase_url}/rest/v1/source_products?id=eq.{source_product_id}&select=*"
        response = self._request_supabase("GET", endpoint)
        rows = response.json()
        if not rows:
            raise ValueError("Source product not found")
        return rows[0]

    def _load_or_create_publication(self, source_product_id: str) -> dict[str, Any]:
        endpoint = f"{settings.supabase_url}/rest/v1/product_channel_publications?source_product_id=eq.{source_product_id}&channel_code=eq.SHOPIFY&select=*"
        response = self._request_supabase("GET", endpoint)
        rows = response.json()
        if rows:
            return rows[0]
        payload = {"source_product_id": source_product_id, "channel_code": "SHOPIFY", "publication_status": "NOT_PUBLISHED", "metadata": {}}
        create = self._request_supabase("POST", f"{settings.supabase_url}/rest/v1/product_channel_publications", headers={**self._headers(), "Prefer": "return=representation"}, json=payload)
        body = create.json()
        return body[0]

    def _update_publication(self, publication_id: str, status: str, error: str | None, metadata: dict[str, Any]) -> None:
        payload = {"publication_status": status, "last_error": error, "metadata": metadata}
        endpoint = f"{settings.supabase_url}/rest/v1/product_channel_publications?id=eq.{publication_id}"
        self._request_supabase("PATCH", endpoint, json=payload)
