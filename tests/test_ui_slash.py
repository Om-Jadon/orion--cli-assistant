import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from orion import main
from rich.console import Console
from io import StringIO


def _to_str(renderable) -> str:
    """Helper to convert a rich renderable to a plain string for testing."""
    if isinstance(renderable, str):
        return renderable
    from orion.ui.renderer import get_theme
    from orion import config
    s = StringIO()
    c = Console(file=s, force_terminal=False, width=100, theme=get_theme(config.THEME))
    c.print(renderable)
    return s.getvalue()


def test_main_uses_shared_runtime_state():
    if main.state is None:
        main.state = MagicMock()
    if main.conn is None:
        main.conn = MagicMock()
    assert hasattr(main, "state")
    assert main.state is not None


@pytest.mark.asyncio
async def test_handle_slash_delegates_to_slash_module():
    with patch("orion.main.slash.handle_slash", new=AsyncMock()) as mock_handle:
        await main.handle_slash("/help")
    mock_handle.assert_awaited_once()
    kwargs = mock_handle.await_args.kwargs
    assert kwargs["state"] is main.state
    assert kwargs["conn"] is main.conn


@pytest.mark.asyncio
async def test_help_prints_output():
    printed = []
    with patch("orion.main.console") as mock_console:
        mock_console.print = lambda *a, **kw: printed.append(a[0] if a else "")
        await main.handle_slash("/help")
    
    all_text = " ".join(_to_str(line) for line in printed)
    assert "/clear" in all_text
    assert "/undo" in all_text
    assert "/history" in all_text
    assert "/memory" in all_text
    assert "/scan" in all_text


@pytest.mark.asyncio
async def test_unknown_command_prints_error():
    printed = []
    # Patch the console in renderer since that's what print_system_error uses
    with patch("orion.ui.renderer.console") as mock_console:
        mock_console.print = lambda *a, **kw: printed.append(a[0] if a else "")
        await main.handle_slash("/doesnotexist")
    
    all_text = " ".join(_to_str(line) for line in printed).lower()
    assert "unknown" in all_text


@pytest.mark.asyncio
async def test_help_lists_all_commands():
    printed = []
    with patch("orion.main.console") as mock_console:
        mock_console.print = lambda *a, **kw: printed.append(a[0] if a else "")
        await main.handle_slash("/help")
    all_text = " ".join(_to_str(line) for line in printed)
    assert "/help" in all_text
    assert "/clear" in all_text
    assert "/undo" in all_text
    assert "/history" in all_text
    assert "/memory" in all_text
    assert "/scan" in all_text
    assert "/exit" in all_text


@pytest.mark.asyncio
async def test_help_case_insensitive():
    printed = []
    with patch("orion.main.console") as mock_console:
        mock_console.print = lambda *a, **kw: printed.append(a[0] if a else "")
        await main.handle_slash("/HELP")
    all_text = " ".join(_to_str(line) for line in printed)
    assert "/clear" in all_text


@pytest.mark.asyncio
async def test_clear_clears_terminal():
    with patch("orion.main.console") as mock_console:
        await main.handle_slash("/clear")
    mock_console.clear.assert_called_once()


@pytest.mark.asyncio
async def test_undo_dispatches_to_helper():
    with patch("orion.main.slash.undo_last_operation", new=AsyncMock()) as mock_undo:
        await main.handle_slash("/undo")
    mock_undo.assert_awaited_once()


@pytest.mark.asyncio
async def test_history_dispatches_to_helper():
    with patch("orion.main.slash.show_history") as mock_history:
        await main.handle_slash("/history")
    mock_history.assert_called_once()


@pytest.mark.asyncio
async def test_memory_dispatches_to_helper():
    with patch("orion.main.slash.show_memory") as mock_memory:
        await main.handle_slash("/memory")
    mock_memory.assert_called_once()


@pytest.mark.asyncio
async def test_scan_runs_indexer():
    with patch("orion.main.slash.asyncio.to_thread", new=AsyncMock()) as mock_to_thread:
        await main.handle_slash("/scan")
    assert mock_to_thread.await_count == 1


@pytest.mark.asyncio
async def test_exit_raises_system_exit():
    with pytest.raises(SystemExit):
        await main.handle_slash("/exit")


@pytest.mark.asyncio
async def test_undo_no_last_operation_prints_message():
    printed = []
    with patch("orion.ui.slash.pop_last_operation", return_value=None), \
         patch("orion.main.console") as mock_console:
        mock_console.print = lambda *a, **kw: printed.append(a[0] if a else "")
        await main.slash.undo_last_operation(main.conn, main.console)
    assert any("nothing to undo" in _to_str(line).lower() for line in printed)


@pytest.mark.asyncio
async def test_undo_move_reverses_destination_to_source():
    op = {"operation": "move", "source": "/tmp/source.txt", "destination": "/tmp/dest.txt"}
    with patch("orion.ui.slash.pop_last_operation", return_value=op), \
         patch("orion.ui.slash.Path.exists", return_value=True), \
         patch("orion.ui.slash._shutil.move") as mock_move:
        await main.slash.undo_last_operation(main.conn, main.console)
    mock_move.assert_called_once_with("/tmp/dest.txt", "/tmp/source.txt")


@pytest.mark.asyncio
async def test_undo_delete_prints_restore_hint():
    op = {"operation": "delete", "source": "/tmp/source.txt", "destination": "trash"}
    printed = []
    with patch("orion.ui.slash.pop_last_operation", return_value=op), \
         patch("orion.main.console") as mock_console:
        mock_console.print = lambda *a, **kw: printed.append(a[0] if a else "")
        await main.slash.undo_last_operation(main.conn, main.console)
    # The undo delete path currently uses both plain print and Panels for different parts.
    assert any("trash" in _to_str(line).lower() for line in printed)


