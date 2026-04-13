import sqlite3
import sqlite_vec
import pytest
from unittest.mock import MagicMock
from unittest.mock import AsyncMock, patch

from orion.memory.embeddings import serialize
from orion.config import EMBED_DIM


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
            embedding float[384]
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
async def test_hybrid_search_returns_results():
    from orion.memory.retrieval import hybrid_search

    conn = make_in_memory_conn()
    try:
        # Insert a row into vec_meta
        conn.execute(
            "INSERT INTO vec_meta (rowid, content, source) VALUES (1, 'the quick brown fox', 'test')"
        )

        # Insert matching row into memory_fts
        conn.execute(
            "INSERT INTO memory_fts (rowid, content, key, source) VALUES (1, 'the quick brown fox', 'key1', 'test')"
        )

        # Build a 384-dim vector and insert into vec_memory
        test_vector = [0.1] * EMBED_DIM
        serialized = serialize(test_vector)
        conn.execute(
            "INSERT INTO vec_memory (rowid, embedding) VALUES (1, ?)",
            (sqlite3.Binary(serialized),)
        )
        conn.commit()

        # Mock embed to return the same vector so semantic search matches
        with patch("orion.memory.retrieval.embed", new=AsyncMock(return_value=test_vector)):
            results = await hybrid_search(conn, "quick brown fox", k=5)

        assert len(results) >= 1
        assert results[0]["content"] == "the quick brown fox"
        assert results[0]["source"] == "test"
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_hybrid_search_logs_debug_for_fts_and_vec_errors():
    from orion.memory.retrieval import hybrid_search

    conn = MagicMock()
    conn.execute.side_effect = [
        sqlite3.OperationalError("fts failed"),
        Exception("vec failed"),
    ]

    with patch("orion.memory.retrieval.embed", new=AsyncMock(return_value=[0.1] * EMBED_DIM)), \
         patch("orion.memory.retrieval.logger.debug") as mock_debug:
        results = await hybrid_search(conn, "query", k=5)

    assert results == []
    assert mock_debug.call_count >= 2

@pytest.mark.asyncio
async def test_hybrid_search_succeeds_when_only_fts_matches():
    from orion.memory.retrieval import hybrid_search

    conn = make_in_memory_conn()
    try:
        # FTS matched but Vector returns nothing (due to missing embedding or threshold logic)
        conn.execute("INSERT INTO vec_meta (rowid, content, source) VALUES (1, 'keyword only', 'test')")
        conn.execute("INSERT INTO memory_fts (rowid, content, key, source) VALUES (1, 'keyword only', 'key1', 'test')")
        conn.commit()

        with patch("orion.memory.retrieval.embed", new=AsyncMock(return_value=[0.1] * EMBED_DIM)):
            results = await hybrid_search(conn, "keyword only", k=5)

        assert len(results) == 1
        assert results[0]["content"] == "keyword only"
    finally:
        conn.close()

@pytest.mark.asyncio
async def test_hybrid_search_succeeds_when_only_vec_matches():
    from orion.memory.retrieval import hybrid_search

    conn = make_in_memory_conn()
    try:
        # Vector matched but FTS returns nothing (no keyword match)
        conn.execute("INSERT INTO vec_meta (rowid, content, source) VALUES (2, 'semantic meaning', 'test')")
        test_vector = [0.1] * EMBED_DIM
        conn.execute("INSERT INTO vec_memory (rowid, embedding) VALUES (2, ?)", (sqlite3.Binary(serialize(test_vector)),))
        conn.commit()

        with patch("orion.memory.retrieval.embed", new=AsyncMock(return_value=test_vector)):
            # "completely different words" won't match FTS
            results = await hybrid_search(conn, "completely different words", k=5)

        assert len(results) == 1
        assert results[0]["content"] == "semantic meaning"
    finally:
        conn.close()
