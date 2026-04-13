from orion.tools.browser import _is_online
from orion.tools.search import web_search_raw


SITE_FILTERS = {
    "youtube": "site:youtube.com",
    "spotify": "site:open.spotify.com",
    "soundcloud": "site:soundcloud.com",
}


async def open_media(query: str, site: str = "youtube") -> str:
    """Find and open media content.

    Args:
        query: The search query for the media content.
        site: The site to search on (default: youtube.com).
    """
    if not _is_online():
        return "Offline: cannot search right now."
    try:
        site_filter = SITE_FILTERS.get(site, f"site:{site}")
        results = await web_search_raw(f"{query} {site_filter}", max_results=5)
        if not results:
            return f"No results found for '{query}'"

        def is_watch_url(href: str) -> bool:
            return "youtube.com/watch" in href or "youtu.be/" in href

        watch_url = next((r.get("href", "") for r in results if is_watch_url(r.get("href", ""))), None)
        url = watch_url or results[0].get("href", "")
        if not url:
            return f"No usable results found for '{query}'"

        import webbrowser
        webbrowser.open(url)
        title = next((r.get("title", url) for r in results if r.get("href", "") == url), url)
        return f"Opening: {title}\n{url}"
    except Exception as e:
        return f"Error: {e}"
