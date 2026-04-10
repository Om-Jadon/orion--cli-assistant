import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from tools.browser import fetch_page, open_url


async def test_fetch_page_offline():
    with patch("tools.browser._is_online", return_value=False):
        result = await fetch_page("https://example.com")
    assert "Offline" in result


async def test_fetch_page_extracts_text():
    with patch("tools.browser._is_online", return_value=True), \
         patch("trafilatura.fetch_url", return_value="<html>...</html>") as mock_fetch, \
         patch("trafilatura.extract", return_value="Clean article text") as mock_extract:
        result = await fetch_page("https://example.com")
    assert result == "Clean article text"
    mock_fetch.assert_called_once_with("https://example.com")
    mock_extract.assert_called_once_with("<html>...</html>")


async def test_fetch_page_no_content():
    with patch("tools.browser._is_online", return_value=True), \
         patch("trafilatura.fetch_url", return_value="<html></html>"), \
         patch("trafilatura.extract", return_value=None), \
         patch("tools.browser._playwright_extract", new=AsyncMock(return_value="Could not extract content from https://example.com")) as mock_fallback:
        result = await fetch_page("https://example.com")
    assert "Could not extract" in result
    assert "https://example.com" in result
    mock_fallback.assert_awaited_once_with("https://example.com")


async def test_fetch_page_truncates():
    long_text = "x" * 7000
    with patch("tools.browser._is_online", return_value=True), \
         patch("trafilatura.fetch_url", return_value="<html>...</html>"), \
         patch("trafilatura.extract", return_value=long_text):
        result = await fetch_page("https://example.com")
    assert len(result) <= 6000


async def test_fetch_page_fetch_error():
    with patch("tools.browser._is_online", return_value=True), \
         patch("trafilatura.fetch_url", side_effect=Exception("Network error")), \
         patch("tools.browser._playwright_extract", new=AsyncMock(return_value="Fallback content")) as mock_fallback:
        result = await fetch_page("https://example.com")
    assert result == "Fallback content"
    mock_fallback.assert_awaited_once_with("https://example.com")


async def test_fetch_page_falls_back_when_tier1_too_short():
    with patch("tools.browser._is_online", return_value=True), \
         patch("trafilatura.fetch_url", return_value="<html>...</html>"), \
         patch("trafilatura.extract", return_value="too short"), \
         patch("tools.browser._playwright_extract", new=AsyncMock(return_value="Longer fallback text")) as mock_fallback:
        result = await fetch_page("https://example.com")

    assert result == "Longer fallback text"
    mock_fallback.assert_awaited_once_with("https://example.com")


async def test_open_url_still_works():
    with tempfile.NamedTemporaryFile(dir=Path.home(), suffix=".txt", delete=False) as f:
        tmp_path = f.name
    try:
        with patch("subprocess.Popen") as mock_popen:
            result = await open_url(tmp_path)
        assert "not found" not in result.lower()
        assert "blocked" not in result.lower()
        assert Path(tmp_path).name in result
    finally:
        Path(tmp_path).unlink(missing_ok=True)
