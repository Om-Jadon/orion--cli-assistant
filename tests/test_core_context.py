import sqlite3
import sqlite_vec
import pytest
from unittest.mock import AsyncMock, patch

from config import EMBED_DIM


def make_conn() -> sqlite3.Connection:
    """Create a real in-memory SQLite connection with full schema applied."""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS conversations (
            id          INTEGER PRIMARY KEY,
            session_id  TEXT NOT NULL,
            role        TEXT NOT NULL,
            content     TEXT NOT NULL,
            timestamp   TEXT DEFAULT (datetime('now')),
            tool_calls  TEXT
        );

        CREATE TABLE IF NOT EXISTS user_profile (
            key         TEXT PRIMARY KEY,
            value       TEXT NOT NULL,
            updated_at  TEXT DEFAULT (datetime('now')),
            confidence  REAL DEFAULT 1.0
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
            content, key, source,
            tokenize='porter unicode61'
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS vec_memory USING vec0(
            embedding float[256]
        );

        CREATE TABLE IF NOT EXISTS vec_meta (
            rowid       INTEGER PRIMARY KEY,
            content     TEXT,
            source      TEXT,
            source_id   INTEGER
        );
    """)
    conn.commit()
    return conn


@pytest.mark.asyncio
async def test_empty_db_returns_empty_string():
    from core.context import build_context

    conn = make_conn()
    result = await build_context(conn, "what is python?", session_id="s1")
    assert result == ""
    conn.close()


@pytest.mark.asyncio
async def test_profile_included_in_context():
    from core.context import build_context
    from memory.store import upsert_profile

    conn = make_conn()
    upsert_profile(conn, "name", "Alice")
    result = await build_context(conn, "what is python?", session_id="s1")
    assert "USER PROFILE:" in result
    assert "name: Alice" in result
    conn.close()


@pytest.mark.asyncio
async def test_recent_turns_included():
    from core.context import build_context
    from memory.store import save_turn

    conn = make_conn()
    save_turn(conn, "s1", "user", "Hello there")
    result = await build_context(conn, "what is python?", session_id="s1")
    assert "RECENT CONVERSATION:" in result
    assert "USER: Hello there" in result
    conn.close()


@pytest.mark.asyncio
async def test_retrieval_not_triggered_for_simple_query():
    from core.context import build_context

    conn = make_conn()
    with patch("core.context.hybrid_search", new=AsyncMock()) as mock_search:
        await build_context(conn, "what is python?", session_id="s1")
        mock_search.assert_not_called()
    conn.close()


@pytest.mark.asyncio
async def test_retrieval_triggered_for_recall_query():
    from core.context import build_context

    conn = make_conn()
    mock_results = [{"content": "We discussed Python yesterday", "source": "test"}]
    with patch("core.context.hybrid_search", new=AsyncMock(return_value=mock_results)):
        result = await build_context(conn, "do you remember what I said?", session_id="s1")
    assert "RELEVANT MEMORY:" in result
    assert "We discussed Python yesterday" in result
    conn.close()
