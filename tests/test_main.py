import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from io import StringIO
from rich.console import Console

import pytest

from orion import main

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


@pytest.mark.asyncio
async def test_main_one_shot_mode_calls_run_once():
    with patch.object(main.sys, "argv", ["orion", "hello"]), \
         patch.object(main.sys.stdin, "isatty", return_value=True), \
         patch("orion.main.run_once", new=AsyncMock()) as mock_run_once:
        await main.main()

    mock_run_once.assert_awaited_once_with("hello", mode="oneshot")


@pytest.mark.asyncio
async def test_main_pipe_mode_calls_streaming():
    with patch.object(main.sys, "argv", ["orion", "summarize this"]), \
         patch.object(main.sys.stdin, "isatty", return_value=False), \
         patch.object(main.sys.stdin, "read", return_value="line1\nline2\n"), \
         patch("orion.main.run_with_streaming", new=AsyncMock(return_value="OK")) as mock_stream, \
         patch("builtins.print"):
        await main.main()

    assert mock_stream.await_count == 1


@pytest.mark.asyncio
async def test_main_ctrl_c_exits_loop_gracefully():
    with patch.object(main.sys, "argv", ["orion"]), \
         patch.object(main.sys.stdin, "isatty", return_value=True), \
         patch("orion.main.show_startup"), \
         patch("orion.main.build_session", return_value=MagicMock()), \
         patch("orion.config.is_config_ready", return_value=True), \
         patch("orion.main.get_input", new=AsyncMock(side_effect=[KeyboardInterrupt()])) as mock_get_input, \
         patch("orion.main.asyncio.to_thread", new=AsyncMock(return_value=None)), \
         patch("orion.main.console.print") as mock_print:
        await main.main()

    mock_get_input.assert_awaited_once()
    assert any("interrupted" in _to_str(call.args[0]).lower() for call in mock_print.call_args_list if call.args)


@pytest.mark.asyncio
async def test_run_once_resets_confirmation_turn_state_before_agent_run():
    with patch("orion.main.safety_confirm.reset_turn_state") as mock_reset, \
         patch("orion.main.print_user"), \
         patch("orion.main.save_turn"), \
         patch("orion.main.build_context", new=AsyncMock(return_value="ctx")), \
         patch("orion.main.run_with_streaming", new=AsyncMock(return_value="ok")), \
         patch("orion.main.print_separator"):
        await main.run_once("delete ~/Downloads/hi.txt")

    mock_reset.assert_called_once()


@pytest.mark.asyncio
async def test_run_once_emits_trace_turn_start_and_end():
    with patch("orion.main.trace_logging.start_turn") as mock_turn_start, \
         patch("orion.main.trace_logging.end_turn") as mock_turn_end, \
         patch("orion.main.safety_confirm.reset_turn_state"), \
         patch("orion.main.print_user"), \
         patch("orion.main.save_turn"), \
         patch("orion.main.build_context", new=AsyncMock(return_value="ctx")), \
         patch("orion.main.run_with_streaming", new=AsyncMock(return_value="ok")), \
         patch("orion.main.print_separator"):
        await main.run_once("hello", mode="interactive")

    mock_turn_start.assert_called_once_with("hello", mode="interactive")
    mock_turn_end.assert_called_once()
    assert mock_turn_end.call_args.kwargs["status"] == "ok"


def test_on_background_scan_done_logs_failure_exception():
    class _FailingTask:
        def result(self):
            raise RuntimeError("scan failed")

    with patch("orion.main.logging.exception") as mock_exc:
        main._on_background_scan_done(_FailingTask())

    mock_exc.assert_called_once()


def test_on_background_scan_done_logs_cancelled_task():
    class _CancelledTask:
        def result(self):
            raise asyncio.CancelledError()

    with patch("orion.main.logging.debug") as mock_debug:
        main._on_background_scan_done(_CancelledTask())

    mock_debug.assert_called_once()


def test_run_background_scan_uses_dedicated_connection_and_closes():
    fake_conn = MagicMock()

    with patch("orion.main.get_connection", return_value=fake_conn), \
         patch("orion.memory.indexer.scan_home") as mock_scan:
        main._run_background_scan()

    mock_scan.assert_called_once_with(fake_conn)
    fake_conn.close.assert_called_once()


def test_run_background_scan_closes_connection_on_error():
    fake_conn = MagicMock()

    with patch("orion.main.get_connection", return_value=fake_conn), \
         patch("orion.memory.indexer.scan_home", side_effect=RuntimeError("scan failed")):
        with pytest.raises(RuntimeError):
            main._run_background_scan()

    fake_conn.close.assert_called_once()


@pytest.mark.filterwarnings("ignore:Exception ignored in.*coroutine object main")
def test_cli_entry_catches_keyboardinterrupt_and_closes_connection():
    fake_conn = MagicMock()

    def _raise_interrupt(coro):
        # We must close the coroutine to avoid "coroutine was never awaited"
        # and also ensure the event loop has a chance to settle if needed.
        coro.close()
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                pass # can't do much if it's already running
        except RuntimeError:
            pass
        raise KeyboardInterrupt()

    async def mock_main():
        pass

    with patch("orion.main.get_connection", return_value=fake_conn), \
         patch("orion.config.is_config_ready", return_value=True), \
         patch("orion.main.main", side_effect=mock_main), \
         patch("orion.main.asyncio.run", side_effect=_raise_interrupt), \
         patch("orion.main.console.print") as mock_print:
        main.cli_entry()

    fake_conn.close.assert_called_once()
    assert any("interrupted" in _to_str(call.args[0]).lower() for call in mock_print.call_args_list if call.args)
