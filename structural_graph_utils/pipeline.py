"""End-to-end run: JSONL of pairs -> graphs, scores, behaviour check, saved artifacts, HTML report."""
import csv
import json
import os
import random
import re
import time
from multiprocessing import Pool

from . import render
from .behavior import compare_behavior, run_code
from .builder import build_graph, graph_to_dict, resolve_entry
from .compare import SCAFFOLD_KINDS, compare_graphs

import ast

SUMMARY_FIELDS = ["task_id", "status", "wl", "align_f1", "edge_jaccard",
                  "node_label_jaccard", "control", "nodes_orig", "nodes_gen", "edges_orig", "edges_gen",
                  "behavior_match", "behavior_n", "flags", "dir", "error"]


def safe_id(task_id):
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(task_id))


def _entry(code, hint):
    try:
        return resolve_entry(ast.parse(code), hint)
    except SyntaxError:
        return None


def _write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _unmatched(G, mapped, other_side_kind=None):
    out = []
    for n, d in sorted(G.nodes(data=True)):
        if d["kind"] in SCAFFOLD_KINDS or n in mapped:
            continue
        line = f"L{d['line']} " if d.get("line") is not None else ""
        out.append(f"{line}{d['label']}  —  {d.get('src') or ''}")
    return out


def process_task(job):
    rec, out_dir, opts = job
    tid = str(rec["task_id"])
    sid = safe_id(tid)
    tdir = os.path.join(out_dir, "tasks", sid)
    os.makedirs(tdir, exist_ok=True)
    row = {k: None for k in SUMMARY_FIELDS}
    row.update(task_id=tid, dir=f"tasks/{sid}", status="ok", flags="")
    orig, gen = rec["original_code"], rec["generated_code"]
    entry_hint = rec.get("entry_point")
    _write(os.path.join(tdir, "original.py"), orig)
    _write(os.path.join(tdir, "generated.py"), gen)

    graphs, errors = {}, []
    for name, code in (("original", orig), ("generated", gen)):
        try:
            G = build_graph(code, entry_hint)
            graphs[name] = G
            _write(os.path.join(tdir, f"{name}.graph.json"), json.dumps(graph_to_dict(G), indent=1))
        except SyntaxError as e:
            errors.append(f"{name} code does not parse: {e.msg} (line {e.lineno})")
    if errors:
        row.update(status="parse_error", error="; ".join(errors))
        _write(os.path.join(tdir, "index.html"), render.task_page(row, orig, gen, None, None, None, None))
        return row

    Go, Gg = graphs["original"], graphs["generated"]
    cmp_ = compare_graphs(Go, Gg)
    m = cmp_["metrics"]
    mapping, sims = cmp_["mapping"], cmp_["sims"]
    cmp_["unmatched_orig"] = _unmatched(Go, set(mapping))
    cmp_["unmatched_gen"] = _unmatched(Gg, set(mapping.values()))
    for k in ("wl", "align_f1", "edge_jaccard", "node_label_jaccard", "control",
              "nodes_orig", "nodes_gen", "edges_orig", "edges_gen"):
        row[k] = round(m[k], 4) if isinstance(m[k], float) else m[k]

    # ---- behaviour (optional)
    behavior = None
    if opts["behavior"] and rec.get("inputs"):
        eo, eg = _entry(orig, entry_hint), _entry(gen, entry_hint)
        if eo and eg:
            ro = run_code(orig, eo, rec["inputs"], opts["per_call"])
            rg = run_code(gen, eg, rec["inputs"], opts["per_call"])
            behavior = compare_behavior(ro, rg, rec["inputs"])
            row["behavior_match"] = round(behavior["fraction"], 4)
            row["behavior_n"] = behavior["n"]
            _write(os.path.join(tdir, "behavior.json"), json.dumps(behavior, indent=1))

    # ---- flags identify structural extraction limitations, not score thresholds
    flags = []
    if not (Go.graph.get("entry_found", True) and Gg.graph.get("entry_found", True)):
        flags.append("ENTRY_NOT_FOUND")
    if Go.graph.get("unsupported") or Gg.graph.get("unsupported"):
        flags.append("UNSUPPORTED_SYNTAX")
    row["flags"] = ";".join(flags)

    # ---- artifacts
    _write(os.path.join(tdir, "comparison.json"), json.dumps({
        "metrics": m,
        "alignment": [{"orig": a, "gen": b, "sim": sims[a],
                       "orig_label": Go.nodes[a]["label"], "orig_line": Go.nodes[a]["line"],
                       "gen_label": Gg.nodes[b]["label"], "gen_line": Gg.nodes[b]["line"]}
                      for a, b in sorted(mapping.items())],
        "unmatched_orig": cmp_["unmatched_orig"],
        "unmatched_gen": cmp_["unmatched_gen"],
        "edges_not_preserved_orig": [list(e) for e in cmp_["bad_edges_orig"]],
        "edges_not_preserved_gen": [list(e) for e in cmp_["bad_edges_gen"]],
    }, indent=1))

    svg_o = svg_g = None
    if opts["render"]:
        inv = {b: a for a, b in mapping.items()}
        dot_o = render.to_dot(Go, mapping, sims, cmp_["bad_edges_orig"], side="orig")
        dot_g = render.to_dot(Gg, mapping, sims, cmp_["bad_edges_gen"], side="gen")
        _write(os.path.join(tdir, "original.dot"), dot_o)
        _write(os.path.join(tdir, "generated.dot"), dot_g)
        svg_o, svg_g = render.dot_to_svg(dot_o), render.dot_to_svg(dot_g)
        if svg_o:
            _write(os.path.join(tdir, "original.svg"), svg_o)
        if svg_g:
            _write(os.path.join(tdir, "generated.svg"), svg_g)
    _write(os.path.join(tdir, "index.html"), render.task_page(row, orig, gen, svg_o, svg_g, cmp_, behavior))
    return row


def load_pairs(path):
    recs = []
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            for k in ("task_id", "original_code", "generated_code"):
                if k not in r:
                    raise SystemExit(f"{path}:{i}: missing required field {k!r}")
            recs.append(r)
    return recs


def pick_review_sample(rows, n, seed):
    ok = [r for r in rows if r["status"] == "ok"]
    rng = random.Random(seed)
    flagged = [r for r in ok if r["flags"]]
    rng.shuffle(flagged)
    chosen = flagged[: n // 2]
    remaining = [r for r in ok if r not in chosen]
    rng.shuffle(remaining)
    return chosen + remaining[:max(0, min(n, len(ok)) - len(chosen))]


def run(input_path, out_dir, workers=4, behavior=False, render_graphs=True, sample=50, seed=0,
        per_call=2.0, limit=None, log=print):
    recs = load_pairs(input_path)
    if limit:
        recs = recs[:limit]
    os.makedirs(out_dir, exist_ok=True)
    opts = dict(behavior=behavior, render=render_graphs, per_call=per_call)
    jobs = [(r, out_dir, opts) for r in recs]
    t0 = time.time()
    rows = []
    if workers <= 1:
        it = map(process_task, jobs)
        pool = None
    else:
        pool = Pool(workers)
        it = pool.imap_unordered(process_task, jobs, chunksize=2)
    for i, row in enumerate(it, 1):
        rows.append(row)
        if i % 25 == 0 or i == len(jobs):
            log(f"  {i}/{len(jobs)} done ({time.time() - t0:.0f}s)")
    if pool:
        pool.close()
        pool.join()
    order = {str(r["task_id"]): i for i, r in enumerate(recs)}
    rows.sort(key=lambda r: order[r["task_id"]])

    with open(os.path.join(out_dir, "summary.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=SUMMARY_FIELDS)
        w.writeheader()
        w.writerows(rows)
    _write(os.path.join(out_dir, "index.html"), render.index_page(rows))
    _write(os.path.join(out_dir, "run_config.json"), json.dumps(
        dict(input=os.path.abspath(input_path), **opts, sample=sample, seed=seed), indent=1))

    chosen = pick_review_sample(rows, sample, seed) if sample else []
    if chosen:
        with open(os.path.join(out_dir, "review_sample.csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["task_id", "wl", "align_f1", "edge_jaccard", "node_label_jaccard", "control",
                        "flags", "page", "human_score_0to5", "notes"])
            for r in chosen:
                w.writerow([r["task_id"], *(r[k] for k in
                            ("wl", "align_f1", "edge_jaccard", "node_label_jaccard", "control")),
                            r["flags"], f"{r['dir']}/index.html", "", ""])
    return rows
