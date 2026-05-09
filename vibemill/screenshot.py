"""Playwright screenshot stage. Captures 1280x720 JPEG at quality 80
from a deployed app URL.

Per OPERATIONS.md, screenshot failure does NOT abort the app. The
orchestrator marks screenshot_status='missing' and ships anyway; the
cemetery (V1+) shows a placeholder. The app's GitHub repo and Vercel
deployment remain.

Requires the Chromium browser binary, installed once via:
    .venv/bin/playwright install chromium
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError, TimeoutError, sync_playwright

from .config import get_settings

log = logging.getLogger(__name__)

VIEWPORT_W = 1280
VIEWPORT_H = 720
JPEG_QUALITY = 80
_PAGE_LOAD_TIMEOUT_MS = 30_000
_NETWORK_IDLE_TIMEOUT_MS = 5_000


@dataclass
class ScreenshotResult:
    local_path: Path
    jpeg_bytes: bytes


def _local_dir() -> Path:
    d = get_settings().VIBEMILL_PATH / "data" / "screenshots"
    d.mkdir(parents=True, exist_ok=True)
    return d


def capture(*, app_id: str, url: str) -> ScreenshotResult:
    """Capture a screenshot of `url`. Returns the local path + raw bytes.

    Raises PlaywrightError or TimeoutError on terminal failure; the caller
    decides whether to mark screenshot_status='missing' and continue.
    """
    out_path = _local_dir() / f"{app_id}.jpg"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            context = browser.new_context(viewport={"width": VIEWPORT_W, "height": VIEWPORT_H})
            page = context.new_page()
            page.goto(url, timeout=_PAGE_LOAD_TIMEOUT_MS, wait_until="domcontentloaded")
            try:
                page.wait_for_load_state("networkidle", timeout=_NETWORK_IDLE_TIMEOUT_MS)
            except TimeoutError:
                # Some apps never reach networkidle (analytics beacons,
                # animated SVGs). The DOM is loaded; that's enough.
                log.info("screenshot %s: networkidle not reached; capturing anyway", app_id)
            jpeg = page.screenshot(type="jpeg", quality=JPEG_QUALITY, full_page=False)
        finally:
            browser.close()
    out_path.write_bytes(jpeg)
    log.info("screenshot %s: %d bytes -> %s", app_id, len(jpeg), out_path)
    return ScreenshotResult(local_path=out_path, jpeg_bytes=jpeg)
