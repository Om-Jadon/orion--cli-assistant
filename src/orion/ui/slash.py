import asyncio
from dataclasses import dataclass
from pathlib import Path
import shutil as _shutil
from typing import Any
from rich.panel import Panel
from rich import box
from rich.table import Table

from orion.memory.store import pop_last_operation, get_recent_turns_list, get_user_profile
from orion.ui.renderer import print_system_error, print_system_info, print_system_warning


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
        grid = Table.grid(padding=(0, 2))
        grid.add_column(style="dim")
        grid.add_column()
        
        commands = [
            ("/help",    "show this message"),
            ("/clear",   "clear the terminal"),
            ("/undo",    "undo last file operation"),
            ("/history", "show this session's conversation"),
            ("/reset",   "clear current conversation context"),
            ("/memory",  "show what orion knows about you"),
            ("/config",  "open configuration file in editor"),
            ("/scan",    "re-index your home directory"),
            ("/exit",    "quit orion"),
        ]
        
        for cmd_name, desc in commands:
            grid.add_row(cmd_name, desc)

        help_panel = Panel(
            grid,
            title="[#cba6f7]✦ slash commands[/#cba6f7]",
            title_align="left",
            border_style="#89B4FA",
            box=box.ROUNDED,
            padding=(0, 2),
            expand=False
        )
        console.print()
        console.print(help_panel)
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
        console.print(Panel("[success]Conversation context cleared.[/success]", border_style="success", box=box.ROUNDED, padding=(0, 1), expand=False))
        return

    if command == "/memory":
        show_memory(conn, console)
        return

    if command == "/config":
        from orion import config
        import subprocess
        print_system_info(f"Opening [bold]{config.CONFIG_FILE}[/bold] in your editor...\n[#89B4FA]Note: Restart Orion for changes to take effect.[/#89B4FA]")
        try:
            # xdg-open is standard on most Linux desktops.
            # Using str() ensures Path object is converted for subprocess.
            subprocess.run(["xdg-open", str(config.CONFIG_FILE)], check=True)
        except Exception as exc:
            console.print(f"[error]Could not open config file:[/error] {exc}")
        return

    if command == "/scan":
        from orion.memory.indexer import scan_home

        console.print(Panel("[dim]Scanning file system...[/dim]", border_style="dim", box=box.ROUNDED, padding=(0, 1), expand=False))
        await asyncio.to_thread(scan_home, conn, False)
        console.print(Panel("[success]File index updated.[/success]", border_style="success", box=box.ROUNDED, padding=(0, 1), expand=False))
        return

    if command == "/exit":
        raise SystemExit(0)

    print_system_error(f"Unknown command: {cmd}. Type /help for available commands.")


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
            console.print(Panel(f"[success]{msg}[/success]", border_style="success", box=box.ROUNDED, padding=(0, 1), expand=False))
            return msg
        except (OSError, _shutil.Error) as exc:
            console.print(Panel(f"[error]Undo failed:[/error] {exc}", border_style="error", box=box.ROUNDED, padding=(0, 1), expand=False))
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

    print_system_info(f"Undo not supported for operation: {operation}")


def show_history(conn, session_id: str, console):
    from orion.ui.renderer import highlight_paths
    from rich.markdown import Markdown
    from rich.text import Text
    from rich.console import Group
    
    turns = get_recent_turns_list(conn, session_id, max_tokens=4000)
    if turns:
        elements = []
        for i, turn in enumerate(turns):
            role = turn["role"].lower()
            text = turn["content"]
            
            header = Text()
            if role == "user":
                header.append("User: ", style="cyan")
            elif role == "assistant":
                header.append("✦ ", style="#cba6f7")
                header.append("Orion: ", style="bold #cba6f7")
            else:
                header.append(f"{role.title()}: ", style="dim")
            
            elements.append(header)
            # Render Markdown for the content to restore bold/italic/link support
            elements.append(Markdown(highlight_paths(text)))
            
            if i < len(turns) - 1:
                elements.append(Text("")) # Vertical spacer between turns

        history_panel = Panel(
            Group(*elements),
            title="[#cba6f7]✦ session history[/#cba6f7]",
            title_align="left",
            border_style="#45475a", # Surface1 (subtle)
            box=box.ROUNDED,
            padding=(0, 2),
            expand=False
        )
        console.print()
        console.print(history_panel)
    else:
        console.print(Panel("[dim]No history yet.[/dim]", border_style="dim", box=box.ROUNDED, padding=(0, 1), expand=False))


def show_memory(conn, console):
    profile = get_user_profile(conn)
    if profile:
        table = Table.grid(padding=(0, 2))
        table.add_column(style="bold #89B4FA")
        table.add_column(style="dim")
        
        for key, value in profile.items():
            # Clean up keys for display
            display_key = key.replace("_", " ").title()
            table.add_row(display_key, value)
            
        memory_panel = Panel(
            table,
            title="[#cba6f7]✦ orion's memory[/#cba6f7]",
            title_align="left",
            border_style="#89B4FA",
            box=box.ROUNDED,
            padding=(0, 2),
            expand=False
        )
        console.print()
        console.print(memory_panel)
    else:
        console.print(Panel("[dim]Nothing stored yet.[/dim]", border_style="dim", box=box.ROUNDED, padding=(0, 1), expand=False))
