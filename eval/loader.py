"""Benchmark task loader for the evaluation harness."""

import json
from pathlib import Path
from typing import List

from .models import EvalTask


def load_task_from_file(file_path: Path) -> EvalTask:
    """Load a benchmark task definition from a JSON file."""
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return EvalTask(
        task_id=data["task_id"],
        name=data.get("name", file_path.stem),
        description=data.get("description", ""),
        initial_context=data.get("initial_context", ""),
        steps=data.get("steps", []),
        expected_findings=data.get("expected_findings", []),
        metadata=data.get("metadata", {}),
    )


def load_all_tasks(tasks_dir: Path | None = None) -> List[EvalTask]:
    """Load all JSON benchmark tasks in the tasks directory."""
    target_dir = tasks_dir or Path(__file__).parent / "tasks"
    tasks = []
    if target_dir.exists():
        files = sorted(target_dir.glob("*.json"), key=lambda p: (0 if "research" in p.name else 1, p.name))
        for json_file in files:
            tasks.append(load_task_from_file(json_file))
    return tasks
