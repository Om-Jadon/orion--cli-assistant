import pytest
from pathlib import Path
from unittest.mock import patch


@pytest.mark.asyncio
async def test_manage_files_list_home():
    from tools.files import manage_files
    result = await manage_files(action="list", path=str(Path.home()))
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_manage_files_list_blocks_outside_home():
    from tools.files import manage_files
    result = await manage_files(action="list", path="/etc")
    assert "Blocked" in result


@pytest.mark.asyncio
async def test_manage_files_find_returns_string():
    from tools.files import manage_files
    result = await manage_files(action="find", query="bashrc")
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_manage_files_read_blocks_outside_home():
    from tools.files import manage_files
    result = await manage_files(action="read", path="/etc/passwd")
    assert "Blocked" in result


@pytest.mark.asyncio
async def test_manage_files_read_nonexistent(tmp_path):
    from tools.files import manage_files
    result = await manage_files(action="read", path=str(Path.home() / "nonexistent_orion_test_file.txt"))
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_manage_files_unknown_action():
    from tools.files import manage_files
    result = await manage_files(action="teleport")
    assert "Unknown action" in result
