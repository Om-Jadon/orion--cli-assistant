import os
import sys as _sys
import tomllib
from pathlib import Path

__version__ = "0.2.0"
HOME          = Path.home()
ORION_DIR     = HOME / ".orion"
DB_PATH       = ORION_DIR / "memory.db"
HISTORY_FILE  = ORION_DIR / "history"

# Preserve any CONFIG_FILE override injected before reload (e.g. in tests).
_mod = _sys.modules.get(__name__)
CONFIG_FILE = (
    _mod.CONFIG_FILE
    if _mod is not None and hasattr(_mod, "CONFIG_FILE")
    else ORION_DIR / "config.toml"
)

def is_config_ready() -> bool:
    """Check if the user has a valid configuration and API key."""
    if not CONFIG_FILE.exists():
        return False
    try:
        with open(CONFIG_FILE, "rb") as f:
            data = tomllib.load(f)
        # Check for absolutely required fields
        if not data.get("model_string") or not data.get("api_key"):
            return False
        return True
    except Exception:
        return False

def save_config(model_string: str, api_key: str) -> bool:
    """Write the basic configuration to TOML safely."""
    import json
    try:
        ORION_DIR.mkdir(parents=True, exist_ok=True)
        # We use json.dumps for safe TOML string quoting/escaping
        config_content = f"""# ==============================================================================
# 🌌 ORION CONFIGURATION
# ==============================================================================
# Auto-generated during setup. You can manually edit these settings.
# Changes will take effect the next time you start Orion.

# 🧠 INTELLIGENCE
# Supported Providers: groq, openai, anthropic, gemini, mistral
# Format: "provider:model" (e.g. "anthropic:claude-3-5-sonnet-latest")
model_string = {json.dumps(model_string)}
api_key = {json.dumps(api_key)}

# 🎨 APPEARANCE
# Themes: "mocha" (default), "latte" (light), or "none" (system)
theme = "mocha"

# Maximum width of the rendered output in the terminal
max_width = 100

# 🛠️ DIAGNOSTICS & PRIVACY
# Enable/disable detailed streaming trace logs in ~/.orion/logs/
trace_logging_enabled = true

# How many days to keep trace logs before auto-cleaning
trace_log_retention_days = 7

# Optional: Uncomment to move trace logs to a different directory.
# trace_log_dir = "~/custom/log/path"
"""
        CONFIG_FILE.write_text(config_content, encoding="utf-8")
        os.chmod(CONFIG_FILE, 0o600)
        return True
    except Exception:
        return False

def reload_config():
    """Reload the module-level configuration state."""
    import importlib
    importlib.reload(_sys.modules[__name__])

_defaults = {
    "theme": "mocha",
    "max_width": 100,
    "trace_logging_enabled": True,
    "trace_log_retention_days": 7,
}


def _as_bool(value, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        v = value.strip().lower()
        if v in {"1", "true", "yes", "on"}:
            return True
        if v in {"0", "false", "no", "off"}:
            return False
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    return default

def _as_int(value, default: int) -> int:
    try:
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, str):
            return int(value.strip())
        return default
    except (ValueError, TypeError):
        return default

def _load_user_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "rb") as f:
                return tomllib.load(f)
        except Exception:
            # If it passed is_config_ready() but fails here, 
            # we fall back to defaults rather than crashing.
            return {}
    return {}

_user = _load_user_config()

THEME     = _user.get("theme",     _defaults["theme"])
MAX_WIDTH = _as_int(_user.get("max_width"), _defaults["max_width"])

TRACE_LOGGING_ENABLED = _as_bool(
    _user.get("trace_logging_enabled", _defaults["trace_logging_enabled"]),
    _defaults["trace_logging_enabled"],
)
TRACE_LOG_RETENTION_DAYS = max(1, _as_int(_user.get("trace_log_retention_days"), _defaults["trace_log_retention_days"]))

_trace_log_dir_raw = _user.get("trace_log_dir")
if _trace_log_dir_raw:
    _trace_log_dir = Path(_trace_log_dir_raw).expanduser()
    TRACE_LOG_DIR = _trace_log_dir if _trace_log_dir.is_absolute() else ORION_DIR / _trace_log_dir
else:
    TRACE_LOG_DIR = ORION_DIR / "logs"

# --- Cloud provider support ---

def _get_model_string(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


MODEL_STRING: str | None = _get_model_string(_user.get("model_string"))
API_KEY:      str | None = _user.get("api_key")

CLOUD_API_KEY_VARS: dict[str, str] = {
    "openai":    "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini":    "GEMINI_API_KEY",
    "groq":      "GROQ_API_KEY",
    "mistral":   "MISTRAL_API_KEY",
}

def _detect_provider(model_string: str | None) -> str | None:
    if not model_string:
        return None
    if model_string.startswith("openai:"):
        return "openai"
    if model_string.startswith("anthropic:"):
        return "anthropic"
    if model_string.startswith("gemini-"):
        return "gemini"
    if model_string.startswith("groq:"):
        return "groq"
    if model_string.startswith("mistral:"):
        return "mistral"
    return None

PROVIDER: str | None = _detect_provider(MODEL_STRING)

EMBED_MODEL        = "BAAI/bge-small-en-v1.5"  # fastembed local model, no Ollama needed
EMBED_DIM          = 384   # bge-small-en-v1.5 output dimension

CONTEXT_PROFILE   = 800
CONTEXT_RECENT    = 2000
CONTEXT_RETRIEVED = 2000
CONTEXT_RESERVE   = 3000
