import httpx
from rich.console import Console
from rich.text import Text
from config import OLLAMA_API_BASE, DB_PATH

def show_startup(console: Console, model: str):
    console.clear()

    wordmark = Text()
    wordmark.append("  ◆ ", style="#89B4FA bold")
    wordmark.append("orion", style="#CDD6F4 bold")
    wordmark.append(f"  {model}", style="#6C7086")

    console.print()
    console.print(wordmark)
    console.print("  [#6C7086]" + "─" * 40 + "[/#6C7086]")
    console.print("  [#6C7086]offline · local · private[/#6C7086]")
    console.print()

    checks = [
        ("ollama", _check_ollama()),
        ("memory", _check_db()),
        ("index",  _check_index()),
    ]

    for name, ok in checks:
        dot = "[#A6E3A1]●[/#A6E3A1]" if ok else "[#F38BA8]●[/#F38BA8]"
        console.print(f"  {dot} [#6C7086]{name}[/#6C7086]")

    console.print()

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

async def prewarm_model(model: str):
    """Pre-load the model so first real query has no cold-start delay."""
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{OLLAMA_API_BASE}/api/generate",
                json={"model": model, "prompt": "", "keep_alive": "10m"},
                timeout=30
            )
    except Exception:
        pass  # non-fatal — just means first query will be slower
