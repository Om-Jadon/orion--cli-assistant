import sqlite3
from pathlib import Path
import pytest

from memory.indexer import _infer_tags


@pytest.fixture()
def conn(tmp_path):
    """In-memory SQLite connection with the files table created."""
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript("""
        CREATE TABLE IF NOT EXISTS files (
            id          INTEGER PRIMARY KEY,
            path        TEXT UNIQUE NOT NULL,
            name        TEXT NOT NULL,
            extension   TEXT,
            size_kb     INTEGER,
            modified_at TEXT,
            tags        TEXT
        );
    """)
    db.commit()
    return db


def _scan(conn, tmp_path, monkeypatch, verbose=False):
    """Patch config.HOME to tmp_path and call scan_home."""
    import config
    import memory.indexer as indexer
    monkeypatch.setattr(config, "HOME", tmp_path)
    monkeypatch.setattr(indexer, "HOME", tmp_path)
    from memory.indexer import scan_home
    scan_home(conn, verbose=verbose)


def test_scan_indexes_supported_files(tmp_path, conn, monkeypatch):
    (tmp_path / "script.py").write_text("print('hello')")
    (tmp_path / "notes.txt").write_text("some notes")

    _scan(conn, tmp_path, monkeypatch)

    rows = conn.execute("SELECT name FROM files ORDER BY name").fetchall()
    names = {r["name"] for r in rows}
    assert "script.py" in names
    assert "notes.txt" in names


def test_scan_skips_unsupported_files(tmp_path, conn, monkeypatch):
    (tmp_path / "program.exe").write_bytes(b"\x00\x01\x02")
    (tmp_path / "music.mp3").write_bytes(b"\xff\xfb\x90")

    _scan(conn, tmp_path, monkeypatch)

    count = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
    assert count == 0


def test_scan_skips_hidden_dirs(tmp_path, conn, monkeypatch):
    hidden = tmp_path / ".hidden"
    hidden.mkdir()
    (hidden / "secret.py").write_text("secret = True")

    _scan(conn, tmp_path, monkeypatch)

    count = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
    assert count == 0


def test_incremental_scan_skips_unchanged_files(tmp_path, conn, monkeypatch):
    f = tmp_path / "data.csv"
    f.write_text("a,b,c")

    _scan(conn, tmp_path, monkeypatch)
    _scan(conn, tmp_path, monkeypatch)

    count = conn.execute("SELECT COUNT(*) FROM files WHERE name = 'data.csv'").fetchone()[0]
    assert count == 1


def test_infer_tags_contains_name_parts():
    tags = _infer_tags(Path("/home/user/projects/my_notes.py"))
    tag_list = tags.split(",")
    assert "my" in tag_list
    assert "notes" in tag_list
