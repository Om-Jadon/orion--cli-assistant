import sqlite3
import pytest


@pytest.fixture
def conn(tmp_path, monkeypatch):
    """Provide a real SQLite connection with migrations applied, isolated per test."""
    import config
    test_db = tmp_path / ".orion" / "memory.db"
    monkeypatch.setattr(config, "DB_PATH", test_db)
    import memory.db
    monkeypatch.setattr(memory.db, "DB_PATH", test_db)
    c = memory.db.get_connection()
    yield c
    c.close()


def test_extracts_name(conn):
    from memory.extractor import extract_and_store
    from memory.store import get_user_profile

    extract_and_store(conn, "my name is Alice")
    profile = get_user_profile(conn)

    assert profile["name"] == "alice"


def test_extracts_role(conn):
    from memory.extractor import extract_and_store
    from memory.store import get_user_profile

    extract_and_store(conn, "i'm a software engineer")
    profile = get_user_profile(conn)

    assert profile["role"] == "software engineer"


def test_extracts_generic_fact(conn):
    from memory.extractor import extract_and_store
    from memory.store import get_user_profile

    extract_and_store(conn, "my favorite language is python")
    profile = get_user_profile(conn)

    assert profile["favorite language"] == "python"


def test_no_match_no_store(conn):
    from memory.extractor import extract_and_store
    from memory.store import get_user_profile

    extract_and_store(conn, "what is the weather?")
    profile = get_user_profile(conn)

    assert profile == {}


def test_multiple_facts_in_one_message(conn):
    """Extract multiple facts from a single message."""
    from memory.extractor import extract_and_store
    from memory.store import get_user_profile

    extract_and_store(conn, "my name is Bob and i'm a data scientist")
    profile = get_user_profile(conn)

    assert profile["name"] == "bob"
    assert profile["role"] == "data scientist"


def test_extracts_with_punctuation(conn):
    """Ensure extraction works with punctuation like periods and commas."""
    from memory.extractor import extract_and_store
    from memory.store import get_user_profile

    extract_and_store(conn, "My name is Charlie. I'm a teacher.")
    profile = get_user_profile(conn)

    assert profile["name"] == "charlie"
    assert profile["role"] == "teacher"


def test_work_context_extraction(conn):
    """Test extraction of work/study context."""
    from memory.extractor import extract_and_store
    from memory.store import get_user_profile

    extract_and_store(conn, "i work at Google")
    profile = get_user_profile(conn)

    assert profile["context"] == "google"


def test_study_context_extraction(conn):
    """Test extraction of study context."""
    from memory.extractor import extract_and_store
    from memory.store import get_user_profile

    extract_and_store(conn, "i study in Germany")
    profile = get_user_profile(conn)

    assert profile["context"] == "germany"


def test_case_insensitivity(conn):
    """Ensure extraction is case-insensitive."""
    from memory.extractor import extract_and_store
    from memory.store import get_user_profile

    extract_and_store(conn, "MY NAME IS DIANA")
    profile = get_user_profile(conn)

    assert profile["name"] == "diana"
