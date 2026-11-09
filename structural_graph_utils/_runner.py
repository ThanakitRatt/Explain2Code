"""Subprocess runner: executes one program on a list of inputs and prints encoded outputs.

Executed as ``python -I _runner.py`` with a JSON job on stdin, so untrusted code never runs in
the parent process.  Self-contained on purpose (no package imports under ``-I``).
NOTE: this is a light safety net (timeouts, memory cap, a few disabled functions), not a real
sandbox. Run the whole pipeline inside a container if the code is not trusted.
"""
import copy
import json
import math
import os
import signal
import sys

MARK = "__STRUCTURAL_GRAPH_UTILS_RESULT__"


def enc(x):
    if x is None or isinstance(x, (bool, int, str)):
        return x
    if isinstance(x, float):
        if x != x:
            return {"__t": "nan"}
        if x in (math.inf, -math.inf):
            return {"__t": "inf" if x > 0 else "-inf"}
        return x
    if isinstance(x, list):
        return [enc(i) for i in x]
    if isinstance(x, tuple):
        return {"__t": "tuple", "v": [enc(i) for i in x]}
    if isinstance(x, (set, frozenset)):
        return {"__t": "set", "v": sorted((enc(i) for i in x), key=lambda i: json.dumps(i, sort_keys=True))}
    if isinstance(x, dict):
        return {"__t": "dict", "v": [[enc(k), enc(v)] for k, v in x.items()]}
    if isinstance(x, (bytes, bytearray)):
        return {"__t": "bytes", "v": bytes(x).hex()}
    return {"__t": "repr", "v": repr(x)[:200]}


def dec(x):
    if isinstance(x, list):
        return [dec(i) for i in x]
    if isinstance(x, dict):
        t = x.get("__t")
        if t == "tuple":
            return tuple(dec(i) for i in x["v"])
        if t == "set":
            items = [dec(i) for i in x["v"]]
            try:
                return set(items)
            except TypeError:
                return items
        if t == "dict":
            out = {}
            for k, v in x["v"]:
                k = dec(k)
                out[tuple(k) if isinstance(k, list) else k] = dec(v)
            return out
        if t == "nan":
            return math.nan
        if t == "inf":
            return math.inf
        if t == "-inf":
            return -math.inf
        if t == "bytes":
            return bytes.fromhex(x["v"])
        return {k: dec(v) for k, v in x.items()}
    return x


class _Timeout(BaseException):
    pass


def _alarm(signum, frame):
    raise _Timeout()


def main():
    job = json.loads(sys.stdin.read())
    real_stdout = sys.stdout
    sys.stdout = open(os.devnull, "w")
    sys.stderr = open(os.devnull, "w")
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (2 << 30, 2 << 30))
    except Exception:
        pass
    per_call = float(job.get("per_call", 2.0))
    results = []
    ns = {"__name__": "__sandbox__"}
    try:
        signal.signal(signal.SIGALRM, _alarm)
        signal.setitimer(signal.ITIMER_REAL, per_call * 2)
        exec(compile(job["code"], "<candidate>", "exec"), ns)
        signal.setitimer(signal.ITIMER_REAL, 0)
        fn = ns.get(job["entry"])
        if not callable(fn):
            raise NameError(f"entry point {job['entry']!r} not defined")
        # light guard against destructive calls
        import shutil, subprocess
        os.system = os.remove = os.rmdir = os.unlink = shutil.rmtree = subprocess.Popen = None
        for args in job["inputs"]:
            args = dec(args)
            try:
                signal.setitimer(signal.ITIMER_REAL, per_call)
                out = fn(*copy.deepcopy(args))
                signal.setitimer(signal.ITIMER_REAL, 0)
                results.append({"ok": True, "v": enc(out)})
            except _Timeout:
                results.append({"ok": False, "err": "Timeout"})
            except BaseException as e:      # noqa: BLE001 - candidate code may raise anything
                signal.setitimer(signal.ITIMER_REAL, 0)
                results.append({"ok": False, "err": type(e).__name__})
    except BaseException as e:               # noqa: BLE001
        signal.setitimer(signal.ITIMER_REAL, 0)
        err = f"LoadError:{type(e).__name__}"
        results = [{"ok": False, "err": err} for _ in job["inputs"]]
    real_stdout.write(MARK + json.dumps(results) + "\n")
    real_stdout.flush()


if __name__ == "__main__":
    main()
