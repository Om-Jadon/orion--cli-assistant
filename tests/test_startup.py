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
    from ui.startup import show_startup
    console = MagicMock()
    show_startup(console, "qwen3:4b")  # should not raise


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
