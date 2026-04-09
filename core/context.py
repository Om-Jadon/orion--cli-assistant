import sqlite3
from memory.store import get_recent_turns, get_user_profile
from memory.retrieval import hybrid_search, should_retrieve
from config import CONTEXT_PROFILE, CONTEXT_RECENT, CONTEXT_RETRIEVED


async def build_context(conn: sqlite3.Connection, query: str, session_id: str) -> str:
    parts = []

    # Tier 1: User profile (always)
    profile = get_user_profile(conn)
    if profile:
        profile_text = "\n".join(f"{k}: {v}" for k, v in profile.items())
        parts.append(f"USER PROFILE:\n{profile_text}")

    # Tier 2: Recent turns (always)
    recent = get_recent_turns(conn, session_id, max_tokens=CONTEXT_RECENT)
    if recent:
        parts.append(f"RECENT CONVERSATION:\n{recent}")

    # Tier 3: Semantic retrieval (only when needed)
    if should_retrieve(query):
        results = await hybrid_search(conn, query, k=5)
        if results:
            retrieved = "\n---\n".join(r["content"] for r in results)
            parts.append(f"RELEVANT MEMORY:\n{retrieved}")

    return "\n\n".join(parts)
