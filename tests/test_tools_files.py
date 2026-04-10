import pytest
from pathlib import Path
import tempfile
import sqlite3
import subprocess
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_list_directory_home():
    from tools.files import list_directory
    result = await list_directory("~")
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_list_directory_blocks_outside_home():
    from tools.files import list_directory
    result = await list_directory("/etc")
    assert "Blocked" in result


@pytest.mark.asyncio
async def test_list_directory_shows_truncation_notice():
    from tools.files import list_directory

    with tempfile.TemporaryDirectory(dir=Path.home()) as tmpdir:
        base = Path(tmpdir)
        for i in range(55):
            (base / f"f{i:02d}.txt").write_text("x")

        result = await list_directory(str(base))

    assert "showing 50 of 55" in result


@pytest.mark.asyncio
async def test_find_files_returns_string():
    from tools.files import find_files
    result = await find_files("bashrc")
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_find_files_empty_query():
    from tools.files import find_files
    result = await find_files("")
    assert "Provide" in result


@pytest.mark.asyncio
async def test_find_files_uses_index_when_available():
    import tools.files as files_mod

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
        with patch("tools.files.asyncio.to_thread", new=AsyncMock()) as mock_to_thread:
            result = await files_mod.find_files("todo")
        assert "/home/jadon/notes/todo.txt" in result
        mock_to_thread.assert_not_called()
    finally:
        files_mod._search_conn = None
        conn.close()


@pytest.mark.asyncio
async def test_find_files_falls_back_to_find_when_index_empty():
    import tools.files as files_mod

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE files (path TEXT, name TEXT, tags TEXT)")
    conn.commit()

    files_mod._search_conn = conn
    try:
        completed = subprocess.CompletedProcess(
            args=["find"], returncode=0, stdout="/home/jadon/a.txt\n", stderr=""
        )
        with patch("tools.files.asyncio.to_thread", new=AsyncMock(return_value=completed)) as mock_to_thread:
            result = await files_mod.find_files("a.txt")
        assert "/home/jadon/a.txt" in result
        assert mock_to_thread.await_count == 1
    finally:
        files_mod._search_conn = None
        conn.close()


@pytest.mark.asyncio
async def test_read_file_blocks_outside_home():
    from tools.files import read_file
    result = await read_file("/etc/passwd")
    assert "Blocked" in result


@pytest.mark.asyncio
async def test_read_file_nonexistent():
    from tools.files import read_file
    result = await read_file(str(Path.home() / "nonexistent_orion_test_file.txt"))
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_move_file_blocks_outside_home():
    from tools.files import move_file
    result = await move_file("/etc/passwd", str(Path.home() / "passwd"))
    assert "Blocked" in result


@pytest.mark.asyncio
async def test_delete_file_blocks_outside_home():
    from tools.files import delete_file
    result = await delete_file("/etc/passwd")
    assert "Blocked" in result


@pytest.mark.asyncio
async def test_delete_file_not_found_returns_not_found():
    from tools.files import delete_file

    missing = str(Path.home() / "orion_missing_delete_target.txt")
    with patch("safety.confirm.ask_confirmation", new=AsyncMock(return_value=True)) as mock_confirm, \
         patch("tools.files.subprocess.run") as mock_run:
        result = await delete_file(missing)

    assert result == f"Not found: {missing}."
    mock_confirm.assert_not_called()
    mock_run.assert_not_called()


@pytest.mark.asyncio
async def test_delete_file_cancelled_when_not_confirmed():
    from tools.files import delete_file

    with tempfile.NamedTemporaryFile(dir=Path.home(), suffix=".txt", delete=False) as f:
        tmp_path = f.name
    try:
        with patch("safety.confirm.ask_confirmation", new=AsyncMock(return_value=False)) as mock_confirm, \
             patch("tools.files.subprocess.run") as mock_run:
            result = await delete_file(tmp_path)

        assert result == "Cancelled."
        mock_confirm.assert_awaited_once()
        mock_run.assert_not_called()
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_delete_file_trashes_when_confirmed():
    from tools.files import delete_file

    with tempfile.NamedTemporaryFile(dir=Path.home(), suffix=".txt", delete=False) as f:
        tmp_path = f.name
    try:
        with patch("safety.confirm.ask_confirmation", new=AsyncMock(return_value=True)) as mock_confirm, \
             patch("tools.files.asyncio.to_thread", new=AsyncMock()) as mock_to_thread:
            result = await delete_file(tmp_path)

        assert "Moved to trash:" in result
        mock_confirm.assert_awaited_once()
        assert mock_to_thread.await_count == 1
    finally:
        Path(tmp_path).unlink(missing_ok=True)
