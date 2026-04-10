import shutil
import subprocess
from pathlib import Path
from safety.boundaries import validate_path

HOME = Path.home()


async def find_files(query: str) -> str:
    """
    Search for files matching a name or keyword pattern.

    Args:
        query: The filename, extension, or keyword to search for (e.g. 'resume.pdf', '.py', 'notes').
    """
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
    """
    List all files and folders inside a directory.

    Args:
        path: The directory path to list. Use '~' for home, or provide an absolute path.
    """
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
    subprocess.Popen(["xdg-open", resolved])
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
    try:
        shutil.move(src, dst)
        return f"Moved {Path(src).name} → {dst}"
    except Exception as e:
        return f"Error moving file: {e}"


async def delete_file(path: str) -> str:
    """
    Permanently delete a file by moving it to the trash.

    Args:
        path: The absolute or home-relative path of the file to delete.
    """
    ok, resolved = validate_path(path)
    if not ok:
        return resolved
    subprocess.run(["gio", "trash", resolved])
    return f"Moved to trash: {Path(resolved).name}"
