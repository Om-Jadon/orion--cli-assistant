import os
import sqlite3
from pathlib import Path
from orion import config

INDEXED_EXTENSIONS = {
    ".pdf", ".pptx", ".ppt", ".docx", ".doc",
    ".txt", ".md", ".csv", ".py", ".ipynb", ".json"
}

def scan_home(conn: sqlite3.Connection, verbose: bool = False):
    """Convenience wrapper to scan the user's HOME directory."""
    scan_directory(conn, config.HOME, verbose)


def scan_directory(conn: sqlite3.Connection, base_path: Path | str, verbose: bool = False):
    """Incremental scan of a given directory."""
    target = Path(base_path).expanduser().resolve()
    for root, dirs, files in os.walk(target):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for filename in files:
            path = Path(root) / filename
            if path.suffix.lower() not in INDEXED_EXTENSIONS:
                continue
            _index_file(conn, path, verbose)
    conn.commit()

def _index_file(conn: sqlite3.Connection, path: Path, verbose: bool):
    try:
        stat   = path.stat()
        mtime  = str(stat.st_mtime)

        existing = conn.execute(
            "SELECT modified_at FROM files WHERE path = ?", (str(path),)
        ).fetchone()
        if existing and existing["modified_at"] == mtime:
            return

        tags = _infer_tags(path)
        conn.execute(
            """INSERT OR REPLACE INTO files
               (path, name, extension, size_kb, modified_at, tags)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (str(path), path.name, path.suffix.lower(),
             stat.st_size // 1024, mtime, tags)
        )
        if verbose:
            print(f"  indexed: {path.name}")

    except (PermissionError, OSError):
        pass
    except Exception as e:
        if verbose:
            print(f"  error indexing {path.name}: {e}")

def _infer_tags(path: Path) -> str:
    parts      = [p.lower() for p in path.parts]
    name_parts = path.stem.lower().replace("_", " ").replace("-", " ").split()
    return ",".join(dict.fromkeys(parts + name_parts))
