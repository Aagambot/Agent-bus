"""End-to-End integration test: Multi-Agent LangGraph workflow with AgentBusStore (FR-21, FR-24)."""

import tempfile
import pytest
from pathlib import Path
from typing_extensions import TypedDict
from typing import List, Optional

from langgraph.graph import StateGraph, START, END

from agentbus.core import Bus
from agentbus.langgraph.store import AgentBusStore
from agentbus.langgraph.nodes import create_index_node, create_retrieve_node, create_handoff_node


class MultiAgentState(TypedDict):
    task: str
    current_agent: str
    content: Optional[str]
    source_id: Optional[str]
    query: Optional[str]
    retrieved_docs: Optional[List[dict]]
    handoff_id: Optional[str]
    final_output: Optional[str]


def test_end_to_end_multi_agent_workflow():
    """Verify an end-to-end 2-agent workflow using AgentBusStore and ready-made nodes."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = str(Path(tmp_dir) / "e2e_graph.db")
        with Bus(db_path=db_path) as bus:
            store = AgentBusStore(bus=bus)

            # Node 1: Researcher agent generates findings
            def researcher_agent(state: MultiAgentState) -> dict:
                research_report = (
                    "# Q3 Financial Performance\n\n"
                    "Gross margins expanded to 52.4% while revenue grew 16.5% YoY. "
                    "Primary growth driver is cloud migration."
                )
                return {
                    "content": research_report,
                    "query": "Gross margins revenue growth",
                    "current_agent": "researcher",
                }

            # Node 2: Ready-made indexing node
            indexer = create_index_node(bus=bus, namespace=("team", "market_research"))

            # Node 3: Ready-made handoff node to synthesizer agent
            handoff = create_handoff_node(
                bus=bus,
                target_agent="synthesizer",
                namespace=("team", "handoffs"),
                note="Analyze research findings",
            )

            # Node 4: Ready-made retrieval node for synthesizer agent
            retriever = create_retrieve_node(
                bus=bus,
                namespace=("team", "market_research"),
                k=2,
            )

            # Node 5: Synthesizer generates final answer from retrieved docs (not raw transcript)
            def synthesizer_agent(state: MultiAgentState) -> dict:
                docs = state.get("retrieved_docs", [])
                assert len(docs) >= 1
                snippet = docs[0]["snippet"]
                conclusion = f"Synthesizer verified: {snippet}"
                return {
                    "final_output": conclusion,
                    "current_agent": "synthesizer",
                }

            # Build the graph
            builder = StateGraph(MultiAgentState)
            builder.add_node("researcher", researcher_agent)
            builder.add_node("index", indexer)
            builder.add_node("handoff", handoff)
            builder.add_node("retrieve", retriever)
            builder.add_node("synthesize", synthesizer_agent)

            builder.add_edge(START, "researcher")
            builder.add_edge("researcher", "index")
            builder.add_edge("index", "handoff")
            builder.add_edge("handoff", "retrieve")
            builder.add_edge("retrieve", "synthesize")
            builder.add_edge("synthesize", END)

            # Compile with AgentBusStore
            graph = builder.compile(store=store)

            # Execute workflow
            initial_state: MultiAgentState = {
                "task": "Analyze Q3 market performance",
                "current_agent": "orchestrator",
                "content": None,
                "source_id": None,
                "query": None,
                "retrieved_docs": None,
                "handoff_id": None,
                "final_output": None,
            }

            final_state = graph.invoke(initial_state)

            # Verify end-to-end outcome
            assert final_state["source_id"] is not None
            assert final_state["handoff_id"] is not None
            assert final_state["retrieved_docs"] is not None
            assert len(final_state["retrieved_docs"]) >= 1
            assert "52.4%" in final_state["final_output"]
            assert "margins" in final_state["final_output"]
            assert final_state["current_agent"] == "synthesizer"
