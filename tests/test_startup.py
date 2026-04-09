import pytest
import httpx
from unittest.mock import patch, MagicMock, AsyncMock


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


def test_check_ollama_false_on_connection_error():
    from ui import startup
    with patch("httpx.get", side_effect=httpx.ConnectError("refused")):
        assert startup._check_ollama() is False


def test_show_startup_does_not_raise():
    from unittest.mock import patch
    import ui.startup as su
    console = MagicMock()
    with patch.object(su, "PROVIDER", "ollama"):
        su.show_startup(console, "qwen3:4b")  # should not raise



@pytest.mark.asyncio
async def test_prewarm_model_swallows_errors():
    from ui.startup import prewarm_model
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__  = AsyncMock(return_value=False)
        mock_client.post       = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_client_cls.return_value = mock_client
        await prewarm_model("qwen3:4b")  # should not raise


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


@pytest.mark.asyncio
async def test_prewarm_skipped_for_cloud_provider():
    """prewarm_model returns without HTTP call when PROVIDER != 'ollama'."""
    from unittest.mock import patch as _patch, AsyncMock, MagicMock
    import ui.startup as su
    with _patch.object(su, "PROVIDER", "openai"), \
         _patch("ui.startup.httpx") as mock_httpx:
        mock_httpx.AsyncClient.return_value.__aenter__ = AsyncMock()
        await su.prewarm_model("openai:gpt-4o")
        mock_httpx.AsyncClient.assert_not_called()


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
