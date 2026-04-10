from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tools.media import open_media


@pytest.mark.asyncio
async def test_open_media_opens_first_result():
    fake_results = [
        {"title": "Test Video", "href": "https://youtube.com/watch?v=abc123", "body": ""},
        {"title": "Other Video", "href": "https://youtube.com/watch?v=xyz456", "body": ""},
    ]
    with patch("tools.media._is_online", return_value=True), \
         patch("tools.media.web_search_raw", new=AsyncMock(return_value=fake_results)), \
         patch("tools.media.subprocess.Popen") as mock_popen:
        result = await open_media("lofi beats", "youtube.com")

    assert result == "Opening: https://youtube.com/watch?v=abc123"
    mock_popen.assert_called_once_with(["xdg-open", "https://youtube.com/watch?v=abc123"])


@pytest.mark.asyncio
async def test_open_media_no_results():
    with patch("tools.media._is_online", return_value=True), \
         patch("tools.media.web_search_raw", new=AsyncMock(return_value=[])):
        result = await open_media("xyzzy nonsense query", "youtube.com")

    assert "No results" in result
    assert "xyzzy nonsense query" in result
    assert "youtube.com" in result


@pytest.mark.asyncio
async def test_open_media_offline():
    with patch("tools.media._is_online", return_value=False):
        result = await open_media("lofi beats", "youtube.com")

    assert result == "Offline: cannot search right now."
