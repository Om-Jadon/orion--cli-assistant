import sqlite3
from memory.store import upsert_profile

_conn = None

def set_connection(conn: sqlite3.Connection):
    """Set the database connection for memory operations."""
    global _conn
    _conn = conn

async def remember_user_fact(key: str, value: str) -> str:
    """
    Intentionally persist a meaningful fact about the user for future sessions.
    
    Args:
        key: A concise identifier for the fact (e.g., 'name', 'role', 'preference', 'project_context').
        value: The detailed information to remember.
    """
    global _conn
    if _conn is None:
        from memory.db import get_connection
        _conn = get_connection()
    
    try:
        # We use a high confidence (1.0) because the LLM has explicitly 
        # decided this is a fact worth remembering.
        upsert_profile(_conn, key, value, confidence=1.0)
        return f"Learned that your {key} is: {value}"
    except Exception as e:
        return f"Error remembering fact: {e}"
