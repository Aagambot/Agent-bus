# CLAUDE.md — agentbus Project Rules

> This file is read by every Claude session and every subagent working on this repo.
> Rules here are mandatory, not suggestions. Read this before writing any code.

---

## Project Overview

**`agentbus`** — A shared, searchable memory bus for multi-agent LangGraph/LangChain systems.
Built on SQLite (WAL mode) with FTS5 hybrid search. Local-first, no external services.

**Python:** 3.10+ only
**DB engine:** SQLite with WAL mode + single writer queue
**License (own code):** Apache-2.0 or MIT (TBD — do not assume)
**Upstream reference:** `mksglu/context-mode` (ELv2 licensed)

---

## Hard Rules (non-negotiable)

### 1. Do not copy ELv2 upstream code
The reference project (`context-mode`) is under the Elastic License 2.0.
**You must not copy, paste, or closely paraphrase its source code into this repo.**
Implement all functionality independently, inspired by the design but written from scratch.
If unsure whether something is too close, stop and ask.

### 2. Never edit tests to make them pass
Tests define the contract. If a test is failing:
- Fix the implementation, not the test
- If you believe the test is genuinely wrong, flag it with a comment and stop — do not modify it
- This rule exists because silent test changes mask real bugs

### 3. Plan before implementing
No code is written for a phase until a `plan.md` (or `plan_phaseN.md`) has been committed and reviewed.
Use plan mode: produce the plan as output only, do not edit files, until the plan is approved.

### 4. Hooks are enforced — do not work around them
Pre-commit hooks block:
- Edits to test files during fix tasks
- Reads of the upstream context-mode source during implementation
- Secrets (API keys, tokens, env vars) in diffs
If a hook fires, stop. Do not bypass it.

---

## Build and Test Commands

```bash
# Run the full test suite (pytest, stop on first failure)
make test

# Equivalent without make
pytest -x --tb=short

# Run only concurrency tests (NFR-2)
pytest tests/test_concurrency.py -v

# Run only crash-safety tests (NFR-6)
pytest tests/test_crash_safety.py -v

# Run all tests with coverage report
pytest --cov=agentbus --cov-report=term-missing
```

**Minimum coverage target:** 80% on `src/agentbus/core/`

---

## Concurrency and Crash-Safety Tests

These two tests must stay green at all times. They were written failing-first (Step 5) before any implementation.

### Concurrency stress test (`tests/test_concurrency.py`)
- Spins up **8 reader threads + 4 writer threads**
- Runs for **60 seconds**
- Asserts: zero SQLite `OperationalError: database is locked` exceptions
- Asserts: all written records are readable after the run

### Kill-mid-write test (`tests/test_crash_safety.py`)
- Spawns a subprocess that writes to the DB in a loop
- Sends `SIGKILL` (or `TerminateProcess` on Windows) mid-write
- Re-opens the DB
- Asserts: DB passes `PRAGMA integrity_check`
- Asserts: no partial/corrupt records

---

## Architecture Constraints

- **Single writer queue:** All writes go through one asyncio queue or threading lock — never write from multiple threads simultaneously
- **WAL mode:** Every DB connection must `PRAGMA journal_mode=WAL` on open
- **WAL mode checkpoint:** Run `PRAGMA wal_checkpoint(TRUNCATE)` on clean shutdown
- **Timeouts:** All SQLite connections must set `timeout=30` (seconds) to avoid indefinite blocking
- **No network calls** except inside `bus.index_url()` — the store is local-first

---

## Python Style

- Type hints on all public functions and class methods
- Docstrings on all public API (NumPy style)
- No `print()` in library code — use `logging.getLogger(__name__)`
- No global mutable state outside the `Bus` class
- All async functions prefixed with `async def`; do not mix sync/async in the same call stack without an explicit bridge

---

## File Layout

```
src/agentbus/          # library source
  core/                # storage engine (chunker, FTS5, event log, snapshots)
  langgraph/           # BaseStore implementation
  langchain/           # BaseRetriever + Tool wrappers
  server/              # optional local HTTP/MCP daemon
  bridge/              # read-only context-mode importer
tests/                 # pytest tests (do not edit to make them pass)
eval/                  # evaluation harness (separate from agent evals)
intent/                # intent.md — the short artifact the chain starts from
README.md              # project overview, quickstart & docs index
PLAYBOOK_PROGRESS.md   # playbook adoption tracker (update after each step)
docs/                  # organized documentation
  specs/               # prd.md, spec.md
  plans/               # plan_phase1.md, plan_phase2.md, plan_phase3.md
  reports/             # benchmark_report.md, review.md
```

---

## Dependency Constraints

- **No binary Python extensions** for the core store — use Python's bundled `sqlite3`
- FTS5 and trigram tokenizer must be verified available before assuming them (see OQ-4 in `intent/intent.md`)
- `langchain` and `langgraph` are optional dependencies (extras), not hard deps of `agentbus-core`
- `httpx` or `aiohttp` for URL fetching — no `requests` in async paths

---

## Security Checklist (run mentally before every PR)

- [ ] No secrets, API keys, or env var values in any committed file or test fixture
- [ ] All retrieved/indexed content is tagged with a trust label before it enters the store
- [ ] Namespace ACL check happens at the store layer, not only in the adapter layer
- [ ] No user-controlled string is interpolated directly into an FTS5 query (use parameterised queries)
- [ ] DB file permissions are `0600` (set on creation)

---

## Licensing Checklist (run before every new module)

- [ ] This file was written independently — no copy-paste from context-mode source
- [ ] Any algorithm borrowed from upstream is re-implemented in a clearly different form
- [ ] No ELv2 code is vendored, included, or imported at runtime
