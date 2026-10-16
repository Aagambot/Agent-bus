# agentbus — Playbook Adoption Progress

> **What this file is:** A living tracker that maps the playbook's dependency-ordered steps onto the `agentbus` PRD.
> Update the status column after each step completes. The "Next Actions" section always reflects the single next concrete thing to do.
>
> **Last updated:** 2026-10-17 — Steps 1 & 2 complete ✅

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
**Status:** 🔲 Not Started — ready to begin (Steps 1 & 2 are done)

**What to do:**
- [ ] Spin up a **read-only `researcher` subagent** over the context-mode source
- [ ] Tasks for the subagent:
  - Read and document the DB schema (table names, columns, indexes)
  - Capture hook payload shapes and event types
  - Confirm FTS5 + trigram tokenizer settings used
  - Document the `BaseStore`-equivalent interface if any
  - Check how context-mode exposes events (DB file vs MCP tool)
- [ ] Write answers back into `intent/intent.md` under each open question
- [ ] Close or defer every `[Verify]` item

**Why subagent:** Exploration work should not flood the main context — this is the exact problem `agentbus` solves.

**Exit criterion:** All `[Verify]` items in `intent.md` are either answered with a source reference or formally descoped.

---

### Step 4 — `spec.md` with licensing + security skills (depends on Steps 2 & 3)
**Playbook play:** Requirements and design
**Status:** Blocked on Step 3

**What to do:**
- [ ] Load two skills into the Claude session: **licensing skill** and **security skill**
- [ ] Turn PRD sections 5-9 into `spec.md`:
  - Components (5.1), Architecture (5.2)
  - Functional requirements (6) — all FR-* items
  - Data model (7)
  - Public API (8)
  - Non-functional requirements (9)
- [ ] Security skill must flag: ACL gaps, trust-label enforcement points, secret-redaction hooks, prompt-injection surface
- [ ] Licensing skill must flag: any pattern that risks ELv2 inheritance
- [ ] **Human review required** before proceeding — read every flagged concern and resolve or accept

**Why now:** Policy applied while the spec is written is cheaper than retrofitting. The `intent.md` + `spec.md` pair is the audit trail.

---

### Step 5 — Feedback loop: failing tests first (depends on Step 4)
**Playbook play:** Feedback loop
**Status:** Blocked on Step 4

**What to do:**
- [ ] Write `Makefile` with a `test` target (`pytest -x --tb=short`)
- [ ] Write **concurrency stress test** (8 readers + 4 writers, 60 s, assert zero lock errors) — must fail now
- [ ] Write **kill-mid-write test** (SIGKILL during a write, re-open DB, assert integrity) — must fail now
- [ ] Confirm both tests run and fail cleanly before any implementation
- [ ] Add tests to CI (GitHub Actions or equivalent)

**Why before code:** Concurrency bugs are subtle. Giving Claude a way to verify its own work catches them during implementation, not after. These tests encode NFR-2 and NFR-6 as runnable checks.

---

### Step 6 — `plan.md` for Phase 1 Core Store (depends on Step 5)
**Playbook play:** Plan mode
**Status:** Blocked on Step 5

**What to do:**
- [ ] Use Claude in **plan mode** (output only, no edits)
- [ ] Produce `plan.md` covering Phase 1 (`agentbus-core`):
  - Files to create and their purpose
  - Order of implementation with justification
  - Risks and proofs (how each risk is mitigated)
  - Mapping to FR-1 through FR-12 and NFR-1, NFR-6
- [ ] **Human review + commit `plan.md`** before any code is written
- [ ] Later reviews will diff implementation against this plan

**Why:** Nothing gets implemented without an accepted plan. The commit timestamp is the audit-trail anchor.

---

### Step 7 — Hooks (depends on Step 6)
**Playbook play:** Hooks
**Status:** Blocked on Step 6

**What to do:**
- [ ] Add hook: **block edits to test files during fix tasks** (skills are advisory; hooks are enforced)
- [ ] Add hook: **block reads of the upstream context-mode source directory during implementation**
- [ ] Add hook: **block secrets in diffs** (regex scan for API keys, tokens, env var patterns)
- [ ] Test each hook fires correctly on a mock trigger

**Why:** The license and test-integrity rules written in `CLAUDE.md` need enforcement, not just advice.

---

### Step 8 — Parallel implementation: core store + eval harness skeleton (depends on Steps 6 & 7)
**Playbook play:** Parallel sessions
**Status:** Blocked on Steps 6 & 7

**What to do:**
- [ ] Open **2 parallel worktree sessions** (they touch different files)
  - **Session A — `agentbus-core`:** Chunker -> FTS5 hybrid search -> RRF -> TTL cache -> event log -> snapshots -> WAL writer queue
  - **Session B — `agentbus-eval` skeleton:** Harness scaffold, condition stubs (A/B/C), benchmark task loader
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

## Next Actions (as of 2026-10-17)

> **Steps 1 and 2 are complete. Step 3 is ready to start.**

1. ✅ ~~Create `CLAUDE.md`~~ — done
2. ✅ ~~Create `intent/intent.md`~~ — done
3. **Run Phase 0 researcher subagent** (Step 3): spin up a read-only subagent over the context-mode source to answer OQ-1 → OQ-7 in `intent/intent.md`. Use the "Researcher Subagent Brief" section at the bottom of `intent/intent.md` as the subagent's task prompt. The subagent must not modify any files — only write answers back into `intent/intent.md`.

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
