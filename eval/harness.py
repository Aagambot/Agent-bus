"""Evaluation harness orchestrator comparing Conditions A, B, and C."""

import tempfile
from pathlib import Path
from typing import List

from .conditions import run_condition_a, run_condition_b, run_condition_c
from .loader import load_all_tasks
from .models import BenchmarkReport, ConditionResult, EvalCondition, EvalTask
from agentbus.core import Bus


class EvalHarness:
    """Runs benchmark evaluation tasks across conditions."""

    def __init__(self, tasks: List[EvalTask] | None = None):
        self.tasks = tasks or load_all_tasks()

    def run_benchmark(self, runs_per_task: int = 1) -> List[BenchmarkReport]:
        """Execute all tasks against Conditions A, B, and C and return report."""
        reports = []

        for task in self.tasks:
            a_results: List[ConditionResult] = []
            b_results: List[ConditionResult] = []
            c_results: List[ConditionResult] = []

            for _ in range(runs_per_task):
                # Condition A
                a_results.append(run_condition_a(task))
                # Condition B
                b_results.append(run_condition_b(task))

                # Condition C (with clean temporary Bus)
                with tempfile.TemporaryDirectory() as tmp_dir:
                    db_path = str(Path(tmp_dir) / "eval.db")
                    with Bus(db_path=db_path) as bus:
                        c_results.append(run_condition_c(task, bus))

            avg_a_tokens = sum(r.handoff_tokens for r in a_results) / len(a_results)
            avg_b_tokens = sum(r.handoff_tokens for r in b_results) / len(b_results)
            avg_c_tokens = sum(r.handoff_tokens for r in c_results) / len(c_results)

            reduction_pct = 0.0
            if avg_a_tokens > 0:
                reduction_pct = max(0.0, (avg_a_tokens - avg_c_tokens) / avg_a_tokens * 100.0)

            success_a = sum(1 for r in a_results if r.success) / len(a_results)
            success_c = sum(1 for r in c_results if r.success) / len(c_results)

            reports.append(
                BenchmarkReport(
                    task_id=task.task_id,
                    runs_per_condition=runs_per_task,
                    condition_a_avg_tokens=avg_a_tokens,
                    condition_b_avg_tokens=avg_b_tokens,
                    condition_c_avg_tokens=avg_c_tokens,
                    token_reduction_pct=round(reduction_pct, 1),
                    condition_a_success_rate=success_a,
                    condition_c_success_rate=success_c,
                )
            )

        return reports
