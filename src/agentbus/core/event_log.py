"""Append-only event log with priority tiers and cursor pagination (FR-9, FR-10, FR-18)."""

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .acl import tuple_to_ns_str, ns_str_to_tuple
from .models import Event


def record_event(
    conn: sqlite3.Connection,
    agent_id: str,
    run_id: str,
    namespace: tuple[str, ...],
    event_type: str,
    priority: int,
    payload: Dict[str, Any] | None = None,
    ref_ids: List[str] | None = None,
) -> str:
    """Append a typed event to the immutable log."""
    event_id = f"evt_{uuid.uuid4().hex}"
    ts = datetime.now(timezone.utc).isoformat()
    ns_str = tuple_to_ns_str(namespace)
    payload_json = json.dumps(payload or {})
    ref_ids_json = json.dumps(ref_ids or [])

    conn.execute(
        """
        INSERT INTO events (event_id, ts, agent_id, run_id, namespace, type, priority, payload_json, ref_ids)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (event_id, ts, agent_id, run_id, ns_str, event_type, priority, payload_json, ref_ids_json),
    )
    return event_id


def poll_events(
    conn: sqlite3.Connection,
    agent_id: str,
    namespace_prefixes: List[tuple[str, ...]],
    since_cursor: Optional[str] = None,
    limit: int = 50,
) -> Tuple[List[Event], str]:
    """Poll events since a cursor (ts:event_id or ISO ts)."""
    sql = """
    SELECT event_id, ts, agent_id, run_id, namespace, type, priority, payload_json, ref_ids
    FROM events
    WHERE 1=1
    """
    params: List[Any] = []

    # Namespace prefix filter
    if namespace_prefixes:
        ns_clauses = []
        for ns in namespace_prefixes:
            ns_str = tuple_to_ns_str(ns)
            ns_clauses.append("(namespace = ? OR namespace LIKE ?)")
            params.extend([ns_str, f"{ns_str}:%"])
        sql += f" AND ({' OR '.join(ns_clauses)})"

    # Cursor filter
    if since_cursor:
        if ":" in since_cursor:
            c_ts, c_id = since_cursor.split(":", 1)
            sql += " AND (ts > ? OR (ts = ? AND event_id > ?))"
            params.extend([c_ts, c_ts, c_id])
        else:
            sql += " AND ts > ?"
            params.append(since_cursor)

    sql += " ORDER BY ts ASC, event_id ASC LIMIT ?"
    params.append(limit)

    cursor = conn.execute(sql, params)
    rows = cursor.fetchall()

    events = []
    next_cursor = since_cursor or ""

    for row in rows:
        eid, ts, aid, rid, ns_str, etype, prio, p_json, r_json = row
        events.append(
            Event(
                event_id=eid,
                ts=ts,
                agent_id=aid,
                run_id=rid,
                namespace=ns_str_to_tuple(ns_str),
                type=etype,
                priority=prio,
                payload=json.loads(p_json),
                ref_ids=json.loads(r_json),
            )
        )
        next_cursor = f"{ts}:{eid}"

    return events, next_cursor
