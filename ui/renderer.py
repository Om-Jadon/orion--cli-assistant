import shutil
from rich.console import Console
from rich.theme import Theme
from rich.markdown import Markdown
from rich.live import Live

MOCHA = Theme({
    "user":      "bold #CDD6F4",
    "assistant": "#89DCEB",
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
    width=min(shutil.get_terminal_size().columns, 100)
)

def print_user(text: str):
    console.print("[dim]you[/dim]")
    console.print(f"[user]{text}[/user]")
    console.print()

def print_separator():
    console.print(f"[border]{'─' * console.width}[/border]")

async def stream_response(token_gen) -> str:
    """
    Stream tokens live with Markdown rendering.
    token_gen must be an async generator yielding string deltas.
    Returns the full assembled response.
    """
    content = ""
    console.print("[dim]orion[/dim]")

    with Live(
        Markdown(""),
        console=console,
        refresh_per_second=15,
        transient=False
    ) as live:
        async for token in token_gen:
            content += token
            live.update(Markdown(content))

    console.print()
    return content
