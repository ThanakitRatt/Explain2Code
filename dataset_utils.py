"""Load HumanEvalPlus and MBPP+ tasks and their per-task test cases."""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Any

from config import PipelineConfig
from path_utils import local_original_path, save_original_code


@dataclass
class TestCase:
    kind: str
    payload: Any
    name: str


@dataclass
class Task:
    task_id: str
    prompt: str
    original_code: str
    entry_point: str
    test_code: str = ""
    test_setup_code: str = ""
    test_cases: list[TestCase] = field(default_factory=list)
    atol: float = 0.0
    raw: dict[str, Any] = field(default_factory=dict)


def _first_function_name(code: str) -> str:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return ""
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return node.name
    return ""


def _function_called_by_tests(code: str, tests: list[str]) -> str:
    """Find the single source function directly exercised by MBPP assertions."""
    try:
        source_tree = ast.parse(code)
    except SyntaxError:
        return ""
    function_names = {
        node.name for node in source_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    called_names = set()
    for test in tests:
        try:
            test_tree = ast.parse(test)
        except SyntaxError:
            continue
        for node in ast.walk(test_tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
            else:
                continue
            if name in function_names:
                called_names.add(name)
    return next(iter(called_names)) if len(called_names) == 1 else ""


class DatasetLoader:
    def __init__(self, cfg: PipelineConfig):
        self.cfg = cfg

    def load(self) -> list[Task]:
        if self.cfg.dataset.name == "humaneval":
            return self._load_humaneval()
        if self.cfg.dataset.name == "mbpp":
            return self._load_mbpp()
        raise ValueError("Dataset name must be 'humaneval' or 'mbpp'.")

    @staticmethod
    def _hf_dataset(dataset_id: str, config_name: str | None, split: str):
        try:
            from datasets import load_dataset
        except ImportError as exc:
            raise RuntimeError(
                "Install the `datasets` package to load HumanEvalPlus/MBPP+."
            ) from exc
        args = [dataset_id]
        if config_name:
            args.append(config_name)
        return load_dataset(*args, split=split)

    def _load_humaneval(self) -> list[Task]:
        dataset_cfg = self.cfg.dataset
        rows = self._hf_dataset(
            dataset_cfg.humaneval_hf_id,
            dataset_cfg.humaneval_config,
            dataset_cfg.humaneval_split,
        )
        plus_tasks = self._load_evalplus_tasks("humaneval")
        tasks = []
        for row in rows:
            task_id = str(row["task_id"])
            plus_task = self._matching_evalplus_task(plus_tasks, task_id)
            code = str(row.get("prompt", "")) + str(row.get("canonical_solution", ""))
            code = self._local_override(task_id, code)
            tests = str(row.get("test", "") or "")
            test_cases = self._evalplus_test_cases(plus_task)
            tasks.append(Task(
                task_id=task_id,
                prompt=str(row.get("prompt", "")),
                original_code=code,
                entry_point=str(row.get("entry_point", "")),
                test_code=tests,
                test_cases=test_cases,
                atol=float(plus_task.get("atol", 0.0)),
                raw=dict(row),
            ))
        return self._materialize(tasks)

    def _load_mbpp(self) -> list[Task]:
        dataset_cfg = self.cfg.dataset
        rows = self._hf_dataset(
            dataset_cfg.mbpp_hf_id, dataset_cfg.mbpp_config, dataset_cfg.mbpp_split
        )
        plus_tasks = self._load_evalplus_tasks("mbpp")
        tasks = []
        for row in rows:
            raw_id = str(row.get("task_id", row.get("id", "")))
            task_id = f"MBPP/{raw_id}"
            plus_task = self._matching_evalplus_task(plus_tasks, task_id)
            source_code = str(row.get("code", row.get("canonical_solution", "")) or "")
            code = self._local_override(task_id, source_code)
            tests = [str(test) for test in (row.get("test_list", []) or [])]
            setup = str(row.get("test_setup_code", "") or "")
            cases = self._evalplus_test_cases(plus_task)
            entry_point = str(row.get("entry_point") or "")
            if not entry_point:
                entry_point = (
                    _function_called_by_tests(source_code, tests)
                    or _first_function_name(source_code)
                )
            tasks.append(Task(
                task_id=task_id,
                prompt=str(row.get("prompt") or row.get("text") or ""),
                original_code=code,
                entry_point=entry_point,
                test_code=str(row.get("test", "") or ""),
                test_setup_code=setup,
                test_cases=cases,
                atol=float(plus_task.get("atol", 0.0)),
                raw=dict(row),
            ))
        return self._materialize(tasks)

    @staticmethod
    def _load_evalplus_tasks(dataset_name: str) -> dict[str, dict[str, Any]]:
        try:
            from evalplus.data import get_human_eval_plus, get_mbpp_plus
        except ImportError as exc:
            raise RuntimeError(
                "Install EvalPlus with `python -m pip install evalplus` "
                "to load the complete HumanEval+/MBPP+ input sets."
            ) from exc

        if dataset_name == "humaneval":
            return get_human_eval_plus()
        if dataset_name == "mbpp":
            return get_mbpp_plus()
        raise ValueError(f"Unsupported EvalPlus dataset: {dataset_name}")

    @staticmethod
    def _matching_evalplus_task(
        plus_tasks: dict[str, dict[str, Any]], task_id: str
    ) -> dict[str, Any]:
        normalized_id = task_id.rsplit("/", 1)[-1].casefold()
        matches = [
            task for key, task in plus_tasks.items()
            if str(key).rsplit("/", 1)[-1].casefold() == normalized_id
        ]
        if len(matches) != 1:
            raise ValueError(
                f"Expected exactly one EvalPlus task matching {task_id!r}; "
                f"found {len(matches)}."
            )
        return matches[0]

    @staticmethod
    def _evalplus_test_cases(plus_task: dict[str, Any]) -> list[TestCase]:
        cases = []
        for input_type in ("base_input", "plus_input"):
            if input_type not in plus_task:
                raise ValueError(
                    f"EvalPlus task {plus_task.get('task_id', '<unknown>')!r} "
                    f"is missing {input_type!r}."
                )
            inputs = plus_task[input_type]
            if input_type == "plus_input" and inputs in (None, {}):
                inputs = []
            if not isinstance(inputs, (list, tuple)):
                task_id = plus_task.get("task_id", "<unknown>")
                raise ValueError(
                    f"EvalPlus task {task_id!r} {input_type} must be a list or tuple; "
                    f"got {type(inputs).__name__}."
                )
            label = input_type.removesuffix("_input")
            cases.extend(
                TestCase("oracle_input", test_input, f"{label}-{index + 1}")
                for index, test_input in enumerate(inputs)
            )
        if not cases:
            raise ValueError(
                f"EvalPlus task {plus_task.get('task_id', '<unknown>')!r} "
                "contains no base or Plus input cases."
            )
        return cases

    def _local_override(self, task_id: str, fallback: str) -> str:
        path = local_original_path(self.cfg, task_id)
        return path.read_text("utf-8") if path.is_file() else fallback

    def _materialize(self, tasks: list[Task]) -> list[Task]:
        for task in tasks:
            save_original_code(self.cfg, task.task_id, task.original_code)
        return tasks

    def select(self, tasks: list[Task], limit: int | None = None,
               task_ids: set[str] | None = None) -> list[Task]:
        if task_ids is not None:
            tasks = [task for task in tasks if task.task_id in task_ids]
        if limit is not None:
            tasks = tasks[:limit]
        return tasks
