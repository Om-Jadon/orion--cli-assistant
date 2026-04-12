Orion Onboarding Flow - Extended Implementation PlanThis document provides the exact code changes, architectural steps, and design philosophy required to implement the first-time user onboarding sequence for the orion-cli project.Goal: Provide a seamless, interactive terminal setup that configures the user's AI provider, validates their API key, gathers initial profile context, and optionally runs a local file scan, all before the main DB and interactive loop start.Why This Matters: In CLI application design, the "Time-to-First-Value" (TTFV) is critical. If a user installs Orion and is immediately greeted by a stack trace because OPENAI_API_KEY is missing from their environment, they are highly likely to abandon the tool. This onboarding flow prevents "blank terminal syndrome," establishes trust through immediate API validation, and personalizes the agent right out of the box.Step 1: Update src/orion/config.pyWe need to add the ability to check if the environment is ready, write the new configuration safely to disk, and automatically inject the api_key into os.environ. This injection is a crucial bridge: it allows us to store the key persistently in config.toml while still satisfying the underlying pydantic-ai and httpx libraries, which expect standard environment variables.Add these imports if missing:import os
import pathlib
import logging

logger = logging.getLogger(__name__)
Add / Update these functions in config.py:CONFIG_DIR = pathlib.Path.home() / ".orion"
CONFIG_FILE = CONFIG_DIR / "config.toml"

def is_config_ready() -> bool:
    """
    Check if the user has a valid configuration and API key.
    This acts as the gatekeeper for the main application loop.
    """
    if not CONFIG_FILE.exists():
        return False
    
    try:
        # Simple string-matching check to see if the file has basic required content.
        # This avoids loading a heavy TOML parser during the initial rapid check.
        content = CONFIG_FILE.read_text(encoding="utf-8")
        return "model_string" in content and "api_key" in content
    except PermissionError:
        logger.error(f"Permission denied reading {CONFIG_FILE}")
        return False
    except Exception as e:
        logger.error(f"Error reading config: {e}")
        return False

def save_config(model_string: str, api_key: str) -> bool:
    """
    Write the basic configuration to TOML manually. 
    Python's built-in `tomllib` is read-only, and for a simple two-line config,
    manual formatting avoids adding third-party dependencies like `tomlkit`.
    """
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        
        config_content = f"""# Orion CLI Configuration
# Auto-generated during initial onboarding.
model_string = "{model_string}"
api_key = "{api_key}"
"""
        # Secure the file so only the owner can read/write it
        CONFIG_FILE.write_text(config_content, encoding="utf-8")
        os.chmod(CONFIG_FILE, 0o600)
        return True
    except Exception as e:
        logger.error(f"Failed to save configuration: {e}")
        return False

def load_config() -> dict:
    """Update your existing load_config to inject the api_key into os.environ."""
    # ... your existing file reading/parsing logic ...
    # Assume parsing results in a dictionary called `config_data`
    
    # NEW LOGIC: Inject API key into environment so providers can find it automatically.
    # This keeps our codebase clean without needing to manually pass keys to every client instance.
    if "api_key" in config_data and "model_string" in config_data:
        provider = config_data["model_string"].split(":")[0]
        key_map = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "groq": "GROQ_API_KEY",
            "gemini": "GEMINI_API_KEY",
            "mistral": "MISTRAL_API_KEY"
        }
        
        env_var = key_map.get(provider)
        if env_var and env_var not in os.environ:
            os.environ[env_var] = config_data["api_key"]
            
    return config_data
Step 2: Create src/orion/ui/onboarding.pyCreate this new file to handle the interactive terminal flow using the rich library. This UI must be intuitive, handle connection failures gracefully, and provide clear feedback.import httpx
import os
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich.table import Table

console = Console()

def validate_api_key(provider: str, api_key: str) -> tuple[bool, str]:
    """
    Synchronously test the API key against the provider's models endpoint.
    Returns a tuple of (is_valid, error_message).
    """
    if provider == "local":
        return True, ""
        
    try:
        with httpx.Client(timeout=10.0) as client:
            if provider == "groq":
                r = client.get("[https://api.groq.com/openai/v1/models](https://api.groq.com/openai/v1/models)", headers={"Authorization": f"Bearer {api_key}"})
            elif provider == "openai":
                r = client.get("[https://api.openai.com/v1/models](https://api.openai.com/v1/models)", headers={"Authorization": f"Bearer {api_key}"})
            elif provider == "anthropic":
                r = client.get("[https://api.anthropic.com/v1/models](https://api.anthropic.com/v1/models)", headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"})
            elif provider == "gemini":
                r = client.get(f"[https://generativelanguage.googleapis.com/v1beta/models?key=](https://generativelanguage.googleapis.com/v1beta/models?key=){api_key}")
            else:
                return False, "Unknown provider configuration."
            
            if r.status_code == 200:
                return True, ""
            elif r.status_code in [401, 403]:
                return False, "Unauthorized. Please check that your API key is correct and active."
            else:
                return False, f"Server returned unexpected status: {r.status_code}"
                
    except httpx.TimeoutException:
        return False, "Connection timed out. Please check your internet connection."
    except httpx.RequestError as e:
        return False, f"Network error occurred: {e}"

def run_onboarding() -> tuple[str, str, str, str, str]:
    """
    Runs the onboarding flow.
    Returns: (model_string, api_key, user_name, user_preferences, scan_dir)
    """
    console.clear()
    console.print(Panel.fit("🚀 Welcome to Orion CLI Assistant", style="bold cyan", border_style="blue"))
    console.print("Let's get your environment set up. This will only take a minute.\n")

    # 1. Identity Setup
    console.print("[dim]Orion can personalize its responses if it knows who it's talking to.[/dim]")
    user_name = Prompt.ask("[bold]What should I call you?[/bold]")

    # 2. Provider Selection
    console.print("\n[bold]Choose your primary AI Engine:[/bold]")
    console.print("  [1] OpenAI     [dim](Requires API Key)[/dim]")
    console.print("  [2] Anthropic  [dim](Requires API Key)[/dim]")
    console.print("  [3] Groq       [green](Recommended: Free & Blazing Fast)[/green]")
    console.print("  [4] Gemini     [dim](Requires API Key)[/dim]")
    console.print("  [5] Local      [dim](Ollama - Requires local setup)[/dim]")
    
    choice_map = {
        "1": ("openai", "openai:gpt-4o-mini"),
        "2": ("anthropic", "anthropic:claude-3-5-sonnet-latest"),
        "3": ("groq", "groq:llama-3.3-70b-versatile"),
        "4": ("gemini", "gemini:gemini-2.5-flash"),
        "5": ("local", "openai:local-model")
    }
    
    choice = Prompt.ask("\nSelect an option", choices=["1", "2", "3", "4", "5"], default="3")
    provider, model_string = choice_map[choice]

    # 3. API Key Entry & Validation Loop
    api_key = ""
    if provider != "local":
        console.print(f"\n[dim]You can get a {provider.title()} API key from their developer dashboard.[/dim]")
        while True:
            api_key = Prompt.ask(f"[bold]Enter your {provider.title()} API Key[/bold]", password=True)
            
            with console.status(f"[yellow]Connecting to {provider.title()} to verify key...[/yellow]"):
                is_valid, err_msg = validate_api_key(provider, api_key)
                
                if is_valid:
                    console.print(f"[green]✅ Connection successful! {provider.title()} is ready.[/green]")
                    break
                else:
                    console.print(f"[red]❌ Validation Failed: {err_msg}[/red]")
                    if not Confirm.ask("Do you want to try entering the key again?", default=True):
                        console.print("[yellow]Warning: Saving invalid key. Orion may crash when queried.[/yellow]")
                        break

    # 4. Personal Context Gathering
    console.print("\n[bold]Personal Context[/bold]")
    console.print("[dim]Examples: 'I use Arch Linux', 'Always write scripts in Python', 'I am a DevOps engineer'[/dim]")
    user_prefs = ""
    if Confirm.ask("Do you want to add any custom rules or workflow preferences?"):
        user_prefs = Prompt.ask("Enter your preferences")

    # 5. Background File Scan
    console.print("\n[bold]Local Indexing[/bold]")
    console.print("[dim]Orion can index a specific folder (like your code directory) so it can find files instantly.[/dim]")
    scan_dir = ""
    if Confirm.ask("Do you want to run a quick file scan now? (You can always run /scan later)"):
        # Default to the current working directory to avoid scanning massive ~ directories
        default_dir = os.getcwd() 
        scan_dir = Prompt.ask("Enter directory path to scan", default=default_dir)

    # 6. Summary Confirmation
    console.print("\n")
    summary = Table(show_header=False, box=None)
    summary.add_row("[bold]Name:[/bold]", user_name or "Not provided")
    summary.add_row("[bold]Provider:[/bold]", provider.title())
    summary.add_row("[bold]Model:[/bold]", model_string)
    summary.add_row("[bold]Preferences:[/bold]", "Saved" if user_prefs else "None")
    
    console.print(Panel(summary, title="Setup Summary", border_style="green", expand=False))
    console.print("\n[bold green]🎉 Setup Complete![/bold green] Launching Orion...\n")
    
    return model_string, api_key, user_name, user_prefs, scan_dir
Step 3: Integrate with src/orion/main.pyModify your main() function or main entry block to check the config before doing anything else. It is critical that this happens before initializing SQLite DB connections, as those might rely on configurations or block the terminal flow.Update src/orion/main.py:import sys
import os
from orion.config import is_config_ready, save_config, load_config
from orion.ui.onboarding import run_onboarding
import logging

logger = logging.getLogger(__name__)

# ... other imports ...

def main():
    # 1. The Onboarding Intercept Hook
    if not is_config_ready():
        # Pause normal startup and run the interactive setup
        model_string, api_key, name, prefs, scan_dir = run_onboarding()
        
        # Persist credentials to ~/.orion/config.toml
        if not save_config(model_string, api_key):
            print("Fatal Error: Could not save configuration. Check permissions.")
            sys.exit(1)
            
        # Ensure the environment is updated immediately for the current session
        os.environ["API_KEY_SETUP_COMPLETE"] = "true" 
        
        # ---------------------------------------------------------
        # NOTE: At this point, config is saved to disk. 
        # Now it is safe to load heavy dependencies and databases.
        # ---------------------------------------------------------
        
        try:
            from orion.memory.db import init_db
            init_db() 
            
            from orion.memory.store import upsert_profile
            # Push gathered data into the AI's permanent memory profile
            if name:
                upsert_profile(f"The user's preferred name is {name}.")
            if prefs:
                upsert_profile(f"User Preferences & Workflow Rules: {prefs}")
                
            # Trigger the initial background scan if requested
            if scan_dir:
                from orion.memory.indexer import index_directory 
                expanded_dir = os.path.expanduser(scan_dir)
                
                if os.path.exists(expanded_dir) and os.path.isdir(expanded_dir):
                    print(f"Running initial metadata index on {expanded_dir}...")
                    index_directory(expanded_dir) 
                else:
                    print(f"Directory {expanded_dir} not found or invalid. Skipping scan.")
                    
        except Exception as e:
            logger.error(f"Error during post-onboarding setup: {e}")
            print(f"Warning: Non-fatal error during setup: {e}")

    # 2. Normal Application Startup
    # Proceed with your existing main loop logic
    try:
        config = load_config()
        # route CLI modes (one-shot, pipe, interactive)
        # ...
    except Exception as e:
        logger.fatal(f"Failed to start Orion: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
Step 4: Testing & Verification StrategyTo ensure this flow works perfectly without corrupting existing data, follow these verification steps during development.1. Simulating a Fresh InstallTo test the onboarding flow repeatedly, you don't need to delete your database. Simply rename your config file to hide it from the is_config_ready() check:mv ~/.orion/config.toml ~/.orion/config.toml.backup
uv run orion
Verify that the onboarding screen appears immediately.2. Validating the "Bad Key" PathDuring onboarding, purposely select OpenAI and paste a random string like sk-12345fakekey.Verify that the UI correctly catches the 401 Unauthorized error and prompts you to try again, rather than crashing or accepting the bad key.3. Permissions CheckThe new save_config function attempts to apply 0o600 permissions (read/write for owner only) to the config file since it contains raw API keys.After completing setup, run ls -la ~/.orion/config.toml and verify the permissions are -rw-------.4. Co-Pilot / Environment VerificationEnsure httpx and rich are present in the dependencies list of pyproject.toml.Ensure that the provider mapping inside load_config (e.g., OPENAI_API_KEY, GROQ_API_KEY) exactly matches the environment variables that pydantic-ai natively searches for when instantiating its models.Confirm that init_db() creates the SQLite tables before upsert_profile attempts to write the user's name to the user_profile table.