"""Public experiment API for running the reconstruction and behavior stages."""
from __future__ import annotations

import csv
import html
import json
import os
import time
from pathlib import Path

from config import (
    AGENT_PRESETS,
    ARTIFACT_ROOT,
    DATA_ROOT,
    RESULT_ROOT,
    TEST_SUITE_VERSION,
    DatasetConfig,
    LLMConfig,
    PipelineConfig,
)
from dataset_utils import DatasetLoader
from evaluate import Evaluator
from llm import LLMClient
from path_utils import artifact_path, result_csv_path, save_original_code
from reconstruction import Reconstruction
from trace import Tracer
from behavior_assessment import BehaviorAssessment
from structural_assessment import StructuralAssessment


def _make_config(agent: str, model_key: str | None, model: str | None,
                 dataset: str, limit: int | None,
                 data_root: Path | None = None, run_name: str = "") -> PipelineConfig:
    if agent not in AGENT_PRESETS:
        raise KeyError(f"Unknown agent {agent!r}; choose one of {tuple(AGENT_PRESETS)}.")
    preset = AGENT_PRESETS[agent]
    key = model_key or next(iter(preset.models))
    if model is None and key not in preset.models:
        raise KeyError(f"Unknown model key {key!r} for {agent}; choose {tuple(preset.models)}.")
    model_id = model or preset.models[key]
    return PipelineConfig(
        dataset=DatasetConfig(name=dataset, limit=limit),
        llm=LLMConfig(
            agent=agent,
            provider=preset.provider,
            model=model_id,
            binary=preset.binary,
            base_url=preset.base_url,
        ),
        run_name=run_name,
        data_root=data_root or DATA_ROOT,
    )


def _completed_ids(path: Path, expected_test_counts: dict[str, int]) -> set[str]:
    if not path.is_file():
        return set()
    with path.open(newline="", encoding="utf-8") as handle:
        return {
            row["task_id"] for row in csv.DictReader(handle)
            if (
                row.get("task_id")
                and not row.get("error")
                and row.get("test_suite_version") == TEST_SUITE_VERSION
                and row.get("task_id") in expected_test_counts
                and row.get("tests_total") == str(expected_test_counts[row["task_id"]])
            )
        }


def run(agent: str, model_key: str | None = None, model: str | None = None,
        datasets: tuple[str, ...] = ("humaneval", "mbpp"),
        limit: int | None = None, task_ids: list[str] | None = None,
        skip_done: bool = True, data_root: Path | None = None,
        verbose: bool = True, batch_size: int | None = None,
        run_name: str = "") -> dict:
    """Run a configured agent/model on one or both benchmark aliases.

    Use ``model_key`` to select a preset, or ``model`` to supply an exact model
    identifier accepted by the CLI/server. Completed task rows are resumed by
    default. ``limit`` restricts work to each dataset's first N tasks;
    ``batch_size`` runs the next N unfinished tasks from the selected dataset.
    ``run_name`` isolates artifacts and results; keep it the same to resume.
    """
    if limit is not None and batch_size is not None:
        raise ValueError("Use either limit or batch_size, not both.")
    if batch_size is not None and batch_size < 1:
        raise ValueError("batch_size must be at least 1.")
    if run_name and not run_name.strip():
        raise ValueError("run_name must not contain only whitespace.")

    outputs = {}
    for dataset_name in datasets:
        if dataset_name not in {"humaneval", "mbpp"}:
            raise ValueError(f"Unsupported dataset {dataset_name!r}.")
        cfg = _make_config(
            agent, model_key, model, dataset_name, limit, data_root, run_name.strip()
        )
        tasks = DatasetLoader(cfg).load()
        if task_ids is not None:
            wanted = set(task_ids)
            tasks = [task for task in tasks if task.task_id in wanted]
        if limit is not None:
            tasks = tasks[:limit]

        evaluator = Evaluator(cfg)
        output_csv = result_csv_path(cfg)
        expected_test_counts = {task.task_id: len(task.test_cases) for task in tasks}
        completed_ids = (
            _completed_ids(output_csv, expected_test_counts) if skip_done else set()
        )
        tasks_to_run = [task for task in tasks if task.task_id not in completed_ids]
        if batch_size is not None:
            tasks_to_run = tasks_to_run[:batch_size]
        print(
            f"\n{agent} / {cfg.llm.model}"
            f"{f' / {cfg.run_name}' if cfg.run_name else ''} / {dataset_name}: "
            f"{len(tasks_to_run)} task(s) to run; {len(completed_ids)} resumed"
        )
        print(
            f"Loaded {len(tasks)} task(s); original code saved under "
            f"{cfg.data_root / 'original_code' / dataset_name}",
            flush=True,
        )
        client = LLMClient(cfg.llm)
        tracer = Tracer(cfg, verbose=verbose)
        reconstruction = Reconstruction(client, cfg, tracer)
        assessment = BehaviorAssessment(cfg)
        structural = StructuralAssessment(cfg)

        for task in tasks_to_run:
            started = time.perf_counter()
            source_path = save_original_code(cfg, task.task_id, task.original_code)
            artifact_path(cfg, "original_code", task.task_id, "original.py").write_text(
                task.original_code, "utf-8"
            )
            error = ""
            try:
                print(f"{task.task_id}: starting explanation/reconstruction", flush=True)
                generated = reconstruction.run(
                    task.task_id, task.original_code, task.entry_point
                )["new_code"]
                measured = assessment.run(task, generated)
                passed, total = measured["tests_passed"], measured["tests_total"]
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
                passed, total = 0, len(task.test_cases)
                artifact_path(cfg, "errors", task.task_id, "error.txt").write_text(
                    error, "utf-8"
                )
                print(f"{task.task_id}: {error}")
            result = evaluator.record(
                task.task_id, passed, total, time.perf_counter() - started
            )
            result.error = error
            evaluator.save()
            print(
                f"{task.task_id}: {passed}/{total} tests passed"
                if total else f"{task.task_id}: no tests found"
            )
            print(f"Original source: {source_path}", flush=True)

        structural_report = structural.build_report(tasks)
        outputs[dataset_name] = {
            "result_csv": evaluator.save(),
            "structural_report": structural_report,
            "tasks_run": len(tasks_to_run),
            "summary": evaluator.summary(),
        }
    index_path = results_index()
    print(f"\nResults index: {index_path}", flush=True)
    return outputs


def results_index(result_root: Path | None = None,
                  artifact_root: Path | None = None) -> Path:
    """Generate an HTML index of saved model/run/dataset results."""
    root = Path(result_root or RESULT_ROOT).expanduser().resolve()
    artifacts = Path(artifact_root or ARTIFACT_ROOT).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    entries = []

    def link(path: Path, label: str) -> str:
        relative = Path(os.path.relpath(path, root)).as_posix()
        return f'<a href="{html.escape(relative, quote=True)}">{html.escape(label)}</a>'

    for behavior_csv in sorted(root.rglob("behavior_assessment.csv")):
        with behavior_csv.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        if not rows:
            continue
        first = rows[0]
        passed = sum(int(row.get("tests_passed") or 0) for row in rows)
        total = sum(int(row.get("tests_total") or 0) for row in rows)
        run_name = first.get("run_name") or "default"
        structural_csv = behavior_csv.with_name("structural_assessment.csv")
        structural_rows = []
        if structural_csv.is_file():
            with structural_csv.open(newline="", encoding="utf-8") as handle:
                structural_rows = list(csv.DictReader(handle))
        score_names = ("wl", "align_f1", "edge_jaccard", "node_label_jaccard", "control")
        score_means = {}
        for key in score_names:
            legacy_key = "op_jaccard" if key == "node_label_jaccard" else key
            values = [float(row.get(key) or row.get(legacy_key)) for row in structural_rows
                      if row.get(key) or row.get(legacy_key)]
            score_means[key] = sum(values) / len(values) if values else None
        artifact_report = (
            artifacts / behavior_csv.parent.relative_to(root)
            / "structural_assessment" / "index.html"
        )
        model_report = behavior_csv.parent.parent / "structural_report.html"
        report_links = [link(behavior_csv, "Behavior CSV")]
        if structural_csv.is_file():
            report_links.append(link(structural_csv, "Structural CSV"))
        if artifact_report.is_file():
            report_links.append(link(artifact_report, "Task reports"))
        if model_report.is_file():
            report_links.append(link(model_report, "Run report"))
        entries.append({
            "agent": first.get("agent", ""),
            "model": first.get("model", ""),
            "run_name": run_name,
            "dataset": first.get("dataset", behavior_csv.parent.name),
            "tasks": len(rows),
            "pass_rate": passed / total if total else None,
            "structural_means": score_means,
            "links": " · ".join(report_links),
        })

    esc = html.escape

    def filter_options(key: str, label: str) -> str:
        values = sorted({str(entry[key]) for entry in entries})
        options = "".join(
            f'<option value="{esc(value, quote=True)}">{esc(value)}</option>'
            for value in values
        )
        return (
            f'<label>{label} <select data-filter="{key}" aria-label="Filter by {label.lower()}">'
            f'<option value="">All</option>{options}</select></label>'
        )

    table_rows = "".join(
        f'<tr data-agent="{esc(entry["agent"], quote=True)}" '
        f'data-model="{esc(entry["model"], quote=True)}" '
        f'data-run_name="{esc(entry["run_name"], quote=True)}" '
        f'data-dataset="{esc(entry["dataset"], quote=True)}" '
        f'data-sort-agent="{esc(entry["agent"], quote=True)}" '
        f'data-sort-model="{esc(entry["model"], quote=True)}" '
        f'data-sort-run_name="{esc(entry["run_name"], quote=True)}" '
        f'data-sort-dataset="{esc(entry["dataset"], quote=True)}" '
        f'data-sort-tasks="{entry["tasks"]}" '
        f'data-sort-pass_rate="{entry["pass_rate"] if entry["pass_rate"] is not None else ""}" '
        + "".join(
            f'data-sort-{key}="{entry["structural_means"][key] if entry["structural_means"][key] is not None else ""}" '
            for key in ("wl", "align_f1", "edge_jaccard", "node_label_jaccard", "control")
        )
        + ">"
        f"<td>{esc(entry['agent'])}</td>"
        f"<td>{esc(entry['model'])}</td>"
        f"<td>{esc(entry['run_name'])}</td>"
        f"<td>{esc(entry['dataset'])}</td>"
        f"<td>{entry['tasks']}</td>"
        f"<td>{f'{entry['pass_rate']:.1%}' if entry['pass_rate'] is not None else 'n/a'}</td>"
        + "".join(f"<td>{entry['structural_means'][key]:.3f}</td>"
                 if entry["structural_means"][key] is not None else "<td>n/a</td>"
                 for key in ("wl", "align_f1", "edge_jaccard", "node_label_jaccard", "control"))
        + f"<td>{entry['links']}</td>"
        "</tr>"
        for entry in entries
    )
    if not table_rows:
        table_rows = '<tr><td colspan="12">No saved result CSVs found yet.</td></tr>'
    sortable_headers = (
        ("agent", "Agent"),
        ("model", "Model"),
        ("run_name", "Run"),
        ("dataset", "Dataset"),
        ("tasks", "Tasks"),
        ("pass_rate", "Behavior pass rate"),
        ("wl", "Mean WL"),
        ("align_f1", "Mean Alignment F1"),
        ("edge_jaccard", "Mean Edge Jaccard"),
        ("node_label_jaccard", "Mean Node-Label Jaccard"),
        ("control", "Mean Control"),
    )
    table_headers = "".join(
        f'<th scope="col" aria-sort="none"><button type="button" data-sort-by="{key}">'
        f'{label} <span aria-hidden="true"></span></button></th>'
        for key, label in sortable_headers
    )
    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Experiment results</title>
<style>
body {{ font: 15px/1.5 system-ui, sans-serif; margin: 2rem auto; max-width: 1200px; padding: 0 1rem; color: #172033; }}
h1 {{ margin-bottom: .25rem; }}
p {{ color: #536078; }}
.controls {{ display: flex; flex-wrap: wrap; align-items: end; gap: .75rem 1rem; margin: 1.25rem 0; }}
.controls label {{ display: grid; gap: .25rem; font-size: .9rem; }}
.controls input, .controls select {{ min-height: 2.25rem; padding: .3rem .5rem; border: 1px solid #aeb9ca; border-radius: 4px; font: inherit; }}
#result-count {{ margin-left: auto; }}
.table-wrap {{ overflow-x: auto; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border-bottom: 1px solid #d8deea; padding: .65rem .75rem; text-align: left; white-space: nowrap; }}
th {{ background: #f3f6fb; }}
th button {{ border: 0; background: none; color: inherit; font: inherit; font-weight: 650; padding: 0; cursor: pointer; white-space: nowrap; }}
th button:hover {{ color: #1459a6; }}
th button:focus-visible, .controls input:focus-visible, .controls select:focus-visible {{ outline: 2px solid #1459a6; outline-offset: 2px; }}
tr:hover {{ background: #f8faff; }}
a {{ color: #1459a6; }}
</style>
</head>
<body>
<h1>Experiment results</h1>
<p>Filter by agent, model, run, or dataset; click a column heading to sort. Select a report link to inspect saved outputs.</p>
<div class="controls" aria-label="Result filters">
<label>Search <input id="result-search" type="search" placeholder="Search results" aria-label="Search results"></label>
{filter_options("agent", "Agent")}
{filter_options("model", "Model")}
{filter_options("run_name", "Run")}
{filter_options("dataset", "Dataset")}
<span id="result-count" role="status" aria-live="polite"></span>
</div>
<div class="table-wrap">
<table>
<thead><tr>{table_headers}<th scope="col">Reports</th></tr></thead>
<tbody>{table_rows}</tbody>
</table>
</div>
<script>
(() => {{
  const body = document.querySelector("tbody");
  const rows = [...body.querySelectorAll("tr[data-agent]")];
  const filters = [...document.querySelectorAll("[data-filter]")];
  const search = document.getElementById("result-search");
  const count = document.getElementById("result-count");
  let sortKey = "";
  let sortDirection = 1;

  function update() {{
    const query = search.value.trim().toLocaleLowerCase();
    for (const row of rows) {{
      const matchesFilters = filters.every(
        (filter) => !filter.value || row.dataset[filter.dataset.filter] === filter.value
      );
      row.hidden = !matchesFilters || !row.textContent.toLocaleLowerCase().includes(query);
    }}
    const visible = rows.filter((row) => !row.hidden);
    if (sortKey) {{
      visible.sort((a, b) => {{
        const left = a.dataset["sort" + sortKey[0].toUpperCase() + sortKey.slice(1)];
        const right = b.dataset["sort" + sortKey[0].toUpperCase() + sortKey.slice(1)];
        const leftNumber = left === "" ? NaN : Number(left);
        const rightNumber = right === "" ? NaN : Number(right);
        const comparison = Number.isNaN(leftNumber) || Number.isNaN(rightNumber)
          ? left.localeCompare(right, undefined, {{ numeric: true, sensitivity: "base" }})
          : leftNumber - rightNumber;
        return comparison * sortDirection;
      }});
      visible.forEach((row) => body.appendChild(row));
    }}
    count.textContent = `${{visible.length}} of ${{rows.length}} result set(s)`;
  }}

  filters.forEach((filter) => filter.addEventListener("change", update));
  search.addEventListener("input", update);
  document.querySelectorAll("[data-sort-by]").forEach((button) => {{
    button.addEventListener("click", () => {{
      const key = button.dataset.sortBy;
      sortDirection = sortKey === key ? -sortDirection : 1;
      sortKey = key;
      document.querySelectorAll("[data-sort-by]").forEach((other) => {{
        const active = other === button;
        other.parentElement.setAttribute(
          "aria-sort",
          active ? (sortDirection === 1 ? "ascending" : "descending") : "none"
        );
        other.querySelector("span").textContent = active
          ? (sortDirection === 1 ? " ▲" : " ▼")
          : "";
      }});
      update();
    }});
  }});
  update();
}})();
</script>
</body>
</html>
"""
    index_path = root / "index.html"
    index_path.write_text(page, encoding="utf-8")
    return index_path


def run_all(datasets: tuple[str, ...] = ("humaneval", "mbpp"),
            limit: int | None = None, skip_done: bool = True,
            include_mock: bool = False, verbose: bool = True,
            batch_size: int | None = None, run_name: str = "") -> dict:
    """Run every configured model preset, across the selected datasets."""
    outputs = {}
    for agent, preset in AGENT_PRESETS.items():
        if agent == "mock" and not include_mock:
            continue
        for model_key in preset.models:
            outputs[f"{agent}/{model_key}"] = run(
                agent,
                model_key=model_key,
                datasets=datasets,
                limit=limit,
                batch_size=batch_size,
                run_name=run_name,
                skip_done=skip_done,
                verbose=verbose,
            )
    return outputs


def prepare_dataset(datasets: tuple[str, ...] = ("humaneval", "mbpp")) -> dict:
    """Download/load benchmark rows and save their original code under data/."""
    prepared = {}
    for dataset_name in datasets:
        if dataset_name not in {"humaneval", "mbpp"}:
            raise ValueError(f"Unsupported dataset {dataset_name!r}.")
        cfg = PipelineConfig(dataset=DatasetConfig(name=dataset_name))
        print(f"Loading {dataset_name} benchmark; this may download it once...", flush=True)
        tasks = DatasetLoader(cfg).load()
        folder = cfg.data_root / "original_code" / dataset_name
        base_cases = sum(
            test.name.startswith("base-")
            for task in tasks for test in task.test_cases
        )
        plus_cases = sum(
            test.name.startswith("plus-")
            for task in tasks for test in task.test_cases
        )
        prepared[dataset_name] = {
            "tasks": len(tasks),
            "base_test_cases": base_cases,
            "plus_test_cases": plus_cases,
            "original_code_folder": str(folder),
            "sample_files": [
                str(save_original_code(cfg, task.task_id, task.original_code))
                for task in tasks[:5]
            ],
        }
        print(
            f"Saved {len(tasks)} original-code files and loaded "
            f"{base_cases + plus_cases} EvalPlus input cases "
            f"({base_cases} base, {plus_cases} Plus) to {folder}",
            flush=True,
        )
    return prepared


def describe() -> dict:
    """Show the benchmark sources, output roots, and configured model choices."""
    info = {
        "project_root": str(Path(__file__).resolve().parent),
        "data_root": str(DATA_ROOT),
        "artifact_root": str(ARTIFACT_ROOT),
        "result_root": str(RESULT_ROOT),
        "datasets": {
            "humaneval": "evalplus/humanevalplus",
            "mbpp": "evalplus/mbppplus",
        },
        "agents": {name: preset.models for name, preset in AGENT_PRESETS.items()},
    }
    print(json.dumps(info, indent=2))
    return info


def summary_table(result_root: Path | None = None, save: bool = True) -> list[dict]:
    """Aggregate pass counts/rates by configured agent, model, and dataset."""
    root = Path(result_root or RESULT_ROOT)
    grouped: dict[tuple[str, str, str, str], dict] = {}
    for csv_path in sorted(root.rglob("behavior_assessment.csv")):
        with csv_path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        if not rows:
            continue
        key = (
            rows[0]["agent"],
            rows[0]["model"],
            rows[0].get("run_name", ""),
            rows[0]["dataset"],
        )
        total = sum(int(row.get("tests_total") or 0) for row in rows)
        passed = sum(int(row.get("tests_passed") or 0) for row in rows)
        grouped[key] = {
            "agent": key[0],
            "model": key[1],
            "run_name": key[2],
            "dataset": key[3],
            "tasks": len(rows),
            "tests_passed": passed,
            "tests_total": total,
            "test_pass_rate_pct": round(passed / total * 100, 2) if total else None,
        }
    result = list(grouped.values())
    if save and result:
        destination = root / "comparison.csv"
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(result[0]))
            writer.writeheader()
            writer.writerows(result)
        print(f"Comparison saved to {destination}")
    return result
