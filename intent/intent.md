# agentbus — Intent

> **Purpose of this file:** A short, actionable summary of what we are building and why.
> This is the starting artifact for the playbook chain. Keep it to ~2 pages.
> The PRD (`PRD Shared Memory Bus for Multi-Agent Systems.md`) is the full source of truth;
> this file condenses it for Claude sessions and subagents.
>
> **Last updated:** 2026-10-17 | **Status:** OQ-1 through OQ-7 answered by Phase 0 discovery. OQ-8 and OQ-9 intentionally deferred.

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
| OQ-1 | What is the exact context-mode DB schema? | §5.2, §7, bridge design | ✅ Answered | See detail below |
| OQ-2 | What do context-mode hook payloads look like? | §5.2 architecture diagram | ✅ Answered | See detail below |
| OQ-3 | What FTS5 tokenizer settings does context-mode use? | §6.1 FR-2 | ✅ Answered | See detail below |
| OQ-4 | Is FTS5 + trigram available in Python's bundled `sqlite3`? | NFR-4 | ✅ Answered | Conditional — see detail below |
| OQ-5 | What are the current LangGraph `BaseStore` method signatures? | FR-21 | ✅ Answered | See detail below |
| OQ-6 | Does Python 3.10 cover the current LangChain/LangGraph support range? | NFR-7 | ✅ Answered | Yes — see detail below |
| OQ-7 | Does context-mode expose events via DB file, MCP tool, or both? | Q1, FR-26 | ✅ Answered | Both — DB file is more stable |
| OQ-8 | Is `agentbus` better as a context-mode MCP companion or standalone-first? | Q2 | ⏳ Deferred (decide post-Phase 1) | — |
| OQ-9 | Which benchmark tasks are representative and reproducible? | Q3, §10.2 | ⏳ Deferred (decide in Phase 3 planning) | — |

---

## Phase 0 Discovery — Detailed Answers

### OQ-1: context-mode DB Schema

**Two separate SQLite databases; both in WAL mode.**

#### ContentStore (`/tmp/context-mode-<PID>.db`) — ephemeral, per-process
Source: `src/store.ts`

```sql
CREATE TABLE sources (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  label           TEXT NOT NULL,
  chunk_count     INTEGER NOT NULL DEFAULT 0,
  code_chunk_count INTEGER NOT NULL DEFAULT 0,
  indexed_at      TEXT NOT NULL DEFAULT (datetime('now')),
  file_path       TEXT,
  content_hash    TEXT
);
CREATE INDEX idx_sources_label ON sources(label);

CREATE VIRTUAL TABLE chunks USING fts5(
  title, content,
  source_id UNINDEXED, content_type UNINDEXED,
  source_category UNINDEXED, session_id UNINDEXED,
  event_id UNINDEXED, timestamp UNINDEXED,
  tokenize='porter unicode61'
);

CREATE VIRTUAL TABLE chunks_trigram USING fts5(
  title, content,
  source_id UNINDEXED, content_type UNINDEXED,
  source_category UNINDEXED, session_id UNINDEXED,
  event_id UNINDEXED, timestamp UNINDEXED,
  tokenize='trigram'
);

CREATE TABLE vocabulary (word TEXT PRIMARY KEY);
```

#### SessionDB (`~/.claude/context-mode/sessions/<hash>.db`) — persistent, per-project
Source: `src/session/db.ts` + search research

```sql
CREATE TABLE events (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id   TEXT NOT NULL,
  type         TEXT NOT NULL,      -- e.g. file_read, file_write, error_tool, git_commit
  category     TEXT NOT NULL,      -- e.g. file, error, git, task, decision, rule, cwd
  data         TEXT NOT NULL,      -- full payload, no truncation
  priority     INTEGER NOT NULL,   -- 1=critical .. 5=low
  created_at   TEXT NOT NULL DEFAULT (datetime('now')),
  model_id     TEXT,
  input_tokens  INTEGER,
  output_tokens INTEGER,
  cost_usd     REAL,
  bytes_avoided INTEGER,
  bytes_retrieved INTEGER
);

CREATE TABLE sessions (
  id          TEXT PRIMARY KEY,   -- session hash
  project_dir TEXT NOT NULL,
  started_at  TEXT NOT NULL
);

CREATE TABLE snapshots (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id  TEXT NOT NULL,
  built_at    TEXT NOT NULL,
  budget_bytes INTEGER,
  body        TEXT NOT NULL      -- compressed resume snippet < 2KB
);
```

**Implication:** `agentbus` table designs mirror these patterns. Implement independently — do not copy upstream code.

---

### OQ-2: Hook Payload Shape

Source: `src/session/extract.ts` — hooks communicate via **JSON over stdin/stdout**.

```typescript
interface HookInput {
  tool_name: string;                          // e.g. "Bash", "Read", "Write"
  tool_input: Record<string, unknown>;         // tool-specific args
  tool_response?: string;                     // stdout from the tool
  tool_output?: { isError?: boolean; is_error?: boolean };
}
```

**Hook lifecycle (files in `hooks/<platform>/`):**

| Hook | Fires when |
|------|------------|
| `sessionstart.mjs` | Session begins or resumes |
| `userpromptsubmit.mjs` | User submits a prompt |
| `pretooluse.mjs` | Before a tool is invoked |
| `posttooluse.mjs` | After a tool finishes — main extraction point |
| `precompact.mjs` | Before context compaction — builds snapshot |
| `stop.mjs` | Agent turn ends |

**Event types extracted by posttooluse:**
`file_read`, `file_write`, `file_edit`, `file_glob`, `file_search`, `rule`, `rule_content`, `cwd`, `error_tool`, `git`, `git_commit`, `task`, `task_create`, `task_update`, `plan_enter`, `plan_exit`, `plan_approved`, `plan_rejected`

**Priority tiers:** 1 = critical (rules, files, tasks) ... 5 = low

**Compaction response:** `{ "additional_context": "<compressed summary < 2KB>" }`

**Implication:** `agentbus-bridge` reads SessionDB `events` table directly — more stable than parsing hook payloads.

---

### OQ-3: FTS5 Tokenizer Settings

Source: `src/store.ts` lines 483-505

| Table | Tokenizer | Purpose |
|-------|-----------|--------|
| `chunks` | `porter unicode61` | Stemmed word-variant search |
| `chunks_trigram` | `trigram` | Substring / partial-identifier search (min 3 chars) |

**Merge strategy:** BM25 scores from both tables merged with Reciprocal Rank Fusion in application code. Chunk size cap: 4096 bytes. Stopword filtering + fuzzy levenshtein correction + proximity-span reranking in application code.

**Implication:** Our dual-FTS5 design is confirmed. Implement RRF in Python, not SQL.

---

### OQ-4: FTS5 + Trigram in Python's bundled `sqlite3`

**Conditional** — requires SQLite >= 3.34.0 (Dec 2020):
- Windows/macOS (python.org installers): bundled SQLite >= 3.35 ✅
- Linux Ubuntu 22.04+ ships SQLite 3.37+ ✅ | Ubuntu 20.04 ships 3.31 ❌

**Decision:** Add a startup capability check; require SQLite >= 3.34.0; document in install instructions. Fail fast with a clear error message if trigram is unavailable.

---

### OQ-5: LangGraph `BaseStore` Method Signatures

Source: LangGraph docs, `langgraph.store.base.BaseStore`

| Async method | Signature |
|-------------|----------|
| `aput` | `(namespace: tuple[str,...], key: str, value: dict, index=None) -> None` |
| `aget` | `(namespace: tuple[str,...], key: str) -> Item | None` |
| `adelete` | `(namespace: tuple[str,...], key: str) -> None` |
| `asearch` | `(namespace_prefix: tuple[str,...], *, query: str|None=None, filter: dict|None=None, limit: int=10, offset: int=0) -> list[SearchResult]` |
| `alist_namespaces` | `(*, prefix=None, suffix=None, max_depth=None, limit=100, offset=0) -> list[tuple[str,...]]` |

Sync equivalents (`put`, `get`, `delete`, `search`, `list_namespaces`) wrap the async methods.
Return types: `Item(namespace, key, value, created_at, updated_at)`, `SearchResult(namespace, key, value, score)`

**Implication:** Implement async methods as primary contract. Namespaces are tuples — store as `":".join(namespace)` in SQLite. `asearch.query` is where FTS5/RRF plugs in.

---

### OQ-6: Python 3.10 Coverage

**Confirmed.** LangChain >= 0.1 and LangGraph >= 0.1 both support Python 3.9+; 3.10 is safe and recommended. Enforce `python_requires >= '3.10'` in `pyproject.toml`.

---

### OQ-7: How context-mode Exposes Events

**Both DB file and MCP tools; DB file is the stable interface for `agentbus-bridge`.**

- **DB file** (`~/.claude/context-mode/sessions/<hash16>.db`): Direct SQLite read. Schema defined in `src/session/db.ts`. Stable at table/column level. WAL-safe for concurrent reads.
- **MCP tools** (`ctx_search`, `ctx_fetch_and_index`, `ctx_session_restore`, etc.): Designed for agent consumption; signatures change with platform adapters.

**File path formula:** `<CONTEXT_MODE_DIR or ~/.claude>/context-mode/sessions/<sha256(canonicalized_projectDir)[0:16]><worktreeSuffix>.db`

**Bridge design:** `agentbus-bridge` opens SessionDB as read-only (`uri=True, mode=ro` in Python), respects WAL mode, queries `events` table with a cursor. No MCP dependency.

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
