"""Run each benchmark test independently and save its individual outcome."""
from __future__ import annotations

import ast
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from config import PipelineConfig, TEST_SUITE_VERSION
from dataset_utils import Task, TestCase
from path_utils import artifact_path


class _KeepOneAssertion(ast.NodeTransformer):
    def __init__(self, selected: int):
        self.selected = selected
        self.index = 0

    def visit_Assert(self, node: ast.Assert):
        current = self.index
        self.index += 1
        if current != self.selected:
            return ast.copy_location(ast.Pass(), node)
        return self.generic_visit(node)


class BehaviorAssessment:
    def __init__(self, cfg: PipelineConfig):
        self.cfg = cfg

    def run(self, task: Task, reconstructed_code: str) -> dict:
        outcomes = []
        for test in task.test_cases:
            try:
                script = self._test_script(task, reconstructed_code, test)
                passed, detail = self._execute(script)
            except (KeyError, ValueError) as exc:
                passed, detail = False, f"{type(exc).__name__}: {exc}"
            outcomes.append({
                "test": test.name,
                "passed": passed,
                "detail": detail,
            })

        total = len(outcomes)
        passed = sum(outcome["passed"] for outcome in outcomes)
        result = {
            "test_suite_version": TEST_SUITE_VERSION,
            "task_id": task.task_id,
            "tests_passed": passed,
            "tests_total": total,
            "test_pass_rate": passed / total if total else None,
            "test_results": outcomes,
        }
        destination = artifact_path(
            self.cfg, "test_results", task.task_id, "behavior_assessment.json"
        )
        destination.write_text(json.dumps(result, indent=2, ensure_ascii=False), "utf-8")
        return result

    def _test_script(self, task: Task, reconstructed_code: str, test: TestCase) -> str:
        shared = "\n".join(part for part in (task.test_setup_code, reconstructed_code) if part)
        if test.kind == "oracle_input":
            reference = repr(
                "\n".join(part for part in (task.test_setup_code, task.original_code) if part)
            )
            candidate = repr(
                "\n".join(part for part in (task.test_setup_code, reconstructed_code) if part)
            )
            arguments = self._argument_expression(test.payload)
            return (
                "def _load(source):\n"
                "    namespace = {'__name__': '__main__'}\n"
                "    exec(compile(source, '<solution>', 'exec'), namespace)\n"
                "    return namespace\n"
                "def _equal(actual, expected, atol):\n"
                "    import math\n"
                "    if isinstance(actual, bool) or isinstance(expected, bool):\n"
                "        return actual is expected\n"
                "    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):\n"
                "        if isinstance(actual, float) or isinstance(expected, float):\n"
                "            return math.isclose(actual, expected, rel_tol=1e-7, abs_tol=atol)\n"
                "        return actual == expected\n"
                "    if type(actual) is not type(expected):\n"
                "        return False\n"
                "    if isinstance(actual, (list, tuple)):\n"
                "        return len(actual) == len(expected) and all(\n"
                "            _equal(a, e, atol) for a, e in zip(actual, expected)\n"
                "        )\n"
                "    if isinstance(actual, dict):\n"
                "        return actual.keys() == expected.keys() and all(\n"
                "            _equal(actual[key], expected[key], atol) for key in actual\n"
                "        )\n"
                "    if isinstance(actual, set):\n"
                "        return actual == expected\n"
                "    return actual == expected\n"
                f"_reference = _load({reference})\n"
                f"_candidate = _load({candidate})\n"
                f"_expected = _reference[{task.entry_point!r}](*{arguments})\n"
                f"_actual = _candidate[{task.entry_point!r}](*{arguments})\n"
                f"_atol = {task.atol!r}\n"
                "assert _equal(_actual, _expected, _atol), "
                "f'expected {_expected!r}, got {_actual!r}'\n"
            )
        if test.kind == "assertion_code":
            return "\n".join(part for part in (shared, str(test.payload)) if part)
        if test.kind == "assertion":
            try:
                tree = ast.parse(task.test_code)
                transformed = _KeepOneAssertion(int(test.payload)).visit(tree)
                ast.fix_missing_locations(transformed)
                selected_test = ast.unparse(transformed)
            except (SyntaxError, ValueError):
                selected_test = task.test_code
            call_check = (
                f"\ncheck({task.entry_point})\n"
                if self._defines_check(task.test_code) else ""
            )
            return "\n".join((reconstructed_code, selected_test, call_check))
        if test.kind == "test_code":
            call_check = (
                f"\ncheck({task.entry_point})\n"
                if self._defines_check(task.test_code) else ""
            )
            return "\n".join((reconstructed_code, task.test_code, call_check))
        raise ValueError(f"Unknown test case kind: {test.kind}")

    @staticmethod
    def _defines_check(test_code: str) -> bool:
        try:
            tree = ast.parse(test_code)
        except SyntaxError:
            return False
        return any(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "check"
            for node in tree.body
        )

    @staticmethod
    def _argument_expression(inputs: Any) -> str:
        if not isinstance(inputs, (list, tuple)):
            inputs = [inputs]
        return repr(tuple(inputs))

    def _execute(self, script: str) -> tuple[bool, str]:
        with tempfile.TemporaryDirectory(prefix="behavior-test-") as folder:
            script_path = Path(folder) / "case.py"
            script_path.write_text(script, "utf-8")
            try:
                proc = subprocess.run(
                    [sys.executable, str(script_path)],
                    capture_output=True, text=True,
                    timeout=self.cfg.test_timeout_sec,
                    cwd=folder,
                )
            except subprocess.TimeoutExpired:
                return False, f"TIMEOUT after {self.cfg.test_timeout_sec}s"
            if proc.returncode == 0:
                return True, ""
            return False, (proc.stderr or proc.stdout).strip()[-2000:]
