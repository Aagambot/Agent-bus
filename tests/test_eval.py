"""Unit tests for agentbus evaluation harness skeleton (Step 8 Session B)."""

import pytest
from pathlib import Path

from eval.harness import EvalHarness
from eval.loader import load_all_tasks


def test_eval_harness_benchmark():
    """Verify eval harness runs conditions A, B, and C on benchmark tasks."""
    tasks = load_all_tasks()
    assert len(tasks) >= 1

    harness = EvalHarness(tasks=tasks)
    reports = harness.run_benchmark(runs_per_task=1)

    assert len(reports) == len(tasks)
    report = reports[0]

    assert report.task_id == "research_handoff_01"
    assert report.condition_a_avg_tokens > report.condition_c_avg_tokens
    assert report.token_reduction_pct > 0.0
    assert report.condition_c_success_rate == 1.0
