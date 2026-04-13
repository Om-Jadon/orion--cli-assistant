import os
import sys
import subprocess
from rich.console import Console
from rich.text import Text
from rich.table import Table
from rich.panel import Panel
from rich import box
from orion import config

from orion.ui.renderer import console

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
                pass

def show_startup(console: Console, model: str):
    ensure_browser_engine(console)
    console.clear()

    # 1. Branding
    brand = Text()
    brand.append("✦ orion", style="orion bold")  # Semantic brand color
    
    # 2. Status Grid
    api_ok = _check_api_key(config.PROVIDER)
    db_ok, file_count = _get_db_status()
    index_ok = file_count > 0
    
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="dim")  # Label
    grid.add_column(style="thinking") # Value

    checks = [
        (config.PROVIDER, api_ok,   "ready" if api_ok else "missing"),
        ("memory", db_ok,    "active" if db_ok else "run /scan"),
        ("index",  index_ok, f"{file_count:,} files" if index_ok else "run /scan"),
    ]

    for name, ok, status_text in checks:
        dot = "[success]●[/success]" if ok else "[error]●[/error]"
        grid.add_row(f"{dot} {name}", status_text)

    # 3. Assemble Startup Panel
    header = Text.from_markup(f"[{config.THEME}]v{config.__version__} · {model}[/]")
    
    startup_content = Table.grid(padding=(1, 0))
    startup_content.add_row(Text("quick · fluent · native", style="dim italic"))
    startup_content.add_row(grid)

    startup_panel = Panel(
        startup_content,
        title=brand,
        subtitle=header,
        subtitle_align="left",
        border_style="muted", # Surface1
        box=box.ROUNDED,
        padding=(0, 2),
        expand=False
    )

    console.print()
    console.print(startup_panel)
    console.print()


def _check_api_key(provider: str) -> bool:
    env_var = config.CLOUD_API_KEY_VARS.get(provider, "")
    if not env_var:
        return True
    if os.environ.get(env_var):
        return True
    
    error_msg = Text.from_markup(
        f"[bold error]Error:[/] [user]{env_var}[/] is not set.\n\n"
        f"Export it in your shell before starting orion:\n\n"
        f"  [accent]export {env_var}=<your-key>[/accent]"
    )
    console.print()
    console.print(Panel(
        error_msg,
        border_style="error",
        padding=(1, 2),
        title="[bold error]Missing Authentication[/]",
        title_align="left",
        box=box.ROUNDED
    ))
    console.print()
    sys.exit(1)

def _get_db_status() -> tuple[bool, int]:
    if not config.DB_PATH.exists():
        return False, 0
    import sqlite3
    conn = sqlite3.connect(config.DB_PATH)
    try:
        file_count = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
        return True, file_count
    except Exception:
        return False, 0
    finally:
        conn.close()
