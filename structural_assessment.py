"""Structural comparison and validation reports for reconstructed programs."""
from __future__ import annotations

import csv
import html
import json
import os
import re
import statistics
from pathlib import Path
from typing import Iterable

from config import PipelineConfig
from dataset_utils import Task
from path_utils import (
    artifact_path,
    model_output_root,
    result_csv_path,
    run_root,
    safe_name,
)
from structural_graph_utils import build_graph, compare_graphs, graph_to_dict
from structural_graph_utils import render


class StructuralAssessment:
    """Compare original/reconstructed AST graphs and publish browsable reports."""

    def __init__(self, cfg: PipelineConfig):
        self.cfg = cfg

    def run_task(self, task: Task, generated_code: str) -> dict:
        result: dict = {"task_id": task.task_id, "status": "ok", "flags": []}
        folder = artifact_path(self.cfg, "structural_assessment", task.task_id, "original.py").parent
        original_path, generated_path = folder / "original.py", folder / "generated.py"
        original_path.write_text(task.original_code, "utf-8")
        generated_path.write_text(generated_code, "utf-8")
        try:
            original = build_graph(task.original_code, task.entry_point)
            generated = build_graph(generated_code, task.entry_point)
            comparison = compare_graphs(original, generated)
        except (SyntaxError, ValueError, TypeError) as exc:
            result.update(status="parse_error", error=f"{type(exc).__name__}: {exc}")
            (folder / "comparison.json").write_text(json.dumps(result, indent=2), "utf-8")
            explanation = self._explanation(task.task_id)
            elapsed_seconds = self._elapsed_time(task.task_id)
            result["elapsed_time_sec"] = elapsed_seconds
            (folder / "index.html").write_text(
                self._task_page(task.task_id, task.original_code, generated_code, result, None, None, [], [],
                               self._behavior(task.task_id), explanation, elapsed_seconds), "utf-8")
            return result

        metrics = comparison["metrics"]
        mapping, sims = comparison["mapping"], comparison["sims"]
        unmatched_original = self._unmatched(original, set(mapping))
        unmatched_generated = self._unmatched(generated, set(mapping.values()))
        comparison_data = {
            "task_id": task.task_id, "status": "ok", "metrics": metrics,
            "alignment": [
                {"original_node": a, "generated_node": b, "similarity": sims[a],
                 "original_label": original.nodes[a]["label"], "original_line": original.nodes[a].get("line"),
                 "generated_label": generated.nodes[b]["label"], "generated_line": generated.nodes[b].get("line")}
                for a, b in sorted(mapping.items())
            ],
            "unmatched_original": unmatched_original, "unmatched_generated": unmatched_generated,
            "edges_not_preserved_original": [list(e) for e in comparison["bad_edges_orig"]],
            "edges_not_preserved_generated": [list(e) for e in comparison["bad_edges_gen"]],
        }
        result.update(metrics={k: round(v, 6) if isinstance(v, float) else v for k, v in metrics.items()})
        result["flags"] = self._flags(original, generated)
        comparison_data["flags"] = result["flags"]
        (folder / "original.graph.json").write_text(json.dumps(graph_to_dict(original), indent=2), "utf-8")
        (folder / "generated.graph.json").write_text(json.dumps(graph_to_dict(generated), indent=2), "utf-8")
        (folder / "comparison.json").write_text(json.dumps(comparison_data, indent=2), "utf-8")
        dot_o = render.to_dot(original, mapping, sims, comparison["bad_edges_orig"], side="orig")
        dot_g = render.to_dot(generated, mapping, sims, comparison["bad_edges_gen"], side="gen")
        (folder / "original.dot").write_text(dot_o, "utf-8")
        (folder / "generated.dot").write_text(dot_g, "utf-8")
        svg_o, svg_g = render.dot_to_svg(dot_o), render.dot_to_svg(dot_g)
        if svg_o:
            (folder / "original.svg").write_text(svg_o, "utf-8")
        if svg_g:
            (folder / "generated.svg").write_text(svg_g, "utf-8")
        behavior = self._behavior(task.task_id)
        elapsed_seconds = self._elapsed_time(task.task_id)
        result["elapsed_time_sec"] = elapsed_seconds
        if behavior:
            result["behavior_label"] = f"{behavior.get('tests_passed', 0)}/{behavior.get('tests_total', 0)}"
        page = self._task_page(task.task_id, task.original_code, generated_code, result, svg_o, svg_g,
                               unmatched_original, unmatched_generated, behavior,
                               self._explanation(task.task_id), elapsed_seconds)
        (folder / "index.html").write_text(page, "utf-8")
        result["artifact_dir"] = str(folder)
        return result

    def build_report(self, tasks: Iterable[Task]) -> Path:
        """Rebuild all structural task artifacts and a model-specific HTML report."""
        rows = []
        for task in tasks:
            code_path = artifact_path(self.cfg, "reconstructed_code", task.task_id, "reconstructed.py")
            if not code_path.is_file():
                continue
            rows.append(self.run_task(task, code_path.read_text("utf-8")))
        root = run_root(self.cfg) / "structural_assessment"
        root.mkdir(parents=True, exist_ok=True)
        fields = ["task_id", "status", "wl", "align_f1", "edge_jaccard", "node_label_jaccard", "control",
                  "nodes_orig", "nodes_gen", "edges_orig", "edges_gen",
                  "elapsed_time_sec", "flags", "error"]
        csv_path = root / "summary.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for row in rows:
                writer.writerow({**{k: "" for k in fields}, **{k: row.get(k) for k in fields if k in row},
                                 **{k: row.get("metrics", {}).get(k) for k in fields if k in row.get("metrics", {})},
                                 "flags": ";".join(row.get("flags", []))})
        (root / "index.html").write_text(self._index_page(rows), "utf-8")
        dataset_results = model_output_root(self.cfg.result_root, self.cfg) / safe_name(
            self.cfg.dataset.name
        )
        dataset_results.mkdir(parents=True, exist_ok=True)
        (dataset_results / "structural_assessment.csv").write_text(csv_path.read_text("utf-8"), "utf-8")
        # Each dataset has its own task report while this page is the model-level entry point.
        model_root = model_output_root(self.cfg.result_root, self.cfg)
        model_root.mkdir(parents=True, exist_ok=True)
        model_page = model_root / "structural_report.html"
        model_page.write_text(self._model_page(root, rows), "utf-8")
        return model_page

    @staticmethod
    def _unmatched(graph, mapped: set[int]) -> list[str]:
        return [(f"L{d['line']} " if d.get("line") is not None else "") + d["label"]
                for n, d in sorted(graph.nodes(data=True)) if d["kind"] != "func" and n not in mapped]

    @staticmethod
    def _flags(original, generated) -> list[str]:
        flags = []
        if not (original.graph.get("entry_found", True) and generated.graph.get("entry_found", True)):
            flags.append("ENTRY_NOT_FOUND")
        if original.graph.get("unsupported") or generated.graph.get("unsupported"):
            flags.append("UNSUPPORTED_SYNTAX")
        return flags

    def _behavior(self, task_id: str):
        behavior_path = artifact_path(self.cfg, "test_results", task_id, "behavior_assessment.json")
        return json.loads(behavior_path.read_text("utf-8")) if behavior_path.is_file() else None

    def _explanation(self, task_id: str) -> str:
        explanation_path = artifact_path(self.cfg, "explanation", task_id, "explanation.txt")
        return explanation_path.read_text("utf-8") if explanation_path.is_file() else ""

    def _elapsed_time(self, task_id: str) -> float | None:
        results_path = result_csv_path(self.cfg)
        if not results_path.is_file():
            return None
        with results_path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                if row.get("task_id") == task_id and row.get("reconstruction_time_sec"):
                    return float(row["reconstruction_time_sec"])
        return None

    @staticmethod
    def _format_explanation(text: str) -> str:
        """Render a small safe Markdown subset for model-generated explanations."""
        def inline(value: str) -> str:
            escaped = html.escape(value)
            escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
            escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
            return re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", escaped)

        blocks = []
        paragraph = []
        list_items = []
        list_tag = None

        def flush_paragraph() -> None:
            if paragraph:
                blocks.append("<p>" + " ".join(inline(line) for line in paragraph) + "</p>")
                paragraph.clear()

        def flush_list() -> None:
            nonlocal list_tag
            if list_items:
                blocks.append(
                    f"<{list_tag}>"
                    + "".join(f"<li>{inline(item)}</li>" for item in list_items)
                    + f"</{list_tag}>"
                )
                list_items.clear()
                list_tag = None

        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                flush_paragraph()
                flush_list()
                continue
            heading = re.match(r"^(#{1,3})\s+(.+)$", stripped)
            bullet = re.match(r"^[-*]\s+(.+)$", stripped)
            numbered = re.match(r"^\d+[.)]\s+(.+)$", stripped)
            if heading:
                flush_paragraph()
                flush_list()
                level = len(heading.group(1)) + 1
                blocks.append(f"<h{level}>{inline(heading.group(2))}</h{level}>")
            elif bullet or numbered:
                flush_paragraph()
                new_list_tag = "ul" if bullet else "ol"
                if list_tag and list_tag != new_list_tag:
                    flush_list()
                list_tag = new_list_tag
                list_items.append((bullet or numbered).group(1))
            else:
                flush_list()
                paragraph.append(stripped)
        flush_paragraph()
        flush_list()
        return "".join(blocks)

    @staticmethod
    def _task_page(task_id, orig, gen, result, svg_o, svg_g, unmatched_o, unmatched_g,
                   behavior, explanation, elapsed_seconds):
        esc = html.escape
        metrics = result.get("metrics", {})
        sections = ["<!doctype html><meta charset='utf-8'><meta name='viewport' content='width=device-width'>",
                    f"<title>{esc(task_id)}</title><style>{render.CSS}</style>",
                    f"<p><a href='../index.html'>&larr; all tasks</a></p><h1>{esc(task_id)}</h1>"]
        if elapsed_seconds is None:
            elapsed_label = "Not recorded"
        else:
            elapsed_label = f"{elapsed_seconds:.3f} seconds"
        sections.append(
            "<p><strong>Task elapsed time:</strong> " + esc(elapsed_label)
            + " <small>(explanation, reconstruction, and behavioral assessment)</small></p>"
        )
        if explanation:
            sections.append(
                "<h2>Model explanation</h2><section class='explanation'>"
                + StructuralAssessment._format_explanation(explanation)
                + "</section>"
            )
        if metrics:
            keys = ["wl", "align_f1", "edge_jaccard", "node_label_jaccard", "control"]
            sections.append("<table><tr>" + "".join(f"<th>{k}</th>" for k in keys) + "</tr><tr>" +
                            "".join(f"<td>{metrics.get(k, 0):.3f}</td>" for k in keys) + "</tr></table>")
            sections.append("<h2>Code</h2><div class='grid'><section class='panel'><h3>Original</h3>" + render._code(orig) +
                            "</section><section class='panel'><h3>Reconstructed</h3>" + render._code(gen) + "</section></div>")
            sections.append("<h2>Structural graphs</h2>" + render.legend() + "<div class='grid'>" +
                            f"<section class='panel'><h3>Original</h3><div class='svgbox'>{render._inline_svg(svg_o)}</div></section>" +
                            f"<section class='panel'><h3>Reconstructed</h3><div class='svgbox'>{render._inline_svg(svg_g)}</div></section></div>")
            sections.append("<h2>Unmatched nodes</h2><div class='grid'><section class='panel'><h3>Original only</h3>" +
                            render._ul(unmatched_o) + "</section><section class='panel'><h3>Reconstructed only</h3>" +
                            render._ul(unmatched_g) + "</section></div>")
        else:
            sections.append(f"<p class='warn'>Structural comparison failed: {esc(result.get('error', 'unknown error'))}</p>")
            sections.append("<h2>Original code</h2>" + render._code(orig) + "<h2>Reconstructed code</h2>" + render._code(gen))
        if behavior:
            sections.append(f"<h2>Behavior assessment</h2><p>{behavior.get('tests_passed', 0)}/{behavior.get('tests_total', 0)} tests passed</p><table><tr><th>Test</th><th>Result</th><th>Detail</th></tr>")
            for test in behavior.get("test_results", []):
                sections.append(f"<tr><td>{esc(test.get('test', ''))}</td><td>{'PASS' if test.get('passed') else 'FAIL'}</td><td><pre>{esc(test.get('detail', ''))}</pre></td></tr>")
            sections.append("</table>")
        return "".join(sections)

    @staticmethod
    def _index_page(rows):
        esc = html.escape
        valid = [r["metrics"] for r in rows if r.get("metrics")]
        means = {key: statistics.mean(m[key] for m in valid) for key in
                 ("wl", "align_f1", "edge_jaccard", "node_label_jaccard", "control")} if valid else {}
        parts = ["<!doctype html><meta charset='utf-8'><meta name='viewport' content='width=device-width'>",
                 f"<title>Assessment</title><style>{render.CSS}</style><script>{render.SORT_JS}</script>",
                 f"<h1>Assessment: {esc(rows[0]['task_id'].split('/')[0] if rows else '')}</h1>"]
        parts.append(f"<p>{len(rows)} task(s); mean scores: " + ", ".join(
            f"{key} {value:.3f}" for key, value in means.items()) + "</p>" if means else f"<p>{len(rows)} task(s)</p>")
        parts.append("<input type='search' placeholder='filter tasks' oninput='filterRows(this.value)'><table id='t'><thead><tr><th>Task</th><th>Time (s)</th><th>WL</th><th>Alignment F1</th><th>Edge Jaccard</th><th>Node-Label Jaccard</th><th>Control</th><th>Behavior</th><th>Flags</th><th>Status</th></tr></thead><tbody>")
        for r in rows:
            m = r.get("metrics", {})
            vals = [m.get(k) for k in ("wl", "align_f1", "edge_jaccard", "node_label_jaccard", "control")]
            link = f"<a href='{safe_name(r['task_id'])}/index.html'>{esc(r['task_id'])}</a>"
            elapsed = r.get("elapsed_time_sec")
            elapsed_cell = f"<td>{elapsed:.3f}</td>" if isinstance(elapsed, (int, float)) else "<td></td>"
            parts.append("<tr><td>" + link + "</td>" + elapsed_cell + "".join(f"<td>{v:.3f}</td>" if isinstance(v, (int,float)) else "<td></td>" for v in vals) +
                         f"<td>{r.get('behavior_label', '')}</td><td>{esc(', '.join(r.get('flags', [])))}</td><td>{esc(r['status'])}</td></tr>")
        parts.append("</tbody></table>")
        return "".join(parts)

    def _model_page(self, dataset_root: Path, rows: list[dict]) -> str:
        model_artifacts = model_output_root(self.cfg.artifact_root, self.cfg)
        model_results = model_output_root(self.cfg.result_root, self.cfg)
        links = []
        for report in sorted(model_artifacts.glob("*/structural_assessment/index.html")):
            href = os.path.relpath(report, start=model_results)
            label = report.parents[1].name
            links.append(f"<li><a href='{html.escape(href)}'>{html.escape(label)}</a></li>")
        return ("<!doctype html><meta charset='utf-8'><title>Assessment report</title>"
                f"<style>{render.CSS}</style><h1>{html.escape(self.cfg.llm.agent)} / {html.escape(self.cfg.llm.model)}</h1>"
                f"<p>{len(rows)} tasks processed for {html.escape(self.cfg.dataset.name)}.</p>"
                "<h2>Dataset reports</h2><ul>" + "".join(links) + "</ul>")
