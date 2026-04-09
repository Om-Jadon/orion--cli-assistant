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
    assert config.MODEL == "qwen3:1.7b"
    assert config.EMBED_MODEL == "BAAI/bge-small-en-v1.5"


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
    # bge-small-en-v1.5 outputs 384-dim vectors (fastembed, no Ollama required)
    assert config.EMBED_DIM == 384


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
    toml_file.write_text('model = "qwen3:1.7b"\nmax_width = 80\n')

    import config as cfg
    try:
        with patch.object(cfg, "CONFIG_FILE", toml_file):
            importlib.reload(cfg)
            assert cfg.MODEL == "qwen3:1.7b"
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
            assert cfg.MODEL == "qwen3:1.7b"
            assert cfg.THEME == "mocha"
            assert cfg.MAX_WIDTH == 100
    finally:
        importlib.reload(cfg)


def test_default_model_string_is_none(tmp_path):
    """When model_string is absent from config.toml, MODEL_STRING must be None."""
    import importlib
    from unittest.mock import patch
    import config as cfg
    with patch.object(cfg, "CONFIG_FILE", tmp_path / "nonexistent.toml"):
        importlib.reload(cfg)
        assert cfg.MODEL_STRING is None
    importlib.reload(cfg)


def test_default_provider_is_ollama(tmp_path):
    """When MODEL_STRING is None, PROVIDER must default to 'ollama'."""
    import importlib
    from unittest.mock import patch
    import config as cfg
    with patch.object(cfg, "CONFIG_FILE", tmp_path / "nonexistent.toml"):
        importlib.reload(cfg)
        assert cfg.PROVIDER == "ollama"
    importlib.reload(cfg)


def test_cloud_api_key_vars_contains_all_providers():
    import config
    required = {"openai", "anthropic", "gemini", "groq", "mistral"}
    assert required.issubset(config.CLOUD_API_KEY_VARS.keys())


def test_provider_detection_from_model_string(tmp_path):
    """PROVIDER is derived from the model_string prefix in config.toml."""
    import importlib
    from unittest.mock import patch
    cases = [
        ("openai:gpt-4o",                  "openai"),
        ("anthropic:claude-sonnet-4-5",    "anthropic"),
        ("gemini-2.0-flash",               "gemini"),
        ("groq:llama-3.3-70b-versatile",   "groq"),
        ("mistral:mistral-large-latest",    "mistral"),
        ("qwen3:4b",                        "ollama"),
    ]
    import config as cfg
    for model_str, expected_provider in cases:
        toml_file = tmp_path / f"{expected_provider}.toml"
        toml_file.write_text(f'model_string = "{model_str}"\n')
        with patch.object(cfg, "CONFIG_FILE", toml_file):
            importlib.reload(cfg)
            assert cfg.MODEL_STRING == model_str
            assert cfg.PROVIDER == expected_provider, (
                f"Expected PROVIDER={expected_provider!r} for model_string={model_str!r}, "
                f"got {cfg.PROVIDER!r}"
            )
    importlib.reload(cfg)


def test_model_string_none_when_absent(tmp_path):
    """model_string key absent from config.toml -> MODEL_STRING is None."""
    import importlib
    from unittest.mock import patch
    import config as cfg
    toml_file = tmp_path / "config.toml"
    toml_file.write_text('model = "qwen3:4b"\n')
    with patch.object(cfg, "CONFIG_FILE", toml_file):
        importlib.reload(cfg)
        assert cfg.MODEL_STRING is None
        assert cfg.PROVIDER == "ollama"
    importlib.reload(cfg)
