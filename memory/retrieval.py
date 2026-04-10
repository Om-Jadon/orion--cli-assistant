import sqlite3
from memory.embeddings import embed, serialize

MIN_RRF_SCORE = 0.01  # minimum combined RRF score to include a result

def _fts_escape(query: str) -> str:
    """Wrap query in double quotes for FTS5 to treat it as a phrase, escaping internal quotes."""
    return '"' + query.replace('"', '""') + '"'

async def hybrid_search(conn: sqlite3.Connection, query: str, k: int = 5) -> list[dict]:
    """Reciprocal Rank Fusion over FTS5 keyword + sqlite-vec semantic results."""
    # BM25 returns negative scores; most-negative = best match, so ASC sorts best matches first
    try:
        fts_results = conn.execute(
            """SELECT rowid, content, bm25(memory_fts) as score
               FROM memory_fts WHERE memory_fts MATCH ?
               ORDER BY score ASC LIMIT 20""",
            (_fts_escape(query),)
        ).fetchall()
    except sqlite3.OperationalError:
        fts_results = []

    try:
        query_vec = await embed(query)
        vec_results = conn.execute(
            """SELECT rowid, distance FROM vec_memory
               WHERE embedding MATCH ?
               ORDER BY distance LIMIT 20""",
            (sqlite3.Binary(serialize(query_vec)),)
        ).fetchall()
    except Exception:
        vec_results = []

    rrf_scores: dict[int, float] = {}
    RRF_K = 60

    for rank, row in enumerate(fts_results):
        rrf_scores[row["rowid"]] = rrf_scores.get(row["rowid"], 0) + 1 / (RRF_K + rank + 1)

    for rank, row in enumerate(vec_results):
        rrf_scores[row["rowid"]] = rrf_scores.get(row["rowid"], 0) + 1 / (RRF_K + rank + 1)

    top_ids = [
        r for r in sorted(rrf_scores, key=lambda r: rrf_scores[r], reverse=True)[:k]
        if rrf_scores[r] >= MIN_RRF_SCORE
    ]

    results = []
    for rowid in top_ids:
        meta = conn.execute(
            "SELECT content, source FROM vec_meta WHERE rowid = ?", (rowid,)
        ).fetchone()
        if meta:
            results.append(dict(meta))

    return results
