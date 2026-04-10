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


@pytest.mark.asyncio
async def test_help_lists_all_commands():
    printed = []
    with patch("main.console") as mock_console:
        mock_console.print = lambda *a, **kw: printed.append(a[0] if a else "")
        await main.handle_slash("/help")
    all_text = " ".join(str(line) for line in printed)
    assert "/help" in all_text
    assert "/think" in all_text
    assert "/clear" in all_text
    assert "/exit" in all_text


@pytest.mark.asyncio
async def test_help_case_insensitive():
    printed = []
    with patch("main.console") as mock_console:
        mock_console.print = lambda *a, **kw: printed.append(a[0] if a else "")
        await main.handle_slash("/HELP")
    assert any("/think" in str(line) for line in printed)


@pytest.mark.asyncio
async def test_clear_resets_session_id():
    original_id = main.session_id
    printed = []
    try:
        with patch("main.console") as mock_console:
            mock_console.print = lambda *a, **kw: printed.append(a[0] if a else "")
            await main.handle_slash("/clear")
        assert main.session_id != original_id
        assert any("cleared" in str(line).lower() for line in printed)
    finally:
        main.session_id = original_id


@pytest.mark.asyncio
async def test_think_toggles_mode_on():
    original_agent = main.agent
    main.think_mode = False
    printed = []
    try:
        with patch("main.console") as mock_console, \
             patch("main.build_agent") as mock_build:
            mock_console.print = lambda *a, **kw: printed.append(a[0] if a else "")
            new_agent = MagicMock()
            mock_build.return_value = new_agent
            await main.handle_slash("/think")
        assert main.think_mode is True
        mock_build.assert_called_once_with(think=True)
        assert main.agent is new_agent
        assert any("on" in str(line).lower() for line in printed)
    finally:
        main.think_mode = False
        main.agent = original_agent


@pytest.mark.asyncio
async def test_think_toggles_mode_off():
    original_agent = main.agent
    main.think_mode = True
    printed = []
    try:
        with patch("main.console") as mock_console, \
             patch("main.build_agent") as mock_build:
            mock_console.print = lambda *a, **kw: printed.append(a[0] if a else "")
            new_agent = MagicMock()
            mock_build.return_value = new_agent
            await main.handle_slash("/think")
        assert main.think_mode is False
        mock_build.assert_called_once_with(think=False)
        assert main.agent is new_agent
        assert any("off" in str(line).lower() for line in printed)
    finally:
        main.think_mode = False
        main.agent = original_agent
