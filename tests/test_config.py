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


def test_default_models():
    import config
    assert config.MODEL_PRIMARY == "qwen3:8b"
    assert config.MODEL_FAST == "qwen3:4b"
    assert config.EMBED_MODEL == "nomic-embed-text"


def test_default_theme_and_width():
    import config
    assert config.THEME == "mocha"
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
    assert config.CONTEXT_PROFILE > 0
    assert config.CONTEXT_RECENT > 0
    assert config.CONTEXT_RETRIEVED > 0
    assert config.CONTEXT_RESERVE > 0


def test_toml_override_updates_public_constants(tmp_path):
    """
    When ~/.orion/config.toml exists, the public constants (MODEL_PRIMARY,
    MAX_WIDTH, etc.) must reflect its values — not just the loader return value.
    Uses importlib.reload to re-execute module-level code with a patched CONFIG_FILE.
    """
    toml_file = tmp_path / "config.toml"
    toml_file.write_text('model_primary = "qwen3:14b"\nmax_width = 80\n')

    import config as cfg
    with patch.object(cfg, "CONFIG_FILE", toml_file):
        importlib.reload(cfg)
        assert cfg.MODEL_PRIMARY == "qwen3:14b"
        assert cfg.MAX_WIDTH == 80

    # Restore defaults — other tests in this process need clean module state
    importlib.reload(cfg)


def test_toml_missing_returns_defaults(tmp_path):
    """When config.toml is absent, module falls back to hardcoded defaults."""
    import config as cfg
    with patch.object(cfg, "CONFIG_FILE", tmp_path / "nonexistent.toml"):
        importlib.reload(cfg)
        assert cfg.MODEL_PRIMARY == "qwen3:8b"
        assert cfg.MAX_WIDTH == 100

    importlib.reload(cfg)
