"""LangChain tool wrappers for tool-calling agents (FR-23, SEC-5)."""

from typing import List, Optional, Tuple
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from agentbus.core import Bus


def get_agentbus_tools(
    bus: Bus,
    default_namespace: Tuple[str, ...] = ("team", "shared"),
    agent_id: str = "agent",
):
    """Factory creating LangChain tools bound to a specific Bus instance."""

    class SearchInput(BaseModel):
        query: str = Field(description="Search keywords or phrase to look up in shared memory.")
        k: int = Field(default=3, description="Number of excerpts to return.")

    @tool("bus_search", args_schema=SearchInput)
    def bus_search(query: str, k: int = 3) -> str:
        """Search the shared memory store for relevant facts, prior research, and code snippets."""
        results = bus.search(query=query, namespace=default_namespace, k=k, agent=agent_id)
        if not results:
            return "No matching records found in shared memory."

        lines = [f"Found {len(results)} relevant excerpt(s) in shared memory:"]
        for i, hit in enumerate(results, 1):
            heading = f" > {hit.heading_path}" if hit.heading_path else ""
            lines.append(
                f"\n### {i}. [Source: {hit.source_id}{heading}] [TRUST: {hit.trust_label}]\n"
                f"> {hit.snippet}"
            )
        return "\n".join(lines)

    class IndexInput(BaseModel):
        content: str = Field(description="Markdown or text content to index into shared memory.")
        uri: str = Field(default="", description="Optional URI or identifier for this document.")

    @tool("bus_index", args_schema=IndexInput)
    def bus_index(content: str, uri: str = "") -> str:
        """Store a document, research notes, or tool output into shared memory."""
        res = bus.index(
            content=content,
            agent=agent_id,
            ns=default_namespace,
            uri=uri,
        )
        if res.cached:
            return f"Content already cached in shared memory. Source ID: {res.source_id}"
        return f"Successfully indexed {res.chunk_count} chunk(s) into shared memory. Source ID: {res.source_id}"

    class HandoffInput(BaseModel):
        to_agent: str = Field(description="Name or ID of the agent receiving this task.")
        source_id: str = Field(description="Source ID of the indexed knowledge to pass.")
        query: str = Field(description="Guidance query for the receiving agent to run.")
        note: str = Field(default="", description="Additional instructions or notes.")

    @tool("bus_handoff", args_schema=HandoffInput)
    def bus_handoff(to_agent: str, source_id: str, query: str, note: str = "") -> str:
        """Handoff a subtask to another agent with source pointers, avoiding transcript bloat."""
        h_id = bus.handoff(
            from_agent=agent_id,
            to_agent=to_agent,
            refs=[source_id],
            query=query,
            note=note,
            ns=default_namespace,
        )
        return f"Handoff successfully recorded (ID: {h_id}). Assigned to agent '{to_agent}' with reference '{source_id}'."

    class LogEventInput(BaseModel):
        event_type: str = Field(description="Type of event: decision, task, error, or constraint.")
        summary: str = Field(description="Summary of the action or decision.")
        priority: int = Field(default=2, description="Priority tier (1=Critical, 2=High, 3=Medium, 4=Low).")

    @tool("bus_log_event", args_schema=LogEventInput)
    def bus_log_event(event_type: str, summary: str, priority: int = 2) -> str:
        """Record an immutable milestone, architectural decision, or error into the event log."""
        prio = max(1, min(4, priority))
        e_id = bus.log_event(
            agent=agent_id,
            ns=default_namespace,
            type=event_type,
            priority=prio,
            payload={"summary": summary},
        )
        return f"Event logged successfully (ID: {e_id})."

    return [bus_search, bus_index, bus_handoff, bus_log_event]
