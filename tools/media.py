import subprocess
from tools.browser import _is_online
from tools.search import web_search_raw


async def open_media(query: str, site: str) -> str:
    """Find and open media content.

    Args:
        query: The search query for the media content.
        site: The site to search on (default: youtube.com).
    """
    if not _is_online():
        return "Offline: cannot search right now."
    try:
        results = await web_search_raw(f"{query} site:{site}", max_results=3)
        if not results:
            return f"No results found for '{query}' on {site}"
        url = results[0]["href"]
        subprocess.Popen(["xdg-open", url])
        return f"Opening: {url}"
    except Exception as e:
        return f"Error: {e}"
