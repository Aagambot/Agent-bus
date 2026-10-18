# Implementation Plan: Phase 3 Evaluation Benchmark (gentbus-eval)

## Goal Description
Implement the complete empirical benchmark suite for **gentbus-eval** (Phase 3 of the PRD/spec). This harness quantitatively measures and validates the core value proposition of gentbus:
1. **Handoff Token Reduction:** Quantify token savings compared to Condition A (raw accumulated transcripts).
2. **Task Success Parity:** Verify that agents running under Condition C (agentbus) achieve equivalent or higher task success compared to Condition A (full context) and Condition B (lossy summary).
3. **Retrieval Precision (Recall@5 & MRR):** Measure the exact proportion of ground-truth findings retrieved within the top 5 results and the Mean Reciprocal Rank across realistic multi-agent handoffs.
4. **Statistical Rigor:** Execute 5+ runs per task per condition, computing mean, standard deviation, and 95% confidence intervals.

All work in this plan delivers **Phase 3** as specified in spec.md (Section 10), resolves **OQ-9** (representative benchmark task corpus), and establishes a reproducible CLI runner and markdown report generator.

---

## Resolved Grilling & Architectural Decisions

1. **Resolution of OQ-9 (Representative Benchmark Tasks):**
   - Synthesizing three distinct multi-agent problem domains reflecting common production workflows:
     - 
esearch_handoff.json: Market analysis & competitive intelligence (3 agents: 2 parallel researchers, 1 synthesizer). Focus: Numerical metrics, financial figures, regional risk factors.
     - code_review_handoff.json: Software engineering & security triage (3 agents: architect, security auditor, test engineer). Focus: Vulnerabilities, architectural constraints, test invariants.
     - incident_response.json: Production SRE incident debugging (3 agents: metrics watcher, log investigator, incident commander). Focus: Timestamps, root-cause hypotheses, mitigation steps.
2. **Condition Execution Models:**
   - **Condition A (Raw Transcript):** Handoff passes the full, cumulative chat/event history at every transition. High token consumption ((N^2)$ accumulation), risk of context window exhaustion.
   - **Condition B (Summarization):** Each agent passes a concise summary of prior work. Low token consumption, but lossy ((1)$ token payload, but high risk of dropping specific numbers, IDs, and edge-case findings).
   - **Condition C (AgentBus Memory):** Content is indexed into the embedded SQLite FTS5 WAL store. Handoffs pass only structured pointers and task-specific search queries. The receiving agent queries relevant context on-demand ((k)$ token payload, zero information loss, verified trust badges).
3. **Evaluation Metrics & Formulas:**
   - **Handoff Token Reduction (%):** (Tokens_A - Tokens_C) / Tokens_A * 100% (Target: >= 50%).
   - **Recall@5:** Proportion of gold findings returned within the top-5 search snippets.
   - **Mean Reciprocal Rank (MRR):** 1/|Q| * sum(1/rank_i), where rank_i is the position of the first relevant snippet.
   - **Task Success Rate Parity:** Condition C success rate >= 95% of Condition A success rate.
   - **95% Confidence Interval:** mean +- 1.96 * (s / sqrt(N)) over N >= 5 runs.
4. **CLI and Automation:**
   - CLI command: python -m eval.cli --runs 5 --output report_phase3.md with structured console tables and exportable Markdown report.

---

## Proposed Changes & File Layout

`
eval/
|-- __init__.py                # Package exports
|-- models.py                  # Enhanced data models (Recall@5, MRR, 95% CI, stats)
|-- loader.py                  # JSON task loader with schema validation
|-- conditions.py              # Realistic Condition A, B, and C implementations
|-- harness.py                 # Multi-run evaluation orchestrator and statistical aggregation
|-- cli.py                     # CLI entrypoint with args (--runs, --tasks, --output)
-- tasks/
    |-- research_handoff.json      # Market analysis task (finance)
    |-- code_review_handoff.json   # Multi-agent code & security review (software)
    -- incident_response.json     # SRE production incident triage (operations)

tests/
-- test_eval.py               # Enhanced unit and integration tests for eval harness
`

---

## Step-by-Step Implementation Sequence

### Step 1: Expand Benchmark Tasks (eval/tasks/)
- Add code_review_handoff.json (3 agents, code snippets, CVE/security audit findings, gold facts).
- Add incident_response.json (3 agents, system alerts, log stack traces, mitigation commands, gold facts).

### Step 2: Upgrade Evaluation Data Models (eval/models.py)
- Add metrics: 
ecall_at_5, mrr, confidence_interval_95.
- Enhance BenchmarkReport with standard deviations and confidence bands for publication quality.

### Step 3: Implement Realistic Conditions (eval/conditions.py)
- Enhance Condition A: Accurately simulate cumulative context window growth across agent turns.
- Enhance Condition B: Simulate realistic extractive/abstractive summarization with potential information drop.
- Enhance Condition C: Real multi-agent handoff via us.index(), us.handoff(), and us.search() with BM25 + Trigram RRF retrieval, measuring exact Recall@5 and MRR for each query.

### Step 4: Upgrade Harness & Statistics (eval/harness.py)
- Support N >= 5 runs per condition.
- Implement statistical aggregations: Mean, Standard Deviation, and 95% Confidence Intervals for tokens and retrieval metrics.
- Generate formatted Markdown report.

### Step 5: Implement CLI Entrypoint (eval/cli.py)
- Provide user-friendly CLI with flags: --runs, --output, --task.

### Step 6: Test Suite & Review
- Enhance 	ests/test_eval.py to test multi-run aggregation, Recall@5, MRR calculation, and CLI invocation.
- Execute full test suite (pytest -v) ensuring zero regressions and >= 80% coverage.
- Conduct REVIEW.md three-pass audit for Phase 3.

---

## Verification & Acceptance Criteria
1. **Token Reduction:** Condition C achieves >= 50% handoff token reduction compared to Condition A.
2. **Success Parity:** Condition C matches or exceeds Condition A success rate (>= 95% parity).
3. **Retrieval Quality:** Recall@5 >= 0.85 and MRR >= 0.80 on all benchmark tasks.
4. **Statistical Stability:** 5+ benchmark runs executed with 95% confidence intervals documented.
5. **Clean CI & Test Integrity:** All tests pass cleanly; pre-commit hooks pass; zero edits to 	est_concurrency.py and 	est_crash_safety.py.
