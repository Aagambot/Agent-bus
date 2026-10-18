"""FTS5 search queries across porter and trigram virtual tables (FR-2, FR-4)."""

import re
import sqlite3
from typing import List, Tuple

from .models import SearchResult


def sanitize_fts5_query(query: str) -> str:
    """Sanitize user query for safe FTS5 execution."""
    if not query:
        return ""
    # Remove quotes, parentheses, stars, and FTS5 operators
    cleaned = re.sub(r'["*^:(){}\[\]]', ' ', query)
    tokens = [t for t in cleaned.split() if t.upper() not in {"AND", "OR", "NOT", "NEAR"}]
    if not tokens:
        return ""
    # Wrap each token in double quotes for exact term safety
    return " OR ".join(f'"{t}"' for t in tokens)


def sanitize_trigram_query(query: str) -> str:
    """Prepare query for trigram index (requires tokens of >= 3 chars)."""
    cleaned = re.sub(r'["*^:(){}\[\]]', ' ', query)
    tokens = [t for t in cleaned.split() if len(t) >= 3 and t.upper() not in {"AND", "OR", "NOT"}]
    if not tokens:
        return ""
    return " OR ".join(f'"{t}"' for t in tokens)


def search_porter(
    conn: sqlite3.Connection,
    query: str,
    namespace_prefix: str,
    limit: int = 50,
    refs: List[str] | None = None,
) -> List[Tuple[str, str, str, str, str, str, str, float]]:
    """Query the porter FTS5 table with heading 2x weighting (FR-3).

    Returns tuples:
    (rowid, heading_path, body, source_id, namespace, agent_id, created_at, bm25_score)
    """
    sanitized = sanitize_fts5_query(query)
    if not sanitized:
        return []

    sql = """
    SELECT
      rowid,
      heading_path,
      snippet(chunks, 1, '<b>', '</b>', '...', 16) AS snippet_text,
      source_id,
      namespace,
      agent_id,
      created_at,
      bm25(chunks, 2.0, 1.0) AS score
    FROM chunks
    WHERE chunks MATCH ?
    """
    params = [sanitized]

    if namespace_prefix:
        sql += " AND (namespace = ? OR namespace LIKE ?)"
        params.extend([namespace_prefix, f"{namespace_prefix}:%"])

    if refs:
        placeholders = ",".join("?" for _ in refs)
        sql += f" AND source_id IN ({placeholders})"
        params.extend(refs)

    sql += " ORDER BY score ASC LIMIT ?"
    params.append(limit)

    try:
        cursor = conn.execute(sql, params)
        return cursor.fetchall()
    except sqlite3.OperationalError:
        return []


def search_trigram(
    conn: sqlite3.Connection,
    query: str,
    namespace_prefix: str,
    limit: int = 50,
    refs: List[str] | None = None,
) -> List[Tuple[str, str, str, str, str, str, str, float]]:
    """Query the trigram FTS5 table for substring / code identifier matching."""
    sanitized = sanitize_trigram_query(query)
    if not sanitized:
        return []

    sql = """
    SELECT
      rowid,
      heading_path,
      snippet(chunks_trigram, 1, '<b>', '</b>', '...', 16) AS snippet_text,
      source_id,
      namespace,
      agent_id,
      created_at,
      bm25(chunks_trigram, 2.0, 1.0) AS score
    FROM chunks_trigram
    WHERE chunks_trigram MATCH ?
    """
    params = [sanitized]

    if namespace_prefix:
        sql += " AND (namespace = ? OR namespace LIKE ?)"
        params.extend([namespace_prefix, f"{namespace_prefix}:%"])

    if refs:
        placeholders = ",".join("?" for _ in refs)
        sql += f" AND source_id IN ({placeholders})"
        params.extend(refs)

    sql += " ORDER BY score ASC LIMIT ?"
    params.append(limit)

    try:
        cursor = conn.execute(sql, params)
        return cursor.fetchall()
    except sqlite3.OperationalError:
        return []
