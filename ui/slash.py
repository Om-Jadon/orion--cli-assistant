import asyncio
from dataclasses import dataclass
from pathlib import Path
import shutil as _shutil
from typing import Any, Callable

from memory.store import get_last_operation, get_recent_turns, get_user_profile


@dataclass
class RuntimeState:
    agent: Any
    think_mode: bool
    session_id: str


async def handle_slash(
    cmd: str,
    *,
    state: RuntimeState,
    conn,
    console,
    build_agent: Callable[..., Any],
):
    parts = cmd.strip().split()
    command = parts[0].lower() if parts else ""

    if command == "/help":
        console.print()
        console.print("  [accent]Slash commands[/accent]")
        console.print()
        console.print("  [dim]/help[/dim]       show this message")
        console.print("  [dim]/think[/dim]      toggle chain-of-thought reasoning")
        console.print("  [dim]/clear[/dim]      clear the terminal")
        console.print("  [dim]/undo[/dim]       undo last file operation")
        console.print("  [dim]/history[/dim]    show this session's conversation")
        console.print("  [dim]/memory[/dim]     show what orion knows about you")
        console.print("  [dim]/scan[/dim]       re-index your home directory")
        console.print("  [dim]/exit[/dim]       quit orion")
        console.print()
        return

    if command == "/clear":
        console.clear()
        return

    if command == "/think":
        state.think_mode = not state.think_mode
        state.agent = build_agent(think=state.think_mode)
        mode = "on" if state.think_mode else "off"
        tag = "success" if state.think_mode else "warning"
        console.print(f"[{tag}]Think mode {mode}.[/{tag}]")
        return

    if command == "/undo":
        await undo_last_operation(conn, console)
        return

    if command == "/history":
        show_history(conn, state.session_id, console)
        return

    if command == "/memory":
        show_memory(conn, console)
        return

    if command == "/scan":
        from memory.indexer import scan_home

        console.print("[dim]Scanning file system...[/dim]")
        await asyncio.to_thread(scan_home, conn, False)
        console.print("[success]File index updated.[/success]")
        return

    if command in ("/exit", "/quit"):
        raise SystemExit(0)

    console.print(f"[error]Unknown command:[/error] {cmd}. Type /help for available commands.")


async def undo_last_operation(conn, console):
    last = get_last_operation(conn)
    if not last:
        console.print("[dim]Nothing to undo.[/dim]")
        return

    operation = last["operation"]
    source = last["source"]
    destination = last["destination"]

    if operation in ("move", "rename"):
        if not source or not destination:
            console.print("[error]Operation metadata incomplete; cannot undo.[/error]")
            return
        if not Path(destination).exists():
            console.print("[warning]Cannot undo: destination no longer exists.[/warning]")
            return
        try:
            _shutil.move(destination, source)
            console.print(f"[success]Undone: moved back to {source}[/success]")
        except (OSError, _shutil.Error) as exc:
            console.print(f"[error]Undo failed:[/error] {exc}")
        return

    if operation == "delete":
        console.print("[dim]Deletion was moved to trash. Restore it from your file manager.[/dim]")
        return

    console.print(f"[dim]Undo not supported for operation: {operation}[/dim]")


def show_history(conn, session_id: str, console):
    history = get_recent_turns(conn, session_id, max_tokens=4000)
    if history:
        console.print(history)
    else:
        console.print("[dim]No history yet.[/dim]")


def show_memory(conn, console):
    profile = get_user_profile(conn)
    if profile:
        for key, value in profile.items():
            console.print(f"  [accent]{key}[/accent]  [dim]{value}[/dim]")
    else:
        console.print("[dim]Nothing stored yet.[/dim]")
