import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import main


@pytest.mark.asyncio
async def test_main_one_shot_mode_calls_run_once():
    with patch.object(main.sys, "argv", ["orion", "hello"]), \
         patch.object(main.sys.stdin, "isatty", return_value=True), \
         patch("main.run_once", new=AsyncMock()) as mock_run_once:
        await main.main()

    mock_run_once.assert_awaited_once_with("hello")


@pytest.mark.asyncio
async def test_main_pipe_mode_calls_streaming():
    with patch.object(main.sys, "argv", ["orion", "summarize this"]), \
         patch.object(main.sys.stdin, "isatty", return_value=False), \
         patch.object(main.sys.stdin, "read", return_value="line1\nline2\n"), \
         patch("main.run_with_streaming", new=AsyncMock(return_value="OK")) as mock_stream, \
         patch("builtins.print"):
        await main.main()

    assert mock_stream.await_count == 1


@pytest.mark.asyncio
async def test_run_once_resets_confirmation_turn_state_before_agent_run():
    with patch("main.safety_confirm.reset_turn_state") as mock_reset, \
         patch("main.print_user"), \
         patch("main.save_turn"), \
         patch("main.extract_and_store"), \
         patch("main.build_context", new=AsyncMock(return_value="ctx")), \
         patch("main.run_with_streaming", new=AsyncMock(return_value="ok")), \
         patch("main.print_separator"):
        await main.run_once("delete ~/Downloads/hi.txt")

    mock_reset.assert_called_once()


def test_on_background_scan_done_logs_failure_exception():
    class _FailingTask:
        def result(self):
            raise RuntimeError("scan failed")

    with patch("main.logging.exception") as mock_exc:
        main._on_background_scan_done(_FailingTask())

    mock_exc.assert_called_once()


def test_on_background_scan_done_logs_cancelled_task():
    class _CancelledTask:
        def result(self):
            raise asyncio.CancelledError()

    with patch("main.logging.debug") as mock_debug:
        main._on_background_scan_done(_CancelledTask())

    mock_debug.assert_called_once()


def test_run_background_scan_uses_dedicated_connection_and_closes():
    fake_conn = MagicMock()

    with patch("main.get_connection", return_value=fake_conn), \
         patch("memory.indexer.scan_home") as mock_scan:
        main._run_background_scan()

    mock_scan.assert_called_once_with(fake_conn)
    fake_conn.close.assert_called_once()


def test_run_background_scan_closes_connection_on_error():
    fake_conn = MagicMock()

    with patch("main.get_connection", return_value=fake_conn), \
         patch("memory.indexer.scan_home", side_effect=RuntimeError("scan failed")):
        with pytest.raises(RuntimeError):
            main._run_background_scan()

    fake_conn.close.assert_called_once()
