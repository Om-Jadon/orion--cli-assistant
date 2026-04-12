import asyncio
import logging
import sys
import uuid
from time import perf_counter
from orion.ui.renderer import console, print_user, print_separator, refresh_console_settings
from orion.ui.input import build_session, get_input
from orion.ui.startup import show_startup
from orion.ui import slash
from orion.core.agent import build_agent
from orion.core.streaming import run_with_streaming
from orion.core.context import build_context
from orion.memory.db import get_connection
from orion.memory.store import save_turn
from orion import config
from orion.core import trace_logging as trace_logging
from orion.tools import files as file_tools
from orion.tools import memory_tool
from orion.safety import confirm as safety_confirm

def setup_runtime():
    """Initializes global state for the application."""
    config.ORION_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.DEBUG, filename=str(config.ORION_DIR / "debug.log"))
    trace_logging.initialize()
    refresh_console_settings()

    global state, conn
    state = slash.RuntimeState(
        agent=build_agent(),
        session_id=str(uuid.uuid4()),
    )
    trace_logging.set_session_id(state.session_id)
    conn = get_connection()
    file_tools.set_connection(conn)
    memory_tool.set_connection(conn)


def cli_entry():
    """Synchronous entry point for the generated CLI tool."""
    # 1. Standard Utility Flags (check before ANY other setup)
    if len(sys.argv) > 1:
        flag = sys.argv[1].lower()
        if flag in ("--help", "-h"):
            print("""
Orion CLI Assistant — Terminal-first AI intelligence for Linux

Usage:
  orion [options] [prompt]

Options:
  -h, --help      Show this help message and exit
  -v, --version   Show program version and exit

Modes:
  Interactive     Start a chat session (run 'orion' with no prompt)
  One-shot        Run a single request (run 'orion "your prompt"')
  Pipe            Analyze stdin stream (run 'cat log.txt | orion "analyze"')

Slash Commands (in Interactive Mode):
  /help           Show session help
  /clear          Clear the terminal screen
  /undo           Revert the last exchanges
  /reset          Clear current conversation context
  /memory         View or clear profile facts
  /scan [path]    Index folder metadata for retrieval
  /history        List recent session IDs
  /exit           Terminate the session

Configuration:
  Settings are stored in ~/.orion/config.toml. 
  Orion will guide you through setup on first launch.
""")
            sys.exit(0)
        
        if flag in ("--version", "-v"):
            print(f"Orion CLI v{config.__version__}")
            sys.exit(0)

    def _fail_init(msg: str, detail: str):
        from rich.panel import Panel
        from rich.text import Text
        error_panel = Panel(
            Text.from_markup(f"[bold #F38BA8]Configuration Error:[/] [bold #CDD6F4]{msg}[/]\n\n[#6C7086]{detail}[/]"),
            border_style="#F38BA8",
            padding=(1, 2),
            title="[bold #F38BA8]Initialization Failed[/]",
            title_align="left"
        )
        console.print()
        console.print(error_panel)
        console.print()
        sys.exit(1)

    # 2. First-run Onboarding Check
    if not config.is_config_ready():
        from orion.ui.onboarding import run_onboarding
        model_string, api_key, name, prefs, scan_dir = run_onboarding()

        if api_key is None:
            # Result of KeyboardInterrupt or cancellation
            console.print("\n  [#6C7086]onboarding cancelled.[/#6C7086]\n")
            sys.exit(0)

        if not api_key:
            console.print("\n  [#F38BA8]Error: API key is required to use Orion.[/#F38BA8]")
            sys.exit(1)

        if not config.save_config(model_string, api_key):
            console.print("[#F38BA8]Error: Could not save configuration to ~/.orion/config.toml[/#F38BA8]")
            sys.exit(1)

        # Reload configuration constants after saving
        config.reload_config()
        refresh_console_settings()

        # Initialize the environment immediately for this process
        provider = model_string.split(":")[0]
        env_var = config.CLOUD_API_KEY_VARS.get(provider)
        if env_var:
            import os
            os.environ[env_var] = api_key

        # 2. Early setup for profile/indexing
        try:
            setup_runtime()
        except ValueError as e:
            _fail_init("Invalid backbone configuration.", str(e))
        except Exception as e:
            _fail_init("System initialization failed.", str(e))
        
        from orion.memory.store import upsert_profile
        if name:
            upsert_profile(conn, "user_name", name)
        if prefs:
            upsert_profile(conn, "user_preferences", prefs)
        
        if scan_dir:
            from orion.memory.indexer import scan_directory
            with console.status(f"[bold blue]Indexing {scan_dir}...[/bold blue]"):
                scan_directory(conn, scan_dir)
    else:
        # Normal startup
        # Ensure the environment has the key for the configured provider
        provider = config.PROVIDER
        env_var = config.CLOUD_API_KEY_VARS.get(provider)
        if env_var and config.API_KEY:
            import os
            os.environ[env_var] = config.API_KEY

        try:
            setup_runtime()
        except ValueError as e:
            _fail_init("Invalid backbone configuration.", str(e))
        except Exception as e:
            _fail_init("System initialization failed.", str(e))

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[#6C7086]Interrupted.[/#6C7086]")
    finally:
        if conn:
            conn.close()


state: slash.RuntimeState = None
conn = None


def _run_background_scan():
    from orion.memory.indexer import scan_home

    scan_conn = get_connection()
    try:
        scan_home(scan_conn)
    finally:
        scan_conn.close()


def _on_background_scan_done(task: asyncio.Task):
    try:
        task.result()
    except asyncio.CancelledError:
        logging.debug("Background home scan task cancelled.")
    except Exception:
        logging.exception("Background home scan task failed.")


def _run_log_retention_cleanup():
    deleted = trace_logging.cleanup_old_logs()
    if deleted:
        logging.debug(
            "Trace log retention removed %s file(s) older than %s days.",
            deleted,
            config.TRACE_LOG_RETENTION_DAYS,
        )


def _on_log_cleanup_done(task: asyncio.Task):
    try:
        task.result()
    except asyncio.CancelledError:
        logging.debug("Trace log retention task cancelled.")
    except Exception:
        logging.exception("Trace log retention task failed.")


async def main():
    # One-shot: orion open the latest markiplier video
    if len(sys.argv) > 1 and sys.stdin.isatty():
        query = " ".join(sys.argv[1:])
        await run_once(query, mode="oneshot")
        return

    # Pipe mode: cat log.txt | orion "what went wrong?"
    if not sys.stdin.isatty():
        piped_input = sys.stdin.read()
        user_query = sys.argv[1] if len(sys.argv) > 1 else "Analyze this:"
        full_query = f"{user_query}\n\n```\n{piped_input[:4000]}\n```"
        started = perf_counter()
        trace_logging.start_turn(full_query, mode="pipe")
        safety_confirm.reset_turn_state()
        save_turn(conn, state.session_id, "user", full_query)
        response = ""
        try:
            context = await build_context(conn, full_query, state.session_id)
            response = await run_with_streaming(state.agent, full_query, context=context)
            if response:
                save_turn(conn, state.session_id, "assistant", response)
            trace_logging.end_turn(
                status="ok",
                assistant_response=response,
                latency_ms=_elapsed_ms(started),
            )
            print(response)
        except KeyboardInterrupt as e:
            trace_logging.end_turn(
                status="interrupted",
                assistant_response=response,
                error=str(e),
                latency_ms=_elapsed_ms(started),
            )
            raise
        except Exception as e:
            trace_logging.end_turn(
                status="error",
                assistant_response=response,
                error=str(e),
                latency_ms=_elapsed_ms(started),
            )
            raise
        return

    display_model = config.MODEL_STRING
    show_startup(console, display_model)
    session = build_session()

    scan_task = asyncio.create_task(asyncio.to_thread(_run_background_scan), name="background-home-scan")
    scan_task.add_done_callback(_on_background_scan_done)

    cleanup_task = asyncio.create_task(asyncio.to_thread(_run_log_retention_cleanup), name="trace-log-cleanup")
    cleanup_task.add_done_callback(_on_log_cleanup_done)

    while True:
        try:
            user_input = await get_input(session)
            stripped = user_input.strip()
            if not stripped:
                continue
            if stripped in ("exit", "quit"):
                break
            if stripped.startswith("/"):
                await handle_slash(stripped)
                continue

            await run_once(stripped, mode="interactive")

        except KeyboardInterrupt:
            console.print("\n[#6C7086]Interrupted.[/#6C7086]")
            break
        except EOFError:
            break


def _elapsed_ms(started: float) -> int:
    return int((perf_counter() - started) * 1000)


async def run_once(query: str, mode: str = "interactive"):
    started = perf_counter()
    trace_logging.start_turn(query, mode=mode)
    safety_confirm.reset_turn_state()
    print_user(query)

    save_turn(conn, state.session_id, "user", query)

    response = ""
    try:
        context = await build_context(conn, query, state.session_id)
        response = await run_with_streaming(state.agent, query, context=context)

        if response:
            save_turn(conn, state.session_id, "assistant", response)

        trace_logging.end_turn(
            status="ok",
            assistant_response=response,
            latency_ms=_elapsed_ms(started),
        )
    except KeyboardInterrupt as e:
        trace_logging.end_turn(
            status="interrupted",
            assistant_response=response,
            error=str(e),
            latency_ms=_elapsed_ms(started),
        )
        raise
    except Exception as e:
        trace_logging.end_turn(
            status="error",
            assistant_response=response,
            error=str(e),
            latency_ms=_elapsed_ms(started),
        )
        raise
    finally:
        print_separator()


async def handle_slash(cmd: str):
    res = await slash.handle_slash(
        cmd,
        state=state,
        conn=conn,
        console=console,
    )
    if res:
        save_turn(conn, state.session_id, "system", f"[UNDO NOTICE] {res}")


if __name__ == "__main__":
    cli_entry()
