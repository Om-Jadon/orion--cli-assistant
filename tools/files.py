import os
import shutil
import subprocess
from pathlib import Path
from safety.boundaries import validate_path

HOME = Path.home()


async def manage_files(
    action: str,
    path: str = "",
    destination: str = "",
    query: str = "",
) -> str:
    """
    Unified file management. Actions: find | list | open | read | move | rename | delete | create.
    Always call action='find' first to locate a file before operating on it.
    """
    if action == "find":
        return _find_files(query or path)

    if action == "list":
        target = Path(path) if path else HOME
        ok, resolved = validate_path(str(target))
        if not ok:
            return resolved
        items = sorted(Path(resolved).iterdir()) if Path(resolved).is_dir() else []
        return "\n".join(str(i) for i in items[:50])

    if action == "open":
        ok, resolved = validate_path(path)
        if not ok:
            return resolved
        if not Path(resolved).exists():
            return f"Not found: {path}. Try action='find' first."
        subprocess.Popen(["xdg-open", resolved])
        return f"Opened {Path(resolved).name}"

    if action == "read":
        ok, resolved = validate_path(path)
        if not ok:
            return resolved
        try:
            return Path(resolved).read_text(errors="replace")[:4000]
        except Exception as e:
            return f"Error reading {path}: {e}"

    if action == "move":
        ok, src = validate_path(path)
        if not ok:
            return src
        ok, dst = validate_path(destination)
        if not ok:
            return dst
        shutil.move(src, dst)
        return f"Moved {Path(src).name} → {dst}"

    if action == "rename":
        ok, src = validate_path(path)
        if not ok:
            return src
        new_path = str(Path(src).parent / destination)
        ok, dst = validate_path(new_path)
        if not ok:
            return dst
        os.rename(src, dst)
        return f"Renamed to {destination}"

    if action == "delete":
        ok, resolved = validate_path(path)
        if not ok:
            return resolved
        subprocess.run(["gio", "trash", resolved])
        return f"Moved to trash: {Path(resolved).name}"

    if action == "create":
        ok, resolved = validate_path(path)
        if not ok:
            return resolved
        p = Path(resolved)
        if path.endswith("/"):
            p.mkdir(parents=True, exist_ok=True)
            return f"Created folder: {resolved}"
        else:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("")
            return f"Created file: {resolved}"

    return f"Unknown action: {action}"


def _find_files(query: str) -> str:
    """Search using find, falls back gracefully."""
    if not query:
        return "Provide a query or path to search."
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
