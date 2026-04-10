import os
import sys
import httpx
from rich.console import Console
from rich.rule import Rule
from rich.text import Text
from config import OLLAMA_API_BASE, DB_PATH, PROVIDER, CLOUD_API_KEY_VARS


def show_startup(console: Console, model: str):
    console.clear()

    line1 = Text()
    line1.append("  ◆", style="#89B4FA bold")
    line1.append("  ")
    line1.append("orion", style="#CDD6F4 bold")

    line2 = Text()
    line2.append(f"     {model}", style="#6C7086")

    console.print()
    console.print()
    console.print(line1)
    console.print(line2)
    console.print()
    console.print("  [#6C7086]quick · fluent · native[/#6C7086]")
    console.print()
    console.print(Rule(style="#45475A"))
    console.print()

    if PROVIDER == "ollama":
        ollama_ok = _check_ollama()
        db_ok = _check_db()
        index_ok = _check_index()
        checks = [
            ("ollama", ollama_ok, "connected" if ollama_ok else "offline"),
            ("memory", db_ok,     "active" if db_ok else "run --init"),
            ("index",  index_ok,  f"{_index_count():,} files" if index_ok else "run --init"),
        ]
    else:
        api_ok = _check_api_key(PROVIDER)
        db_ok = _check_db()
        index_ok = _check_index()
        checks = [
            (PROVIDER, api_ok,   "ready"),
            ("memory", db_ok,    "active" if db_ok else "run --init"),
            ("index",  index_ok, f"{_index_count():,} files" if index_ok else "run --init"),
        ]

    for name, ok, status_text in checks:
        dot = "[#A6E3A1]●[/#A6E3A1]" if ok else "[#F38BA8]●[/#F38BA8]"
        console.print(f"  {dot} [#6C7086]{name:<10}[/#6C7086] [#585B70]{status_text}[/#585B70]")

    console.print()
    console.print()


def _check_api_key(provider: str) -> bool:
    """
    Check that the required API key env var is set for the given cloud provider.
    Prints a clear error to stderr and exits with code 1 if the key is missing.
    Returns True when the key is present (used as the startup check result).
    """
    env_var = CLOUD_API_KEY_VARS.get(provider, "")
    if not env_var:
        return True  # unknown provider — let PydanticAI surface the error at inference time
    if os.environ.get(env_var):
        return True
    print(
        f"\nError: {env_var} is not set.\n"
        f"Export it in your shell before starting orion:\n\n"
        f"  export {env_var}=<your-key>\n",
        file=sys.stderr,
    )
    sys.exit(1)


def _check_ollama() -> bool:
    try:
        r = httpx.get(f"{OLLAMA_API_BASE}/api/tags", timeout=2)
        return r.status_code == 200
    except Exception:
        return False


def _check_db() -> bool:
    return DB_PATH.exists()


def _check_index() -> bool:
    if not DB_PATH.exists():
        return False
    import sqlite3
    try:
        conn = sqlite3.connect(DB_PATH)
        count = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
        conn.close()
        return count > 0
    except Exception:
        return False


def _index_count() -> int:
    if not DB_PATH.exists():
        return 0
    import sqlite3
    try:
        conn = sqlite3.connect(DB_PATH)
        count = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
        conn.close()
        return count
    except Exception:
        return 0


async def prewarm_model(model: str):
    """Pre-load the Ollama model to avoid cold-start on first query.
    No-op for cloud providers."""
    if PROVIDER != "ollama":
        return
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{OLLAMA_API_BASE}/api/generate",
                json={"model": model, "prompt": "", "keep_alive": "10m"},
                timeout=30,
            )
    except Exception:
        pass  # non-fatal — first query will be slightly slower
