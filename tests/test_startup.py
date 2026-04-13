import pytest
import sqlite3
from unittest.mock import patch


def test_get_db_status_returns_false_zero_when_missing(tmp_path):
    from orion.ui import startup
    with patch("orion.config.DB_PATH", tmp_path / "missing.db"):
        assert startup._get_db_status() == (False, 0)


def test_get_db_status_returns_true_zero_when_db_exists_without_index_table(tmp_path):
    from orion.ui import startup

    db = tmp_path / "orion.memory.db"
    conn = sqlite3.connect(db)
    conn.close()
    with patch("orion.config.DB_PATH", db):
        assert startup._get_db_status() == (False, 0)


@pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")
def test_show_startup_does_not_raise():
    from io import StringIO
    from rich.console import Console
    from orion.ui import startup as su
    from orion.ui.renderer import get_theme
    console = Console(file=StringIO(), theme=get_theme("mocha"), highlight=False, width=120)
    with patch("orion.config.PROVIDER", "openai"), \
         patch.object(su, "ensure_browser_engine"), \
         patch.object(su, "_check_api_key", return_value=True), \
         patch.object(su, "_get_db_status", return_value=(True, 123)):
        su.show_startup(console, "openai:gpt-4o")


def test_check_api_key_passes_when_env_var_set():
    """_check_api_key returns True when the env var is present."""
    import os
    from unittest.mock import patch as _patch
    from orion.ui.startup import _check_api_key
    with _patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
        assert _check_api_key("openai") is True


def test_check_api_key_exits_when_env_var_missing():
    """_check_api_key calls sys.exit(1) when the env var is absent."""
    import os
    from unittest.mock import patch as _patch
    from orion.ui.startup import _check_api_key
    env_without_key = {k: v for k, v in os.environ.items() if k != "OPENAI_API_KEY"}
    with _patch.dict(os.environ, env_without_key, clear=True), \
         pytest.raises(SystemExit) as exc_info:
        _check_api_key("openai")
    assert exc_info.value.code == 1


def test_check_api_key_unknown_provider_returns_true():
    """_check_api_key returns True for an unrecognised provider (no env var to check)."""
    from orion.ui.startup import _check_api_key
    assert _check_api_key("unknown_provider") is True

@pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")
def test_tagline_in_show_startup():
    """show_startup prints 'quick · fluent · native' unconditionally."""
    from rich.console import Console
    from io import StringIO
    from unittest.mock import patch as _patch
    from orion.ui import startup as su
    from orion.ui.renderer import get_theme
    buf = StringIO()
    con = Console(file=buf, theme=get_theme("mocha"), highlight=False, width=120)
    with _patch("orion.config.PROVIDER", "openai"), \
         _patch("orion.ui.startup.ensure_browser_engine"), \
         _patch("orion.ui.startup._check_api_key", return_value=True), \
         _patch("orion.ui.startup._get_db_status", return_value=(False, 0)):
        su.show_startup(con, "openai:gpt-4o")
    output = buf.getvalue()
    assert "quick" in output
    assert "fluent" in output
    assert "native" in output
