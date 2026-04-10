import pytest
from unittest.mock import patch, MagicMock
import main


@pytest.mark.asyncio
async def test_help_prints_output():
    printed = []
    with patch("main.console") as mock_console:
        mock_console.print = lambda *a, **kw: printed.append(a[0] if a else "")
        await main.handle_slash("/help")
    assert any("/think" in str(line) for line in printed)
    assert any("/clear" in str(line) for line in printed)


@pytest.mark.asyncio
async def test_unknown_command_prints_error():
    printed = []
    with patch("main.console") as mock_console:
        mock_console.print = lambda *a, **kw: printed.append(a[0] if a else "")
        await main.handle_slash("/doesnotexist")
    assert any("unknown" in str(line).lower() for line in printed)
