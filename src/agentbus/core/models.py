"""Data models and type definitions for agentbus-core."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal


class TrustLabel(str, Enum):
    """Trust tier of indexed or stored content (SEC-5)."""
    AGENT_GENERATED = "agent-generated"
    EXTERNAL_FETCHED = "external-fetched"
    USER_PROVIDED = "user-provided"


@dataclass
class SearchResult:
    """A scored chunk match returned from hybrid search."""
    chunk_id: str
    source_id: str
    heading_path: str
    snippet: str
    score: float
    trust_label: str
    agent_id: str
    namespace: tuple[str, ...]
    created_at: str


@dataclass
class Event:
    """An append-only recorded event in the workflow."""
    event_id: str
    ts: str
    agent_id: str
    run_id: str
    namespace: tuple[str, ...]
    type: str
    priority: int
    payload: dict[str, Any] = field(default_factory=dict)
    ref_ids: list[str] = field(default_factory=list)


@dataclass
class SessionGuide:
    """Structured summary and restore payload for resuming an agent session."""
    summary: str
    recent_events: list[Event] = field(default_factory=list)
    available_sources: list[str] = field(default_factory=list)
    query_hint: str = ""


@dataclass
class IndexResult:
    """Result of an index operation."""
    source_id: str
    content_hash: str
    chunk_count: int
    cached: bool = False


@dataclass
class Chunk:
    """An individual text chunk before database insertion."""
    heading_path: str
    body: str
    source_id: str
    namespace: str
    agent_id: str
    created_at: str
