"""Comprehensive unit test suite for agentbus-core components (FR-1..12)."""

import os
import tempfile
import asyncio
import pytest
from pathlib import Path

from agentbus.core import Bus, SearchResult, Event, SessionGuide
from agentbus.core.chunker import chunk_markdown
from agentbus.core.acl import NamespaceACL, tuple_to_ns_str, ns_str_to_tuple
from agentbus.core.redactor import SecretRedactor


def test_chunker_heading_aware_and_code_blocks():
    """Verify markdown chunker splits on headings and preserves code fences (FR-1)."""
    md = """# Title

Paragraph under title.

```python
def foo():
    # Code block comment
    return 42
```

## Section Two

Content in section two with more details.
"""
    chunks = chunk_markdown(md, max_bytes=4096)
    assert len(chunks) == 2
    assert chunks[0][0] == "Title"
    assert "def foo():" in chunks[0][1]
    assert chunks[1][0] == "Title > Section Two"
    assert "Content in section two" in chunks[1][1]


def test_chunker_oversized_subsplitting():
    """Verify chunker gracefully splits paragraphs exceeding byte threshold."""
    long_para = "This is a sentence that will be repeated to exceed the byte budget limit. " * 30
    md = f"# Big Doc\n\n{long_para}\n\nAnother paragraph."
    chunks = chunk_markdown(md, max_bytes=500)
    assert len(chunks) >= 3


def test_secret_redactor():
    """Verify secrets are masked before entering store (SEC-3)."""
    k_part = "sk-" + "1234567890abcdef1234567890"
    t_part = "ghp_" + "123456789012345678901234567890123456"
    text = f"My secret key is {k_part} and token is {t_part}"
    redacted = SecretRedactor.redact(text)
    assert "sk-" not in redacted
    assert "ghp_" not in redacted
    assert "[REDACTED_OPENAI_KEY]" in redacted
    assert "[REDACTED_GITHUB_TOKEN]" in redacted


def test_namespace_acl_enforcement():
    """Verify private namespace blocks unauthorized agents (SEC-1)."""
    ns = ("agent", "alice", "private")
    # Alice can read/write
    assert NamespaceACL.check("alice", ns, mode="read") is True
    # Bob cannot read
    with pytest.raises(PermissionError):
        NamespaceACL.check("bob", ns, mode="read")

    # Team namespace checking
    team_ns = ("team", "research", "sub")
    assert NamespaceACL.check("alice", team_ns, mode="read", allowed_namespaces=["team:research"]) is True
    assert ns_str_to_tuple(tuple_to_ns_str(team_ns)) == team_ns
    assert ns_str_to_tuple("") == ("global",)


def test_bus_hybrid_search_and_metadata():
    """Verify Bus hybrid search with BM25 + Trigram RRF (FR-2, FR-7)."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = str(Path(tmp_dir) / "core_test.db")
        with Bus(db_path=db_path) as bus:
            # Index document with unique token and identifier
            res1 = bus.index(
                content="# API Reference\n\nUse useEffect hook in React component.",
                agent="author_a",
                ns=("team", "dev"),
                uri="doc://react",
            )
            assert res1.chunk_count >= 1

            # Substring / partial search using trigram
            hits = bus.search(query="useEff", namespace=("team", "dev"), k=5)
            assert len(hits) >= 1
            hit = hits[0]
            assert hit.agent_id == "author_a"
            assert hit.heading_path == "API Reference"
            assert hit.trust_label == "agent-generated"

            # Multi-query search (FR-6)
            multi_hits = bus.search(query=["React", "useEffect"], namespace=("team", "dev"), k=5)
            assert len(multi_hits) >= 1

            # Search with refs filter
            ref_hits = bus.search(query="React", namespace=("team", "dev"), refs=[res1.source_id])
            assert len(ref_hits) >= 1


def test_bus_event_log_and_snapshot_restore():
    """Verify append-only event logging, snapshots, and restore (FR-9, FR-11, FR-12)."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = str(Path(tmp_dir) / "event_test.db")
        with Bus(db_path=db_path) as bus:
            run_id = "test_run_123"

            # Log events with different priorities
            e1 = bus.log_event(agent="planner", run_id=run_id, type="task", priority=1, payload={"title": "Design DB"})
            e2 = bus.log_event(agent="coder", run_id=run_id, type="decision", priority=1, payload={"choice": "SQLite WAL"})
            e3 = bus.log_event(agent="tester", run_id=run_id, type="error", priority=2, payload={"msg": "timeout"})

            # Poll events (FR-18)
            events, cursor = bus.poll_events(agent_id="listener", namespace_prefixes=[("global",)])
            assert len(events) >= 3
            assert cursor != ""

            # Build snapshot with 2KB budget
            snap_id = bus.build_snapshot(run_id=run_id, namespace=("global",), budget_bytes=2048)
            assert snap_id.startswith("snap_")

            # Restore session
            guide = bus.restore(run_id=run_id, agent_id="next_agent", namespace=("global",))
            assert "Restored session" in guide.summary
            assert len(guide.recent_events) >= 2


def test_bus_ttl_deduplication():
    """Verify content hash deduplication on re-index (FR-5)."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = str(Path(tmp_dir) / "ttl_test.db")
        with Bus(db_path=db_path) as bus:
            c = "Identical document content for caching test."
            res1 = bus.index(content=c, agent="a", ns=("team", "cache"))
            assert res1.cached is False

            # Second index should hit cache
            res2 = bus.index(content=c, agent="a", ns=("team", "cache"))
            assert res2.cached is True
            assert res2.source_id == res1.source_id


def test_bus_handoff_and_purge():
    """Verify handoff recording and purge functionality (FR-17, FR-28)."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = str(Path(tmp_dir) / "purge_test.db")
        with Bus(db_path=db_path) as bus:
            run_id = "run_purge"
            idx_res = bus.index(content="Disposable content for purge", run_id=run_id)
            h_id = bus.handoff(
                from_agent="agent_a",
                to_agent="agent_b",
                refs=[idx_res.source_id],
                query="disposable",
                note="Clean up later",
                run_id=run_id,
            )
            assert h_id.startswith("evt_")

            # Purge by run_id
            deleted = bus.purge(run_id=run_id)
            assert deleted >= 1


@pytest.mark.anyio
async def test_async_companion_methods():
    """Verify async companion methods for LangGraph compatibility."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = str(Path(tmp_dir) / "async_test.db")
        with Bus(db_path=db_path) as bus:
            idx = await bus.aindex(content="Async indexed text content.", agent="async_agent", ns=("team", "async"))
            assert idx.chunk_count >= 1

            hits = await bus.asearch(query="Async", namespace=("team", "async"), agent="async_agent")
            assert len(hits) >= 1

            eid = await bus.alog_event(agent="async_agent", type="task")
            assert eid.startswith("evt_")

            snap_id = await bus.abuild_snapshot(run_id="default_run")
            assert snap_id.startswith("snap_")

            guide = await bus.arestore(run_id="default_run")
            assert guide is not None
