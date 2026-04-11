import logging
import subprocess
import socket
from pathlib import Path
import trafilatura
from orion.safety.boundaries import validate_path


MAX_EXTRACT_CHARS = 6000
MIN_EXTRACT_CHARS = 10
logger = logging.getLogger(__name__)


async def open_url(url: str) -> str:
    """
    Open a web URL in the default browser, or a local file in its default app.

    Args:
        url: The full URL (e.g. 'https://example.com') or local file path to open.
    """
    if url.startswith(("http://", "https://")):
        if not _is_online():
            return "Offline: cannot open web URLs right now."
        import webbrowser
        webbrowser.open(url)
        return f"Opened: {url}"
    else:
        ok, resolved = validate_path(url)
        if not ok:
            return resolved
        if not Path(resolved).exists():
            return f"File not found: {url}"
        import webbrowser
        webbrowser.open(f"file://{resolved}")
        return f"Opened: {Path(resolved).name}"


async def fetch_page(url: str) -> str:
    """
    Extract and return the readable text content from a web page.
    Use this to read the details of a specific site after finding it via search.
    """
    if not _is_online():
        return "Offline: cannot fetch pages right now."

    # Tier 1: Fast extraction from fetched HTML
    try:
        downloaded = trafilatura.fetch_url(url)
        text = trafilatura.extract(downloaded)
        if text and len(text) >= MIN_EXTRACT_CHARS:
            return text[:MAX_EXTRACT_CHARS]
    except Exception as e:
        logger.debug("fetch_page error: %s", e)

    # Tier 2: JS-rendered fallback
    return await _playwright_extract(url)


async def _playwright_extract(url: str) -> str:
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.webkit.launch(headless=True)
            try:
                page = await browser.new_page()
                await page.goto(url, timeout=15000)
                content = await page.content()
            finally:
                await browser.close()

        text = trafilatura.extract(content)
        return text[:MAX_EXTRACT_CHARS] if text else f"Could not extract content from {url}"
    except Exception as e:
        return f"Could not fetch page: {e}"


def _is_online() -> bool:
    try:
        with socket.create_connection(("8.8.8.8", 53), timeout=2):
            pass
        return True
    except OSError:
        return False
