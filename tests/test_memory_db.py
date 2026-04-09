import sqlite3
import tempfile
from pathlib import Path
import pytest


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Redirect DB_PATH to a temp directory for each test."""
    import config
    test_db = tmp_path / ".orion" / "memory.db"
    monkeypatch.setattr(config, "DB_PATH", test_db)
    # Also patch the reference inside memory.db module
    import memory.db
    monkeypatch.setattr(memory.db, "DB_PATH", test_db)
    yield test_db


def test_get_connection_creates_db(isolated_db):
    from memory.db import get_connection
    conn = get_connection()
    assert isinstance(conn, sqlite3.Connection)
    assert isolated_db.exists()
    conn.close()


def test_migrations_create_all_tables(isolated_db):
    from memory.db import get_connection
    conn = get_connection()

    # Query sqlite_master for all table/virtual table names
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table', 'shadow') OR "
        "(type='table' AND name NOT LIKE 'sqlite_%')"
    ).fetchall()
    # Use a separate query that covers virtual tables too
    names = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table') "
            "AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    }

    expected = {
        "conversations",
        "user_profile",
        "files",
        "operation_log",
        "memory_fts",
        "vec_memory",
        "vec_meta",
    }
    assert expected.issubset(names), f"Missing tables: {expected - names}"
    conn.close()


def test_idempotent_migrations(isolated_db):
    from memory.db import get_connection
    conn1 = get_connection()
    conn1.close()
    # Second call must not raise
    conn2 = get_connection()
    conn2.close()
