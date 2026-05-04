from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any

import requests

from app.config import settings

logger = logging.getLogger(__name__)

_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
_MAX_ATTEMPTS = 3
_BASE_BACKOFF_SECONDS = 0.5


@dataclass(frozen=True)
class ShopifyGraphQLError:
    message: str
    path: list[str | int] | None = None
    extensions: dict[str, Any] | None = None


@dataclass(frozen=True)
class ShopifyGraphQLResult:
    ok: bool
    operation_name: str
    status_code: int | None
    duration_ms: float
    data: dict[str, Any] | None
    graphql_errors: list[ShopifyGraphQLError]
    user_errors: list[dict[str, Any]]
    error: dict[str, Any] | None


class ShopifyClient:
    def __init__(self) -> None:
        self.store_domain = (settings.shopify_store_domain or "").strip()
        self.api_version = settings.shopify_api_version
        self.client_id = (settings.shopify_client_id or "").strip()
        self.client_secret = settings.shopify_client_secret

    @property
    def configured(self) -> bool:
        return bool(self.store_domain and self.api_version and self.client_id and self.client_secret)

    @property
    def endpoint(self) -> str:
        return f"https://{self.store_domain}/admin/api/{self.api_version}/graphql.json"

    def graphql(
        self,
        query: str,
        variables: dict[str, Any] | None = None,
        *,
        idempotency_key: str | None = None,
        operation_name: str | None = None,
        timeout_seconds: float = 20.0,
    ) -> ShopifyGraphQLResult:
        op_name = operation_name or self._extract_operation_name(query)
        start = time.perf_counter()

        if not self.configured:
            return ShopifyGraphQLResult(
                ok=False,
                operation_name=op_name,
                status_code=None,
                duration_ms=0.0,
                data=None,
                graphql_errors=[],
                user_errors=[],
                error={"type": "configuration_error", "message": "Shopify client is not fully configured."},
            )

        headers = {
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": self.client_secret,
            "X-Shopify-Api-Key": self.client_id,
        }
        if idempotency_key:
            headers["X-Idempotency-Key"] = idempotency_key

        payload = {"query": query, "variables": variables or {}}
        last_error: dict[str, Any] | None = None
        response: requests.Response | None = None

        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                response = requests.post(
                    self.endpoint,
                    headers=headers,
                    data=json.dumps(payload),
                    timeout=timeout_seconds,
                )
            except requests.RequestException as exc:
                last_error = {
                    "type": "network_error",
                    "message": str(exc),
                    "attempt": attempt,
                    "retryable": True,
                }
                if attempt < _MAX_ATTEMPTS:
                    time.sleep(_BASE_BACKOFF_SECONDS * (2 ** (attempt - 1)))
                    continue
                break

            if response.status_code in _RETRYABLE_STATUS_CODES and attempt < _MAX_ATTEMPTS:
                last_error = {
                    "type": "http_error",
                    "message": f"Shopify returned retryable status {response.status_code}.",
                    "attempt": attempt,
                    "retryable": True,
                    "status_code": response.status_code,
                }
                time.sleep(_BASE_BACKOFF_SECONDS * (2 ** (attempt - 1)))
                continue

            break

        duration_ms = (time.perf_counter() - start) * 1000
        masked_headers = self._masked_headers(headers)

        if response is None:
            logger.error(
                "shopify_graphql_failed operation=%s status=%s duration_ms=%.2f headers=%s error=%s",
                op_name,
                None,
                duration_ms,
                masked_headers,
                last_error,
            )
            return ShopifyGraphQLResult(
                ok=False,
                operation_name=op_name,
                status_code=None,
                duration_ms=duration_ms,
                data=None,
                graphql_errors=[],
                user_errors=[],
                error=last_error,
            )

        status_code = response.status_code
        body: dict[str, Any] = {}
        try:
            body = response.json()
        except ValueError:
            last_error = {
                "type": "parse_error",
                "message": "Shopify response was not valid JSON.",
                "status_code": status_code,
            }

        graphql_errors = [
            ShopifyGraphQLError(
                message=str(item.get("message") or "Unknown GraphQL error"),
                path=item.get("path"),
                extensions=item.get("extensions"),
            )
            for item in body.get("errors", [])
            if isinstance(item, dict)
        ]

        user_errors = self._collect_user_errors(body.get("data"))
        ok = bool(response.ok and not graphql_errors and not user_errors and last_error is None)

        if not ok and last_error is None:
            last_error = {
                "type": "graphql_or_user_error",
                "message": "Shopify returned GraphQL errors or userErrors.",
                "status_code": status_code,
            }

        logger.info(
            "shopify_graphql operation=%s status=%s duration_ms=%.2f graphql_errors=%s user_errors=%s headers=%s",
            op_name,
            status_code,
            duration_ms,
            len(graphql_errors),
            len(user_errors),
            masked_headers,
        )

        return ShopifyGraphQLResult(
            ok=ok,
            operation_name=op_name,
            status_code=status_code,
            duration_ms=duration_ms,
            data=body.get("data") if isinstance(body.get("data"), dict) else None,
            graphql_errors=graphql_errors,
            user_errors=user_errors,
            error=last_error,
        )

    @staticmethod
    def _extract_operation_name(query: str) -> str:
        text = (query or "").strip().splitlines()
        for line in text:
            line = line.strip()
            if line.startswith("mutation ") or line.startswith("query "):
                parts = line.split()
                if len(parts) >= 2:
                    return parts[1].split("(")[0].strip("{")
        return "anonymous"

    @staticmethod
    def _masked_headers(headers: dict[str, str]) -> dict[str, str]:
        masked = dict(headers)
        if "X-Shopify-Access-Token" in masked:
            masked["X-Shopify-Access-Token"] = "***"
        if "Authorization" in masked:
            masked["Authorization"] = "***"
        if "X-Shopify-Api-Key" in masked:
            masked["X-Shopify-Api-Key"] = "***"
        return masked

    @staticmethod
    def _collect_user_errors(data: Any) -> list[dict[str, Any]]:
        user_errors: list[dict[str, Any]] = []
        if not isinstance(data, dict):
            return user_errors

        stack: list[Any] = [data]
        while stack:
            current = stack.pop()
            if isinstance(current, dict):
                for key, value in current.items():
                    if key == "userErrors" and isinstance(value, list):
                        for err in value:
                            if isinstance(err, dict):
                                user_errors.append(err)
                    else:
                        stack.append(value)
            elif isinstance(current, list):
                stack.extend(current)
        return user_errors
