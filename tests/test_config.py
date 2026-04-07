import importlib
import pytest
from pathlib import Path
from unittest.mock import patch


def test_paths_are_under_home():
    import config
    home = Path.home()
    assert config.ORION_DIR.is_relative_to(home)
    assert config.DB_PATH.is_relative_to(home)
    assert config.HISTORY_FILE.is_relative_to(home)


def test_default_model():
    import config
    assert config.MODEL == "qwen3:4b"
    assert config.EMBED_MODEL == "nomic-embed-text"


def test_think_off_is_dict():
    import config
    assert isinstance(config.THINK_OFF, dict)
    assert config.THINK_OFF.get("think") is False


def test_default_theme_and_width():
    import config
    assert config.THEME == "mocha"
    assert isinstance(config.MAX_WIDTH, int)
    assert config.MAX_WIDTH == 100


def test_ollama_urls():
    import config
    assert config.OLLAMA_BASE == "http://localhost:11434/v1"
    assert config.OLLAMA_API_BASE == "http://localhost:11434"


def test_embed_dim():
    import config
    # nomic-embed-text natively outputs 768-dim vectors.
    # We intentionally truncate to 256 via Matryoshka truncation in
    # memory/embeddings.py (Stage 4). This constant must stay 256.
    assert config.EMBED_DIM == 256


def test_keep_alive_values_are_strings():
    import config
    assert isinstance(config.KEEP_ALIVE_ACTIVE, str)
    assert isinstance(config.KEEP_ALIVE_IDLE, str)
    assert isinstance(config.KEEP_ALIVE_BATTERY, str)


def test_context_budgets_are_positive_ints():
    import config
    for name in ("CONTEXT_PROFILE", "CONTEXT_RECENT", "CONTEXT_RETRIEVED", "CONTEXT_RESERVE"):
        value = getattr(config, name)
        assert isinstance(value, int), f"{name} must be int, got {type(value)}"
        assert value > 0, f"{name} must be positive"


def test_toml_override_updates_public_constants(tmp_path):
    """
    When ~/.orion/config.toml exists, the public constants must reflect its values.
    Uses importlib.reload to re-execute module-level code with a patched CONFIG_FILE.
    """
    toml_file = tmp_path / "config.toml"
    toml_file.write_text('model = "qwen3:14b"\nmax_width = 80\n')

    import config as cfg
    try:
        with patch.object(cfg, "CONFIG_FILE", toml_file):
            importlib.reload(cfg)
            assert cfg.MODEL == "qwen3:14b"
            assert cfg.MAX_WIDTH == 80
    finally:
        # Restore defaults — other tests in this process need clean module state
        importlib.reload(cfg)


def test_toml_missing_returns_defaults(tmp_path):
    """When config.toml is absent, module falls back to hardcoded defaults."""
    import config as cfg
    try:
        with patch.object(cfg, "CONFIG_FILE", tmp_path / "nonexistent.toml"):
            importlib.reload(cfg)
            assert cfg.MODEL == "qwen3:4b"
            assert cfg.THEME == "mocha"
            assert cfg.MAX_WIDTH == 100
    finally:
        importlib.reload(cfg)
