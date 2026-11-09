"""Command line:  python -m structural_graph_utils run ...   |   python -m structural_graph_utils agree ..."""
import argparse
import csv
import statistics

from .pipeline import run


def _ranks(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return r


def spearman(a, b):
    ra, rb = _ranks(a), _ranks(b)
    ma, mb = statistics.mean(ra), statistics.mean(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    den = (sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb)) ** 0.5
    return num / den if den else float("nan")


def cmd_agree(args):
    xs, ys = [], {key: [] for key in
                  ("wl", "align_f1", "edge_jaccard", "node_label_jaccard", "control")}
    with open(args.csv, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            h = (r.get("human_score_0to5") or "").strip()
            if h:
                xs.append(float(h))
                for key in ys:
                    ys[key].append(float(r[key]))
    if len(xs) < 3:
        raise SystemExit("need at least 3 rows with human_score_0to5 filled in")
    print(f"rated pairs: {len(xs)}")
    for key, values in ys.items():
        print(f"Spearman(human, {key}) = {spearman(xs, values):.3f}")
    for level in sorted(set(xs)):
        indexes = [i for i, score in enumerate(xs) if score == level]
        means = ", ".join(f"{key}={statistics.mean(values[i] for i in indexes):.3f}"
                           for key, values in ys.items())
        print(f"  human={level:g}: n={len(indexes):3d}  {means}")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="structural_graph_utils")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="build graphs, compare, save everything")
    r.add_argument("--input", required=True, help="JSONL: task_id, original_code, generated_code [, entry_point, inputs]")
    r.add_argument("--out", required=True, help="output directory")
    r.add_argument("--workers", type=int, default=4)
    r.add_argument("--behavior", action="store_true", help="also run both programs on `inputs` (subprocess)")
    r.add_argument("--no-render", action="store_true", help="skip Graphviz SVGs (faster)")
    r.add_argument("--sample", type=int, default=50, help="size of the manual-review sample (0 = none)")
    r.add_argument("--seed", type=int, default=0)
    r.add_argument("--per-call", type=float, default=2.0, help="seconds allowed per behaviour call")
    r.add_argument("--limit", type=int, default=None, help="only the first N records")

    a = sub.add_parser("agree", help="correlate your manual ratings with each structural score")
    a.add_argument("csv", help="review_sample.csv with human_score_0to5 filled in")

    args = ap.parse_args(argv)
    if args.cmd == "run":
        rows = run(args.input, args.out, workers=args.workers, behavior=args.behavior,
                   render_graphs=not args.no_render, sample=args.sample, seed=args.seed,
                   per_call=args.per_call, limit=args.limit)
        ok = [x for x in rows if x["status"] == "ok"]
        bad = [x for x in rows if x["status"] != "ok"]
        print(f"\n{len(rows)} tasks: {len(ok)} compared, {len(bad)} with parse errors")
        if ok:
            for key in ("wl", "align_f1", "edge_jaccard", "node_label_jaccard", "control"):
                print(f"mean {key} {statistics.mean(x[key] for x in ok):.3f}")
        print(f"flagged: {sum(1 for x in rows if x['flags'])}")
        print(f"open {args.out}/index.html")
    else:
        cmd_agree(args)


if __name__ == "__main__":
    main()
