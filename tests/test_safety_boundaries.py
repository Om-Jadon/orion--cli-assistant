import pytest
from pathlib import Path


def test_validate_path_allows_home_subpath():
    from orion.safety.boundaries import validate_path
    home = Path.home()
    ok, resolved = validate_path(str(home / "Documents"))
    assert ok is True
    assert "Documents" in resolved


def test_validate_path_blocks_outside_home():
    from orion.safety.boundaries import validate_path
    ok, msg = validate_path("/etc/passwd")
    assert ok is False
    assert "Blocked" in msg


def test_validate_path_expands_tilde():
    from orion.safety.boundaries import validate_path
    ok, resolved = validate_path("~/Downloads")
    assert ok is True
    assert str(Path.home()) in resolved


def test_validate_sudo_blocks_sudo():
    from orion.safety.boundaries import validate_sudo
    blocked, reason = validate_sudo("sudo apt install vim")
    assert blocked is True
    assert "sudo" in reason.lower()


def test_validate_sudo_blocks_rm_rf():
    from orion.safety.boundaries import validate_sudo
    blocked, reason = validate_sudo("rm -rf /home/user/data")
    assert blocked is True


def test_validate_sudo_allows_safe_command():
    from orion.safety.boundaries import validate_sudo
    blocked, _ = validate_sudo("ls -la ~/Downloads")
    assert blocked is False


def test_validate_sudo_blocks_fork_bomb():
    from orion.safety.boundaries import validate_sudo
    blocked, reason = validate_sudo(":(){ :|:& };:")
    assert blocked is True
