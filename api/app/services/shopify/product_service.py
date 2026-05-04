from __future__ import annotations

import logging
from typing import Any

import requests
from requests import Response

from app.config import settings
from app.services.shopify.client import ShopifyClient
from app.services.shopify.product_mapper import map_product_to_product_set_input, normalize_price, normalize_sku, validate_product_for_shopify
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
        logger.info("shopify_publish_loaded_product", extra={"source_product_id": source_product_id, "source_product_key": product.get("source_product_key"), "source_model_no": product.get("source_model_no")})
        publication = self._load_or_create_publication(source_product_id)

        product_input, mapper_errors = map_product_to_product_set_input(product)
        variant = (product_input.get("variants") or [{}])[0]
        logger.info("shopify_publish_transform", extra={"source_product_id": source_product_id, "candidate_sku_inputs": {"source_product_key": product.get("source_product_key"), "source_model_no": product.get("source_model_no"), "transformed_sku": variant.get("sku")}, "candidate_price_inputs": {"list_price_raw": product.get("list_price"), "normalized_decimal": str(normalize_price(product.get("list_price"))) if normalize_price(product.get("list_price")) is not None else None}})
        product_input["status"] = status
        validation_errors = mapper_errors + validate_product_for_shopify(product_input)
        logger.info("shopify_publish_validation", extra={"source_product_id": source_product_id, "payload_variant_sku": variant.get("sku"), "payload_variant_price": variant.get("price"), "validation_errors": validation_errors})

        if validation_errors:
            error_text = "; ".join(validation_errors)
            self._update_publication(publication, "NEEDS_REVIEW", error_text, publication.get("metadata") or {})
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
        self._update_publication(publication, "QUEUED", None, metadata)

        result = self.client.graphql(mutation, variables, operation_name="ProductSet")
        if not result.ok:
            err = result.error or {"message": "Unknown Shopify error"}
            all_errors = [err.get("message", "Unknown error")] + [e.message for e in result.graphql_errors]
            all_errors.extend(str(e.get("message")) for e in result.user_errors if isinstance(e, dict))
            error_text = "; ".join([e for e in all_errors if e])
            self._update_publication(publication, "FAILED", error_text, metadata)
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
        self._update_publication(publication, final_status, None, new_metadata)
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
        active_profile = request_headers.get("Accept-Profile", "probuy")

        response = requests.request(method, endpoint, headers=request_headers, timeout=20, **kwargs)
        if response.status_code == 406:
            logger.error("supabase_profile_not_acceptable", extra={"endpoint": endpoint, "profile": active_profile})
            raise RuntimeError(
                f"Supabase rejected profile '{active_profile}'. Ensure the schema is exposed in Supabase REST API settings."
            )

        response.raise_for_status()
        return response

    def _load_source_product(self, source_product_id: str) -> dict[str, Any]:
        endpoint = f"{settings.supabase_url}/rest/v1/source_products?id=eq.{source_product_id}&select=*"
        try:
            response = self._request_supabase("GET", endpoint)
        except requests.HTTPError as exc:
            status_code = exc.response.status_code if exc.response is not None else None
            if status_code == 404:
                body: dict[str, Any] = {}
                try:
                    body = exc.response.json() if exc.response is not None else {}
                except ValueError:
                    body = {}
                message = " ".join(str(body.get(k, "")) for k in ("message", "details", "hint")).lower()
                if "schema cache" in message or "could not find the table" in message:
                    raise RuntimeError(
                        "Supabase could not find 'source_products' in the configured 'probuy' schema profile. "
                        "Verify the table location and REST-exposed schema settings."
                    ) from exc
                raise ValueError(f"Source product not found: {source_product_id}") from exc
            raise
        rows = response.json()
        if not rows:
            raise ValueError("Source product not found")

        product = rows[0]
        latest_price = self._load_latest_price_row(source_product_id)
        if latest_price and latest_price.get("list_price") is not None:
            product["list_price"] = latest_price.get("list_price")
        product["normalized_sku"] = normalize_sku(product)
        normalized_list_price = normalize_price(product.get("list_price"))
        product["normalized_list_price"] = f"{normalized_list_price:.2f}" if normalized_list_price is not None else None
        return product

    def _load_latest_price_row(self, source_product_id: str) -> dict[str, Any] | None:
        base_endpoint = (
            f"{settings.supabase_url}/rest/v1/source_product_prices?source_product_id=eq.{source_product_id}"
            "&select=list_price,effective_at,pricing_update_date,updated_at"
        )
        endpoint = f"{base_endpoint}&order=coalesce(effective_at,pricing_update_date,updated_at).desc&limit=1"
        try:
            response = self._request_supabase("GET", endpoint)
        except requests.HTTPError as exc:
            status_code = exc.response.status_code if exc.response is not None else None
            if status_code != 400:
                raise
            # Some PostgREST/Supabase configurations reject function-based ordering.
            # Fall back to a simple timestamp sort and compute recency locally.
            fallback_endpoint = f"{base_endpoint}&order=updated_at.desc&limit=25"
            response = self._request_supabase("GET", fallback_endpoint)

        rows = response.json()
        if not rows:
            return None

        def _sort_key(row: dict[str, Any]) -> str:
            return str(row.get("effective_at") or row.get("pricing_update_date") or row.get("updated_at") or "")

        return max(rows, key=_sort_key)

    def _load_or_create_publication(self, source_product_id: str) -> dict[str, Any]:
        endpoint = f"{settings.supabase_url}/rest/v1/product_channel_publications?source_product_id=eq.{source_product_id}&select=*"
        response = self._request_supabase("GET", endpoint)
        rows = response.json()
        if rows:
            for row in rows:
                if str(row.get("channel_code") or "").upper() == "SHOPIFY":
                    return row
            return rows[0]

        payload = {"source_product_id": source_product_id, "channel_code": "SHOPIFY", "publication_status": "NOT_PUBLISHED", "metadata": {}}
        endpoint = f"{settings.supabase_url}/rest/v1/product_channel_publications"
        try:
            create = self._request_supabase("POST", endpoint, headers={**self._headers(), "Prefer": "return=representation"}, json=payload)
        except requests.HTTPError as exc:
            status_code = exc.response.status_code if exc.response is not None else None
            body_text = (exc.response.text if exc.response is not None else "").lower()
            if status_code == 400 and "channel_code" in body_text:
                legacy_payload = {"source_product_id": source_product_id, "publication_status": "NOT_PUBLISHED", "metadata": {}}
                create = self._request_supabase("POST", endpoint, headers={**self._headers(), "Prefer": "return=representation"}, json=legacy_payload)
            else:
                raise
        body = create.json()
        return body[0]

    def _update_publication(self, publication: dict[str, Any], status: str, error: str | None, metadata: dict[str, Any]) -> None:
        publication_id = str(publication.get("id") or "")
        if not publication_id:
            logger.warning("shopify_publication_update_skipped_missing_id")
            return

        available_fields = set(publication.keys())
        payload: dict[str, Any] = {}
        if "publication_status" in available_fields:
            payload["publication_status"] = status
        if "last_error" in available_fields:
            payload["last_error"] = error
        if "metadata" in available_fields:
            payload["metadata"] = metadata
        if not payload:
            logger.warning("shopify_publication_update_skipped_no_mutable_columns", extra={"publication_id": publication_id})
            return

        endpoint = f"{settings.supabase_url}/rest/v1/product_channel_publications?id=eq.{publication_id}"
        try:
            self._request_supabase("PATCH", endpoint, json=payload)
        except requests.HTTPError as exc:
            status_code = exc.response.status_code if exc.response is not None else None
            body_text = (exc.response.text if exc.response is not None else "").lower()
            if status_code == 400:
                # Legacy schemas can miss last_error/metadata columns; retry with status-only patch.
                status_only_payload = {"publication_status": status}
                try:
                    self._request_supabase("PATCH", endpoint, json=status_only_payload)
                    logger.warning("shopify_publication_update_legacy_fallback", extra={"publication_id": publication_id, "status": status})
                except Exception:
                    logger.warning("shopify_publication_update_legacy_fallback_failed", extra={"publication_id": publication_id, "status": status})
                return
            logger.warning(
                "shopify_publication_update_failed",
                extra={"publication_id": publication_id, "status": status, "status_code": status_code, "error": body_text[:300]},
            )
