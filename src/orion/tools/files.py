import asyncio
import logging
import os
import sqlite3
import shutil
import subprocess
from pathlib import Path
from orion import config
from orion.safety.boundaries import validate_path
from orion.safety import confirm

logger = logging.getLogger(__name__)
_operation_conn = None
_search_conn = None

# Heavy directories to ignore during discovery to save tokens and prevent "trash" noise.
IGNORE_DIRS = {".git", "node_modules", "__pycache__", ".venv", ".orion", ".pytest_cache"}


def set_connection(conn):
    global _operation_conn, _search_conn
    _operation_conn = conn
    _search_conn = conn


def _log_operation(operation: str, source: str, destination: str):
    """Best-effort operation logging used by /undo command."""
    global _operation_conn
    try:
        if _operation_conn is None:
            from orion.memory.db import get_connection
            _operation_conn = get_connection()
        from orion.memory.store import log_operation
        log_operation(_operation_conn, operation, source, destination)
    except Exception:
        pass


def _classify_move_action(src: str, dst: str) -> str:
    dst_path = Path(dst)
    if dst_path.exists() and dst_path.is_dir():
        return "move"
    if Path(src).parent == dst_path.parent:
        return "rename"
    return "move"


def _has_graphical_session() -> bool:
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


async def find_files(query: str) -> str:
    """
    Search for files matching a name or keyword pattern. 
    MANDATORY: You MUST use this to locate a file before reading, opening, or deleting it.
    This tool recursively searches your home directory (up to depth 8), excluding junk folders like node_modules.

    Args:
        query: The filename, extension, or keyword to search for (e.g. 'resume.pdf', '.py', 'notes').
    """
    if not query:
        return "Provide a filename or search term."

    if _search_conn is not None:
        try:
            pattern = f"%{query}%"
            rows = _search_conn.execute(
                """SELECT path FROM files
                   WHERE name LIKE ? OR tags LIKE ?
                   LIMIT 10""",
                (pattern, pattern),
            ).fetchall()
            indexed = [row["path"] for row in rows]
            if indexed:
                return "\n".join(indexed)
        except sqlite3.Error as e:
            logger.debug("find_files index query failed: %s", e)

    try:
        # Build exclude arguments for 'find' command
        exclude_args = []
        for d in IGNORE_DIRS:
            exclude_args.extend(["-not", "-path", f"*/{d}/*"])

        out = await asyncio.to_thread(
            subprocess.run,
            ["find", str(config.HOME), "-maxdepth", "8", "-not", "-path", "*/.*"] + exclude_args + ["-iname", f"*{query}*"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        results = [r for r in out.stdout.strip().split("\n") if r][:10]
    except subprocess.TimeoutExpired:
        return "Search timed out. Try being more specific."
    except Exception as e:
        return f"Search failed: {e}"
    return "\n".join(results) or f"No files found matching '{query}'"


async def list_directory(path: str) -> str:
    """
    List all files and folders inside a directory.

    Args:
        path: The directory path to list. Use '~' for home, or provide an absolute path.
    """
    target = Path(path).expanduser() if path and path != "~" else config.HOME
    ok, resolved = validate_path(str(target))
    if not ok:
        return resolved
    p = Path(resolved)
    if not p.is_dir():
        return f"Not a directory: {resolved}"
    
    # Filter items based on IGNORE_DIRS and hidden files
    items = sorted(
        item for item in p.iterdir() 
        if item.name not in IGNORE_DIRS and not item.name.startswith(".")
    )
    
    shown = "\n".join(str(i) for i in items[:50])
    if len(items) > 50:
        shown += f"\n(showing 50 of {len(items)})"
    return shown


async def read_file(path: str) -> str:
    """
    Read and return the full text contents of a file.

    Args:
        path: The absolute or home-relative path of the file to read.
    """
    ok, resolved = validate_path(path)
    if not ok:
        return resolved
    try:
        return Path(resolved).read_text(errors="replace")[:4000]
    except Exception as e:
        return f"Error reading {path}: {e}"


async def open_file(path: str) -> str:
    """
    Open a file in its default application (e.g. PDF reader, image viewer).

    Args:
        path: The absolute or home-relative path of the file to open.
    """
    ok, resolved = validate_path(path)
    if not ok:
        return resolved
    if not Path(resolved).exists():
        return f"Not found: {path}. Use find_files first to locate it."
    if not _has_graphical_session():
        return "Cannot open file: no graphical desktop session detected. Use read_file or open it manually from a desktop session."
    if shutil.which("xdg-open") is None:
        return "Cannot open file: xdg-open is not installed on this system."
    try:
        subprocess.Popen(["xdg-open", resolved])
    except OSError as e:
        return f"Could not open file with xdg-open: {e}"
    return f"Opened {Path(resolved).name}"


async def move_file(source: str, destination: str) -> str:
    """
    Move or rename a file from one path to another.

    Args:
        source: The current absolute path of the file to move.
        destination: The target absolute path or directory to move the file to.
    """
    ok, src = validate_path(source)
    if not ok:
        return src
    ok, dst = validate_path(destination)
    if not ok:
        return dst
    action = _classify_move_action(src, dst)
    confirmed = await confirm.ask_file_action_confirmation(
        action,
        source_path=src,
        destination_path=dst,
    )
    if not confirmed.confirmed:
        if confirmed.repeated_denial:
            return (
                f"File {action} cancelled. Confirmation was already denied for this exact action in this turn. "
                f"from={src}; to={dst}"
            )
        return (
            f"File {action} cancelled by user confirmation. from={src}; to={dst}"
        )
    try:
        moved_to = shutil.move(src, dst)
        _log_operation("move", src, str(moved_to))
        return f"Moved {Path(src).name} -> {moved_to}"
    except Exception as e:
        return f"Error moving file: {e}"


async def delete_file(path: str) -> str:
    """
    Delete a file by moving it to the trash.

    Args:
        path: The absolute or home-relative path of the file to delete.
    """
    ok, resolved = validate_path(path)
    if not ok:
        return resolved
    if not Path(resolved).exists():
        return f"Not found: {path}."
    confirmed = await confirm.ask_file_action_confirmation(
        "delete",
        source_path=resolved,
    )
    if not confirmed.confirmed:
        if confirmed.repeated_denial:
            return (
                "File delete cancelled. Confirmation was already denied for this exact action in this turn. "
                f"path={resolved}"
            )
        return (
            f"File delete cancelled by user confirmation. path={resolved}"
        )
    result = await asyncio.to_thread(
        subprocess.run, ["gio", "trash", resolved], capture_output=True, text=True
    )
    if result.returncode != 0:
        return f"Error moving to trash: {result.stderr.strip() or 'unknown error'}"
    _log_operation("delete", resolved, "trash")
    return f"Moved to trash: {Path(resolved).name}"


async def write_file(path: str, content: str) -> str:
    """
    Create a new file or overwrite an existing one with specific content.
    MANDATORY: Use this instead of shell redirection (like '>' or '>>') to ensure safe file creation.
    This tool handles user confirmation for overwriting existing files.

    Args:
        path: The absolute or home-relative path of the file to write.
        content: The full text content to write to the file.
    """
    ok, resolved = validate_path(path)
    if not ok:
        return resolved

    p = Path(resolved)
    action = "overwrite" if p.exists() else "create"

    confirmed = await confirm.ask_file_action_confirmation(
        action,
        source_path=resolved,
    )
    if not confirmed.confirmed:
        if confirmed.repeated_denial:
            return (
                f"File {action} cancelled. Confirmation was already denied for this exact action in this turn. "
                f"path={resolved}"
            )
        return f"File {action} cancelled by user confirmation. path={resolved}"

    try:
        p.write_text(content)
        # Log as 'create' regardless of whether it was an overwrite for simple undo support
        _log_operation("create", None, resolved)
        return f"Successfully {action}ed {p.name}"
    except Exception as e:
        return f"Error writing file: {e}"
