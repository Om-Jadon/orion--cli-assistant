import pytest


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
