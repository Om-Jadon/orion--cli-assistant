import os
import httpx
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich import box
from rich.text import Text
from rich.align import Align
from orion import config
from orion.core.model_fallback import get_recommended_model

console = Console()

# --- Palette (Catppuccin Mocha) ---
C_PRIMARY = "#89B4FA"  # Sapphire
C_SUCCESS = "#A6E3A1"  # Green
C_WARN    = "#F9E2AF"  # Yellow
C_ERROR   = "#F38BA8"  # Red
C_DIM     = "#6C7086"  # Overlay0
C_TEXT    = "#CDD6F4"  # Text
from orion.ui.renderer import print_system_error, print_system_success, print_system_warning

def _print_step(step: int, total: int, title: str):
    """Prints a consistent, stylized phase header."""
    header = Text()
    header.append(" ◆ ", style=f"{C_PRIMARY} bold")
    header.append(f"[ {step} / {total} ] ", style=C_DIM)
    header.append(title.upper(), style=f"{C_TEXT} bold")
    console.print(header)
    console.print()

def validate_api_key(provider: str, api_key: str) -> tuple[bool, str]:
    """Synchronously test the API key against the provider's models endpoint."""
    if provider == "local":
        return True, ""
        
    try:
        with httpx.Client(timeout=10.0) as client:
            if provider == "groq":
                url = "https://api.groq.com/openai/v1/models"
                headers = {"Authorization": f"Bearer {api_key}"}
            elif provider == "openai":
                url = "https://api.openai.com/v1/models"
                headers = {"Authorization": f"Bearer {api_key}"}
            elif provider == "anthropic":
                url = "https://api.anthropic.com/v1/models"
                headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
            elif provider == "gemini":
                url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
                headers = {}
            else:
                return False, "Unknown provider configuration."
            
            r = client.get(url, headers=headers)
            if r.status_code == 200:
                return True, ""
            elif r.status_code in [401, 403]:
                return False, "Unauthorized. Check your API key."
            else:
                return False, f"Server Error: {r.status_code}"
    except httpx.TimeoutException:
        return False, "Connection timed out."
    except Exception as e:
        return False, f"Network Error: {e}"


def run_onboarding() -> tuple[str | None, str | None, str | None, str | None, str | None]:
    """Runs the interactive onboarding flow."""
    total_steps = 5
    
    try:
        console.clear()
        console.print()
        
        welcome_msg = Text.from_markup(f"Welcome to [bold {C_PRIMARY}]Orion[/bold {C_PRIMARY}]")
        console.print(Align.center(Panel(
            welcome_msg,
            subtitle=f"[{C_DIM}]v{config.__version__}[/{C_DIM}]",
            box=box.ROUNDED,
            border_style="#cba6f7",
            padding=(1, 6)
        )))
        
        console.print(Align.center(f"\n[{C_DIM}]Let's get your terminal environment set up. This will only take a minute.[/{C_DIM}]\n"))

        # 1. Identity
        _print_step(1, total_steps, "Identity")
        user_name = Prompt.ask(f"    [{C_DIM}]What should Orion call you?[/{C_DIM}]", default="Explorer")

        # 2. Provider Selection
        console.print()
        _print_step(2, total_steps, "AI Provider")
        
        table = Table(
            box=box.SIMPLE,
            show_header=True,
            header_style=f"bold {C_PRIMARY}",
            border_style=C_DIM,
            padding=(0, 2)
        )
        table.add_column("#", style=C_PRIMARY, justify="right")
        table.add_column("Provider", style=f"bold {C_TEXT}")
        table.add_column("Details", style=C_DIM)
        
        table.add_row("1", "OpenAI",    get_recommended_model("openai").split(":", 1)[-1])
        table.add_row("2", "Anthropic", get_recommended_model("anthropic").split(":", 1)[-1])
        table.add_row("3", "Groq",      f"[{C_SUCCESS}]Generous Free Tier & High Performance[/{C_SUCCESS}] ({get_recommended_model('groq').split(':', 1)[-1]})")
        table.add_row("4", "Gemini",    get_recommended_model("gemini").split(":", 1)[-1])
        
        console.print(Align.left(table, pad=4))

        choice_map = {
            "1": ("openai",    get_recommended_model("openai")),
            "2": ("anthropic", get_recommended_model("anthropic")),
            "3": ("groq",      get_recommended_model("groq")),
            "4": ("gemini",     get_recommended_model("gemini")),
        }
        
        choice = Prompt.ask(f"\n    [{C_TEXT}]Select a backbone[/{C_TEXT}]", choices=["1", "2", "3", "4"], default="3")
        provider, model_string = choice_map[choice]

        # 3. API Key
        console.print()
        _print_step(3, total_steps, "Authentication")
        api_key = ""
        while True:
            api_key = Prompt.ask(f"    [{C_TEXT}]Enter {provider.title()} API Key[/{C_TEXT}]")
            if not api_key:
                print_system_error("Key cannot be empty.")
                continue

            with console.status(f"    [{C_WARN}]Verifying {provider.title()} connection...[/{C_WARN}]"):
                is_valid, err_msg = validate_api_key(provider, api_key)
                
                if is_valid:
                    console.print(f"    [{C_SUCCESS}]Connection successful![/{C_SUCCESS}]")
                    break
                else:
                    print_system_error(err_msg)
                    console.print(f"    [{C_WARN}]Please re-enter your key to continue.[/{C_WARN}]")

        # 4. Preferences
        console.print()
        _print_step(4, total_steps, "Behavior")
        console.print(f"    [{C_DIM}]e.g. 'Short answers', 'Always use Python', 'Linux specialist'[/{C_DIM}]")
        user_prefs = ""
        if Confirm.ask(f"    [{C_TEXT}]Add custom agent instructions?[/{C_TEXT}]", default=False):
            user_prefs = Prompt.ask(f"    [{C_TEXT}]Enter preferences[/{C_TEXT}]")

        # 5. Indexing
        console.print()
        _print_step(5, total_steps, "Memory")
        scan_dir = None
        if Confirm.ask(f"    [{C_TEXT}]Scan current directory now to build knowledge index?[/{C_TEXT}]", default=True):
            default_dir = os.path.expanduser("~")
            path_str = Prompt.ask(f"    [{C_TEXT}]Path to index[/{C_TEXT}]", default=default_dir)
            scan_dir = os.path.expanduser(path_str)

        # --- Summary ---
        console.clear()
        console.print()
        
        summary = Table.grid(padding=(0, 2))
        summary.add_row(f"[{C_DIM}]User[/{C_DIM}]", f"[bold {C_TEXT}]{user_name}[/bold {C_TEXT}]")
        summary.add_row(f"[{C_DIM}]Provider[/{C_DIM}]", f"[bold {C_PRIMARY}]{provider.title()}[/bold {C_PRIMARY}]")
        summary.add_row(f"[{C_DIM}]Model[/{C_DIM}]", f"[{C_TEXT}]{model_string}[/{C_TEXT}]")
        summary.add_row(f"[{C_DIM}]Memory[/{C_DIM}]", f"[{C_TEXT}]{scan_dir or 'Skipped'}[/{C_TEXT}]")

        console.print(Align.center(Panel(
            summary,
            title=f"[{C_SUCCESS}]Configuration Summary[/{C_SUCCESS}]",
            box=box.ROUNDED,
            border_style="#cba6f7",
            padding=(1, 4)
        )))
        
        console.print(Align.center(f"\n[bold {C_SUCCESS}]Orion is ready![/bold {C_SUCCESS}]\n"))
        
        return model_string, api_key, user_name, user_prefs, scan_dir
    except (KeyboardInterrupt, EOFError):
        # Graceful exit on Ctrl+C or Ctrl+D during onboarding
        return None, None, None, None, None
