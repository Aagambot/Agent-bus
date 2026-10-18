"""Public Bus facade for agentbus-core."""

import asyncio
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import weakref
from contextlib import contextmanager

from .acl import NamespaceACL, tuple_to_ns_str, ns_str_to_tuple
from .chunker import chunk_markdown
from .db import create_connection, init_db
from .event_log import record_event, poll_events
from .fts5 import search_porter, search_trigram
from .models import Event, IndexResult, SearchResult, SessionGuide, TrustLabel
from .redactor import SecretRedactor
from .rrf import merge_rrf
from .snapshot import build_snapshot, restore_session
from .ttl_cache import check_cache, compute_content_hash
from .writer_queue import WriterQueue


class Bus:
    """The central embedded shared memory bus."""

    def __init__(self, db_path: str = "~/.agentbus/default.db", default_agent: str = "default", timeout: float = 30.0):
        if db_path != ":memory:":
            self.db_path = str(Path(os.path.expanduser(db_path)).resolve())
        else:
            self.db_path = ":memory:"

        self.default_agent = default_agent
        self.timeout = timeout

        # Initialize schema
        init_db(self.db_path)

        # Dedicated serialized writer queue
        self._writer_queue = WriterQueue(self.db_path, timeout=timeout)
        self._finalizer = weakref.finalize(self, self._writer_queue.close)

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    @contextmanager
    def _get_read_conn(self):
        """Yield a read connection and ensure it is closed."""
        conn = create_connection(self.db_path, timeout=self.timeout)
        try:
            yield conn
        finally:
            conn.close()

    def index(
        self,
        content: str,
        agent: str = "default",
        ns: Optional[Tuple[str, ...]] = None,
        namespace: Optional[Tuple[str, ...]] = None,
        uri: str = "",
        trust_label: str = "agent-generated",
        run_id: str = "default_run",
    ) -> IndexResult:
        """Index markdown or text content into the shared store."""
        target_ns = ns or namespace or NamespaceACL.get_default_namespace(agent)
        NamespaceACL.check(agent, target_ns, mode="write")

        # Pre-index secret redaction (SEC-3)
        clean_content = SecretRedactor.redact(content)
        content_hash = compute_content_hash(clean_content)
        uri = uri or f"text://{content_hash[:16]}"

        # Fast cache / deduplication check
        with self._get_read_conn() as read_conn:
            existing_id = check_cache(read_conn, uri=uri, content_hash=content_hash)
            if existing_id:
                return IndexResult(source_id=existing_id, content_hash=content_hash, chunk_count=0, cached=True)

        source_id = f"src_{uuid.uuid4().hex}"
        now_ts = datetime.now(timezone.utc).isoformat()
        ns_str = tuple_to_ns_str(target_ns)
        byte_count = len(clean_content.encode("utf-8"))

        # Chunk content
        raw_chunks = chunk_markdown(clean_content)

        def write_tx(conn: sqlite3.Connection) -> IndexResult:
            # 1. Insert source
            conn.execute(
                """
                INSERT INTO sources (source_id, uri, namespace, agent_id, run_id, trust_label, fetched_at, content_hash, byte_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (source_id, uri, ns_str, agent, run_id, trust_label, now_ts, content_hash, byte_count),
            )

            # 2. Insert chunks into Porter & Trigram FTS5 tables
            if raw_chunks:
                porter_rows = [
                    (h_path, body, source_id, ns_str, agent, now_ts)
                    for h_path, body in raw_chunks
                ]
                conn.executemany(
                    """
                    INSERT INTO chunks (heading_path, body, source_id, namespace, agent_id, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    porter_rows,
                )
                conn.executemany(
                    """
                    INSERT INTO chunks_trigram (heading_path, body, source_id, namespace, agent_id, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    porter_rows,
                )

            return IndexResult(source_id=source_id, content_hash=content_hash, chunk_count=len(raw_chunks), cached=False)

        return self._writer_queue.submit(write_tx)

    def index_url(
        self,
        url: str,
        agent: str = "default",
        ns: Optional[Tuple[str, ...]] = None,
        namespace: Optional[Tuple[str, ...]] = None,
        ttl_ms: int = 86_400_000,
        force: bool = False,
        run_id: str = "default_run",
    ) -> IndexResult:
        """Fetch and index URL content with TTL caching (FR-5)."""
        import urllib.request

        target_ns = ns or namespace or NamespaceACL.get_default_namespace(agent)
        NamespaceACL.check(agent, target_ns, mode="write")

        # Check TTL cache before network call
        if not force:
            with self._get_read_conn() as read_conn:
                cached_id = check_cache(read_conn, uri=url, content_hash="", ttl_ms=ttl_ms, force=force)
                if cached_id:
                    return IndexResult(source_id=cached_id, content_hash="", chunk_count=0, cached=True)

        req = urllib.request.Request(url, headers={"User-Agent": "AgentBus/0.1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw_text = resp.read().decode("utf-8", errors="replace")

        return self.index(
            content=raw_text,
            agent=agent,
            ns=target_ns,
            uri=url,
            trust_label=TrustLabel.EXTERNAL_FETCHED.value,
            run_id=run_id,
        )

    def search(
        self,
        query: Union[str, List[str]],
        namespace: Optional[Tuple[str, ...]] = None,
        ns: Optional[Tuple[str, ...]] = None,
        k: int = 5,
        refs: Optional[List[str]] = None,
        agent: str = "default",
    ) -> List[SearchResult]:
        """Hybrid lexical search across Porter and Trigram indexes (FR-2, FR-4, FR-6)."""
        target_ns = namespace or ns or ("global",)
        NamespaceACL.check(agent, target_ns, mode="read")
        ns_prefix = tuple_to_ns_str(target_ns)

        queries = [query] if isinstance(query, str) else query
        all_hits = []

        with self._get_read_conn() as read_conn:
            for q in queries:
                porter_hits = search_porter(read_conn, q, namespace_prefix=ns_prefix, limit=k * 5, refs=refs)
                trigram_hits = search_trigram(read_conn, q, namespace_prefix=ns_prefix, limit=k * 5, refs=refs)
                merged = merge_rrf(porter_hits, trigram_hits, k=60, top_n=k)

                for item in merged:
                    # Fetch trust label from sources table
                    s_id = item["source_id"]
                    t_cursor = read_conn.execute("SELECT trust_label FROM sources WHERE source_id = ? LIMIT 1", (s_id,))
                    t_row = t_cursor.fetchone()
                    trust_label = t_row[0] if t_row else TrustLabel.AGENT_GENERATED.value

                    all_hits.append(
                        SearchResult(
                            chunk_id=item["chunk_id"],
                            source_id=item["source_id"],
                            heading_path=item["heading_path"],
                            snippet=item["snippet"],
                            score=item["score"],
                            trust_label=trust_label,
                            agent_id=item["agent_id"],
                            namespace=ns_str_to_tuple(item["namespace"]),
                            created_at=item["created_at"],
                        )
                    )

        # Deduplicate results by chunk_id and sort by score descending
        seen = set()
        unique_results = []
        for hit in sorted(all_hits, key=lambda r: r.score, reverse=True):
            if hit.chunk_id not in seen:
                seen.add(hit.chunk_id)
                unique_results.append(hit)
                if len(unique_results) >= k:
                    break

        return unique_results

    def log_event(
        self,
        agent: str = "default",
        run_id: str = "default_run",
        ns: Optional[Tuple[str, ...]] = None,
        namespace: Optional[Tuple[str, ...]] = None,
        type: str = "decision",
        priority: int = 1,
        payload: Optional[Dict[str, Any]] = None,
        ref_ids: Optional[List[str]] = None,
    ) -> str:
        """Append an immutable event to the log (FR-9, FR-10)."""
        target_ns = ns or namespace or ("global",)
        NamespaceACL.check(agent, target_ns, mode="write")

        def write_tx(conn: sqlite3.Connection) -> str:
            return record_event(
                conn,
                agent_id=agent,
                run_id=run_id,
                namespace=target_ns,
                event_type=type,
                priority=priority,
                payload=payload,
                ref_ids=ref_ids,
            )

        return self._writer_queue.submit(write_tx)

    def handoff(
        self,
        from_agent: str,
        to_agent: str,
        refs: List[str],
        query: str,
        note: str = "",
        ns: Optional[Tuple[str, ...]] = None,
        namespace: Optional[Tuple[str, ...]] = None,
        run_id: str = "default_run",
    ) -> str:
        """Create an agent handoff record (FR-17)."""
        target_ns = ns or namespace or ("team", "handoff")
        payload = {
            "from": from_agent,
            "to": to_agent,
            "refs": refs,
            "query": query,
            "note": note,
        }
        return self.log_event(
            agent=from_agent,
            run_id=run_id,
            ns=target_ns,
            type="handoff",
            priority=2,
            payload=payload,
            ref_ids=refs,
        )

    def build_snapshot(
        self,
        run_id: str,
        namespace: Optional[Tuple[str, ...]] = None,
        ns: Optional[Tuple[str, ...]] = None,
        budget_bytes: int = 2048,
    ) -> str:
        """Build a byte-budgeted snapshot from event history (FR-11)."""
        target_ns = namespace or ns or ("global",)

        def write_tx(conn: sqlite3.Connection) -> str:
            return build_snapshot(conn, run_id=run_id, namespace=target_ns, budget_bytes=budget_bytes)

        return self._writer_queue.submit(write_tx)

    def restore(
        self,
        run_id: str,
        agent_id: str = "default",
        namespace: Optional[Tuple[str, ...]] = None,
        ns: Optional[Tuple[str, ...]] = None,
    ) -> SessionGuide:
        """Restore session guide from snapshot (FR-12)."""
        target_ns = namespace or ns or ("global",)

        def write_tx(conn: sqlite3.Connection) -> SessionGuide:
            return restore_session(conn, run_id=run_id, agent_id=agent_id, namespace=target_ns)

        return self._writer_queue.submit(write_tx)

    def poll_events(
        self,
        agent_id: str = "default",
        namespace_prefixes: Optional[List[Tuple[str, ...]]] = None,
        since_cursor: Optional[str] = None,
        limit: int = 50,
    ) -> Tuple[List[Event], str]:
        """Poll events for subscribers (FR-18)."""
        prefixes = namespace_prefixes or [("global",)]
        with self._get_read_conn() as read_conn:
            return poll_events(read_conn, agent_id=agent_id, namespace_prefixes=prefixes, since_cursor=since_cursor, limit=limit)

    def purge(
        self,
        namespace: Optional[Tuple[str, ...]] = None,
        run_id: Optional[str] = None,
        older_than_days: Optional[int] = 14,
    ) -> int:
        """Purge data by namespace, run_id, or age (FR-28)."""
        if not namespace and not run_id and older_than_days is None:
            raise ValueError("Must specify at least one purge criteria (namespace, run_id, or older_than_days)")

        def write_tx(conn: sqlite3.Connection) -> int:
            deleted_count = 0
            if run_id:
                # Delete chunks
                conn.execute("DELETE FROM chunks WHERE source_id IN (SELECT source_id FROM sources WHERE run_id = ?)", (run_id,))
                conn.execute("DELETE FROM chunks_trigram WHERE source_id IN (SELECT source_id FROM sources WHERE run_id = ?)", (run_id,))
                res = conn.execute("DELETE FROM sources WHERE run_id = ?", (run_id,))
                deleted_count += res.rowcount
                conn.execute("DELETE FROM events WHERE run_id = ?", (run_id,))
                conn.execute("DELETE FROM snapshots WHERE run_id = ?", (run_id,))
            return deleted_count

        return self._writer_queue.submit(write_tx)

    def close(self) -> None:
        """Close bus and flush write queue."""
        self._writer_queue.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    # Async companions for LangGraph BaseStore / event loop usage
    async def aindex(self, *args, **kwargs) -> IndexResult:
        return await asyncio.to_thread(self.index, *args, **kwargs)

    async def asearch(self, *args, **kwargs) -> List[SearchResult]:
        return await asyncio.to_thread(self.search, *args, **kwargs)

    async def alog_event(self, *args, **kwargs) -> str:
        return await asyncio.to_thread(self.log_event, *args, **kwargs)

    async def ahandoff(self, *args, **kwargs) -> str:
        return await asyncio.to_thread(self.handoff, *args, **kwargs)

    async def abuild_snapshot(self, *args, **kwargs) -> str:
        return await asyncio.to_thread(self.build_snapshot, *args, **kwargs)

    async def arestore(self, *args, **kwargs) -> SessionGuide:
        return await asyncio.to_thread(self.restore, *args, **kwargs)

    async def apoll_events(self, *args, **kwargs) -> Tuple[List[Event], str]:
        return await asyncio.to_thread(self.poll_events, *args, **kwargs)
