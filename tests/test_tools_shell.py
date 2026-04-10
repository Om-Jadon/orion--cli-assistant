import pytest
import subprocess
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_run_shell_blocks_sudo():
    from tools.shell import run_shell
    result = await run_shell("sudo ls")
    assert "Blocked" in result


@pytest.mark.asyncio
async def test_run_shell_blocks_rm_rf():
    from tools.shell import run_shell
    result = await run_shell("rm -rf ~/important_stuff")
    assert "Blocked" in result


@pytest.mark.asyncio
async def test_run_shell_runs_safe_command():
    from tools.shell import run_shell
    result = await run_shell("echo hello")
    assert "hello" in result


@pytest.mark.asyncio
async def test_run_shell_returns_string_on_error():
    from tools.shell import run_shell
    result = await run_shell("ls /path/that/does/not/exist/orion_test")
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_run_shell_uses_to_thread_for_subprocess():
    from tools.shell import run_shell

    completed = subprocess.CompletedProcess(
        args=["echo", "hello"], returncode=0, stdout="hello\n", stderr=""
    )
    with patch("tools.shell.asyncio.to_thread", new=AsyncMock(return_value=completed)) as mock_to_thread:
        result = await run_shell("echo hello")

    assert "hello" in result
    assert mock_to_thread.await_count == 1
