import subprocess
import socket
from pathlib import Path
from safety.boundaries import validate_path


async def open_url(url: str) -> str:
    """Open a URL or local file in the default browser/app."""
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
    """Extract clean text from a web page. Full implementation in Stage 5."""
    return "fetch_page not available until Stage 5 (requires trafilatura)."


def _is_online() -> bool:
    try:
        socket.setdefaulttimeout(2)
        socket.create_connection(("8.8.8.8", 53))
        return True
    except OSError:
        return False
