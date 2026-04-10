import pytest
from pathlib import Path
import tempfile
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
             patch("tools.files.subprocess.run") as mock_run:
            result = await delete_file(tmp_path)

        assert "Moved to trash:" in result
        mock_confirm.assert_awaited_once()
        mock_run.assert_called_once()
    finally:
        Path(tmp_path).unlink(missing_ok=True)
