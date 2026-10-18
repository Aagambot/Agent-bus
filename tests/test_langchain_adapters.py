"""Unit tests for LangChain retriever and tool adapters (FR-22, FR-23)."""

import tempfile
import pytest
from pathlib import Path

from agentbus.core import Bus
from agentbus.langchain.retriever import AgentBusRetriever
from agentbus.langchain.tools import get_agentbus_tools


def test_agentbus_retriever():
    """Verify AgentBusRetriever returns Documents with mandatory trust label (SEC-5)."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = str(Path(tmp_dir) / "retriever_test.db")
        with Bus(db_path=db_path) as bus:
            ns = ("team", "retriever_test")
            bus.index(
                content="# API Spec\n\nRate limit is 50 requests per second.",
                agent="author",
                ns=ns,
            )

            retriever = AgentBusRetriever(bus=bus, namespace=ns, k=2)
            docs = retriever.invoke("rate limit requests")

            assert len(docs) >= 1
            doc = docs[0]
            assert "50" in doc.page_content
            assert "requests" in doc.page_content
            assert "trust_label" in doc.metadata
            assert doc.metadata["trust_label"] == "agent-generated"
            assert doc.metadata["agent_id"] == "author"


def test_agentbus_tools():
    """Verify tool wrappers for LLMs return clean formatted markdown."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = str(Path(tmp_dir) / "tools_test.db")
        with Bus(db_path=db_path) as bus:
            ns = ("team", "tools_test")
            tools = get_agentbus_tools(bus=bus, default_namespace=ns, agent_id="agent_tool")
            tool_map = {t.name: t for t in tools}

            assert "bus_search" in tool_map
            assert "bus_index" in tool_map
            assert "bus_handoff" in tool_map
            assert "bus_log_event" in tool_map

            # 1. Test bus_index
            index_output = tool_map["bus_index"].invoke({"content": "# Architecture\n\nUsing Event Sourcing pattern."})
            assert "Successfully indexed" in index_output
            assert "Source ID: src_" in index_output

            # 2. Test bus_search
            search_output = tool_map["bus_search"].invoke({"query": "Event Sourcing", "k": 1})
            assert "TRUST: agent-generated" in search_output
            assert "Event" in search_output
            assert "Sourcing" in search_output

            # 3. Test bus_handoff
            handoff_output = tool_map["bus_handoff"].invoke({
                "to_agent": "analyst",
                "source_id": "src_123",
                "query": "Event Sourcing",
                "note": "Verify pattern suitability"
            })
            assert "Handoff successfully recorded" in handoff_output

            # 4. Test bus_log_event
            log_output = tool_map["bus_log_event"].invoke({
                "event_type": "decision",
                "summary": "Confirmed SQLite WAL architecture",
                "priority": 1
            })
            assert "Event logged successfully" in log_output
