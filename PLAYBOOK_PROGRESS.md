# agentbus — Playbook Adoption Progress

> **What this file is:** A living tracker that maps the playbook's dependency-ordered steps onto the `agentbus` PRD.
> Update the status column after each step completes. The "Next Actions" section always reflects the single next concrete thing to do.
>
> **Last updated:** 2026-10-18 — Steps 1–7 complete ✅ | **Step 8 next**

---

## Legend

| Badge | Meaning |
|-------|---------|
| ✅ Done | Step is complete and committed |
| 🔄 In Progress | Work has started but is not merged |
| ⏳ Blocked | Waiting on a prior step or external input |
| 🔲 Not Started | No work has begun |

---

## Step-by-Step Status

### Step 1 — `CLAUDE.md` (entry-point; no prerequisites)
**Playbook play:** CLAUDE.md
**Status:** ✅ Done

**What was done:**
- [x] Created `CLAUDE.md` at repo root
- [x] Added: build commands (`make test`, pytest variants), Python 3.10+ constraint, SQLite WAL requirement
- [x] Added rule: `"Do not copy ELv2 upstream code"`
- [x] Added rule: `"Never edit tests to make them pass"`
- [x] Added: concurrency stress test and kill-mid-write test descriptions with exact commands
- [x] Added: security checklist, licensing checklist, file layout, dependency constraints

**Why first:** Every later Claude session and every subagent reads this file. Rules here prevent repeated mistakes from the start.

---

### Step 2 — `intent/intent.md` (entry-point; no prerequisites)
**Playbook play:** Capture intent
**Status:** ✅ Done

**What was done:**
- [x] Created `intent/intent.md` with the directory
- [x] Condensed PRD sections 1-3 into ~2 pages (what, why, what it's not, core verbs, constraints, phases)
- [x] Listed all 9 open questions (OQ-1 → OQ-9) mapped to their PRD source
- [x] Added researcher subagent brief with explicit read-only instructions

**Why now:** The playbook's chain starts from this short artifact. The PRD is too long to serve as intent. Open questions become the first task list for the researcher subagent.

---

### Step 3 — Phase 0 Discovery (depends on Step 2)
**Playbook play:** Subagents
**Status:** ✅ Done

**What was done:**
- [x] Ran Phase 0 researcher subagent over context-mode public GitHub source
- [x] **OQ-1:** Confirmed two-DB architecture — ContentStore (ephemeral, FTS5) and SessionDB (persistent, events). Full schemas documented in `intent/intent.md`
- [x] **OQ-2:** Hook payloads are JSON over stdin/stdout; 6 hook types; 19+ event type categories; priority 1–5
- [x] **OQ-3:** Porter unicode61 tokenizer (for `chunks`) + trigram tokenizer (for `chunks_trigram`); RRF merge in app code; 4096-byte chunk cap
- [x] **OQ-4:** Trigram requires SQLite >= 3.34.0 — Windows/macOS safe; Linux needs Ubuntu 22.04+. Startup capability check added to design
- [x] **OQ-5:** LangGraph `BaseStore` async methods: `aput`, `aget`, `adelete`, `asearch`, `alist_namespaces` with full signatures documented
- [x] **OQ-6:** Python 3.10+ confirmed as safe for LangChain and LangGraph
- [x] **OQ-7:** DB file is the stable bridge interface — opens read-only, WAL-safe, no MCP dependency needed
- [x] OQ-8 and OQ-9 formally deferred to post-Phase 1
- [x] All answers written back into `intent/intent.md`

**Exit criterion met:** All `[Verify]` items answered or formally descoped.

---

### Step 4 — `spec.md` with licensing + security skills (depends on Steps 2 & 3)
**Playbook play:** Requirements and design
**Status:** ✅ Done

**What was done:**
- [x] Loaded security and licensing context from PRD + Phase 0 findings
- [x] Turned PRD §§5–9 into `spec.md` with full component, architecture, DB schema, functional, and NFR sections
- [x] Schemas deliberately diverged from upstream (different column names) to support LIC-2
- [x] Security skill pass flagged 9 concerns: [SEC-1] ACL enforcement → [SEC-9] token logging
- [x] Licensing skill pass flagged 4 concerns: [LIC-1] independent impl → [LIC-4] bridge legal review
- [x] 6 open design decisions (DD-1 → DD-6) documented for human sign-off

**Why now:** Policy applied while the spec is written is cheaper than retrofitting. The `intent.md` + `spec.md` pair is the audit trail.

---

### Step 5 — Feedback loop: failing tests first (depends on Step 4)
**Playbook play:** Feedback loop
**Status:** ✅ Done

**What was done:**
- [x] Created `pyproject.toml` with Python >=3.10 requirements, extras, and pytest config
- [x] Wrote `Makefile` with `test`, `test-concurrency`, `test-crash-safety`, and `coverage` targets
- [x] Wrote **concurrency stress test** (`tests/test_concurrency.py`, 8 readers + 4 writers, 60 s default, assert zero lock errors) — verified fails cleanly before implementation
- [x] Wrote **kill-mid-write test** (`tests/test_crash_safety.py`, SIGKILL / TerminateProcess mid-write, re-open DB, assert integrity) — verified fails cleanly before implementation
- [x] Confirmed both tests run via `pytest` and fail cleanly before any implementation
- [x] Added test matrix to CI (`.github/workflows/ci.yml` on Python 3.10-3.12 across Ubuntu, macOS, Windows)

**Why before code:** Concurrency bugs are subtle. Giving Claude a way to verify its own work catches them during implementation, not after. These tests encode NFR-2 and NFR-6 as runnable checks.

**Why before code:** Concurrency bugs are subtle. Giving Claude a way to verify its own work catches them during implementation, not after. These tests encode NFR-2 and NFR-6 as runnable checks.

---

### Step 6 — plan.md for Phase 1 Core Store (depends on Step 5)
**Playbook play:** Plan mode
**Status:** ✅ Done

**What was done:**
- [x] Used plan mode and /grill-me deep-dive to produce plan.md
- [x] Resolved 5 critical edge-case risks: hybrid multi-process/thread concurrency, sync/async dual API, atomic batch indexing, safe fallback chunk slicing, and permissive reader default for test compatibility
- [x] Specified exact file layout under src/agentbus/core/ (12 modules)
- [x] Mapped all requirements to FR-1..12 and NFR-1, NFR-6
- [x] Human review completed and plan.md committed

**Why:** Nothing gets implemented without an accepted plan. The commit timestamp is the audit-trail anchor.

---

### Step 7 — Hooks (depends on Step 6)
**Playbook play:** Hooks
**Status:** ✅ Done

**What was done:**
- [x] Created scripts/hooks/check_hooks.py enforcing:
  1. Block edits to test files during fix tasks (CLAUDE.md Rule 2)
  2. Block references / imports of upstream context-mode ELv2 source (CLAUDE.md Rule 1)
  3. Block secrets in diffs (CLAUDE.md Security Checklist)
- [x] Configured git pre-commit hook in .githooks/ and linked via git config core.hooksPath .githooks
- [x] Added hooks target to Makefile
- [x] Created tests/test_hooks.py with 6 unit tests verifying each hook fires correctly on mock triggers
- [x] Verified all hook tests pass cleanly

**Why:** The license and test-integrity rules written in CLAUDE.md need enforcement, not just advice.

---

### Step 8 — Parallel implementation: core store + eval harness skeleton (depends on Steps 6 & 7)
**Playbook play:** Parallel sessions
**Status:** 🔲 Not Started — ready to begin (Steps 6 & 7 complete)

**What to do:**
- [ ] Open **2 parallel worktree sessions** (they touch different files)
  - **Session A — agentbus-core:** Chunker -> FTS5 hybrid search -> RRF -> TTL cache -> event log -> snapshots -> WAL writer queue
  - **Session B — agentbus-eval skeleton:** Harness scaffold, condition stubs (A/B/C), benchmark task loader
- [ ] Do **not** start adapters yet — they depend on the core API being stable
- [ ] Both sessions run against the failing tests from Step 5; green tests = done

**Why 2 sessions:** They touch different files (no merge conflicts). The playbook advises <= 3 parallel sessions; 2 is safe here.

**Exit criterion:** Concurrency stress test and kill-mid-write test both pass.

---

### Step 9 — `REVIEW.md` and PR review loop for Phase 1 (depends on Step 8)
**Playbook play:** PR review loop
**Status:** Blocked on Step 8

**What to do:**
- [ ] Write `REVIEW.md` template with three passes:
  1. **Bug pass** — logic errors, edge cases, off-by-ones
  2. **Security pass** — prompt injection vectors, ACL leaks, secret exposure, trust-label enforcement
  3. **Compliance pass** — diff against `spec.md` and `plan.md`; flag any deviations
- [ ] Add `REVIEW.md` run to CI (Claude reviews every PR diff)
- [ ] Complete review for Phase 1 PR; document any findings

**Why:** Solo developers need a reviewer too. The security pass is especially important because a shared store widens cross-agent attack surface.

---

### Step 10 — Repeat Steps 6-9 for Phase 2 (adapters) and Phase 3 (evaluation)
**Playbook play:** Plan mode -> review loop
**Status:** Blocked on Step 9

**Phase 2 — Adapters (`agentbus-langgraph`, `agentbus-langchain`):**
- [ ] Plan mode -> `plan_phase2.md` -> commit
- [ ] Implement: `BaseStore`, `BaseRetriever`, tools, namespaces/ACL, handoff primitive
- [ ] FR-15 through FR-23 pass; example graph runs end-to-end
- [ ] Run `REVIEW.md` three-pass review

**Phase 3 — Evaluation (`agentbus-eval`):**
- [ ] Plan mode -> `plan_phase3.md` -> commit
- [ ] Implement: 3 conditions (A: full transcript, B: summary, C: agentbus), benchmark tasks, 5+ runs each
- [ ] Produce metrics report: handoff token reduction, task success parity, Recall@5, MRR, CI
- [ ] Run `REVIEW.md` three-pass review

---

### Step 11 — Maintain loop (optional; after v0.1)
**Playbook play:** Closing the loop
**Status:** 🔲 Not Started (intentionally deferred)

**What to do (post-v0.1):**
- [ ] Define a band on search p95 latency (target: < 100 ms per NFR-1)
- [ ] Define a band on CI failure rate
- [ ] When either band is breached, auto-write a new `intent.md` as a work item

**Why deferred:** Last play in the dependency graph; not needed before v0.1.

---

## Two Separate Eval Tracks (Do Not Mix)

| Track | What it tests | Owner |
|-------|--------------|-------|
| **Agent evals** | Whether `CLAUDE.md`, skills, and hooks still steer Claude correctly | Playbook continuous evals |
| **Product evals** | Whether `agentbus` cuts tokens at equal task success | PRD section 10 evaluation plan |

> Mixing them makes a failing score uninterpretable. Keep them in separate test suites with separate CI jobs.

---

## Progress Indicators (git-based, zero cost)

Track these two metrics after every phase:

| Indicator | How to measure | What it shows |
|-----------|----------------|---------------|
| `intent.md` to `spec.md` commit delta | `git log --format="%H %ai" -- intent/intent.md spec.md` | How long discovery takes |
| `spec.md` changes after first `plan.md` commit | `git log --oneline -- spec.md` after first plan commit | Whether up-front spec quality is improving |

---

## Next Actions (as of 2026-10-18)

> **Steps 1–7 complete. Enforced hooks active and tested. Step 8 (Parallel Implementation) next.**

1. ✅ ~~Create `CLAUDE.md`~~ — done
2. ✅ ~~Create `intent/intent.md`~~ — done
3. ✅ ~~Phase 0 researcher subagent~~ — done
4. ✅ ~~Write `spec.md`~~ — done
5. ✅ ~~Write failing tests (Step 5)~~: `Makefile`, `tests/test_concurrency.py`, `tests/test_crash_safety.py`, `.github/workflows/ci.yml` — done
6. ✅ ~~Plan Phase 1 Core Store (Step 6)~~: plan.md written, grilled, reviewed, and committed — done
7. ✅ ~~Hooks (Step 7)~~: pre-commit hook, Makefile target, and verified tests — done
8. **Parallel implementation (Step 8)**: Open parallel sessions for Phase 1 Core Store (agentbus-core) and evaluation harness skeleton (agentbus-eval).

---

## Open Questions (from PRD `[Verify]` items)

| ID | Question | Status | Answer |
|----|----------|--------|--------|
| OQ-1 | What is the exact context-mode DB schema (tables, columns, indexes)? | Unanswered | — |
| OQ-2 | What do context-mode hook payloads look like? | Unanswered | — |
| OQ-3 | What FTS5 tokenizer settings does context-mode use? | Unanswered | — |
| OQ-4 | Is FTS5 + trigram available in Python's bundled `sqlite3` on Linux/macOS/Windows? | Unanswered | — |
| OQ-5 | What are the current LangGraph `BaseStore` method signatures? | Unanswered | — |
| OQ-6 | Does Python 3.10 cover current LangChain/LangGraph support range? | Unanswered | — |
| OQ-7 | Does context-mode expose events via DB file, MCP tool, or both? | Unanswered | — |
| OQ-8 | Is exposing `agentbus` as a context-mode MCP companion better than standalone first? | Unanswered (decide post-Phase 1) | — |
| OQ-9 | Which benchmark tasks are representative and reproducible? | Unanswered (decide in Phase 3 planning) | — |

---

## File Map (target structure when complete)

```
Agent-bus/
├── CLAUDE.md                  <- Step 1
├── PLAYBOOK_PROGRESS.md       <- this file
├── Makefile                   <- Step 5
├── intent/
│   └── intent.md              <- Steps 2 & 3
├── spec.md                    <- Step 4
├── plan.md                    <- Step 6 (Phase 1)
├── plan_phase2.md             <- Step 10 (Phase 2)
├── plan_phase3.md             <- Step 10 (Phase 3)
├── REVIEW.md                  <- Step 9
├── .github/
│   └── workflows/
│       └── ci.yml             <- Steps 5 & 9
├── src/
│   └── agentbus/
│       ├── core/              <- Step 8 Session A
│       ├── langgraph/         <- Step 10 Phase 2
│       ├── langchain/         <- Step 10 Phase 2
│       ├── server/            <- Phase 4
│       └── bridge/            <- Phase 4
├── eval/                      <- Step 8 Session B + Phase 3
└── tests/
    ├── test_concurrency.py    <- Step 5 (written failing first)
    └── test_crash_safety.py   <- Step 5 (written failing first)
```
