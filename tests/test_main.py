from unittest.mock import AsyncMock, patch

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
async def test_main_init_mode_runs_scan_and_prints_done():
    lines = []

    def _capture(*args, **kwargs):
        lines.append(" ".join(str(a) for a in args))

    with patch.object(main.sys, "argv", ["orion", "--init"]), \
         patch("memory.indexer.scan_home") as mock_scan_home, \
         patch("main.asyncio.to_thread", new=AsyncMock(side_effect=lambda fn, *a: fn(*a))), \
         patch("main.console.print", side_effect=_capture):
        await main.main()

    mock_scan_home.assert_called_once()
    assert any("Done" in line for line in lines)
