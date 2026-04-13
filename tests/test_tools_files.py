import pytest
from pathlib import Path
import tempfile
import sqlite3
import subprocess
from unittest.mock import AsyncMock, patch
from orion.safety.confirm import ConfirmationResult


def _confirm_result(
    decision: str,
    *,
    action: str,
    source_path: str | None = None,
    destination_path: str | None = None,
    repeated_denial: bool = False,
) -> ConfirmationResult:
    return ConfirmationResult(
        decision=decision,
        scope="file",
        action=action,
        source_path=source_path,
        destination_path=destination_path,
        repeated_denial=repeated_denial,
    )


@pytest.mark.asyncio
async def test_list_directory_home():
    from orion.tools.files import list_directory
    result = await list_directory("~")
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_list_directory_blocks_outside_home():
    from orion.tools.files import list_directory
    result = await list_directory("/etc")
    assert "Blocked" in result


@pytest.mark.asyncio
async def test_list_directory_shows_truncation_notice():
    from orion.tools.files import list_directory

    with tempfile.TemporaryDirectory(dir=Path.home()) as tmpdir:
        base = Path(tmpdir)
        for i in range(55):
            (base / f"f{i:02d}.txt").write_text("x")

        result = await list_directory(str(base))

    assert "showing 50 of 55" in result


@pytest.mark.asyncio
async def test_find_files_returns_string():
    from orion.tools.files import find_files
    result = await find_files("bashrc")
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_find_files_empty_query():
    from orion.tools.files import find_files
    result = await find_files("")
    assert "Provide" in result


@pytest.mark.asyncio
async def test_find_files_uses_index_when_available():
    from orion.tools import files as files_mod

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE files (path TEXT, name TEXT, tags TEXT)")
    conn.execute(
        "INSERT INTO files (path, name, tags) VALUES (?, ?, ?)",
        ("/home/jadon/notes/todo.txt", "todo.txt", "notes,todo"),
    )
    conn.commit()

    files_mod._search_conn = conn
    try:
        with patch("orion.tools.files.asyncio.to_thread", new=AsyncMock()) as mock_to_thread:
            result = await files_mod.find_files("todo")
        assert "/home/jadon/notes/todo.txt" in result
        mock_to_thread.assert_not_called()
    finally:
        files_mod._search_conn = None
        conn.close()


@pytest.mark.asyncio
async def test_find_files_falls_back_to_find_when_index_empty():
    from orion.tools import files as files_mod

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE files (path TEXT, name TEXT, tags TEXT)")
    conn.commit()

    files_mod._search_conn = conn
    try:
        completed = subprocess.CompletedProcess(
            args=["find"], returncode=0, stdout="/home/jadon/a.txt\n", stderr=""
        )
        with patch("orion.tools.files.asyncio.to_thread", new=AsyncMock(return_value=completed)) as mock_to_thread:
            result = await files_mod.find_files("a.txt")
        assert "/home/jadon/a.txt" in result
        assert mock_to_thread.await_count == 1
        args = mock_to_thread.await_args.args
        assert args[0] is subprocess.run
        find_cmd = args[1]
        assert find_cmd[:4] == ["find", str(Path.home()), "-maxdepth", "8"]
    finally:
        files_mod._search_conn = None
        conn.close()


@pytest.mark.asyncio
async def test_find_files_fallback_handles_os_errors():
    from orion.tools import files as files_mod

    files_mod._search_conn = None
    with patch("orion.tools.files.asyncio.to_thread", new=AsyncMock(side_effect=OSError("find unavailable"))):
        result = await files_mod.find_files("todo")

    assert "Search failed:" in result
    assert "find unavailable" in result


@pytest.mark.asyncio
async def test_read_file_blocks_outside_home():
    from orion.tools.files import read_file
    result = await read_file("/etc/passwd")
    assert "Blocked" in result


@pytest.mark.asyncio
async def test_read_file_nonexistent():
    from orion.tools.files import read_file
    result = await read_file(str(Path.home() / "nonexistent_orion_test_file.txt"))
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_open_file_returns_error_without_graphical_session():
    from orion.tools.files import open_file

    with tempfile.NamedTemporaryFile(dir=Path.home(), suffix=".txt", delete=False) as f:
        tmp_path = f.name
    try:
        with patch.dict("orion.tools.files.os.environ", {}, clear=True), \
             patch("orion.tools.files.subprocess.Popen") as mock_popen:
            result = await open_file(tmp_path)

        assert "no graphical desktop session detected" in result
        mock_popen.assert_not_called()
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_open_file_returns_error_when_xdg_open_missing():
    from orion.tools.files import open_file

    with tempfile.NamedTemporaryFile(dir=Path.home(), suffix=".txt", delete=False) as f:
        tmp_path = f.name
    try:
        with patch.dict("orion.tools.files.os.environ", {"DISPLAY": ":0"}, clear=True), \
             patch("orion.tools.files.shutil.which", return_value=None), \
             patch("orion.tools.files.subprocess.Popen") as mock_popen:
            result = await open_file(tmp_path)

        assert "xdg-open is not installed" in result
        mock_popen.assert_not_called()
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_write_file_blocks_outside_home():
    from orion.tools.files import write_file

    result = await write_file("/etc/orion_test.txt", "hello")
    assert "Blocked" in result


@pytest.mark.asyncio
async def test_write_file_creates_new_file_when_confirmed():
    from orion.tools.files import write_file

    with tempfile.NamedTemporaryFile(dir=Path.home(), suffix=".txt", delete=False) as f:
        tmp_path = Path(f.name)
    tmp_path.unlink()

    try:
        with patch(
            "orion.safety.confirm.ask_file_action_confirmation",
            new=AsyncMock(return_value=_confirm_result("confirmed", action="create", source_path=str(tmp_path))),
        ) as mock_confirm, \
             patch("orion.tools.files._log_operation") as mock_log:
            result = await write_file(str(tmp_path), "hello world")

        assert result == f"Successfully createed {tmp_path.name}"
        assert tmp_path.read_text() == "hello world"
        mock_confirm.assert_awaited_once()
        assert mock_confirm.await_args.args[0] == "create"
        mock_log.assert_called_once_with("create", None, str(tmp_path))
    finally:
        tmp_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_write_file_overwrites_existing_file_when_confirmed():
    from orion.tools.files import write_file

    with tempfile.NamedTemporaryFile(dir=Path.home(), suffix=".txt", delete=False) as f:
        tmp_path = Path(f.name)
        tmp_path.write_text("old")

    try:
        with patch(
            "orion.safety.confirm.ask_file_action_confirmation",
            new=AsyncMock(return_value=_confirm_result("confirmed", action="overwrite", source_path=str(tmp_path))),
        ) as mock_confirm:
            result = await write_file(str(tmp_path), "new content")

        assert result == f"Successfully overwriteed {tmp_path.name}"
        assert tmp_path.read_text() == "new content"
        assert mock_confirm.await_args.args[0] == "overwrite"
    finally:
        tmp_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_write_file_cancelled_when_not_confirmed():
    from orion.tools.files import write_file

    with tempfile.NamedTemporaryFile(dir=Path.home(), suffix=".txt", delete=False) as f:
        tmp_path = Path(f.name)
    tmp_path.unlink()

    try:
        with patch(
            "orion.safety.confirm.ask_file_action_confirmation",
            new=AsyncMock(return_value=_confirm_result("denied", action="create", source_path=str(tmp_path))),
        ) as mock_confirm:
            result = await write_file(str(tmp_path), "hello")

        assert result == f"File create cancelled by user confirmation. path={tmp_path}"
        mock_confirm.assert_awaited_once()
        assert not tmp_path.exists()
    finally:
        tmp_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_write_file_repeated_denial_returns_specific_message():
    from orion.tools.files import write_file

    with tempfile.NamedTemporaryFile(dir=Path.home(), suffix=".txt", delete=False) as f:
        tmp_path = Path(f.name)
    tmp_path.unlink()

    try:
        with patch(
            "orion.safety.confirm.ask_file_action_confirmation",
            new=AsyncMock(
                return_value=_confirm_result(
                    "denied",
                    action="create",
                    source_path=str(tmp_path),
                    repeated_denial=True,
                )
            ),
        ):
            result = await write_file(str(tmp_path), "hello")

        assert "Confirmation was already denied for this exact action in this turn" in result
        assert f"path={tmp_path}" in result
        assert not tmp_path.exists()
    finally:
        tmp_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_move_file_blocks_outside_home():
    from orion.tools.files import move_file
    result = await move_file("/etc/passwd", str(Path.home() / "passwd"))
    assert "Blocked" in result


@pytest.mark.asyncio
async def test_move_file_cancelled_when_not_confirmed_and_uses_full_paths_in_prompt():
    from orion.tools.files import move_file

    with tempfile.NamedTemporaryFile(dir=Path.home(), suffix=".txt", delete=False) as f:
        src = f.name
    dst = str(Path.home() / "orion_move_destination.txt")

    try:
        with patch(
            "orion.safety.confirm.ask_file_action_confirmation",
            new=AsyncMock(
                return_value=_confirm_result(
                    "denied",
                    action="rename",
                    source_path=src,
                    destination_path=dst,
                )
            ),
        ) as mock_confirm, \
             patch("orion.tools.files.shutil.move") as mock_move:
            result = await move_file(src, dst)

        assert "cancelled by user confirmation" in result
        assert "from=" in result
        assert "to=" in result
        mock_move.assert_not_called()
        mock_confirm.assert_awaited_once()
        assert mock_confirm.await_args.args[0] == "rename"
        kwargs = mock_confirm.await_args.kwargs
        assert kwargs["source_path"] == src
        assert kwargs["destination_path"] == dst
    finally:
        Path(src).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_delete_file_blocks_outside_home():
    from orion.tools.files import delete_file
    result = await delete_file("/etc/passwd")
    assert "Blocked" in result


@pytest.mark.asyncio
async def test_delete_file_not_found_returns_not_found():
    from orion.tools.files import delete_file

    missing = str(Path.home() / "orion_missing_delete_target.txt")
    with patch(
        "orion.safety.confirm.ask_file_action_confirmation",
        new=AsyncMock(return_value=_confirm_result("confirmed", action="delete", source_path=missing)),
    ) as mock_confirm, \
         patch("orion.tools.files.subprocess.run") as mock_run:
        result = await delete_file(missing)

    assert result == f"Not found: {missing}."
    mock_confirm.assert_not_called()
    mock_run.assert_not_called()


@pytest.mark.asyncio
async def test_delete_file_cancelled_when_not_confirmed():
    from orion.tools.files import delete_file

    with tempfile.NamedTemporaryFile(dir=Path.home(), suffix=".txt", delete=False) as f:
        tmp_path = f.name
    try:
        with patch(
            "orion.safety.confirm.ask_file_action_confirmation",
            new=AsyncMock(return_value=_confirm_result("denied", action="delete", source_path=tmp_path)),
        ) as mock_confirm, \
             patch("orion.tools.files.subprocess.run") as mock_run:
            result = await delete_file(tmp_path)

        assert "File delete cancelled by user confirmation." in result
        mock_confirm.assert_awaited_once()
        assert mock_confirm.await_args.args[0] == "delete"
        kwargs = mock_confirm.await_args.kwargs
        assert kwargs["source_path"] == tmp_path
        mock_run.assert_not_called()
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_delete_file_trashes_when_confirmed():
    from orion.tools.files import delete_file

    with tempfile.NamedTemporaryFile(dir=Path.home(), suffix=".txt", delete=False) as f:
        tmp_path = f.name
    try:
        completed = subprocess.CompletedProcess(
            args=["gio", "trash", tmp_path],
            returncode=0,
            stdout="",
            stderr="",
        )
        with patch(
            "orion.safety.confirm.ask_file_action_confirmation",
            new=AsyncMock(return_value=_confirm_result("confirmed", action="delete", source_path=tmp_path)),
        ) as mock_confirm, \
             patch("orion.tools.files.asyncio.to_thread", new=AsyncMock(return_value=completed)) as mock_to_thread:
            result = await delete_file(tmp_path)

        assert "Moved to trash:" in result
        mock_confirm.assert_awaited_once()
        assert mock_to_thread.await_count == 1
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_delete_file_returns_error_when_trash_command_fails():
    from orion.tools.files import delete_file

    with tempfile.NamedTemporaryFile(dir=Path.home(), suffix=".txt", delete=False) as f:
        tmp_path = f.name
    try:
        failed = subprocess.CompletedProcess(
            args=["gio", "trash", tmp_path],
            returncode=1,
            stdout="",
            stderr="permission denied",
        )
        with patch(
            "orion.safety.confirm.ask_file_action_confirmation",
            new=AsyncMock(return_value=_confirm_result("confirmed", action="delete", source_path=tmp_path)),
        ), patch("orion.tools.files.asyncio.to_thread", new=AsyncMock(return_value=failed)):
            result = await delete_file(tmp_path)

        assert result == "Error moving to trash: permission denied"
    finally:
        Path(tmp_path).unlink(missing_ok=True)
