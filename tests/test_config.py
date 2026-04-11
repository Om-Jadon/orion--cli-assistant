import importlib
import pytest
from pathlib import Path
from unittest.mock import patch


def test_paths_are_under_home():
    from orion import config
    home = Path.home()
    assert config.ORION_DIR.is_relative_to(home)
    assert config.DB_PATH.is_relative_to(home)
    assert config.HISTORY_FILE.is_relative_to(home)
    assert config.TRACE_LOG_DIR.is_relative_to(home)


def test_legacy_think_off_constant_removed():
    from orion import config
    assert not hasattr(config, "THINK_OFF")


def test_default_theme_and_width():
    from orion import config
    assert config.THEME == "mocha"
    assert isinstance(config.MAX_WIDTH, int)
    assert config.MAX_WIDTH == 100


def test_embed_dim():
    from orion import config
    assert config.EMBED_MODEL == "BAAI/bge-small-en-v1.5"
    # bge-small-en-v1.5 outputs 384-dim vectors
    assert config.EMBED_DIM == 384


def test_context_budgets_are_positive_ints():
    from orion import config
    for name in ("CONTEXT_PROFILE", "CONTEXT_RECENT", "CONTEXT_RETRIEVED", "CONTEXT_RESERVE"):
        value = getattr(config, name)
        assert isinstance(value, int), f"{name} must be int, got {type(value)}"
        assert value > 0, f"{name} must be positive"


def test_trace_logging_defaults():
    from orion import config
    assert config.TRACE_LOGGING_ENABLED is True
    assert config.TRACE_LOG_RETENTION_DAYS == 7


def test_toml_override_updates_public_constants(tmp_path):
    """
    When ~/.orion/config.toml exists, the public constants must reflect its values.
    Uses importlib.reload to re-execute module-level code with a patched CONFIG_FILE.
    """
    toml_file = tmp_path / "config.toml"
    toml_file.write_text(
        'model_string = "openai:gpt-4o-mini"\n'
        'max_width = 80\n'
        'trace_logging_enabled = false\n'
        'trace_log_retention_days = 14\n'
    )

    from orion import config as cfg
    try:
        with patch.object(cfg, "CONFIG_FILE", toml_file):
            importlib.reload(cfg)
            assert cfg.MODEL_STRING == "openai:gpt-4o-mini"
            assert cfg.PROVIDER == "openai"
            assert cfg.MAX_WIDTH == 80
            assert cfg.TRACE_LOGGING_ENABLED is False
            assert cfg.TRACE_LOG_RETENTION_DAYS == 14
    finally:
        # Restore defaults — other tests in this process need clean module state
        importlib.reload(cfg)


def test_toml_missing_model_string_exits(tmp_path):
    """When config.toml is absent, model_string requirement must hard-fail."""
    from orion import config as cfg
    try:
        with patch.object(cfg, "CONFIG_FILE", tmp_path / "nonexistent.toml"):
            with pytest.raises(SystemExit):
                importlib.reload(cfg)
    finally:
        importlib.reload(cfg)


def test_model_string_absent_in_toml_exits(tmp_path):
    """model_string key missing from orion.config.toml must hard-fail."""
    from orion import config as cfg
    toml_file = tmp_path / "config.toml"
    toml_file.write_text('theme = "mocha"\n')
    try:
        with patch.object(cfg, "CONFIG_FILE", toml_file):
            with pytest.raises(SystemExit):
                importlib.reload(cfg)
    finally:
        importlib.reload(cfg)


def test_cloud_api_key_vars_contains_all_providers():
    from orion import config
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
    ]
    from orion import config as cfg
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


def test_unknown_provider_prefix_exits(tmp_path):
    from orion import config as cfg
    toml_file = tmp_path / "invalid.toml"
    toml_file.write_text('model_string = "qwen3:4b"\n')
    try:
        with patch.object(cfg, "CONFIG_FILE", toml_file):
            with pytest.raises(SystemExit):
                importlib.reload(cfg)
    finally:
        importlib.reload(cfg)


