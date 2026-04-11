import sys as _sys
import tomllib
from pathlib import Path

__version__ = "0.1.0"
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

def _load_user_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "rb") as f:
                return tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            raise SystemExit(
                f"Error: {CONFIG_FILE} contains invalid TOML.\n{e}\n"
                "Fix the file or delete it to use defaults."
            ) from e
    return {}

_user = _load_user_config()

THEME     = _user.get("theme",     _defaults["theme"])
MAX_WIDTH = int(_user.get("max_width", _defaults["max_width"]))

TRACE_LOGGING_ENABLED = _as_bool(
    _user.get("trace_logging_enabled", _defaults["trace_logging_enabled"]),
    _defaults["trace_logging_enabled"],
)
TRACE_LOG_RETENTION_DAYS = max(1, int(_user.get("trace_log_retention_days", _defaults["trace_log_retention_days"])))

_trace_log_dir_raw = _user.get("trace_log_dir")
if _trace_log_dir_raw:
    _trace_log_dir = Path(_trace_log_dir_raw).expanduser()
    TRACE_LOG_DIR = _trace_log_dir if _trace_log_dir.is_absolute() else ORION_DIR / _trace_log_dir
else:
    TRACE_LOG_DIR = ORION_DIR / "logs"

# --- Cloud provider support ---

def _require_model_string(value: object) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    raise SystemExit(
        "Error: model_string is required in ~/.orion/config.toml.\n"
        "Example: model_string = \"openai:gpt-4o-mini\"\n"
        "Supported prefixes: openai:, anthropic:, gemini-, groq:, mistral:"
    )


MODEL_STRING: str = _require_model_string(_user.get("model_string"))

CLOUD_API_KEY_VARS: dict[str, str] = {
    "openai":    "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini":    "GEMINI_API_KEY",
    "groq":      "GROQ_API_KEY",
    "mistral":   "MISTRAL_API_KEY",
}

def _detect_provider(model_string: str) -> str:
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
    raise SystemExit(
        f"Error: unsupported model_string {model_string!r}.\n"
        "Supported prefixes: openai:, anthropic:, gemini-, groq:, mistral:"
    )

PROVIDER: str = _detect_provider(MODEL_STRING)

EMBED_MODEL        = "BAAI/bge-small-en-v1.5"  # fastembed local model, no Ollama needed
EMBED_DIM          = 384   # bge-small-en-v1.5 output dimension

CONTEXT_PROFILE   = 800
CONTEXT_RECENT    = 2000
CONTEXT_RETRIEVED = 2000
CONTEXT_RESERVE   = 3000
