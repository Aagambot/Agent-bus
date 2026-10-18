"""agentbus - A shared, searchable memory bus for multi-agent systems."""

from .core.bus import Bus
from .core.models import Event, IndexResult, SearchResult, SessionGuide, TrustLabel

__all__ = ["Bus", "SearchResult", "Event", "SessionGuide", "IndexResult", "TrustLabel"]
__version__ = "0.1.0"
