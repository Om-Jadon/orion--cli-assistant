import pytest
from unittest.mock import patch, MagicMock


def test_check_db_false_when_missing(tmp_path):
    from ui import startup
    with patch.object(startup, 'DB_PATH', tmp_path / "missing.db"):
        assert startup._check_db() is False


def test_check_db_true_when_exists(tmp_path):
    from ui import startup
    db = tmp_path / "memory.db"
    db.touch()
    with patch.object(startup, 'DB_PATH', db):
        assert startup._check_db() is True


def test_check_index_false_when_db_missing(tmp_path):
    from ui import startup
    with patch.object(startup, 'DB_PATH', tmp_path / "missing.db"):
        assert startup._check_index() is False


def test_show_startup_does_not_raise():
    import ui.startup as su
    console = MagicMock()
    with patch.object(su, "PROVIDER", "openai"), \
         patch.object(su, "_check_api_key", return_value=True), \
         patch.object(su, "_check_db", return_value=True), \
         patch.object(su, "_check_index", return_value=True), \
         patch.object(su, "_index_count", return_value=123):
        su.show_startup(console, "openai:gpt-4o")


def test_check_api_key_passes_when_env_var_set():
    """_check_api_key returns True when the env var is present."""
    import os
    from unittest.mock import patch as _patch
    from ui.startup import _check_api_key
    with _patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
        assert _check_api_key("openai") is True


def test_check_api_key_exits_when_env_var_missing():
    """_check_api_key calls sys.exit(1) when the env var is absent."""
    import os
    from unittest.mock import patch as _patch
    from ui.startup import _check_api_key
    env_without_key = {k: v for k, v in os.environ.items() if k != "OPENAI_API_KEY"}
    with _patch.dict(os.environ, env_without_key, clear=True), \
         pytest.raises(SystemExit) as exc_info:
        _check_api_key("openai")
    assert exc_info.value.code == 1


def test_check_api_key_unknown_provider_returns_true():
    """_check_api_key returns True for an unrecognised provider (no env var to check)."""
    from ui.startup import _check_api_key
    assert _check_api_key("unknown_provider") is True

def test_tagline_in_show_startup():
    """show_startup prints 'quick · fluent · native' unconditionally."""
    from rich.console import Console
    from io import StringIO
    from unittest.mock import patch as _patch
    import ui.startup as su
    buf = StringIO()
    con = Console(file=buf, highlight=False, width=120)
    with _patch.object(su, "PROVIDER", "openai"), \
         _patch("ui.startup._check_api_key", return_value=True), \
         _patch("ui.startup._check_db", return_value=False), \
         _patch("ui.startup._check_index", return_value=False):
        su.show_startup(con, "openai:gpt-4o")
    output = buf.getvalue()
    assert "quick" in output
    assert "fluent" in output
    assert "native" in output
