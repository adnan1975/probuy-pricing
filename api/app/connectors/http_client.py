from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

HttpMetricsHook = Callable[["HTTPRequestMetrics"], None]


@dataclass(frozen=True)
class HTTPRequestMetrics:
    method: str
    url: str
    status_code: int | None
    latency_ms: float
    payload_size_bytes: int


class HTTPClient:
    """Shared HTTP client with pooling, retry/backoff, and request instrumentation."""

    default_timeout: tuple[float, float] = (3.05, 10.0)

    def __init__(
        self,
        *,
        default_headers: Mapping[str, str] | None = None,
        retries: int = 3,
        backoff_factor: float = 0.5,
        status_forcelist: tuple[int, ...] = (429, 500, 502, 503, 504),
        pool_connections: int = 20,
        pool_maxsize: int = 20,
        metrics_hooks: list[HttpMetricsHook] | None = None,
    ) -> None:
        self.logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
        self.default_headers = dict(default_headers or {})
        self.metrics_hooks: list[HttpMetricsHook] = metrics_hooks or []

        retry = Retry(
            total=retries,
            connect=retries,
            read=retries,
            status=retries,
            backoff_factor=backoff_factor,
            status_forcelist=status_forcelist,
            allowed_methods=frozenset({"GET"}),
            respect_retry_after_header=True,
            raise_on_status=False,
        )
        adapter = HTTPAdapter(
            max_retries=retry,
            pool_connections=pool_connections,
            pool_maxsize=pool_maxsize,
        )

        self.session = requests.Session()
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def get(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        timeout: float | tuple[float, float] | None = None,
        metrics_hooks: list[HttpMetricsHook] | None = None,
        **kwargs: Any,
    ) -> requests.Response:
        merged_headers = dict(self.default_headers)
        if headers:
            merged_headers.update(headers)

        start = time.perf_counter()
        response: requests.Response | None = None
        try:
            response = self.session.get(
                url,
                params=params,
                headers=merged_headers or None,
                timeout=timeout or self.default_timeout,
                **kwargs,
            )
            return response
        finally:
            latency_ms = (time.perf_counter() - start) * 1000
            payload_size = len(response.content) if response is not None else 0
            metrics = HTTPRequestMetrics(
                method="GET",
                url=url,
                status_code=response.status_code if response is not None else None,
                latency_ms=latency_ms,
                payload_size_bytes=payload_size,
            )
            self._emit_metrics(metrics, metrics_hooks)

    def get_text(self, *args: Any, **kwargs: Any) -> str:
        response = self.get(*args, **kwargs)
        response.raise_for_status()
        return response.text

    def get_json(self, *args: Any, **kwargs: Any) -> Any:
        response = self.get(*args, **kwargs)
        response.raise_for_status()
        return response.json()

    def _emit_metrics(
        self,
        metrics: HTTPRequestMetrics,
        request_hooks: list[HttpMetricsHook] | None,
    ) -> None:
        self.logger.info(
            "http_request method=%s url=%s status=%s latency_ms=%.2f payload_bytes=%s",
            metrics.method,
            metrics.url,
            metrics.status_code,
            metrics.latency_ms,
            metrics.payload_size_bytes,
        )

        for hook in [*self.metrics_hooks, *(request_hooks or [])]:
            try:
                hook(metrics)
            except Exception:  # noqa: BLE001
                self.logger.exception("HTTP metrics hook raised an exception")


_shared_http_client: HTTPClient | None = None


def get_shared_http_client() -> HTTPClient:
    global _shared_http_client
    if _shared_http_client is None:
        _shared_http_client = HTTPClient(
            default_headers={
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "en-CA,en-US;q=0.9,en;q=0.8",
            }
        )
    return _shared_http_client
