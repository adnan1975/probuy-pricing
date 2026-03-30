from __future__ import annotations

import asyncio
from typing import Any

try:
    from playwright.async_api import Browser
    from playwright.async_api import Error as PlaywrightError
    from playwright.async_api import Playwright
    from playwright.async_api import async_playwright
except Exception:  # pragma: no cover - exercised in environments without playwright
    Browser = Any  # type: ignore[assignment]
    Playwright = Any  # type: ignore[assignment]
    async_playwright = None
    PlaywrightError = Exception


class PlaywrightLifecycle:
    """Process-wide Playwright runtime with one long-lived browser instance.

    Connector requests should create short-lived browser contexts from this shared browser.
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None

    @property
    def available(self) -> bool:
        return async_playwright is not None

    async def get_browser(self) -> Browser:
        if not self.available:
            raise RuntimeError("Playwright is not available in this runtime")

        async with self._lock:
            if self._browser is not None:
                return self._browser

            self._playwright = await async_playwright().start()
            # Render-compatible Chromium defaults.
            self._browser = await self._playwright.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            return self._browser

    async def shutdown(self) -> None:
        async with self._lock:
            browser = self._browser
            playwright = self._playwright
            self._browser = None
            self._playwright = None

        if browser is not None:
            try:
                await browser.close()
            except PlaywrightError:
                pass

        if playwright is not None:
            try:
                await playwright.stop()
            except PlaywrightError:
                pass


playwright_lifecycle = PlaywrightLifecycle()
