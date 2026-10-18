"""Unit tests for LangGraph BaseStore adapter (AgentBusStore) (FR-21)."""

import tempfile
import pytest
from pathlib import Path

from agentbus.core import Bus
from agentbus.langgraph.store import AgentBusStore


def test_store_put_get_delete():
    """Verify standard key-value operations on AgentBusStore."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = str(Path(tmp_dir) / "store_test.db")
        with Bus(db_path=db_path) as bus:
            store = AgentBusStore(bus=bus, agent_id="agent_1")
            ns = ("users", "123")

            # 1. Put
            store.put(ns, "profile", {"name": "Alice", "role": "Architect", "level": 5})

            # 2. Get
            item = store.get(ns, "profile")
            assert item is not None
            assert item.key == "profile"
            assert item.value["name"] == "Alice"
            assert item.value["level"] == 5

            # 3. Update
            store.put(ns, "profile", {"name": "Alice", "role": "Principal Architect", "level": 6})
            item2 = store.get(ns, "profile")
            assert item2.value["role"] == "Principal Architect"

            # 4. Delete
            store.delete(ns, "profile")
            assert store.get(ns, "profile") is None


def test_store_search_with_query_and_filter():
    """Verify semantic search and metadata filtering in AgentBusStore."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = str(Path(tmp_dir) / "store_search.db")
        with Bus(db_path=db_path) as bus:
            store = AgentBusStore(bus=bus, agent_id="agent_1")
            ns_prefix = ("team", "engineering")

            # Insert multiple items
            store.put(
                ("team", "engineering", "backend"),
                "auth_spec",
                {"title": "OAuth2 Auth Flow", "summary": "Detailed token exchange specification", "status": "approved"}
            )
            store.put(
                ("team", "engineering", "frontend"),
                "ui_spec",
                {"title": "Dashboard Design", "summary": "Frontend layout with React components", "status": "draft"}
            )

            # Search with query
            results = store.search(ns_prefix, query="OAuth2 token")
            assert len(results) >= 1
            assert results[0].key == "auth_spec"

            # Search with filter
            draft_results = store.search(ns_prefix, filter={"status": "draft"})
            assert len(draft_results) == 1
            assert draft_results[0].key == "ui_spec"

            # List namespaces
            namespaces = store.list_namespaces(prefix=("team", "engineering"))
            assert len(namespaces) == 2


@pytest.mark.anyio
async def test_store_async_methods():
    """Verify async BaseStore methods (aput, aget, asearch)."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = str(Path(tmp_dir) / "store_async.db")
        with Bus(db_path=db_path) as bus:
            store = AgentBusStore(bus=bus, agent_id="agent_async")
            ns = ("async", "data")

            await store.aput(ns, "k1", {"val": "Async stored text"})
            item = await store.aget(ns, "k1")
            assert item is not None
            assert item.value["val"] == "Async stored text"

            items = await store.asearch(ns, query="Async")
            assert len(items) >= 1

            await store.adelete(ns, "k1")
            assert await store.aget(ns, "k1") is None
