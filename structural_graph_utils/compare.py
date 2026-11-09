"""Semantic comparison of two program graphs built by the same builder.

Scaffolding nodes (Func, Param) are used as *context* for matching but are not counted
in the scores, otherwise tiny functions would look similar just because they all have a
function node, parameters and a return.

Metrics (all in [0, 1])
    wl            Weisfeiler-Lehman subtree kernel, cosine-normalised (depth 3).
    align_f1      F1 of a node alignment (Hungarian over WL-signature agreement, soft credit)
                  averaged with the F1 of edges preserved by that alignment.  This is the
                  most readable metric: the alignment is saved and drawn in the report.
    edge_jaccard  weighted Jaccard of (src-label, edge-label, dst-label) triples.
    node_label_jaccard weighted Jaccard of non-function node-label multisets.
    control       weighted Jaccard of (loop/branch, nesting depth) multiset.
"""
import hashlib
from collections import Counter, defaultdict

import numpy as np

try:
    from scipy.optimize import linear_sum_assignment
except Exception:        # pragma: no cover
    linear_sum_assignment = None

WL_DEPTH = 3
SCAFFOLD_KINDS = {"func"}
def _h(obj):
    return hashlib.blake2b(repr(obj).encode(), digest_size=8).hexdigest()


def weighted_jaccard(c1, c2):
    keys = set(c1) | set(c2)
    den = sum(max(c1[k], c2[k]) for k in keys)
    return 1.0 if den == 0 else sum(min(c1[k], c2[k]) for k in keys) / den


def wl_iterations(G, depth=WL_DEPTH):
    cur = {n: d["label"] for n, d in G.nodes(data=True)}
    outs = {n: [(d["label"], v) for _, v, d in G.out_edges(n, data=True)] for n in G}
    ins = {n: [(d["label"], u) for u, _, d in G.in_edges(n, data=True)] for n in G}
    its = [cur]
    for _ in range(depth):
        nxt = {}
        for n in G:
            nxt[n] = _h((cur[n],
                         sorted((el, cur[v]) for el, v in outs[n]),
                         sorted((el, cur[u]) for el, u in ins[n])))
        its.append(nxt)
        cur = nxt
    return its


def _core(G):
    return {n for n, d in G.nodes(data=True) if d["kind"] not in SCAFFOLD_KINDS}


def _core_edges(G):
    return {(u, v, k) for u, v, k in G.edges(keys=True)
            if G.nodes[u]["kind"] != "func" and G.nodes[v]["kind"] != "func"}


def wl_similarity(G1, G2, its1, its2):
    def feats(G, its):
        core = _core(G)
        c = Counter()
        for k, d in enumerate(its):
            for n in core:
                c[(k, d[n])] += 1
        return c
    f1, f2 = feats(G1, its1), feats(G2, its2)
    if not f1 and not f2:
        return 1.0
    if not f1 or not f2:
        return 0.0
    dot = sum(c * f2[k] for k, c in f1.items() if k in f2)
    n1 = sum(c * c for c in f1.values()) ** 0.5
    n2 = sum(c * c for c in f2.values()) ** 0.5
    return dot / (n1 * n2)


def align_nodes(G1, G2, its1, its2):
    """Match nodes of G1 to nodes of G2. sim = share of WL levels (0..K-1) that agree, label must agree."""
    K = len(its1)
    by_label = defaultdict(list)
    for b in G2:
        by_label[its2[0][b]].append(b)
    n1, n2 = list(G1), list(G2)
    i1 = {n: i for i, n in enumerate(n1)}
    i2 = {n: i for i, n in enumerate(n2)}
    sim = np.zeros((len(n1), len(n2)))
    for a in n1:
        for b in by_label.get(its1[0][a], ()):
            j = 0
            while j < K and its1[j][a] == its2[j][b]:
                j += 1
            sim[i1[a], i2[b]] = j / K
    mapping, sims = {}, {}
    if sim.size:
        if linear_sum_assignment is not None:
            rows, cols = linear_sum_assignment(-sim)
            pairs = list(zip(rows, cols))
        else:       # greedy fallback
            idx = sorted(((-sim[i, j], i, j) for i in range(sim.shape[0]) for j in range(sim.shape[1])
                          if sim[i, j] > 0))
            used_r, used_c, pairs = set(), set(), []
            for _, i, j in idx:
                if i not in used_r and j not in used_c:
                    used_r.add(i), used_c.add(j), pairs.append((i, j))
        for i, j in pairs:
            if sim[i, j] > 0:
                mapping[n1[i]] = n2[j]
                sims[n1[i]] = float(sim[i, j])
    return mapping, sims


def _f1(p, r):
    return 0.0 if p + r == 0 else 2 * p * r / (p + r)


def compare_graphs(G1, G2):
    """G1 = original, G2 = generated.  Returns metrics + alignment details for rendering."""
    its1, its2 = wl_iterations(G1), wl_iterations(G2)
    core1, core2 = _core(G1), _core(G2)
    mapping, sims = align_nodes(G1, G2, its1, its2)

    # --- node level (soft credit, core nodes only)
    soft = sum(s for a, s in sims.items() if a in core1 and mapping[a] in core2)
    p_n = soft / len(core2) if core2 else (1.0 if not core1 else 0.0)
    r_n = soft / len(core1) if core1 else (1.0 if not core2 else 0.0)
    node_f1 = 1.0 if not core1 and not core2 else _f1(p_n, r_n)

    # --- edge level
    E1, E2 = _core_edges(G1), _core_edges(G2)
    E2_set = set(E2)
    preserved = {(u, v, k) for (u, v, k) in E1
                 if u in mapping and v in mapping and (mapping[u], mapping[v], k) in E2_set}
    inv = {b: a for a, b in mapping.items()}
    preserved_g = {(mapping[u], mapping[v], k) for (u, v, k) in preserved}
    p_e = len(preserved) / len(E2) if E2 else (1.0 if not E1 else 0.0)
    r_e = len(preserved) / len(E1) if E1 else (1.0 if not E2 else 0.0)
    edge_f1 = 1.0 if not E1 and not E2 else _f1(p_e, r_e)

    # --- count-based similarities
    node_labels1 = Counter(G1.nodes[n]["label"] for n in core1)
    node_labels2 = Counter(G2.nodes[n]["label"] for n in core2)
    trip = lambda G, E: Counter((G.nodes[u]["label"], k, G.nodes[v]["label"]) for u, v, k in E)
    ctl = lambda G: Counter((d["label"], d["depth"]) for _, d in G.nodes(data=True)
                            if d["kind"] in ("loop", "branch"))

    m = {
        "wl": wl_similarity(G1, G2, its1, its2),
        "align_f1": (node_f1 + edge_f1) / 2,
        "edge_jaccard": weighted_jaccard(trip(G1, E1), trip(G2, E2)),
        "node_label_jaccard": weighted_jaccard(node_labels1, node_labels2),
        "control": weighted_jaccard(ctl(G1), ctl(G2)),
    }
    m["nodes_orig"], m["nodes_gen"] = len(core1), len(core2)
    m["edges_orig"], m["edges_gen"] = len(E1), len(E2)
    return {
        "metrics": m,
        "mapping": mapping,
        "sims": sims,
        "bad_edges_orig": sorted(E1 - preserved),
        "bad_edges_gen": sorted(E2 - preserved_g),
    }
