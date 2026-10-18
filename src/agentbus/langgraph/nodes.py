"""Ready-made nodes and factory functions for LangGraph workflows (FR-24)."""

from typing import Any, Callable, Dict, Optional, Tuple
from agentbus.core import Bus


def create_index_node(
    bus: Bus,
    content_key: str = "content",
    result_key: str = "source_id",
    namespace: Tuple[str, ...] = ("team", "shared"),
    agent_id: str = "agent",
) -> Callable[[Dict[str, Any]], Dict[str, Any]]:
    """Build a graph node that indexes content into AgentBus."""
    def node_fn(state: Dict[str, Any]) -> Dict[str, Any]:
        text = state.get(content_key, "")
        if not text:
            return {}
        result = bus.index(
            content=text,
            agent=state.get("current_agent", agent_id),
            ns=state.get("namespace", namespace),
            run_id=state.get("run_id", "default_run"),
        )
        return {result_key: result.source_id}

    return node_fn


def create_retrieve_node(
    bus: Bus,
    query_key: str = "query",
    results_key: str = "retrieved_docs",
    namespace: Tuple[str, ...] = ("team", "shared"),
    k: int = 3,
) -> Callable[[Dict[str, Any]], Dict[str, Any]]:
    """Build a graph node that queries AgentBus hybrid search."""
    def node_fn(state: Dict[str, Any]) -> Dict[str, Any]:
        query = state.get(query_key, "")
        if not query:
            return {results_key: []}
        hits = bus.search(
            query=query,
            namespace=state.get("namespace", namespace),
            k=k,
        )
        formatted_hits = [
            {
                "snippet": h.snippet,
                "heading": h.heading_path,
                "source_id": h.source_id,
                "trust_label": h.trust_label,
                "score": h.score,
            }
            for h in hits
        ]
        return {results_key: formatted_hits}

    return node_fn


def create_handoff_node(
    bus: Bus,
    target_agent: str,
    refs_key: str = "source_id",
    query_key: str = "query",
    note: str = "Handoff to next agent",
    namespace: Tuple[str, ...] = ("team", "handoff"),
) -> Callable[[Dict[str, Any]], Dict[str, Any]]:
    """Build a graph node that records an agent-to-agent handoff event."""
    def node_fn(state: Dict[str, Any]) -> Dict[str, Any]:
        from_agent = state.get("current_agent", "prior_agent")
        ref_id = state.get(refs_key)
        refs = [ref_id] if ref_id else []
        query = state.get(query_key, "")

        handoff_id = bus.handoff(
            from_agent=from_agent,
            to_agent=target_agent,
            refs=refs,
            query=query,
            note=note,
            ns=namespace,
            run_id=state.get("run_id", "default_run"),
        )
        return {
            "handoff_id": handoff_id,
            "current_agent": target_agent,
        }

    return node_fn
