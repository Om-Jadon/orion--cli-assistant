import pytest
from pathlib import Path


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
