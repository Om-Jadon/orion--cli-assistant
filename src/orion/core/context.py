import sqlite3
from orion.memory.store import get_recent_turns, get_user_profile
from orion.memory.retrieval import hybrid_search
from orion import config


async def build_context(conn: sqlite3.Connection, query: str, session_id: str) -> str:
    parts = []

    # Tier 1: User profile (always)
    profile = get_user_profile(conn)
    if profile:
        profile_text = "\n".join(f"{k}: {v}" for k, v in profile.items())
        parts.append(f"USER PROFILE:\n{profile_text}")

    # Tier 2: Recent turns (always)
    recent = get_recent_turns(conn, session_id, max_tokens=config.CONTEXT_RECENT)
    if recent:
        parts.append(f"RECENT CONVERSATION:\n{recent}")

    # Tier 3: Semantic retrieval (always; MIN_RRF_SCORE threshold filters low-relevance noise)
    results = await hybrid_search(conn, query, k=5)
    if results:
        snippets = [
            result.get("content")
            for result in results
            if isinstance(result, dict) and result.get("content")
        ]
        if snippets:
            retrieved = "\n---\n".join(snippets)
            parts.append(f"RELEVANT MEMORY:\n{retrieved}")

    return "\n\n".join(parts)
