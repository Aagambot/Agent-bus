"""TTL Caching and content-hash deduplication for URL / document indexing (FR-5)."""

import hashlib
import sqlite3
import time
from datetime import datetime, timezone
from typing import Optional


def compute_content_hash(content: str) -> str:
    """Compute SHA-256 hash of text content for deduplication."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def check_cache(
    conn: sqlite3.Connection,
    uri: str,
    content_hash: str,
    ttl_ms: int = 86_400_000,
    force: bool = False,
) -> Optional[str]:
    """Check if URI or content hash is already cached and valid."""
    if force:
        return None

    # 1. Check exact content hash match
    cursor = conn.execute(
        "SELECT source_id FROM sources WHERE content_hash = ? LIMIT 1",
        (content_hash,),
    )
    row = cursor.fetchone()
    if row:
        return row[0]

    # 2. Check URI and TTL
    if uri and uri.startswith(("http://", "https://")):
        cursor = conn.execute(
            """
            SELECT source_id, fetched_at, ttl_ms
            FROM sources
            WHERE uri = ?
            ORDER BY fetched_at DESC
            LIMIT 1
            """,
            (uri,),
        )
        row = cursor.fetchone()
        if row:
            source_id, fetched_at_str, row_ttl = row
            try:
                # Parse ISO timestamp
                fetched_at = datetime.fromisoformat(fetched_at_str.replace("Z", "+00:00"))
                now = datetime.now(timezone.utc)
                age_ms = (now - fetched_at).total_seconds() * 1000.0
                if age_ms < row_ttl:
                    return source_id
            except Exception:
                pass

    return None
