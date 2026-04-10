import re
import sqlite3
from memory.store import upsert_profile

# Patterns that signal a learnable fact about the user
FACT_PATTERNS = [
    (r"\bmy name is (\w+)", "name"),
    (r"\bi(?:'m| am) (?:a |an )?(.+?)(?:\.|,| and |$)", "role"),
    (r"\bi (?:work|study) (?:at|in|on) (.+?)(?:\.|,|$)", "context"),
    (r"\bmy (.+?) is (.+?)(?:\.|,| and |$)", None),   # generic "my X is Y"
]


def extract_and_store(conn: sqlite3.Connection, user_text: str):
    """
    Run after each user turn. Extract facts and upsert into user_profile.
    Lightweight regex — no LLM call needed.
    """
    text = user_text.strip()

    for pattern, key in FACT_PATTERNS:
        m = re.search(pattern, text, flags=re.IGNORECASE)
        if not m:
            continue

        if key:
            upsert_profile(conn, key, m.group(1).strip(), confidence=0.8)
        else:
            # Generic "my X is Y"
            if len(m.groups()) >= 2:
                upsert_profile(conn, m.group(1).strip().lower(), m.group(2).strip(), confidence=0.7)
