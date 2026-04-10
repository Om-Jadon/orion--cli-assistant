from safety.confirm import requires_confirmation
import pytest
from unittest.mock import AsyncMock, patch


@pytest.fixture(autouse=True)
def _reset_confirmation_state():
    from safety.confirm import reset_turn_state

    reset_turn_state()
    yield
    reset_turn_state()


def test_requires_confirmation_detects_destructive_terms():
    assert requires_confirmation("delete this file") is True
    assert requires_confirmation("overwrite notes.txt") is True


def test_requires_confirmation_ignores_safe_text():
    assert requires_confirmation("list files in downloads") is False
    assert requires_confirmation("read this file") is False


@pytest.mark.asyncio
async def test_ask_confirmation_stops_active_spinner_before_prompt():
    from safety.confirm import ask_confirmation

    with patch("ui.spinner.stop_active_spinner", new=AsyncMock()) as mock_stop, \
         patch("safety.confirm._SESSION.prompt_async", new=AsyncMock(return_value="yes")):
        result = await ask_confirmation("Delete file?")

    assert result is True
    mock_stop.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("answer", ["y", "Y", "yes", "YES", "YeS"])
async def test_ask_confirmation_accepts_yes_or_y_in_any_case(answer):
    from safety.confirm import ask_confirmation

    with patch("ui.spinner.stop_active_spinner", new=AsyncMock()), \
         patch("safety.confirm._SESSION.prompt_async", new=AsyncMock(return_value=answer)):
        result = await ask_confirmation("Delete file?")

    assert result is True


@pytest.mark.asyncio
async def test_ask_confirmation_cancels_on_non_yes_text():
    from safety.confirm import ask_confirmation

    with patch("ui.spinner.stop_active_spinner", new=AsyncMock()), \
         patch("safety.confirm._SESSION.prompt_async", new=AsyncMock(return_value="anything else")):
        result = await ask_confirmation("Delete file?")

    assert result is False


@pytest.mark.asyncio
async def test_ask_command_confirmation_formats_exact_command():
    from safety.confirm import ask_command_confirmation

    with patch("safety.confirm.ask_confirmation", new=AsyncMock(return_value=True)) as mock_ask:
        result = await ask_command_confirmation("echo hello && pwd")

    assert result.confirmed is True
    assert result.scope == "shell"
    assert result.action == "run"
    assert result.command == "echo hello && pwd"
    description = mock_ask.await_args.args[0]
    assert "Run shell command:" in description
    assert "echo hello && pwd" in description


@pytest.mark.asyncio
async def test_ask_file_action_confirmation_formats_delete_with_full_path():
    from safety.confirm import ask_file_action_confirmation

    path = "/home/jadon/Downloads/hi.txt"
    with patch("safety.confirm.ask_confirmation", new=AsyncMock(return_value=True)) as mock_ask:
        result = await ask_file_action_confirmation("delete", source_path=path)

    assert result.confirmed is True
    assert result.scope == "file"
    assert result.action == "delete"
    assert result.source_path == path
    description = mock_ask.await_args.args[0]
    assert "File Delete Confirmation" in description
    assert path in description


@pytest.mark.asyncio
async def test_ask_file_action_confirmation_formats_rename_with_both_paths():
    from safety.confirm import ask_file_action_confirmation

    src = "/home/jadon/Downloads/a.txt"
    dst = "/home/jadon/Downloads/b.txt"
    with patch("safety.confirm.ask_confirmation", new=AsyncMock(return_value=True)) as mock_ask:
        result = await ask_file_action_confirmation(
            "rename",
            source_path=src,
            destination_path=dst,
        )

    assert result.confirmed is True
    assert result.scope == "file"
    assert result.action == "rename"
    assert result.source_path == src
    assert result.destination_path == dst
    description = mock_ask.await_args.args[0]
    assert "File Rename Confirmation" in description
    assert src in description
    assert dst in description


@pytest.mark.asyncio
async def test_repeated_same_file_action_denial_is_short_circuited():
    from safety.confirm import ask_file_action_confirmation

    with patch("ui.spinner.stop_active_spinner", new=AsyncMock()), \
         patch("safety.confirm._SESSION.prompt_async", new=AsyncMock(return_value="no")) as mock_prompt:
        first = await ask_file_action_confirmation("delete", source_path="/home/jadon/a.txt")
        second = await ask_file_action_confirmation("delete", source_path="/home/jadon/a.txt")

    assert first.confirmed is False
    assert first.repeated_denial is False
    assert second.confirmed is False
    assert second.repeated_denial is True
    assert mock_prompt.await_count == 1


@pytest.mark.asyncio
async def test_denial_of_one_action_does_not_block_different_action():
    from safety.confirm import ask_file_action_confirmation

    with patch("ui.spinner.stop_active_spinner", new=AsyncMock()), \
         patch("safety.confirm._SESSION.prompt_async", new=AsyncMock(side_effect=["no", "yes"])) as mock_prompt:
        first = await ask_file_action_confirmation("delete", source_path="/home/jadon/a.txt")
        second = await ask_file_action_confirmation(
            "rename",
            source_path="/home/jadon/a.txt",
            destination_path="/home/jadon/b.txt",
        )

    assert first.confirmed is False
    assert second.confirmed is True
    assert mock_prompt.await_count == 2


@pytest.mark.asyncio
async def test_denial_cache_treats_different_case_paths_as_distinct_targets():
    from safety.confirm import ask_file_action_confirmation

    with patch("ui.spinner.stop_active_spinner", new=AsyncMock()), \
         patch("safety.confirm._SESSION.prompt_async", new=AsyncMock(side_effect=["no", "yes"])) as mock_prompt:
        first = await ask_file_action_confirmation("delete", source_path="/home/jadon/A.txt")
        second = await ask_file_action_confirmation("delete", source_path="/home/jadon/a.txt")

    assert first.confirmed is False
    assert first.repeated_denial is False
    assert second.confirmed is True
    assert second.repeated_denial is False
    assert mock_prompt.await_count == 2
