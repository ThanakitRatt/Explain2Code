"""Behavioural equivalence: run original and generated code on the same inputs.

Used as an independent sanity signal next to the graph score.  Inputs come from the JSONL
record (``inputs``: list of argument lists; tuples/sets/NaN may be written with the tagged
form produced by ``_runner.enc``).
"""
import json
import math
import os
import subprocess
import sys

from ._runner import MARK

RUNNER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_runner.py")


def run_code(code, entry, inputs, per_call=2.0):
    """Returns a list with one {ok, v|err} dict per input."""
    if not inputs:
        return []
    job = json.dumps({"code": code, "entry": entry, "inputs": inputs, "per_call": per_call})
    total = min(300.0, per_call * (len(inputs) + 2) + 10)
    try:
        p = subprocess.run([sys.executable, "-I", RUNNER], input=job, capture_output=True,
                           text=True, timeout=total)
    except subprocess.TimeoutExpired:
        return [{"ok": False, "err": "RunnerTimeout"} for _ in inputs]
    for line in reversed(p.stdout.splitlines()):
        if line.startswith(MARK):
            try:
                return json.loads(line[len(MARK):])
            except json.JSONDecodeError:
                break
    return [{"ok": False, "err": "RunnerCrash"} for _ in inputs]


def _key(x):
    return json.dumps(x, sort_keys=True)


def enc_equal(a, b, rel=1e-6, abs_=1e-9):
    """Structural equality on encoded values; floats compared with tolerance, sets/dicts unordered."""
    if isinstance(a, bool) or isinstance(b, bool):
        return type(a) is type(b) and a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return math.isclose(a, b, rel_tol=rel, abs_tol=abs_)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(enc_equal(x, y) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        if a.get("__t") != b.get("__t"):
            return False
        t = a.get("__t")
        if t == "dict":
            da = {_key(k): v for k, v in a["v"]}
            db = {_key(k): v for k, v in b["v"]}
            return da.keys() == db.keys() and all(enc_equal(da[k], db[k]) for k in da)
        if t in ("tuple", "set"):
            return enc_equal(a["v"], b["v"])
        return a == b
    return a == b


def compare_behavior(orig, gen, inputs):
    """Row-wise comparison of two run_code results."""
    rows, match = [], 0
    for args, o, g in zip(inputs, orig, gen):
        if o["ok"] and g["ok"]:
            eq = enc_equal(o["v"], g["v"])
        elif not o["ok"] and not g["ok"]:
            eq = o["err"] == g["err"]
        else:
            eq = False
        match += eq
        rows.append({"input": args, "orig": o, "gen": g, "equal": eq})
    n = len(rows)
    return {"n": n, "match": match, "fraction": (match / n) if n else None, "rows": rows}
