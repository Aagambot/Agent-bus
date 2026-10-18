"""LangGraph BaseStore implementation for agentbus (FR-21)."""

import asyncio
import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Literal, Optional, Tuple, Union

from langgraph.store.base import (
    BaseStore,
    GetOp,
    Item,
    ListNamespacesOp,
    Op,
    PutOp,
    Result,
    SearchItem,
    SearchOp,
)

from agentbus.core import Bus
from agentbus.core.acl import NamespaceACL, tuple_to_ns_str, ns_str_to_tuple


class AgentBusStore(BaseStore):
    """A durable, searchable shared memory store for LangGraph graphs."""

    def __init__(self, bus: Bus, agent_id: str = "default"):
        self.bus = bus
        self.agent_id = agent_id

    def _matches_filter(self, item_val: Dict[str, Any], filter_dict: Optional[Dict[str, Any]]) -> bool:
        """Evaluate filter dictionary against item value in Python memory."""
        if not filter_dict:
            return True
        for k, v in filter_dict.items():
            actual = item_val.get(k)
            if isinstance(v, list):
                if actual not in v:
                    return False
            elif actual != v:
                return False
        return True

    def _get(self, namespace: Tuple[str, ...], key: str) -> Optional[Item]:
        """Internal fetch for single key-value item."""
        NamespaceACL.check(self.agent_id, namespace, mode="read")
        ns_str = tuple_to_ns_str(namespace)

        with self.bus._get_read_conn() as conn:
            cursor = conn.execute(
                "SELECT value_json, updated_at FROM items WHERE namespace = ? AND key = ? LIMIT 1",
                (ns_str, key),
            )
            row = cursor.fetchone()
            if not row:
                return None
            val_json, updated_at_str = row
            val_dict = json.loads(val_json)
            return Item(
                value=val_dict,
                key=key,
                namespace=namespace,
                created_at=updated_at_str,
                updated_at=updated_at_str,
            )

    def _put(
        self,
        namespace: Tuple[str, ...],
        key: str,
        value: Dict[str, Any],
        index: Union[Literal[False], List[str], None] = None,
        ttl: Optional[float] = None,
    ) -> None:
        """Internal upsert for key-value item with FTS5 indexing."""
        NamespaceACL.check(self.agent_id, namespace, mode="write")
        ns_str = tuple_to_ns_str(namespace)
        now_ts = datetime.now(timezone.utc).isoformat()
        val_json = json.dumps(value)

        def write_tx(conn: sqlite3.Connection) -> None:
            conn.execute(
                """
                INSERT INTO items (namespace, key, value_json, version, updated_by, updated_at)
                VALUES (?, ?, ?, 1, ?, ?)
                ON CONFLICT(namespace, key) DO UPDATE SET
                  value_json = excluded.value_json,
                  version = items.version + 1,
                  updated_by = excluded.updated_by,
                  updated_at = excluded.updated_at
                """,
                (ns_str, key, val_json, self.agent_id, now_ts),
            )

        self.bus._writer_queue.submit(write_tx)

        # Indexing into FTS5 hybrid search
        if index is not False:
            text_parts = []
            if isinstance(index, list):
                for f in index:
                    if f in value:
                        text_parts.append(f"- **{f}**: {str(value[f])}")
            else:
                # Default: index all top-level string fields
                for f_name, f_val in value.items():
                    if isinstance(f_val, str) and f_val.strip():
                        text_parts.append(f"- **{f_name}**: {f_val}")

            if text_parts:
                doc_text = f"# Item: {key}\n\n" + "\n".join(text_parts)
                self.bus.index(
                    content=doc_text,
                    agent=self.agent_id,
                    ns=namespace,
                    uri=f"item://{ns_str}/{key}",
                )

    def _delete(self, namespace: Tuple[str, ...], key: str) -> None:
        """Internal delete for key-value item."""
        NamespaceACL.check(self.agent_id, namespace, mode="write")
        ns_str = tuple_to_ns_str(namespace)
        item_uri = f"item://{ns_str}/{key}"

        def write_tx(conn: sqlite3.Connection) -> None:
            conn.execute("DELETE FROM items WHERE namespace = ? AND key = ?", (ns_str, key))
            conn.execute(
                "DELETE FROM chunks WHERE source_id IN (SELECT source_id FROM sources WHERE uri = ?)",
                (item_uri,),
            )
            conn.execute(
                "DELETE FROM chunks_trigram WHERE source_id IN (SELECT source_id FROM sources WHERE uri = ?)",
                (item_uri,),
            )
            conn.execute("DELETE FROM sources WHERE uri = ?", (item_uri,))

        self.bus._writer_queue.submit(write_tx)

    def _search(
        self,
        namespace_prefix: Tuple[str, ...],
        query: Optional[str] = None,
        filter: Optional[Dict[str, Any]] = None,
        limit: int = 10,
        offset: int = 0,
    ) -> List[SearchItem]:
        """Internal search implementation."""
        NamespaceACL.check(self.agent_id, namespace_prefix, mode="read")
        ns_prefix_str = tuple_to_ns_str(namespace_prefix)

        results: List[SearchItem] = []

        if query:
            hits = self.bus.search(query=query, namespace=namespace_prefix, k=limit + offset + 20)
            seen_keys = set()
            for hit in hits:
                uri = ""
                with self.bus._get_read_conn() as conn:
                    c = conn.execute("SELECT uri FROM sources WHERE source_id = ? LIMIT 1", (hit.source_id,))
                    row = c.fetchone()
                    if row:
                        uri = row[0]

                key = uri.split("/")[-1] if uri.startswith("item://") else hit.source_id
                if key in seen_keys:
                    continue
                seen_keys.add(key)

                item = self._get(hit.namespace, key)
                val_dict = item.value if item else {"snippet": hit.snippet, "heading": hit.heading_path}

                if self._matches_filter(val_dict, filter):
                    results.append(
                        SearchItem(
                            namespace=hit.namespace,
                            key=key,
                            value=val_dict,
                            created_at=hit.created_at,
                            updated_at=hit.created_at,
                            score=hit.score,
                        )
                    )
        else:
            with self.bus._get_read_conn() as conn:
                sql = """
                SELECT namespace, key, value_json, updated_at
                FROM items
                WHERE (namespace = ? OR namespace LIKE ?)
                ORDER BY updated_at DESC
                """
                cursor = conn.execute(sql, (ns_prefix_str, f"{ns_prefix_str}:%"))
                rows = cursor.fetchall()
                for ns_str, k, v_json, u_at in rows:
                    v_dict = json.loads(v_json)
                    if self._matches_filter(v_dict, filter):
                        results.append(
                            SearchItem(
                                namespace=ns_str_to_tuple(ns_str),
                                key=k,
                                value=v_dict,
                                created_at=u_at,
                                updated_at=u_at,
                                score=None,
                            )
                        )

        return results[offset : offset + limit]

    def _list_namespaces(self, op: ListNamespacesOp) -> List[Tuple[str, ...]]:
        """Internal list_namespaces implementation handling match conditions."""
        with self.bus._get_read_conn() as conn:
            cursor = conn.execute("SELECT DISTINCT namespace FROM items")
            all_ns_strs = [r[0] for r in cursor.fetchall()]

        namespaces = [ns_str_to_tuple(s) for s in all_ns_strs]

        filtered = []
        for ns in namespaces:
            match = True
            if op.match_conditions:
                for cond in op.match_conditions:
                    c_path = cond.path
                    if cond.match_type == "prefix" and ns[:len(c_path)] != c_path:
                        match = False
                        break
                    elif cond.match_type == "suffix" and ns[-len(c_path):] != c_path:
                        match = False
                        break
            if not match:
                continue

            if op.max_depth and len(ns) > op.max_depth:
                continue
            filtered.append(ns)

        filtered.sort()
        return filtered[op.offset : op.offset + op.limit]

    def batch(self, ops: Iterable[Op]) -> List[Result]:
        """Execute a batch of store operations (BaseStore requirement)."""
        results: List[Result] = []
        for op in ops:
            if isinstance(op, GetOp):
                results.append(self._get(op.namespace, op.key))
            elif isinstance(op, PutOp):
                if op.value is None:
                    self._delete(op.namespace, op.key)
                else:
                    self._put(op.namespace, op.key, op.value, index=op.index, ttl=op.ttl)
                results.append(None)
            elif isinstance(op, SearchOp):
                results.append(
                    self._search(
                        op.namespace_prefix,
                        query=op.query,
                        filter=op.filter,
                        limit=op.limit,
                        offset=op.offset,
                    )
                )
            elif isinstance(op, ListNamespacesOp):
                results.append(self._list_namespaces(op))
            else:
                raise NotImplementedError(f"Unsupported store op: {type(op)}")
        return results

    async def abatch(self, ops: Iterable[Op]) -> List[Result]:
        """Execute a batch of store operations asynchronously."""
        return await asyncio.to_thread(self.batch, ops)
