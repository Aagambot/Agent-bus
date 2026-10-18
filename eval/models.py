# Data models for the agentbus evaluation harness (Phase 3).
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class EvalCondition(str, Enum):
    CONDITION_A = "condition_a_full_transcript"
    CONDITION_B = "condition_b_summary"
    CONDITION_C = "condition_c_agentbus"


@dataclass
class EvalTask:
    task_id: str
    name: str
    description: str
    initial_context: str
    steps: List[Dict[str, Any]]
    expected_findings: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConditionResult:
    condition: EvalCondition
    task_id: str
    run_id: str
    success: bool
    total_tokens_sent: int
    handoff_tokens: int
    duration_seconds: float
    findings_recalled: int
    total_expected_findings: int
    recall_at_5: float = 0.0
    recall_at_k: float = 0.0
    mrr: float = 0.0
    error_message: Optional[str] = None


@dataclass
class AggregatedConditionStats:
    condition: EvalCondition
    runs: int
    mean_handoff_tokens: float
    std_handoff_tokens: float
    ci95_handoff_tokens: Tuple[float, float]
    mean_total_tokens: float
    success_rate: float
    mean_recall_at_5: float
    mean_mrr: float
    mean_duration_seconds: float

    @classmethod
    def compute(cls, condition: EvalCondition, results: List[ConditionResult]) -> "AggregatedConditionStats":
        n = len(results)
        if n == 0:
            return cls(
                condition=condition,
                runs=0,
                mean_handoff_tokens=0.0,
                std_handoff_tokens=0.0,
                ci95_handoff_tokens=(0.0, 0.0),
                mean_total_tokens=0.0,
                success_rate=0.0,
                mean_recall_at_5=0.0,
                mean_mrr=0.0,
                mean_duration_seconds=0.0,
            )
        handoffs = [r.handoff_tokens for r in results]
        mean_h = sum(handoffs) / n
        var_h = sum((x - mean_h) ** 2 for x in handoffs) / max(n - 1, 1)
        std_h = math.sqrt(var_h)
        margin = 1.96 * (std_h / math.sqrt(n)) if n > 1 else 0.0
        ci95 = (round(max(0.0, mean_h - margin), 1), round(mean_h + margin, 1))
        mean_total = sum(r.total_tokens_sent for r in results) / n
        success = sum(1 for r in results if r.success) / n
        mean_rec = sum(r.recall_at_5 for r in results) / n
        mean_mrr = sum(r.mrr for r in results) / n
        mean_dur = sum(r.duration_seconds for r in results) / n
        return cls(
            condition=condition,
            runs=n,
            mean_handoff_tokens=round(mean_h, 1),
            std_handoff_tokens=round(std_h, 2),
            ci95_handoff_tokens=ci95,
            mean_total_tokens=round(mean_total, 1),
            success_rate=round(success, 3),
            mean_recall_at_5=round(mean_rec, 3),
            mean_mrr=round(mean_mrr, 3),
            mean_duration_seconds=round(mean_dur, 4),
        )


@dataclass
class BenchmarkReport:
    task_id: str
    task_name: str
    runs_per_condition: int
    stats_a: AggregatedConditionStats
    stats_b: AggregatedConditionStats
    stats_c: AggregatedConditionStats
    token_reduction_pct: float
    success_parity_ratio: float

    @property
    def condition_a_avg_tokens(self) -> float:
        return self.stats_a.mean_handoff_tokens

    @property
    def condition_b_avg_tokens(self) -> float:
        return self.stats_b.mean_handoff_tokens

    @property
    def condition_c_avg_tokens(self) -> float:
        return self.stats_c.mean_handoff_tokens

    @property
    def condition_a_success_rate(self) -> float:
        return self.stats_a.success_rate

    @property
    def condition_c_success_rate(self) -> float:
        return self.stats_c.success_rate
