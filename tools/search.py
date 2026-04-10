import asyncio

from duckduckgo_search import DDGS
from tools.browser import _is_online


async def web_search(query: str, max_results: int = 5) -> str:
    """Search the web via DuckDuckGo and return formatted markdown results."""
    if not _is_online():
        return "Offline: cannot search right now."

    max_results = min(max_results, 10)

    try:
        results = await asyncio.to_thread(lambda: list(DDGS().text(query, max_results=max_results)))
        if not results:
            return f"No results found for '{query}'"
        lines = []
        for r in results:
            title = r.get("title", "")
            url = r.get("href", "")
            body = r.get("body", "")
            lines.append(f"**{title}**\n{url}\n{body}\n")
        return "\n".join(lines)
    except Exception as e:
        return f"Search error: {e}"


async def web_search_raw(query: str, max_results: int = 5) -> list[dict]:
    """Return raw DuckDuckGo search results. Used internally by open_media."""
    max_results = min(max_results, 10)
    try:
        return await asyncio.to_thread(lambda: list(DDGS().text(query, max_results=max_results)))
    except Exception:
        return []
