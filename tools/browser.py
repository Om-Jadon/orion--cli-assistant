import subprocess
import socket
from pathlib import Path
import trafilatura
from safety.boundaries import validate_path


async def open_url(url: str) -> str:
    """
    Open a web URL in the default browser, or a local file in its default app.

    Args:
        url: The full URL (e.g. 'https://example.com') or local file path to open.
    """
    if url.startswith(("http://", "https://")):
        if not _is_online():
            return "Offline: cannot open web URLs right now."
        subprocess.Popen(["xdg-open", url])
        return f"Opened: {url}"
    else:
        ok, resolved = validate_path(url)
        if not ok:
            return resolved
        if not Path(resolved).exists():
            return f"File not found: {url}"
        subprocess.Popen(["xdg-open", resolved])
        return f"Opened: {Path(resolved).name}"


async def fetch_page(url: str) -> str:
    """Extract clean text from a web page using trafilatura."""
    if not _is_online():
        return "Offline: cannot fetch pages right now."
    try:
        downloaded = trafilatura.fetch_url(url)
        text = trafilatura.extract(downloaded)
        if not text:
            return f"Could not extract content from {url}"
        return text[:4000]
    except Exception as e:
        return f"Error fetching {url}: {e}"


def _is_online() -> bool:
    try:
        socket.setdefaulttimeout(2)
        socket.create_connection(("8.8.8.8", 53))
        return True
    except OSError:
        return False
