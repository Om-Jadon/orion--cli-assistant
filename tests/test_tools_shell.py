import pytest
import subprocess
from unittest.mock import AsyncMock, patch
from safety.confirm import ConfirmationResult


def _shell_confirm(decision: str, *, command: str, repeated_denial: bool = False) -> ConfirmationResult:
    return ConfirmationResult(
        decision=decision,
        scope="shell",
        action="run",
        command=command,
        repeated_denial=repeated_denial,
    )


@pytest.mark.asyncio
async def test_run_shell_blocks_sudo():
    from tools.shell import run_shell
    with patch(
        "safety.confirm.ask_command_confirmation",
        new=AsyncMock(return_value=_shell_confirm("confirmed", command="sudo ls")),
    ) as mock_confirm:
        result = await run_shell("sudo ls")
    assert "Blocked" in result
    mock_confirm.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_shell_blocks_rm_rf():
    from tools.shell import run_shell
    with patch(
        "safety.confirm.ask_command_confirmation",
        new=AsyncMock(return_value=_shell_confirm("confirmed", command="rm -rf ~/important_stuff")),
    ) as mock_confirm:
        result = await run_shell("rm -rf ~/important_stuff")
    assert "Blocked" in result
    mock_confirm.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_shell_runs_safe_command():
    from tools.shell import run_shell
    with patch(
        "safety.confirm.ask_command_confirmation",
        new=AsyncMock(return_value=_shell_confirm("confirmed", command="echo hello")),
    ) as mock_confirm:
        result = await run_shell("echo hello")
    assert "hello" in result
    mock_confirm.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_shell_copy_command_does_not_prompt_confirmation():
    from tools.shell import run_shell

    completed = subprocess.CompletedProcess(
        args=["cp", "a", "b"], returncode=0, stdout="", stderr=""
    )
    with patch(
        "safety.confirm.ask_command_confirmation",
        new=AsyncMock(return_value=_shell_confirm("confirmed", command="cp ~/a.txt ~/b.txt")),
    ) as mock_confirm, \
         patch("tools.shell.asyncio.to_thread", new=AsyncMock(return_value=completed)) as mock_to_thread:
        result = await run_shell("cp ~/a.txt ~/b.txt")

    assert result == "(no output)"
    mock_confirm.assert_not_awaited()
    assert mock_to_thread.await_count == 1


@pytest.mark.asyncio
async def test_run_shell_quoted_separator_text_does_not_prompt_confirmation():
    from tools.shell import run_shell

    completed = subprocess.CompletedProcess(
        args=["echo"], returncode=0, stdout="ok", stderr=""
    )
    with patch(
        "safety.confirm.ask_command_confirmation",
        new=AsyncMock(return_value=_shell_confirm("confirmed", command="echo 'hello && goodbye'")),
    ) as mock_confirm, \
         patch("tools.shell.asyncio.to_thread", new=AsyncMock(return_value=completed)) as mock_to_thread:
        result = await run_shell("echo 'hello && goodbye'")

    assert "ok" in result
    mock_confirm.assert_not_awaited()
    assert mock_to_thread.await_count == 1


@pytest.mark.asyncio
async def test_run_shell_quoted_redirection_text_does_not_prompt_confirmation():
    from tools.shell import run_shell

    completed = subprocess.CompletedProcess(
        args=["echo"], returncode=0, stdout="ok", stderr=""
    )
    with patch(
        "safety.confirm.ask_command_confirmation",
        new=AsyncMock(return_value=_shell_confirm("confirmed", command="echo 'value > file'")),
    ) as mock_confirm, \
         patch("tools.shell.asyncio.to_thread", new=AsyncMock(return_value=completed)) as mock_to_thread:
        result = await run_shell("echo 'value > file'")

    assert "ok" in result
    mock_confirm.assert_not_awaited()
    assert mock_to_thread.await_count == 1


@pytest.mark.asyncio
async def test_run_shell_returns_string_on_error():
    from tools.shell import run_shell
    with patch(
        "safety.confirm.ask_command_confirmation",
        new=AsyncMock(return_value=_shell_confirm("confirmed", command="ls /path/that/does/not/exist/orion_test")),
    ) as mock_confirm:
        result = await run_shell("ls /path/that/does/not/exist/orion_test")
    assert isinstance(result, str)
    assert len(result) > 0
    mock_confirm.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_shell_uses_to_thread_for_subprocess():
    from tools.shell import run_shell

    completed = subprocess.CompletedProcess(
        args=["echo", "hello"], returncode=0, stdout="hello\n", stderr=""
    )
    with patch(
        "safety.confirm.ask_command_confirmation",
        new=AsyncMock(return_value=_shell_confirm("confirmed", command="echo hello")),
    ) as mock_confirm, \
         patch("tools.shell.asyncio.to_thread", new=AsyncMock(return_value=completed)) as mock_to_thread:
        result = await run_shell("echo hello")

    assert "hello" in result
    assert mock_to_thread.await_count == 1
    mock_confirm.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_shell_cancelled_when_not_confirmed():
    from tools.shell import run_shell

    command = "mv ~/a.txt ~/b.txt"
    with patch(
        "safety.confirm.ask_command_confirmation",
        new=AsyncMock(return_value=_shell_confirm("denied", command=command)),
    ) as mock_confirm, \
         patch("tools.shell.asyncio.to_thread", new=AsyncMock()) as mock_to_thread:
        result = await run_shell(command)

    assert "Shell command cancelled by user confirmation." in result
    mock_confirm.assert_awaited_once()
    mock_to_thread.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_shell_destructive_command_prompts_confirmation():
    from tools.shell import run_shell

    completed = subprocess.CompletedProcess(
        args=["mv", "a", "b"], returncode=0, stdout="", stderr=""
    )
    with patch(
        "safety.confirm.ask_command_confirmation",
        new=AsyncMock(return_value=_shell_confirm("confirmed", command="mv ~/a.txt ~/b.txt")),
    ) as mock_confirm, \
         patch("tools.shell.asyncio.to_thread", new=AsyncMock(return_value=completed)) as mock_to_thread:
        result = await run_shell("mv ~/a.txt ~/b.txt")

    assert result == "(no output)"
    mock_confirm.assert_awaited_once()
    assert mock_to_thread.await_count == 1


@pytest.mark.asyncio
async def test_run_shell_git_force_push_prompts_confirmation():
    from tools.shell import run_shell

    completed = subprocess.CompletedProcess(
        args=["git", "push"], returncode=0, stdout="", stderr=""
    )
    with patch(
        "safety.confirm.ask_command_confirmation",
        new=AsyncMock(return_value=_shell_confirm("confirmed", command="git push --force")),
    ) as mock_confirm, \
         patch("tools.shell.asyncio.to_thread", new=AsyncMock(return_value=completed)) as mock_to_thread:
        result = await run_shell("git push --force")

    assert result == "(no output)"
    mock_confirm.assert_awaited_once()
    assert mock_to_thread.await_count == 1


@pytest.mark.asyncio
async def test_run_shell_curl_post_prompts_confirmation():
    from tools.shell import run_shell

    completed = subprocess.CompletedProcess(
        args=["curl"], returncode=0, stdout="ok", stderr=""
    )
    with patch(
        "safety.confirm.ask_command_confirmation",
        new=AsyncMock(return_value=_shell_confirm("confirmed", command="curl -X POST https://example.com/api -d '{}' ")),
    ) as mock_confirm, \
         patch("tools.shell.asyncio.to_thread", new=AsyncMock(return_value=completed)) as mock_to_thread:
        result = await run_shell("curl -X POST https://example.com/api -d '{}' ")

    assert "ok" in result
    mock_confirm.assert_awaited_once()
    assert mock_to_thread.await_count == 1


@pytest.mark.asyncio
async def test_run_shell_curl_get_does_not_prompt_confirmation():
    from tools.shell import run_shell

    completed = subprocess.CompletedProcess(
        args=["curl"], returncode=0, stdout="ok", stderr=""
    )
    with patch(
        "safety.confirm.ask_command_confirmation",
        new=AsyncMock(return_value=_shell_confirm("confirmed", command="curl https://example.com")),
    ) as mock_confirm, \
         patch("tools.shell.asyncio.to_thread", new=AsyncMock(return_value=completed)) as mock_to_thread:
        result = await run_shell("curl https://example.com")

    assert "ok" in result
    mock_confirm.assert_not_awaited()
    assert mock_to_thread.await_count == 1


@pytest.mark.asyncio
async def test_run_shell_curl_dump_headers_does_not_prompt_confirmation():
    from tools.shell import run_shell

    completed = subprocess.CompletedProcess(
        args=["curl"], returncode=0, stdout="ok", stderr=""
    )
    with patch(
        "safety.confirm.ask_command_confirmation",
        new=AsyncMock(return_value=_shell_confirm("confirmed", command="curl -D headers.txt https://example.com")),
    ) as mock_confirm, \
         patch("tools.shell.asyncio.to_thread", new=AsyncMock(return_value=completed)) as mock_to_thread:
        result = await run_shell("curl -D headers.txt https://example.com")

    assert "ok" in result
    mock_confirm.assert_not_awaited()
    assert mock_to_thread.await_count == 1


@pytest.mark.asyncio
async def test_run_shell_output_redirection_prompts_confirmation():
    from tools.shell import run_shell

    completed = subprocess.CompletedProcess(
        args=["echo"], returncode=0, stdout="", stderr=""
    )
    with patch(
        "safety.confirm.ask_command_confirmation",
        new=AsyncMock(return_value=_shell_confirm("confirmed", command="echo hello > ~/tmp.txt")),
    ) as mock_confirm, \
         patch("tools.shell.asyncio.to_thread", new=AsyncMock(return_value=completed)) as mock_to_thread:
        result = await run_shell("echo hello > ~/tmp.txt")

    assert result == "(no output)"
    mock_confirm.assert_awaited_once()
    assert mock_to_thread.await_count == 1


@pytest.mark.asyncio
async def test_run_shell_systemctl_restart_prompts_confirmation():
    from tools.shell import run_shell

    completed = subprocess.CompletedProcess(
        args=["systemctl"], returncode=0, stdout="", stderr=""
    )
    with patch(
        "safety.confirm.ask_command_confirmation",
        new=AsyncMock(return_value=_shell_confirm("confirmed", command="systemctl restart nginx")),
    ) as mock_confirm, \
         patch("tools.shell.asyncio.to_thread", new=AsyncMock(return_value=completed)) as mock_to_thread:
        result = await run_shell("systemctl restart nginx")

    assert result == "(no output)"
    mock_confirm.assert_awaited_once()
    assert mock_to_thread.await_count == 1
