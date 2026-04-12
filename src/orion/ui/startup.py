import os
import sys
import subprocess
from rich.console import Console
from rich.rule import Rule
from rich.text import Text
from orion import config


_STATUS_NAME_WIDTH = 10  # column width for status label alignment
console = Console()


def ensure_browser_engine(console_obj: Console = console):
    """Checks for Playwright binaries and installs them if missing."""
    cache_dir = os.path.expanduser("~/.cache/ms-playwright")
    if not os.path.exists(cache_dir):
        with console_obj.status("[bold blue]Setting up web extraction engine...[/bold blue]"):
            try:
                subprocess.run(
                    ["playwright", "install", "webkit"],
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            except Exception:
                # Silently fail, tools will handle it if browser is actually missing later
                pass


def show_startup(console: Console, model: str):
    ensure_browser_engine(console)
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

    api_ok = _check_api_key(config.PROVIDER)
    db_ok = _check_db()
    index_ok = _check_index()
    checks = [
        (config.PROVIDER, api_ok,   "ready" if api_ok else "missing"),
        ("memory", db_ok,    "active" if db_ok else "run /scan"),
        ("index",  index_ok, f"{_index_count():,} files" if index_ok else "run /scan"),
    ]

    for name, ok, status_text in checks:
        dot = "[#A6E3A1]●[/#A6E3A1]" if ok else "[#F38BA8]●[/#F38BA8]"
        console.print(f"  {dot} [#6C7086]{name:<{_STATUS_NAME_WIDTH}}[/#6C7086] [#585B70]{status_text}[/#585B70]")

    console.print()
    console.print()


def _check_api_key(provider: str) -> bool:
    """
    Check that the required API key env var is set for the given cloud provider.
    Prints a clear error to stderr and exits with code 1 if the key is missing.
    Returns True when the key is present (used as the startup check result).
    """
    env_var = config.CLOUD_API_KEY_VARS.get(provider, "")
    if not env_var:
        return True  # unknown provider — let PydanticAI surface the error at inference time
    if os.environ.get(env_var):
        return True
    from rich.panel import Panel
    error_msg = Text.from_markup(
        f"[bold #F38BA8]Error:[/] [bold #CDD6F4]{env_var}[/] is not set.\n\n"
        f"Export it in your shell before starting orion:\n\n"
        f"  [#89B4FA]export {env_var}=<your-key>[/]"
    )
    console.print()
    console.print(Panel(
        error_msg,
        border_style="#F38BA8",
        padding=(1, 2),
        title="[bold #F38BA8]Missing Authentication[/]",
        title_align="left"
    ))
    console.print()
    sys.exit(1)


def _check_db() -> bool:
    return config.DB_PATH.exists()


def _check_index() -> bool:
    if not config.DB_PATH.exists():
        return False
    import sqlite3
    try:
        with sqlite3.connect(config.DB_PATH) as conn:
            count = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
            return count > 0
    except Exception:
        return False


def _index_count() -> int:
    if not config.DB_PATH.exists():
        return 0
    import sqlite3
    try:
        with sqlite3.connect(config.DB_PATH) as conn:
            return conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
    except Exception:
        return 0
