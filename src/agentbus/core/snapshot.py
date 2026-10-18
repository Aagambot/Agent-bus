"""Byte-budgeted snapshot builder and session restore guide (FR-11, FR-12)."""

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .acl import tuple_to_ns_str, ns_str_to_tuple
from .models import Event, SessionGuide


def build_snapshot(
    conn: sqlite3.Connection,
    run_id: str,
    namespace: tuple[str, ...],
    budget_bytes: int = 2048,
) -> str:
    """Build a byte-budgeted snapshot summary from recorded events (FR-11)."""
    snapshot_id = f"snap_{uuid.uuid4().hex}"
    built_at = datetime.now(timezone.utc).isoformat()
    ns_str = tuple_to_ns_str(namespace)

    # Fetch events ordered by priority ASC (P1 first), ts DESC
    cursor = conn.execute(
        """
        SELECT event_id, ts, agent_id, run_id, namespace, type, priority, payload_json, ref_ids
        FROM events
        WHERE run_id = ? AND (namespace = ? OR namespace LIKE ?)
        ORDER BY priority ASC, ts DESC
        """,
        (run_id, ns_str, f"{ns_str}:%"),
    )
    rows = cursor.fetchall()

    included_events: List[Dict[str, Any]] = []
    dropped_count = 0
    current_bytes = 0

    # Skeleton JSON overhead estimate ~200 bytes
    base_budget = max(budget_bytes - 200, 500)

    for row in rows:
        eid, ts, aid, rid, r_ns, etype, prio, p_json, r_json = row
        item = {
            "id": eid,
            "ts": ts,
            "agent": aid,
            "type": etype,
            "prio": prio,
            "data": json.loads(p_json),
        }
        item_bytes = len(json.dumps(item).encode("utf-8"))

        if current_bytes + item_bytes <= base_budget or prio == 1:
            included_events.append(item)
            current_bytes += item_bytes
        else:
            dropped_count += 1

    body_obj = {
        "run_id": run_id,
        "built_at": built_at,
        "events": included_events,
        "budget_used": current_bytes,
        "budget_total": budget_bytes,
        "dropped_count": dropped_count,
    }
    body_json = json.dumps(body_obj)

    conn.execute(
        """
        INSERT INTO snapshots (snapshot_id, run_id, namespace, built_at, budget_bytes, body, consumed)
        VALUES (?, ?, ?, ?, ?, ?, 0)
        """,
        (snapshot_id, run_id, ns_str, built_at, budget_bytes, body_json),
    )
    return snapshot_id


def restore_session(
    conn: sqlite3.Connection,
    run_id: str,
    agent_id: str,
    namespace: tuple[str, ...],
) -> SessionGuide:
    """Restore previous session state into a compact SessionGuide (FR-12)."""
    ns_str = tuple_to_ns_str(namespace)

    # 1. Fetch latest snapshot
    cursor = conn.execute(
        """
        SELECT snapshot_id, body
        FROM snapshots
        WHERE run_id = ? AND namespace = ?
        ORDER BY built_at DESC
        LIMIT 1
        """,
        (run_id, ns_str),
    )
    snap_row = cursor.fetchone()

    events_list: List[Event] = []
    summary_text = "No prior snapshot found."

    if snap_row:
        snap_id, body_json = snap_row
        body = json.loads(body_json)
        summary_text = (
            f"Restored session for run '{run_id}'. Contains {len(body.get('events', []))} priority events "
            f"({body.get('dropped_count', 0)} low-priority events pruned to fit {body.get('budget_total', 2048)}B budget)."
        )
        for ev in body.get("events", []):
            events_list.append(
                Event(
                    event_id=ev["id"],
                    ts=ev["ts"],
                    agent_id=ev["agent"],
                    run_id=run_id,
                    namespace=namespace,
                    type=ev["type"],
                    priority=ev["prio"],
                    payload=ev.get("data", {}),
                )
            )
        # Mark consumed
        conn.execute("UPDATE snapshots SET consumed = 1 WHERE snapshot_id = ?", (snap_id,))

    # 2. Fetch available sources indexed in this run
    s_cursor = conn.execute(
        "SELECT source_id FROM sources WHERE run_id = ? LIMIT 50",
        (run_id,),
    )
    sources = [r[0] for r in s_cursor.fetchall()]

    return SessionGuide(
        summary=summary_text,
        recent_events=events_list,
        available_sources=sources,
        query_hint=f"run_id:{run_id} status",
    )
