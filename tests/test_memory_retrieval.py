import sqlite3
import sqlite_vec
import pytest
from unittest.mock import AsyncMock, patch

from memory.embeddings import serialize
from config import EMBED_DIM


def make_in_memory_conn() -> sqlite3.Connection:
    """Create a real in-memory SQLite connection with sqlite-vec loaded and schema applied."""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    conn.executescript("""
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


def test_should_retrieve_true():
    from memory.retrieval import should_retrieve
    assert should_retrieve("do you remember what I said?") is True


def test_should_retrieve_false():
    from memory.retrieval import should_retrieve
    assert should_retrieve("what is python?") is False


@pytest.mark.asyncio
async def test_hybrid_search_returns_results():
    from memory.retrieval import hybrid_search

    conn = make_in_memory_conn()

    # Insert a row into vec_meta
    conn.execute(
        "INSERT INTO vec_meta (rowid, content, source) VALUES (1, 'the quick brown fox', 'test')"
    )

    # Insert matching row into memory_fts
    conn.execute(
        "INSERT INTO memory_fts (rowid, content, key, source) VALUES (1, 'the quick brown fox', 'key1', 'test')"
    )

    # Build a 256-dim vector and insert into vec_memory
    test_vector = [0.1] * EMBED_DIM
    serialized = serialize(test_vector)
    conn.execute(
        "INSERT INTO vec_memory (rowid, embedding) VALUES (1, ?)",
        (sqlite3.Binary(serialized),)
    )
    conn.commit()

    # Mock embed to return the same vector so semantic search matches
    with patch("memory.retrieval.embed", new=AsyncMock(return_value=test_vector)):
        results = await hybrid_search(conn, "quick brown fox", k=5)

    assert len(results) >= 1
    assert results[0]["content"] == "the quick brown fox"
    assert results[0]["source"] == "test"

    conn.close()
