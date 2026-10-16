# agentbus — Intent

> **Purpose of this file:** A short, actionable summary of what we are building and why.
> This is the starting artifact for the playbook chain. Keep it to ~2 pages.
> The PRD (`PRD Shared Memory Bus for Multi-Agent Systems.md`) is the full source of truth;
> this file condenses it for Claude sessions and subagents.
>
> **Last updated:** 2026-10-17 | **Status:** Draft — Open questions not yet answered (see Step 3)

---

## What We Are Building

**`agentbus`** — An open-source Python library that gives multiple LLM agents (LangGraph / LangChain) one shared, searchable knowledge store and one shared session-event log.

**The core problem it solves:**
In multi-agent graphs, agents hand off work by passing full transcripts or raw tool output. This inflates tokens at every hop and loses information when it is trimmed.
`agentbus` lets an agent pass a short pointer (source IDs + a query) and lets the receiver retrieve only the ranked chunks it needs.

---

## Why This and Not Something Else

| Problem | Why existing tools don't solve it |
|---------|----------------------------------|
| Transcript passing is expensive | Tokens grow with every agent hop; no existing LangGraph primitive stops this |
| `context-mode` state is per-project, per-platform | Two agents cannot share the same index; the silo is by design |
| No shared event record | A second agent cannot learn from a first agent's errors or constraints |
| LangGraph long-term memory has no ranked search | Teams hand-roll per-agent vector stores; state diverges |

---

## Primary Goal (the one thing that must be true)

> Reduce tokens spent on inter-agent handoffs by **≥ 70%** versus full-transcript passing, **at equal task success** (within 3 percentage points).

Everything else is in service of proving or disproving this.

---

## What It Is (core components, v1)

| Component | One-line description |
|-----------|---------------------|
| `agentbus-core` | SQLite (WAL) + FTS5 hybrid search + event log + snapshots |
| `agentbus-langgraph` | `BaseStore` drop-in for `graph.compile(store=...)` |
| `agentbus-langchain` | `BaseRetriever` + Tool wrappers (`bus_search`, `bus_index`, etc.) |
| `agentbus-server` | Optional local HTTP/MCP daemon for non-Python agents |
| `agentbus-bridge` | Read-only importer for context-mode session events |
| `agentbus-eval` | Benchmark harness (3 conditions, 5+ runs, confidence intervals) |

---

## What It Is Not (v1)

- Not a hosted or managed service (ELv2 restriction; staying local avoids it)
- Not a LangGraph checkpointer replacement (different concerns)
- Not an orchestration layer (the bus is memory infrastructure)
- Not distributed / multi-machine (adds consensus problems; validate idea first)

---

## The Three Core Verbs

```python
bus.index(content, agent="researcher", ns=("team", "research"))  # store & chunk
bus.handoff(from_="researcher", to="writer", refs=[src.id], query="auth flow")  # pass pointer
hits = bus.search(query, refs=h.refs, k=5)  # retrieve ranked snippets with provenance
```

Everything else (snapshots, restore, event log, ACLs) supports these three verbs.

---

## Non-Negotiable Constraints

- **Python 3.10+** only
- **SQLite WAL mode** with a single writer queue — no `database is locked` errors
- **No network calls** except explicit `index_url()` — local-first
- **No ELv2 code copied** from context-mode — implement independently
- **Never edit tests to make them pass** — fix the implementation

---

## Phases (condensed)

| Phase | Duration | Key deliverable | Exit criterion |
|-------|----------|-----------------|----------------|
| 0. Discovery | 1 week | All `[Verify]` items answered | This file's Open Questions section is closed |
| 1. Core store | 2 weeks | Chunker, FTS5/RRF, event log, snapshots, WAL queue | FR-1→FR-12 pass; concurrency + crash tests green |
| 2. Adapters | 2 weeks | `BaseStore`, retriever, tools, ACL, handoff | FR-15→FR-23 pass; example graph runs |
| 3. Evaluation | 2 weeks | 3-condition benchmark, 5+ runs, metrics report | Token reduction and task-success metrics produced |
| 4. Interop + server | 2 weeks | MCP/HTTP server, context-mode bridge, CLI | UC5 demo works |
| 5. Release | 1 week | Docs, 3 examples, PyPI v0.1 | Public release |

---

## Open Questions (all `[Verify]` items from the PRD)

> **These must be answered by the Phase 0 researcher subagent (Step 3).**
> Do not start Step 4 (spec.md) until every item below is either answered or formally descoped.

| ID | Question | Source in PRD | Status | Answer / Resolution |
|----|----------|---------------|--------|---------------------|
| OQ-1 | What is the exact context-mode DB schema? (table names, columns, indexes, FTS5 virtual tables) | §5.2, §7, bridge design | ❓ Unanswered | — |
| OQ-2 | What do context-mode hook payloads look like? (event types, payload shape, priority tiers) | §5.2 architecture diagram | ❓ Unanswered | — |
| OQ-3 | What FTS5 tokenizer settings does context-mode use? (porter stemmer, trigram, column weights) | §6.1 FR-2 | ❓ Unanswered | — |
| OQ-4 | Is FTS5 + trigram tokenizer available in Python's bundled `sqlite3` on Linux/macOS/Windows? | NFR-4 | ❓ Unanswered | — |
| OQ-5 | What are the current LangGraph `BaseStore` method signatures? (`put`, `get`, `delete`, `search`, `list_namespaces` — sync and async) | FR-21 | ❓ Unanswered | — |
| OQ-6 | Does Python 3.10 cover the current LangChain/LangGraph support range? | NFR-7 | ❓ Unanswered | — |
| OQ-7 | Does context-mode expose events via DB file, MCP tool, or both? Which is more stable? | Q1, FR-26 | ❓ Unanswered | — |
| OQ-8 | Is exposing `agentbus` as a context-mode MCP companion better than standalone-first? | Q2 | ❓ Unanswered (decide post-Phase 1) | — |
| OQ-9 | Which benchmark tasks are representative and reproducible for the evaluation? | Q3, §10.2 | ❓ Unanswered (decide in Phase 3 planning) | — |

---

## Researcher Subagent Brief (Step 3)

When running the Phase 0 researcher subagent, give it this task list. It should:

1. **Read context-mode source** (read-only; do not modify)
2. For each open question OQ-1 → OQ-7, produce:
   - A direct answer with a file path and line number reference
   - A one-line summary of the implication for `agentbus` design
3. Write answers into this file under "Answer / Resolution" for each OQ row
4. If a question cannot be answered from the source, mark it `Descoped` with a reason

**Do not start implementation. Do not modify any context-mode files. Read only.**
