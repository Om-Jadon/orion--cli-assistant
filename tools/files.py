import os
import shutil
import subprocess
from pathlib import Path
from safety.boundaries import validate_path

HOME = Path.home()


async def find_files(query: str) -> str:
    """Search for files matching a name pattern. Use this to locate any file before operating on it."""
    if not query:
        return "Provide a filename or search term."
    try:
        out = subprocess.run(
            ["find", str(HOME), "-iname", f"*{query}*",
             "-not", "-path", "*/.*", "-maxdepth", "8"],
            capture_output=True, text=True, timeout=5
        )
        results = [r for r in out.stdout.strip().split("\n") if r][:10]
    except subprocess.TimeoutExpired:
        return "Search timed out. Try being more specific."
    return "\n".join(results) or f"No files found matching '{query}'"


async def list_directory(path: str) -> str:
    """List contents of a directory. Pass '~' for the home directory."""
    target = Path(path).expanduser() if path and path != "~" else HOME
    ok, resolved = validate_path(str(target))
    if not ok:
        return resolved
    p = Path(resolved)
    if not p.is_dir():
        return f"Not a directory: {resolved}"
    items = sorted(p.iterdir())
    return "\n".join(str(i) for i in items[:50])


async def read_file(path: str) -> str:
    """Read and return the contents of a file."""
    ok, resolved = validate_path(path)
    if not ok:
        return resolved
    try:
        return Path(resolved).read_text(errors="replace")[:4000]
    except Exception as e:
        return f"Error reading {path}: {e}"


async def open_file(path: str) -> str:
    """Open a file in the default application using xdg-open."""
    ok, resolved = validate_path(path)
    if not ok:
        return resolved
    if not Path(resolved).exists():
        return f"Not found: {path}. Use find_files first to locate it."
    subprocess.Popen(["xdg-open", resolved])
    return f"Opened {Path(resolved).name}"


async def move_file(source: str, destination: str) -> str:
    """Move or rename a file. Provide full paths for both source and destination."""
    ok, src = validate_path(source)
    if not ok:
        return src
    ok, dst = validate_path(destination)
    if not ok:
        return dst
    try:
        shutil.move(src, dst)
        return f"Moved {Path(src).name} → {dst}"
    except Exception as e:
        return f"Error moving file: {e}"


async def delete_file(path: str) -> str:
    """Move a file to the trash."""
    ok, resolved = validate_path(path)
    if not ok:
        return resolved
    subprocess.run(["gio", "trash", resolved])
    return f"Moved to trash: {Path(resolved).name}"
