"""Data models for the agentbus evaluation harness (Phase 3 skeleton)."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class EvalCondition(str, Enum):
    """The three benchmark conditions compared in evaluation."""
    CONDITION_A = "condition_a_full_transcript"
    CONDITION_B = "condition_b_summary"
    CONDITION_C = "condition_c_agentbus"


@dataclass
class EvalTask:
    """A multi-agent benchmark task."""
    task_id: str
    name: str
    description: str
    initial_context: str
    steps: List[Dict[str, Any]]
    expected_findings: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConditionResult:
    """Outcome metrics for a single condition run."""
    condition: EvalCondition
    task_id: str
    run_id: str
    success: bool
    total_tokens_sent: int
    handoff_tokens: int
    duration_seconds: float
    findings_recalled: int
    total_expected_findings: int
    recall_at_k: float = 0.0
    error_message: Optional[str] = None


@dataclass
class BenchmarkReport:
    """Comparative summary report across conditions."""
    task_id: str
    runs_per_condition: int
    condition_a_avg_tokens: float
    condition_b_avg_tokens: float
    condition_c_avg_tokens: float
    token_reduction_pct: float  # (A - C) / A * 100
    condition_a_success_rate: float
    condition_c_success_rate: float
