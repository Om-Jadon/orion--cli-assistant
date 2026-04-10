import sqlite3
import sqlite_vec
from config import DB_PATH, EMBED_DIM


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    _run_migrations(conn)
    return conn


def _run_migrations(conn: sqlite3.Connection):
    conn.executescript(f"""
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

        CREATE TABLE IF NOT EXISTS files (
            id          INTEGER PRIMARY KEY,
            path        TEXT UNIQUE NOT NULL,
            name        TEXT NOT NULL,
            extension   TEXT,
            size_kb     INTEGER,
            modified_at TEXT,
            tags        TEXT
        );

        CREATE TABLE IF NOT EXISTS operation_log (
            id          INTEGER PRIMARY KEY,
            operation   TEXT NOT NULL,
            source      TEXT,
            destination TEXT,
            timestamp   TEXT DEFAULT (datetime('now'))
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
            content, key, source,
            tokenize='porter unicode61'
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS vec_memory USING vec0(
            embedding float[{EMBED_DIM}]
        );

        CREATE TABLE IF NOT EXISTS vec_meta (
            rowid       INTEGER PRIMARY KEY,
            content     TEXT,
            source      TEXT,
            source_id   INTEGER
        );
    """)
    conn.commit()
