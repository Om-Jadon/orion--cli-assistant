from unittest.mock import patch, MagicMock
import pytest
from orion.tools.search import web_search, web_search_raw


MOCK_RESULTS = [
    {"title": "Example Title", "href": "https://example.com", "body": "Example body text."},
    {"title": "Another Title", "href": "https://another.com", "body": "Another body text."},
]


@pytest.mark.asyncio
async def test_web_search_returns_string():
    mock_ddgs = MagicMock()
    mock_ddgs.text.return_value = MOCK_RESULTS
    with patch("orion.tools.search._is_online", return_value=True), \
         patch("orion.tools.search.DDGS", return_value=mock_ddgs):
        result = await web_search("python tutorials")
    assert isinstance(result, str)
    assert "Example Title" in result
    assert "https://example.com" in result


@pytest.mark.asyncio
async def test_web_search_empty_results():
    mock_ddgs = MagicMock()
    mock_ddgs.text.return_value = []
    with patch("orion.tools.search._is_online", return_value=True), \
         patch("orion.tools.search.DDGS", return_value=mock_ddgs):
        result = await web_search("xyzzy nonexistent query")
    assert "No results" in result


@pytest.mark.asyncio
async def test_web_search_offline():
    with patch("orion.tools.search._is_online", return_value=False):
        result = await web_search("anything")
    assert "Offline" in result


@pytest.mark.asyncio
async def test_web_search_raw_returns_list():
    mock_ddgs = MagicMock()
    mock_ddgs.text.return_value = MOCK_RESULTS
    with patch("orion.tools.search.DDGS", return_value=mock_ddgs):
        result = await web_search_raw("python tutorials")
    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0]["title"] == "Example Title"


@pytest.mark.asyncio
async def test_web_search_raw_error():
    mock_ddgs = MagicMock()
    mock_ddgs.text.side_effect = Exception("network error")
    with patch("orion.tools.search.DDGS", return_value=mock_ddgs):
        result = await web_search_raw("anything")
    assert result == []
