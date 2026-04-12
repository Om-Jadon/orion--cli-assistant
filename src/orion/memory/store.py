import json
import sqlite3
from math import ceil
from orion import config


def save_turn(conn: sqlite3.Connection, session_id: str, role: str,
              content: str, tool_calls: list | None = None):
    conn.execute(
        """INSERT INTO conversations (session_id, role, content, tool_calls)
           VALUES (?, ?, ?, ?)""",
        (session_id, role, content, json.dumps(tool_calls) if tool_calls else None)
    )
    conn.commit()


def delete_session_history(conn: sqlite3.Connection, session_id: str):
    """Permanently delete all conversation turns for a given session."""
    conn.execute("DELETE FROM conversations WHERE session_id = ?", (session_id,))
    conn.commit()


def get_recent_turns(conn: sqlite3.Connection, session_id: str,
                     max_tokens: int | None = None) -> str:
    turns = get_recent_turns_list(conn, session_id, max_tokens)
    lines = [f"{t['role'].upper()}: {t['content']}" for t in turns]
    return "\n".join(lines)


def get_recent_turns_list(conn: sqlite3.Connection, session_id: str,
                          max_tokens: int | None = None) -> list[dict]:
    if max_tokens is None:
        max_tokens = config.CONTEXT_RECENT
    rows = conn.execute(
        """SELECT role, content FROM conversations
           WHERE session_id = ?
           ORDER BY id DESC LIMIT 20""",
        (session_id,)
    ).fetchall()

    turns = []
    total = 0
    for row in reversed(rows):
        role = row["role"]
        content = row["content"]
        tokens = _estimate_token_count(f"{role.upper()}: {content}")
        
        if total + tokens > max_tokens:
            break
            
        turns.append({"role": role, "content": content})
        total += tokens

    return turns


def _estimate_token_count(text: str) -> int:
    # Use a conservative estimate to avoid undercounting code/URLs with little whitespace.
    word_estimate = len(text.split())
    char_estimate = ceil(len(text) / 4)
    return max(word_estimate, char_estimate)


def upsert_profile(conn: sqlite3.Connection, key: str, value: str,
                   confidence: float = 1.0):
    conn.execute(
        """INSERT INTO user_profile (key, value, confidence)
           VALUES (?, ?, ?)
           ON CONFLICT(key) DO UPDATE SET
               value      = excluded.value,
               confidence = excluded.confidence,
               updated_at = datetime('now')""",
        (key, value, confidence)
    )
    conn.commit()


def get_user_profile(conn: sqlite3.Connection) -> dict:
    rows = conn.execute(
        "SELECT key, value FROM user_profile ORDER BY confidence DESC"
    ).fetchall()
    return {row["key"]: row["value"] for row in rows}


def delete_profile_key(conn: sqlite3.Connection, key: str) -> bool:
    """Delete a specific key from the user profile. Returns True if successful."""
    res = conn.execute("DELETE FROM user_profile WHERE key = ?", (key,))
    conn.commit()
    return res.rowcount > 0


def log_operation(conn: sqlite3.Connection, operation: str,
                  source: str, destination: str):
    conn.execute(
        """INSERT INTO operation_log (operation, source, destination)
           VALUES (?, ?, ?)""",
        (operation, source, destination)
    )
    conn.commit()


def get_last_operation(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM operation_log ORDER BY id DESC LIMIT 1"
    ).fetchone()


def pop_last_operation(conn: sqlite3.Connection) -> sqlite3.Row | None:
    """Fetch the latest operation and remove it from the log (atomic pop)."""
    row = conn.execute(
        "SELECT * FROM operation_log ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if row:
        conn.execute("DELETE FROM operation_log WHERE id = ?", (row["id"],))
        conn.commit()
    return row
