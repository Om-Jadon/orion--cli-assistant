import sqlite3
import pytest


@pytest.fixture
def conn(tmp_path, monkeypatch):
    """Provide a real SQLite connection with migrations applied, isolated per test."""
    from orion import config
    test_db = tmp_path / ".orion" / "orion.memory.db"
    monkeypatch.setattr(config, "DB_PATH", test_db)
    from orion.memory import db
    monkeypatch.setattr(db, "DB_PATH", test_db)
    c = db.get_connection()
    yield c
    c.close()


def test_save_and_retrieve_turns(conn):
    from orion.memory.store import save_turn, get_recent_turns

    save_turn(conn, "s1", "user", "Hello")
    save_turn(conn, "s1", "assistant", "Hi there")
    save_turn(conn, "s1", "user", "How are you?")

    result = get_recent_turns(conn, "s1")

    assert "USER: Hello" in result
    assert "ASSISTANT: Hi there" in result
    assert "USER: How are you?" in result

    # Verify ordering — earlier turns come before later ones
    lines = result.splitlines()
    assert lines[0] == "USER: Hello"
    assert lines[1] == "ASSISTANT: Hi there"
    assert lines[2] == "USER: How are you?"


def test_recent_turns_token_limit(conn):
    from orion.memory.store import save_turn, get_recent_turns

    # Save 20 turns, each with a moderately long message (~15 words)
    for i in range(20):
        words = " ".join([f"word{j}" for j in range(15)])
        save_turn(conn, "s2", "user", words)

    # With max_tokens=50, only a few turns should be included
    result = get_recent_turns(conn, "s2", max_tokens=50)
    lines = [l for l in result.splitlines() if l.strip()]

    # All 20 turns would be ~320 words total, well above 50 — so we expect truncation
    assert len(lines) < 20


def test_recent_turns_does_not_undercount_long_url_like_content(conn):
    from orion.memory.store import save_turn, get_recent_turns

    # No-whitespace content used to be severely undercounted by split() word counting.
    long_url_like = "https://example.com/" + ("segment-" * 80)
    save_turn(conn, "s3", "user", long_url_like)

    # A realistic token budget should treat this as large enough to exceed 10 tokens.
    result = get_recent_turns(conn, "s3", max_tokens=10)
    assert result == ""


def test_upsert_profile_insert_and_update(conn):
    from orion.memory.store import upsert_profile, get_user_profile

    upsert_profile(conn, "name", "Alice", confidence=0.9)
    profile = get_user_profile(conn)
    assert profile["name"] == "Alice"

    # Update same key
    upsert_profile(conn, "name", "Bob", confidence=1.0)
    profile = get_user_profile(conn)
    assert profile["name"] == "Bob"
    # Should still only have one entry for 'name'
    rows = conn.execute("SELECT COUNT(*) FROM user_profile WHERE key = 'name'").fetchone()
    assert rows[0] == 1


def test_get_user_profile_returns_dict(conn):
    from orion.memory.store import upsert_profile, get_user_profile

    upsert_profile(conn, "location", "NYC", confidence=0.8)
    upsert_profile(conn, "language", "Python", confidence=1.0)

    profile = get_user_profile(conn)

    assert isinstance(profile, dict)
    assert profile["location"] == "NYC"
    assert profile["language"] == "Python"


def test_log_and_get_last_operation(conn):
    from orion.memory.store import log_operation, get_last_operation

    log_operation(conn, "move", "/src/file.txt", "/dst/file.txt")
    row = get_last_operation(conn)

    assert row is not None
    assert row["operation"] == "move"
    assert row["source"] == "/src/file.txt"
    assert row["destination"] == "/dst/file.txt"


def test_get_last_operation_returns_most_recent(conn):
    from orion.memory.store import log_operation, get_last_operation

    log_operation(conn, "copy", "/a", "/b")
    log_operation(conn, "delete", "/c", "/d")

    row = get_last_operation(conn)
    assert row["operation"] == "delete"
    assert row["source"] == "/c"
