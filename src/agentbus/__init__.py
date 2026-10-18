"""agentbus - A shared, searchable memory bus for multi-agent systems."""

from .core.bus import Bus
from .core.models import Event, IndexResult, SearchResult, SessionGuide, TrustLabel

__all__ = ["Bus", "SearchResult", "Event", "SessionGuide", "IndexResult", "TrustLabel"]
__version__ = "0.1.0"

# Optional LangGraph adapter
try:
    from .langgraph.store import AgentBusStore
    from .langgraph.nodes import create_index_node, create_retrieve_node, create_handoff_node
    __all__.extend(["AgentBusStore", "create_index_node", "create_retrieve_node", "create_handoff_node"])
except ImportError:
    pass

# Optional LangChain adapter
try:
    from .langchain.retriever import AgentBusRetriever
    from .langchain.tools import get_agentbus_tools
    __all__.extend(["AgentBusRetriever", "get_agentbus_tools"])
except ImportError:
    pass
