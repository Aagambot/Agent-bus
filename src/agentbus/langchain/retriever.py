"""LangChain BaseRetriever adapter for agentbus (FR-22)."""

import asyncio
from typing import Any, List, Tuple
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from pydantic import ConfigDict

from agentbus.core import Bus


class AgentBusRetriever(BaseRetriever):
    """Retriever for querying AgentBus hybrid search from LangChain LCEL pipelines."""

    bus: Any
    agent_id: str = "default"
    namespace: Tuple[str, ...] = ("global",)
    k: int = 5

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun | None = None
    ) -> List[Document]:
        """Execute hybrid search and return LangChain Document objects with trust labels."""
        results = self.bus.search(query=query, namespace=self.namespace, k=self.k, agent=self.agent_id)
        docs = []
        for r in results:
            docs.append(
                Document(
                    page_content=r.snippet,
                    metadata={
                        "source_id": r.source_id,
                        "heading_path": r.heading_path,
                        "score": r.score,
                        "trust_label": r.trust_label,  # SEC-5: mandatory trust label
                        "agent_id": r.agent_id,
                        "created_at": r.created_at,
                    },
                )
            )
        return docs

    async def _aget_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun | None = None
    ) -> List[Document]:
        return await asyncio.to_thread(self._get_relevant_documents, query, run_manager=run_manager)
