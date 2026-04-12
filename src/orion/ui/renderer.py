from rich.console import Console
from rich.theme import Theme
from rich.markdown import Markdown
from rich.live import Live
from rich.panel import Panel
from rich.rule import Rule
from rich import box
import re
from orion import config

MOCHA = Theme({
    "user":      "bold #CDD6F4",
    "assistant": "#89DCEB",
    "orion":     "#89DCEB",
    "dim":       "#6C7086",
    "thinking":  "italic #585B70",
    "success":   "#A6E3A1",
    "warning":   "#F9E2AF",
    "error":     "#F38BA8",
    "accent":    "#89B4FA",
    "border":    "#313244",
    "muted":     "#45475A",
})

LATTE = Theme({
    "user":      "bold #4C4F69",
    "assistant": "#04A5E5",
    "orion":     "#04A5E5",
    "dim":       "#9CA0B0",
    "thinking":  "italic #ACB0BE",
    "success":   "#40A02B",
    "warning":   "#DF8E1D",
    "error":     "#D20F39",
    "accent":    "#1E66F5",
    "border":    "#DCE0E8",
    "muted":     "#BCC0CC",
})

_active_live: Live | None = None

def get_theme(name: str) -> Theme:
    if name.lower() == "latte":
        return LATTE
    if name.lower() == "none":
        return Theme() # Default rich colors
    return MOCHA

console = Console(
    theme=get_theme(config.THEME),
    highlight=False,
    width=config.MAX_WIDTH
)

def refresh_console_settings():
    """Update console settings from the current configuration."""
    console.width = config.MAX_WIDTH
    # In Rich, themes are immutable after Console init, but we can push a new one
    console.push_theme(get_theme(config.THEME))

def pause_live():
    """Temporarily stop the active Live display to allow for tool confirmations."""
    if _active_live and _active_live.is_started:
        _active_live.stop()

def resume_live():
    """Restart the active Live display after a tool interaction."""
    if _active_live and not _active_live.is_started:
        _active_live.start()

def highlight_paths(text: str) -> str:
    """
    Dynamically finds absolute Linux paths (starting with / or ~/) 
    and wraps them in markdown backticks to avoid markup leaks.
    """
    # Regex for typical Linux paths, avoiding double-wrapping if already backticked
    path_pattern = r"(?<!`)(~?/[a-zA-Z0-9_.-]+(?:/[a-zA-Z0-9_.-]+)*)(?!`)"
    return re.sub(path_pattern, r"`\1`", text)


def print_user(text: str):
    user_name = config.USER_NAME or "You"
    console.print(f"[dim]{user_name}:[/dim] {text}")
    console.print()

def print_system_error(msg: str):
    """Prints a standard high-visibility Red Rounded Panel for errors."""
    panel = Panel(
        msg,
        title="[bold]Error[/bold]",
        border_style="error",
        box=box.ROUNDED,
        padding=(0, 1),
        expand=False
    )
    console.print()
    console.print(panel)

def print_system_success(msg: str):
    """Prints a standard Green Rounded Panel for success notifications."""
    panel = Panel(
        f"[success]{msg}[/success]",
        border_style="success",
        box=box.ROUNDED,
        padding=(0, 1),
        expand=False
    )
    console.print()
    console.print(panel)

def print_system_warning(msg: str):
    """Prints a standard Yellow Rounded Panel for warnings."""
    panel = Panel(
        msg,
        title="[bold]Warning[/bold]",
        border_style="warning",
        box=box.ROUNDED,
        padding=(0, 1),
        expand=False
    )
    console.print()
    console.print(panel)

def print_system_info(msg: str):
    """Prints a standard neutral/dim Rounded Panel for info notifications."""
    panel = Panel(
        f"[dim]{msg}[/dim]",
        border_style="#45475a", # Surface1 (subtle)
        box=box.ROUNDED,
        padding=(0, 1),
        expand=False
    )
    console.print()
    console.print(panel)

def print_separator():
    console.print(Rule(style="#313244"))

async def stream_response(token_gen) -> str:
    """
    Stream tokens live with Markdown rendering inside a Panel.
    token_gen must be an async generator yielding string deltas.
    Returns the full assembled response.
    """
    content = ""
    console.print()

    panel_kwargs = dict(
        title="[bold #cba6f7]✦ orion[/bold #cba6f7]",
        title_align="left",
        border_style="#cba6f7",
        box=box.ROUNDED,
        padding=(0, 1),
    )

    global _active_live
    with Live(
        Panel(Markdown(""), **panel_kwargs),
        console=console,
        refresh_per_second=15,
        transient=False
    ) as live:
        _active_live = live
        try:
            async for token in token_gen:
                content += token
                # Note: Markdown auto-highlights code, but we apply path highlight to text deltas if needed.
                # However, trafilatura-style tool outputs often are displayed here too.
                live.update(Panel(Markdown(highlight_paths(content)), **panel_kwargs))
        finally:
            _active_live = None

    console.print()
    return content
