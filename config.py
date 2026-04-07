import sys as _sys
import tomllib
from pathlib import Path

HOME          = Path.home()
ORION_DIR     = HOME / ".orion"
DB_PATH       = ORION_DIR / "memory.db"
HISTORY_FILE  = ORION_DIR / "history"

# Preserve any CONFIG_FILE override injected before reload (e.g. in tests).
# On first import _sys.modules[__name__] may not exist yet, so fall back to default.
_mod = _sys.modules.get(__name__)
CONFIG_FILE = (
    _mod.CONFIG_FILE
    if _mod is not None and hasattr(_mod, "CONFIG_FILE")
    else ORION_DIR / "config.toml"
)

_defaults = {
    "model_primary": "qwen3:8b",
    "model_fast":    "qwen3:4b",
    "theme":         "mocha",
    "max_width":     100,
}

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

MODEL_PRIMARY = _user.get("model_primary", _defaults["model_primary"])
MODEL_FAST    = _user.get("model_fast",    _defaults["model_fast"])
THEME         = _user.get("theme",         _defaults["theme"])
MAX_WIDTH     = int(_user.get("max_width",  _defaults["max_width"]))

OLLAMA_BASE        = "http://localhost:11434/v1"   # OpenAI-compatible endpoint (used by openai SDK)
OLLAMA_API_BASE    = "http://localhost:11434"       # Native Ollama API (used for embeddings, tags, generate)
EMBED_MODEL        = "nomic-embed-text"
EMBED_DIM          = 256   # Matryoshka truncation of nomic-embed-text's 768-dim output

KEEP_ALIVE_ACTIVE  = "10m"
KEEP_ALIVE_IDLE    = "2m"
KEEP_ALIVE_BATTERY = "30s"

CONTEXT_PROFILE   = 800
CONTEXT_RECENT    = 2000
CONTEXT_RETRIEVED = 2000
CONTEXT_RESERVE   = 3000
