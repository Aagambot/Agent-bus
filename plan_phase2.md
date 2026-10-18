# Implementation Plan: Phase 2 Framework Adapters (`agentbus-langgraph` & `agentbus-langchain`)

## Goal Description
Implement the official integration adapters for **LangGraph** and **LangChain** on top of `agentbus-core`. This enables developers to attach `agentbus` directly into LangGraph state machines via `BaseStore`, query memory in LCEL chains via `BaseRetriever`, and empower tool-calling LLMs with verified AgentBus tools (`bus_search`, `bus_index`, `bus_handoff`, `bus_log_event`, `bus_snapshot`).

All work in this plan delivers **Phase 2** as specified in `spec.md`, satisfies requirements **FR-15 through FR-24**, and includes an end-to-end multi-agent LangGraph workflow test.

---

## Resolved Grilling & Architectural Decisions

Following the Phase 2 architectural deep-dive (`/grill-me`), the following design decisions are finalized:

1. **`store.put()` Indexing Policy (FR-21):**
   - When `index=None` (or omitted), `AgentBusStore` automatically indexes all top-level string/text fields into FTS5 for hybrid search, avoiding unnecessary overhead on nested binary/structured data.
   - When `index=['field1', ...]` is passed, only those specific fields are indexed.
   - When `index=False`, content is stored as pure key-value in `items` table without entering FTS5.
2. **Tool Output Representation (FR-23, SEC-5):**
   - Tools return clean, token-efficient Markdown formatted excerpts with explicit trust badges (e.g. `[TRUST: external-fetched]`).
   - This provides the lowest token cost, avoids JSON hallucination errors in small LLMs, and enforces strict prompt-injection defenses.
3. **Metadata Filtering (FR-21):**
   - In `store.search(namespace_prefix, filter={...})`, prefix matches are retrieved from SQLite and evaluated against filter key-value conditions in Python memory, supporting equality and containment checks without brittle SQL query generation.
4. **LangGraph Ready-Made Nodes (FR-24):**
   - Provide both ready-to-use pre-configured nodes (`index_node`, `retrieve_node`, `handoff_node`) for standard graphs and customizable factory builders (`create_index_node(content_key="...")`, etc.) for custom State schemas.

---

## Proposed Changes & File Layout

```
src/
└── agentbus/
    ├── langgraph/
    │   ├── __init__.py
    │   ├── store.py         # AgentBusStore(BaseStore) implementation (FR-21)
    │   └── nodes.py         # Ready-made graph nodes & factory builders (FR-24)
    └── langchain/
        ├── __init__.py
        ├── retriever.py     # AgentBusRetriever(BaseRetriever) (FR-22)
        └── tools.py         # bus_search, bus_index, bus_handoff, bus_log_event, bus_snapshot (FR-23)
```

---

### Component 1: LangGraph Adapter (`agentbus-langgraph`)

#### `[NEW] src/agentbus/langgraph/store.py`
Implements `AgentBusStore(BaseStore)`:
- `get` / `aget`: Fetches row from `items` table by `(namespace, key)`, parses JSON, returns `Item`.
- `put` / `aput`: Upserts into `items` table with version increment. If `index` specified or `None`, extracts string fields and indexes into FTS5 chunks.
- `delete` / `adelete`: Removes from `items` and associated chunks.
- `search` / `asearch`: If `query` is provided, executes hybrid FTS5/RRF search over chunks matching `namespace_prefix`. If `query` is None, returns raw items under prefix. Applies in-memory `filter`. Returns `list[SearchItem]`.
- `list_namespaces` / `alist_namespaces`: Queries distinct namespace paths matching prefix/suffix criteria.

#### `[NEW] src/agentbus/langgraph/nodes.py`
Ready-made workflow nodes for LangGraph state graphs (FR-24):
- Factory builders: `create_index_node()`, `create_retrieve_node()`, `create_handoff_node()`.
- Default nodes: `index_node`, `retrieve_node`, `handoff_node`.

---

### Component 2: LangChain Adapter (`agentbus-langchain`)

#### `[NEW] src/agentbus/langchain/retriever.py`
Implements `AgentBusRetriever(BaseRetriever)` (FR-22):
- Bound to `bus`, `agent_id`, `namespace`, and `k`.
- Implements `_get_relevant_documents(query)` and `_aget_relevant_documents(query)`.
- Returns `list[Document]` where:
  - `page_content = result.snippet`
  - `metadata = {"source_id": result.source_id, "heading_path": result.heading_path, "score": result.score, "trust_label": result.trust_label, "agent_id": result.agent_id}`.

#### `[NEW] src/agentbus/langchain/tools.py`
Pre-built tools for function-calling models with Pydantic JSON schemas (FR-23):
- `bus_search`: Searches shared memory for relevant facts or tool outputs with formatted markdown results.
- `bus_index`: Stores text or notes into shared memory under a namespace.
- `bus_handoff`: Delegates a subtask to another agent passing source pointers and guidance query.
- `bus_log_event`: Records a major finding, decision, or error into the append-only event log.
- `bus_snapshot`: Generates a budgeted snapshot of the current session state.

---

## Requirement Mapping (FR-15..24)

| Requirement | Implementation Module | Verification / Proof |
| :--- | :--- | :--- |
| **FR-15** Namespaces as tuples (`global`, `team`, `run`, `private`) | `store.py`, `retriever.py` | Namespace path mapping and scope tests |
| **FR-16** Per-agent identity on every call | `store.py`, `retriever.py` | Identity tracking in `items.updated_by` |
| **FR-17** Handoff primitive | `tools.py`, `nodes.py` | Agent-to-agent handoff event verification |
| **FR-19** Write conflict policy (version checks on items) | `store.py` | Version check collision test on `put()` |
| **FR-20** Trust labels (`[SEC-5]`) | `retriever.py`, `store.py` | Metadata assertion in retrieved `Document` |
| **FR-21** `BaseStore` subclass | `store.py` | Full `BaseStore` test suite (`put`, `get`, `delete`, `search`, `list_namespaces`) |
| **FR-22** `BaseRetriever` subclass | `retriever.py` | LCEL pipe execution test (`retriever | prompt | model`) |
| **FR-23** Tool wrappers | `tools.py` | Tool invocation with Pydantic schemas |
| **FR-24** Ready-made LangGraph nodes | `nodes.py` | End-to-end multi-agent LangGraph workflow |

---

## Verification Plan

### Automated Tests
1. **LangGraph BaseStore Test (`tests/test_langgraph_store.py`):**
   - Tests `put`, `get`, `delete`, `list_namespaces`, and semantic `search(query="...")` across namespaces.
   - Tests both synchronous and asynchronous methods (`aput`, `aget`, `asearch`).
2. **LangChain Retriever & Tools Test (`tests/test_langchain_adapters.py`):**
   - Tests `AgentBusRetriever` returning valid `Document` objects with mandatory `trust_label`.
   - Tests tool execution for `bus_search`, `bus_index`, `bus_handoff`.
3. **End-to-End Multi-Agent Graph Test (`tests/test_end_to_end_graph.py`):**
   - Compiles a real LangGraph `StateGraph` using `store=AgentBusStore(bus)`.
   - Executes Agent 1 (Researcher) indexing data $\to$ Handoff $\to$ Agent 2 (Writer) retrieving data from store without passing full transcript.
