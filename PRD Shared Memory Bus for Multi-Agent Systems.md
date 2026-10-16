# PRD: Shared Memory Bus for Multi-Agent Systems

**Working name:** `agentbus` **Author:** Aagam **Status:** Draft v1 **Date:** October 16, 2026 **Basis:** the public README of `mksglu/context-mode` (source code not reviewed; items marked **\[Verify\]** must be confirmed against the code before build).

---

## 1. Summary

`agentbus` is an open-source Python library plus a small local service that lets multiple LLM agents (LangGraph / LangChain) read and write **one shared, searchable knowledge store and one shared session-event log**, instead of passing full transcripts between agents.

It reuses the design ideas proven in context-mode (SQLite FTS5, BM25 + trigram search merged with Reciprocal Rank Fusion, priority-tiered event capture, snapshot-and-restore) and removes its main scope limit: context-mode keeps state per project and per platform, so agents cannot share it.

**Why this project exists:** In multi-agent graphs, the usual handoff is to pass messages or whole transcripts to the next agent. That inflates tokens at every hop and loses information when it is trimmed. A shared indexed store lets an agent pass a short pointer and let the receiver retrieve only what it needs.

---

## 2. Problem Statement

| # | Problem | Evidence / reason |
| --- | --- | --- |
| P1 | Handoffs between agents carry too much context | Raw transcripts or tool outputs are copied into each downstream prompt; cost grows with every hop. |
| P2 | Context-mode state is isolated | Its content index is a per-project SQLite database and sessions are tracked per platform, so two agents cannot query the same index. |
| P3 | No shared record of what agents did | Events (files touched, errors, decisions) are captured per session, so a second agent cannot learn from a first agent's errors or constraints. |
| P4 | LangGraph long-term memory has no built-in compression or ranked search for tool-output-scale data | Teams hand-roll vector stores per agent, duplicating work and diverging state. |
| P5 | Parallel agents duplicate work | Without a shared log, two agents can fetch and index the same URL or re-run the same analysis. |

---

## 3. Goals and Non-Goals

### 3.1 Goals

| ID | Goal | Why it matters |
| --- | --- | --- |
| G1 | Reduce tokens spent on inter-agent handoffs by at least 70% versus full-transcript passing, at equal task success | This is the core value claim; it must be measurable. |
| G2 | Provide a drop-in LangGraph `BaseStore` implementation and LangChain retriever/tools | Adoption depends on needing no framework changes. |
| G3 | Support safe concurrent read/write by multiple agents on one store | Shared state is useless if it corrupts or blocks. |
| G4 | Record a shared, queryable event log with provenance (who, when, which run) | Enables learning from other agents and debugging. |
| G5 | Run fully local with zero external services by default | Matches context-mode's local-first design and keeps data private. |
| G6 | Interoperate with context-mode (read its events, expose its tools) | Builds on the repo rather than forking it, and reaches its 17-platform user base. |

### 3.2 Non-Goals

| Non-goal | Reason |
| --- | --- |
| Hosted or managed multi-tenant service | context-mode is under the Elastic License 2.0, which restricts offering it as a managed service; staying local avoids the issue entirely. |
| Replacing LangGraph checkpointers | Checkpointers save graph state per thread; this project handles retrieval-oriented shared knowledge. Mixing them would widen scope. |
| Training or fine-tuning models | Not needed to prove the value claim. |
| Agent orchestration logic | The bus is memory infrastructure; orchestration stays in LangGraph. |
| Cross-machine distributed deployment (v1) | Adds consensus and networking problems that do not help validate the idea. |

---

## 4. Users and Use Cases

### 4.1 Personas

| Persona | Need | Why they matter |
| --- | --- | --- |
| **Agent developer** (primary) | Build a LangGraph multi-agent app without custom memory plumbing | Largest group using LangGraph/LangChain. |
| **AI/ML researcher** | Compare context strategies with reproducible metrics | Needs the evaluation harness (see section 10). |
| **Coding-agent power user** | Let several coding agents (e.g., Claude Code and Codex CLI) share discoveries on one repo | Direct extension of context-mode's current audience. |

### 4.2 Core Use Cases

| ID | Use case | Flow | Why it is valuable |
| --- | --- | --- | --- |
| UC1 | **Researcher → Writer handoff** | Researcher agent fetches 20 pages, indexes them; hands the Writer a list of source IDs and a query; Writer retrieves only relevant chunks. | Replaces copying 20 pages into the Writer's prompt. |
| UC2 | **Parallel workers, shared dedupe** | Three workers fetch docs; the store returns a cache hit if another already indexed that URL within TTL. | Avoids repeated fetch cost and conflicting copies. |
| UC3 | **Failure learning** | Agent A hits an error and a constraint; Agent B queries the event log before attempting the same step. | Prevents repeated mistakes across agents. |
| UC4 | **Resume after crash or compaction** | A new agent run restores a priority-tiered snapshot of the shared log. | Reuses the proven snapshot-and-restore pattern. |
| UC5 | **Cross-platform coding agents** | Claude Code's context-mode events are readable by a LangGraph review agent. | Delivers G6 and removes the per-platform silo. |

---

## 5. Product Scope

### 5.1 Components

| Component | Description | Why this form |
| --- | --- | --- |
| **`agentbus-core`** (Python) | Storage engine: SQLite (WAL mode) with FTS5, chunking, hybrid search, event log, snapshots | Python matches the LangChain/LangGraph ecosystem; SQLite keeps it local and dependency-light. |
| **`agentbus-langgraph`** | `BaseStore` implementation and helper nodes | LangGraph's long-term memory interface is `BaseStore`, so implementing it makes the bus a drop-in. |
| **`agentbus-langchain`** | `BaseRetriever` and `Tool` wrappers (`bus_index`, `bus_search`, `bus_log_event`, `bus_snapshot`) | Lets non-LangGraph LangChain agents use the same store. |
| **`agentbus-server`** (optional) | Local daemon exposing the store over HTTP/MCP | Needed when agents run in separate processes or are non-Python (e.g., coding agents). |
| **`agentbus-bridge`** | Read-only importer for context-mode's session events and an MCP passthrough | Delivers interoperability without modifying the upstream repo. |
| **`agentbus-eval`** | Benchmark harness (see section 10) | Proves or disproves the token-savings claim. |

### 5.2 Architecture

```
 LangGraph agents (Python, in-process)        Other agents (separate processes)
        │  BaseStore / Tools                        │  HTTP / MCP
        ▼                                           ▼
 ┌──────────────────── agentbus-core ───────────────────────┐
 │  Namespace + ACL layer                                    │
 │  Chunker  →  FTS5 (porter) + FTS5 (trigram)  →  RRF merge │
 │  (optional) embedding index + reranker  [Phase 2]         │
 │  Event log (append-only) + Snapshot builder               │
 │  SQLite, WAL mode, single writer queue                    │
 └──────────────▲────────────────────────────────────────────┘
                │ read-only import
        agentbus-bridge ← context-mode per-project SQLite  [Verify schema]
```

**Why a separate store rather than patching context-mode:** context-mode's index is designed around one agent per project, and its license restricts managed-service use. A separate store that follows the same design and reads its data avoids forking and avoids license risk, while still benefiting from its proven approach.

---

## 6. Functional Requirements

Priority: **P0** = required for v1, **P1** = should have, **P2** = later.

### 6.1 Knowledge Store

| ID | Requirement | Pri | Why |
| --- | --- | --- | --- |
| FR-1 | Index text/markdown by heading-aware chunks, keeping code blocks intact | P0 | Mirrors context-mode; preserves meaning of code in search results. |
| FR-2 | Hybrid lexical search: porter-stemmed FTS5 and trigram FTS5 merged with RRF | P0 | Documented context-mode approach; handles both word variants and partial identifiers like `useEff`. |
| FR-3 | Title/heading weighting in ranking | P1 | Improves navigational queries at low cost. |
| FR-4 | Search returns snippets around matched terms, not truncated heads | P0 | Keeps returned tokens small, which is the product's purpose. |
| FR-5 | Fetch-and-index for URLs with TTL cache (default 24h, per-call override, force bypass) | P0 | Delivers UC2 dedupe; TTL pattern is already validated upstream. |
| FR-6 | Multi-query search in one call | P1 | Reduces round trips and tool calls per agent step. |
| FR-7 | Source-level metadata on every chunk: `agent_id`, `run_id`, `source`, `created_at`, `content_type` | P0 | Provenance is required to trust shared content and to filter by author. |
| FR-8 | Optional dense-embedding index plus reranker | P2 | Addresses lexical-only misses, but adds model dependencies, so it follows v1. |

### 6.2 Shared Event Log

| ID | Requirement | Pri | Why |
| --- | --- | --- | --- |
| FR-9 | Append-only event log with typed events: file, task, decision, error, error-resolution, constraint, blocker, git, handoff | P0 | Reuses the proven category set; adds `handoff` for multi-agent use. |
| FR-10 | Priority tiers P1-P4 per event type | P0 | Needed so snapshots drop low-value events first. |
| FR-11 | Snapshot builder with a configurable token/byte budget (default 2 KB) | P0 | Matches the upstream budgeted-snapshot design and keeps restores cheap. |
| FR-12 | Restore API returning a structured "session guide" and indexing the detailed events for search | P0 | Lets an agent resume with a short summary and pull detail on demand. |
| FR-13 | Error-to-fix pair detection across sequential events | P1 | High-value signal for UC3. |
| FR-14 | Loop detection (same action 3+ times) | P2 | Useful guard, not essential to v1. |

### 6.3 Multi-Agent Semantics

| ID | Requirement | Pri | Why |
| --- | --- | --- | --- |
| FR-15 | Namespaces as tuples (e.g., `("team", "research")`) with scope levels: `private` (one agent), `team`, `run`, `global` | P0 | Matches LangGraph's namespace model and prevents agents from reading what they should not. |
| FR-16 | Per-agent identity passed on every call; enforced by the store | P0 | Required for provenance and access control. |
| FR-17 | Handoff primitive: `handoff(from, to, refs=[source_ids], query, note)` creating an event the receiver can resolve | P0 | The central feature replacing transcript passing. |
| FR-18 | Subscription/poll API for new events since a cursor | P1 | Lets an agent react to others' work without rescanning. |
| FR-19 | Write conflict policy: append-only for events; last-write-wins with version check for key-value items | P0 | Avoids silent overwrites between concurrent agents. |
| FR-20 | Content trust labels (`agent-generated`, `external-fetched`, `user-provided`) returned with results | P0 | Retrieved content can contain injected instructions; labels let downstream agents treat it as data. |

### 6.4 Framework Adapters

| ID | Requirement | Pri | Why |
| --- | --- | --- | --- |
| FR-21 | `BaseStore` subclass supporting `put`, `get`, `delete`, `search`, `list_namespaces` (sync and async) **\[Verify current LangGraph interface at build time\]** | P0 | Makes `graph.compile(store=AgentBusStore(...))` work unchanged. |
| FR-22 | LangChain `BaseRetriever` returning `Document` objects with provenance metadata | P0 | Gives non-LangGraph users the same search. |
| FR-23 | Tool wrappers with JSON-schema arguments for tool-calling models | P0 | Lets agents call `bus_search` directly. |
| FR-24 | Ready-made LangGraph nodes: `index_node`, `retrieve_node`, `handoff_node` | P1 | Reduces boilerplate in the reference examples. |

### 6.5 Interoperability and Server

| ID | Requirement | Pri | Why |
| --- | --- | --- | --- |
| FR-25 | Local server exposing the API over MCP and HTTP | P1 | Allows coding agents and non-Python processes to join. |
| FR-26 | Bridge to import context-mode session events read-only **\[Verify schema\]** | P1 | Delivers G6 and UC5. |
| FR-27 | CLI: `agentbus stats`, `search`, `events`, `purge`, `export` | P1 | Operability and debugging; mirrors the upstream utility commands. |
| FR-28 | Purge by namespace, run, or age; 14-day default retention with override | P0 | Privacy and disk control; consistent with upstream cleanup behavior. |

---

## 7. Data Model

| Table | Key fields | Why |
| --- | --- | --- |
| `sources` | `source_id`, `uri`, `namespace`, `agent_id`, `run_id`, `trust_label`, `fetched_at`, `ttl_ms`, `content_hash` | One row per indexed document; hash prevents duplicate indexing (UC2). |
| `chunks` | `chunk_id`, `source_id`, `heading_path`, `content_type`, `text` | Unit of retrieval. |
| `chunks_fts_porter`, `chunks_fts_trigram` | FTS5 virtual tables over `text` and `heading_path` | Two tokenizers feed RRF (FR-2). |
| `events` | `event_id`, `ts`, `agent_id`, `run_id`, `namespace`, `type`, `priority`, `payload_json`, `ref_ids` | Shared append-only log. |
| `items` | `namespace`, `key`, `value_json`, `version`, `updated_by`, `updated_at` | Backing for `BaseStore` key-value operations (FR-21). |
| `snapshots` | `snapshot_id`, `run_id`, `built_at`, `budget_bytes`, `body`, `consumed` | Resume data (FR-11, FR-12). |
| `agents` | `agent_id`, `role`, `allowed_namespaces` | Access control (FR-15, FR-16). |

**Why SQLite in WAL mode with a single writer queue:** WAL allows many concurrent readers during a write, and serializing writes through one queue avoids `database is locked` errors under parallel agents, which is the main concurrency risk.

---

## 8. Public API (Python, illustrative)

```python
from agentbus import Bus
from agentbus.langgraph import AgentBusStore

bus = Bus(path="~/.agentbus/project.db")

# LangGraph
graph = builder.compile(store=AgentBusStore(bus))

# Researcher agent
src = bus.index_url("https://example.com/spec", agent="researcher", ns=("team", "research"))
bus.handoff(from_="researcher", to="writer", refs=[src.id], query="auth flow limits")

# Writer agent
h = bus.next_handoff(agent="writer")
hits = bus.search(h.query, refs=h.refs, k=5)   # small, ranked snippets with provenance

# Recovery
guide = bus.restore(run="run-42")               # structured summary, details searchable
```

**Why this shape:** Three verbs (`index`, `handoff`, `search`) cover the primary flow; everything else is optional, which keeps the learning curve short.

---

## 9. Non-Functional Requirements

| ID | Requirement | Target | Why |
| --- | --- | --- | --- |
| NFR-1 | Search latency (p95) on 100k chunks | < 100 ms | Agents call search repeatedly per step; slow search erodes the token-for-time trade. |
| NFR-2 | Concurrent agents supported | At least 8 readers + 4 writers without lock errors | Realistic upper bound for a local multi-agent graph. |
| NFR-3 | Index throughput | At least 1 MB of text/second on a laptop | Fetch-heavy agents index many pages. |
| NFR-4 | Install | `pip install agentbus` with no native build step on Linux/macOS/Windows | Upstream notes native-module friction (better-sqlite3, glibc); Python's bundled `sqlite3` with FTS5 avoids it **\[Verify FTS5 and trigram availability per platform\]**. |
| NFR-5 | Data locality | No network calls except explicit URL fetches | Privacy; consistent with the local-first goal. |
| NFR-6 | Crash safety | No corrupted DB after kill -9 during writes | WAL plus transactions; required for UC4. |
| NFR-7 | Python support | 3.10+ | Matches current LangChain/LangGraph support range **\[Verify\]**. |
| NFR-8 | Test coverage | At least 80% on core | Concurrency bugs are subtle; tests are the main defense. |

---

## 10. Success Metrics and Evaluation Plan

### 10.1 Metrics

| Metric | Definition | Target | Why |
| --- | --- | --- | --- |
| **Handoff token reduction** | Tokens in downstream prompts: bus vs full-transcript baseline | ≥ 70% lower | Primary value claim (G1). |
| **Task success parity** | Pass rate on benchmark tasks, bus vs baseline | Within 3 points (non-inferior) | Savings that hurt accuracy are not savings. |
| **Retrieval quality** | Recall@5 and MRR on labeled queries | Recall@5 ≥ 0.85 | Measures whether the right chunks come back. |
| **Dedupe rate** | Fetches avoided via cache hits in parallel runs | Report only | Quantifies UC2. |
| **Repeated-error rate** | Errors repeated by a second agent with vs without the log | ≥ 50% lower | Quantifies UC3. |
| **Cost per task** | Total tokens × price | Lower than baseline | Business-level outcome. |

### 10.2 Experimental Design

| Item | Plan | Why |
| --- | --- | --- |
| Conditions | (A) full-transcript handoff, (B) summary handoff, (C) agentbus handoff | B is the fair, stronger baseline; beating only A would overstate the result. |
| Tasks | Multi-agent research-and-write tasks; multi-step coding tasks on a fixed repo set | Covers both the LangGraph and coding-agent use cases. |
| Repetitions | At least 5 runs per task per condition | LLM output varies; single runs are not evidence. |
| Reporting | Mean, confidence interval, and failure examples | Avoids cherry-picking. |

---

## 11. Security, Privacy, and Safety

| Risk | Mitigation | Why |
| --- | --- | --- |
| **Prompt injection via shared content**: one agent indexes a malicious page; another retrieves and obeys it | Trust labels on all results (FR-20); document that retrieved text is data; optional pattern scan on ingest | A shared store widens the attack surface across agents. |
| **Cross-agent data leakage** | Namespace ACLs enforced in the store, default `private` | Least privilege between agents. |
| **Secrets captured in events or tool output** | Redaction hooks (regex for common key formats) before indexing; never log environment values | Event capture can otherwise persist credentials. |
| **Poisoned or low-quality writes** | Provenance on every record; ability to purge by `agent_id` or `run_id` | Makes bad data attributable and removable. |
| **Local file exposure** | File permissions `0600` on the DB; no network listener by default | Prevents other local users or processes reading it. |
| **Server exposure** | Bind to localhost, require a token | The optional server must not become an open endpoint. |

---

## 12. Licensing and Legal

| Point | Decision | Why |
| --- | --- | --- |
| Upstream license | context-mode is ELv2 | Restricts providing it as a hosted/managed service and circumventing license keys; permits use and modification otherwise. |
| Code reuse | Implement `agentbus-core` independently; do not copy upstream source | Avoids inheriting ELv2 obligations in your own code and keeps your license choice open. |
| Interop | Read upstream data and call its MCP tools only | Interaction through public interfaces is lower risk than embedding code. |
| Own license | Apache-2.0 or MIT for `agentbus` | Maximizes adoption; **confirm with legal review before release** (this PRD is not legal advice). |

---

## 13. Milestones

Assumes one developer, part-time alongside coursework.

| Phase | Duration | Deliverables | Exit criteria |
| --- | --- | --- | --- |
| **0. Discovery** | 1 week | Read context-mode source; confirm DB schema, hook payloads, FTS5 settings; pick license; decide bridge feasibility | All **\[Verify\]** items resolved or descoped |
| **1. Core store** | 2 weeks | Chunker, FTS5 hybrid search with RRF, TTL cache, event log, snapshots, WAL + writer queue | FR-1 to FR-12 pass tests; NFR-1 and NFR-6 met |
| **2. LangGraph/LangChain adapters** | 2 weeks | `BaseStore`, retriever, tools, namespaces/ACL, handoff primitive | FR-15 to FR-23 pass; example graph runs end-to-end |
| **3. Evaluation** | 2 weeks | Harness, 3 conditions, benchmark tasks, results report | Metrics in section 10 produced with confidence intervals |
| **4. Interop + server** | 2 weeks | MCP/HTTP server, context-mode bridge, CLI | FR-25 to FR-27 pass; UC5 demo works |
| **5. Release** | 1 week | Docs, 3 reference examples, PyPI package, blog/paper write-up | Public v0.1 |
| **6. (Later) Semantic layer** | 3 weeks | Embeddings + reranker (FR-8), re-run evaluation | Recall@5 improvement shown vs lexical-only |

**Why evaluation precedes interop:** If the token-savings claim fails, interop work is wasted; testing the thesis first reduces risk.

---

## 14. Risks and Open Questions

| ID | Risk / question | Impact | Mitigation | Why it matters |
| --- | --- | --- | --- | --- |
| R1 | Savings vs summary-passing baseline are smaller than expected | High | Report honestly; pivot to the event-log value (UC3) | A fair baseline may show a modest gain. |
| R2 | Lexical-only retrieval misses relevant chunks in agent-to-agent queries | Medium | Phase 6 embeddings; query-expansion by the agent | Agents often phrase queries differently than the source text. |
| R3 | SQLite write contention with many writers | Medium | Single writer queue; batch writes; benchmark early | Core to G3. |
| R4 | Upstream schema or hook changes break the bridge | Medium | Bridge is optional, versioned, and fails open | Upstream is fast-moving (2,000+ commits). |
| R5 | LangGraph `BaseStore` interface changes | Medium | Pin versions; thin adapter layer; CI against latest | Framework APIs evolve quickly. |
| R6 | Shared memory spreads injected or wrong content between agents | High | Trust labels, ACLs, purge-by-agent | Specific to this project's design. |
| R7 | Scope creep into orchestration | Medium | Non-goals enforced in review | Keeps v1 shippable. |
| Q1 | Does context-mode expose a stable way to read its events (DB schema vs MCP tool)? |  | Phase 0 | Determines bridge design. |
| Q2 | Is it better to expose `agentbus` as a context-mode MCP companion or as a standalone library first? |  | Decide after Phase 1 | Affects the audience reached. |
| Q3 | Which benchmark tasks are representative and reproducible? |  | Decide in Phase 3 planning | Weak tasks produce weak evidence. |

---

## 15. Out of Scope for v1

| Item | Why deferred |
| --- | --- |
| Dense embeddings and reranking | Adds dependencies; validate the core idea with lexical search first. |
| Learned snapshot prioritization | Separate research project (idea #4 from the earlier list). |
| Distributed or multi-machine store | Needs consensus and networking; not required to test the thesis. |
| Web dashboard | CLI stats are enough to debug and demo. |
| Support for non-LangChain frameworks (CrewAI, AutoGen) | The HTTP/MCP server leaves the door open without extra adapters. |

---

## 16. Acceptance Criteria for v0.1

| # | Criterion |
| --- | --- |
| 1 | Two LangGraph agents share one store through `AgentBusStore` and complete a handoff using only source IDs plus a query. |
| 2 | Hybrid search returns ranked snippets with provenance and trust labels. |
| 3 | Eight concurrent agents run for 10 minutes with no lock errors or data loss. |
| 4 | Killing the process mid-write leaves a readable database. |
| 5 | The evaluation report shows handoff token reduction and task-success parity with confidence intervals against both baselines. |
| 6 | Namespace ACLs block a `private` read from another agent. |
| 7 | Documentation includes quickstart, API reference, and three runnable examples. |
