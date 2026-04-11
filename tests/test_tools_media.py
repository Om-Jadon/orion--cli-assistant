from unittest.mock import AsyncMock, patch

import pytest

from orion.tools.media import open_media


@pytest.mark.asyncio
async def test_open_media_prefers_watch_result_and_uses_default_site():
    fake_results = [
        {"title": "Channel", "href": "https://youtube.com/@example", "body": ""},
        {"title": "Test Video", "href": "https://youtube.com/watch?v=abc123", "body": ""},
    ]
    with patch("orion.tools.media._is_online", return_value=True), \
         patch("orion.tools.media.web_search_raw", new=AsyncMock(return_value=fake_results)), \
         patch("webbrowser.open") as mock_popen:
        result = await open_media("lofi beats")

    assert result == "Opening: Test Video\nhttps://youtube.com/watch?v=abc123"
    mock_popen.assert_called_once_with("https://youtube.com/watch?v=abc123")


@pytest.mark.asyncio
async def test_open_media_no_results():
    with patch("orion.tools.media._is_online", return_value=True), \
         patch("orion.tools.media.web_search_raw", new=AsyncMock(return_value=[])):
        result = await open_media("xyzzy nonsense query", "youtube.com")

    assert "No results" in result
    assert "xyzzy nonsense query" in result


@pytest.mark.asyncio
async def test_open_media_offline():
    with patch("orion.tools.media._is_online", return_value=False):
        result = await open_media("lofi beats")

    assert result == "Offline: cannot search right now."
