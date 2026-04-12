from rich.console import Console
from rich.theme import Theme
from rich.markdown import Markdown
from rich.live import Live
from rich.rule import Rule
from rich.panel import Panel
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

console = Console(
    theme=MOCHA,
    highlight=False,
    width=config.MAX_WIDTH
)

def refresh_console_settings():
    """Update console settings from the current configuration."""
    console.width = config.MAX_WIDTH

def print_user(text: str):
    console.print(Rule(title="[#6C7086]you[/#6C7086]", align="left", style="#45475A"))
    console.print(f"[user]{text}[/user]")
    console.print()

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
        title="[#89B4FA]◆[/#89B4FA] [#89DCEB]orion[/#89DCEB]",
        title_align="left",
        border_style="#313244",
        padding=(0, 1),
    )

    with Live(
        Panel(Markdown(""), **panel_kwargs),
        console=console,
        refresh_per_second=15,
        transient=False
    ) as live:
        async for token in token_gen:
            content += token
            live.update(Panel(Markdown(content), **panel_kwargs))

    console.print()
    return content
