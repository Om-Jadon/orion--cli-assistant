import asyncio
from dataclasses import dataclass
from pathlib import Path
import shutil as _shutil
from typing import Any

from orion.memory.store import pop_last_operation, get_recent_turns, get_user_profile


@dataclass
class RuntimeState:
    agent: Any
    session_id: str


async def handle_slash(
    cmd: str,
    *,
    state: RuntimeState,
    conn,
    console,
) -> str | None:
    parts = cmd.strip().split()
    command = parts[0].lower() if parts else ""

    if command == "/help":
        console.print()
        console.print("  [accent]Slash commands[/accent]")
        console.print()
        console.print("  [dim]/help[/dim]       show this message")
        console.print("  [dim]/clear[/dim]      clear the terminal")
        console.print("  [dim]/undo[/dim]       undo last file operation")
        console.print("  [dim]/history[/dim]    show this session's conversation")
        console.print("  [dim]/reset[/dim]      clear current conversation context")
        console.print("  [dim]/memory[/dim]     show what orion knows about you")
        console.print("  [dim]/scan[/dim]       re-index your home directory")
        console.print("  [dim]/exit[/dim]       quit orion")
        console.print()
        return

    if command == "/clear":
        console.clear()
        return

    if command == "/undo":
        return await undo_last_operation(conn, console)

    if command == "/history":
        show_history(conn, state.session_id, console)
        return

    if command == "/reset":
        from orion.memory.store import delete_session_history
        delete_session_history(conn, state.session_id)
        console.print("[success]Conversation context cleared.[/success]")
        return

    if command == "/memory":
        show_memory(conn, console)
        return

    if command == "/scan":
        from orion.memory.indexer import scan_home

        console.print("[dim]Scanning file system...[/dim]")
        await asyncio.to_thread(scan_home, conn, False)
        console.print("[success]File index updated.[/success]")
        return

    if command in ("/exit", "/quit"):
        raise SystemExit(0)

    console.print(f"[error]Unknown command:[/error] {cmd}. Type /help for available commands.")


async def undo_last_operation(conn, console) -> str | None:
    last = pop_last_operation(conn)
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
            console.print("[warning]Cannot undo: target no longer exists.[/warning]")
            return
        try:
            _shutil.move(destination, source)
            msg = f"Undone: moved {Path(destination).name} back to {source}"
            console.print(f"[success]{msg}[/success]")
            return msg
        except (OSError, _shutil.Error) as exc:
            console.print(f"[error]Undo failed:[/error] {exc}")
        return

    if operation == "delete":
        if not source:
            console.print("[error]Deletion metadata incomplete; cannot undo.[/error]")
            return
        try:
            import subprocess
            
            # gio trash --restore often requires the trash:/// URI, not the original path.
            # We find it by matching the original path in 'gio trash --list'.
            list_proc = await asyncio.to_thread(
                subprocess.run, ["gio", "trash", "--list"], capture_output=True, text=True
            )
            
            trash_uri = None
            for line in list_proc.stdout.splitlines():
                if "\t" in line:
                    uri, path = line.split("\t", 1)
                    if path.strip() == source:
                        trash_uri = uri.strip()
                        break
            
            # If we couldn't find a URI, fallback to the source path (best effort)
            target = trash_uri or source

            res = await asyncio.to_thread(
                subprocess.run,
                ["gio", "trash", "--restore", target],
                capture_output=True,
                text=True
            )
            if res.returncode == 0:
                msg = f"Undone: restored {Path(source).name} from trash"
                console.print(f"[success]{msg}.[/success]")
                return msg
            else:
                err = res.stderr.strip() or "Is the file already restored?"
                console.print(f"[error]Undo failed:[/error] {err}")
        except Exception as exc:
            console.print(f"[error]Undo failed:[/error] {exc}")
        return

    if operation == "create":
        if not destination:
            console.print("[error]Creation metadata incomplete; cannot undo.[/error]")
            return
        if not Path(destination).exists():
            console.print("[warning]Cannot undo: created file no longer exists.[/warning]")
            return
        try:
            import subprocess
            res = await asyncio.to_thread(
                subprocess.run,
                ["gio", "trash", destination],
                capture_output=True,
                text=True
            )
            if res.returncode == 0:
                msg = f"Undone: moved created file {Path(destination).name} to trash"
                console.print(f"[success]{msg}.[/success]")
                return msg
            else:
                console.print(f"[error]Undo failed:[/error] {res.stderr.strip()}")
        except Exception as exc:
            console.print(f"[error]Undo failed:[/error] {exc}")
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
