"""Persist per-task behavioral test totals and aggregate test pass rates."""
from __future__ import annotations

import csv
import os
from dataclasses import asdict, dataclass
from pathlib import Path

from config import PipelineConfig, TEST_SUITE_VERSION
from path_utils import result_csv_path


@dataclass
class EvaluationResult:
    agent: str
    provider: str
    model: str
    run_name: str
    dataset: str
    task_id: str
    tests_passed: int
    tests_total: int
    test_pass_rate_pct: float | None
    reconstruction_time_sec: float
    test_suite_version: str
    error: str = ""


class Evaluator:
    def __init__(self, cfg: PipelineConfig):
        self.cfg = cfg
        self.rows: list[EvaluationResult] = []

    def record(self, task_id: str, tests_passed: int, tests_total: int,
               elapsed: float) -> EvaluationResult:
        rate = tests_passed / tests_total * 100 if tests_total else None
        result = EvaluationResult(
            agent=self.cfg.llm.agent,
            provider=self.cfg.llm.provider,
            model=self.cfg.llm.model,
            run_name=self.cfg.run_name,
            dataset=self.cfg.dataset.name,
            task_id=task_id,
            tests_passed=tests_passed,
            tests_total=tests_total,
            test_pass_rate_pct=round(rate, 2) if rate is not None else None,
            reconstruction_time_sec=round(elapsed, 3),
            test_suite_version=TEST_SUITE_VERSION,
        )
        self.rows.append(result)
        return result

    def save(self) -> Path:
        path = result_csv_path(self.cfg)
        old_rows = []
        if path.is_file():
            with path.open(newline="", encoding="utf-8") as handle:
                old_rows = list(csv.DictReader(handle))
        current_ids = {row.task_id for row in self.rows}
        combined = [row for row in old_rows if row.get("task_id") not in current_ids]
        combined.extend(asdict(row) for row in self.rows)
        columns = list(asdict(self.rows[0]).keys()) if self.rows else list(EvaluationResult.__annotations__)
        temp = path.with_suffix(".csv.tmp")
        with temp.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader()
            writer.writerows(combined)
        os.replace(temp, path)
        return path

    def summary(self) -> dict:
        passed = sum(row.tests_passed for row in self.rows)
        total = sum(row.tests_total for row in self.rows)
        return {
            "tasks": len(self.rows),
            "tests_passed": passed,
            "tests_total": total,
            "test_pass_rate_pct": round(passed / total * 100, 2) if total else None,
        }
