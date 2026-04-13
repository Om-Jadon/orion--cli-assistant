import sqlite3
from typing import Literal
from orion.memory.store import upsert_profile, delete_profile_key

_conn = None

def set_connection(conn: sqlite3.Connection):
    """Set the database connection for memory operations."""
    global _conn
    _conn = conn

def manage_user_memory(
    action: Literal["upsert", "delete"], 
    key: str, 
    value: str = None
) -> str:
    """
    Intentionally manage facts about the user for future sessions.
    MANDATORY: You MUST use this tool to persist or remove facts. Never just claim to remember something in text.
    
    Args:
        action: 'upsert' to add/update, 'delete' to remove.
        key: A concise identifier for the fact (e.g., 'name', 'role', 'preference', 'project').
        value: The information to remember (required for 'upsert'). Use 'None' for 'delete'.
    """
    global _conn
    if _conn is None:
        from orion.memory.db import get_connection
        _conn = get_connection()
    
    try:
        if action == "upsert":
            if not value:
                return "Error: value is required when action is 'upsert'."
            upsert_profile(_conn, key, value, confidence=1.0)
            return f"Successfully learned that your {key} is: {value}"
        
        elif action == "delete":
            existed = delete_profile_key(_conn, key)
            if existed:
                return f"Successfully forgotten: {key}"
            else:
                return f"No information found for key: {key}"
        
        else:
            return f"Error: unknown action '{action}'. Use 'upsert' or 'delete'."
            
    except Exception as e:
        return f"Error managing memory: {e}"
