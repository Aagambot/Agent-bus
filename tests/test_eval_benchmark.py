# Unit and integration tests for Phase 3 evaluation benchmark.
import pytest
from pathlib import Path

from eval.harness import EvalHarness
from eval.loader import load_all_tasks, load_task_from_file
from eval.models import (
    AggregatedConditionStats,
    ConditionResult,
    EvalCondition,
    EvalTask,
)
from eval.cli import main as cli_main

def test_eval_loader_finds_all_tasks():
    tasks = load_all_tasks()
    assert len(tasks) == 3
    task_ids = {t.task_id for t in tasks}
    assert 'research_handoff_01' in task_ids
    assert 'code_review_handoff_02' in task_ids
    assert 'incident_response_03' in task_ids

def test_eval_harness_multi_run_metrics():
    tasks = load_all_tasks()
    harness = EvalHarness(tasks=tasks)
    reports = harness.run_benchmark(runs_per_task=2)
    assert len(reports) == 3
    for r in reports:
        assert r.token_reduction_pct >= 50.0
        assert r.condition_c_success_rate == 1.0
        assert r.stats_c.mean_recall_at_5 == 1.0
        assert r.stats_c.mean_mrr == 1.0
        assert r.success_parity_ratio >= 1.0

def test_eval_aggregated_stats_ci95():
    empty_stats = AggregatedConditionStats.compute(EvalCondition.CONDITION_A, [])
    assert empty_stats.runs == 0
    assert empty_stats.mean_handoff_tokens == 0.0
    results = [
        ConditionResult(
            condition=EvalCondition.CONDITION_C,
            task_id='t1',
            run_id='r1',
            success=True,
            total_tokens_sent=200,
            handoff_tokens=100,
            duration_seconds=0.05,
            findings_recalled=3,
            total_expected_findings=3,
            recall_at_5=1.0,
            mrr=1.0,
        ),
        ConditionResult(
            condition=EvalCondition.CONDITION_C,
            task_id='t1',
            run_id='r2',
            success=True,
            total_tokens_sent=220,
            handoff_tokens=110,
            duration_seconds=0.06,
            findings_recalled=3,
            total_expected_findings=3,
            recall_at_5=1.0,
            mrr=1.0,
        ),
    ]
    stats = AggregatedConditionStats.compute(EvalCondition.CONDITION_C, results)
    assert stats.runs == 2
    assert stats.mean_handoff_tokens == 105.0
    assert stats.ci95_handoff_tokens[0] <= 105.0 <= stats.ci95_handoff_tokens[1]

def test_eval_generate_markdown_report():
    harness = EvalHarness()
    reports = harness.run_benchmark(runs_per_task=1)
    md = harness.generate_markdown_report(reports)
    assert '# agentbus Benchmark Evaluation Report' in md
    assert 'Token Reduction' in md
    assert 'Recall@5' in md

def test_eval_cli_execution(tmp_path):
    out_file = tmp_path / 'out.md'
    exit_code = cli_main([
        '--runs', '1', '--output', str(out_file)
    ])
    assert exit_code == 0
    assert out_file.exists()
    content = out_file.read_text(encoding='utf-8')
    assert 'agentbus Benchmark Evaluation Report' in content
