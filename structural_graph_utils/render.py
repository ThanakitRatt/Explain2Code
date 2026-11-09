"""Graphviz + HTML rendering so a human can validate pairs quickly."""
import html
import json
import shutil
import subprocess

KIND_STYLE = {   # fill colour, shape
    "func": ("#e3e3e3", "box"),
    "param": ("#cfe8ff", "ellipse"),
    "const": ("#f4f4f4", "ellipse"),
    "op": ("#fff6bf", "box"),
    "call": ("#ffdfb0", "box"),
    "branch": ("#e4d4ff", "diamond"),
    "loop": ("#d3c0ff", "hexagon"),
    "phi": ("#ffd0e6", "ellipse"),
    "elem": ("#d2f4e8", "box"),
    "store": ("#ffc999", "box"),
    "return": ("#c4efc4", "box"),
    "term": ("#f4b6b0", "box"),
    "other": ("#ffffff", "box"),
}


def _esc(s):
    return str(s).replace("\\", "\\\\").replace('"', '\\"')


def to_dot(G, mapping=None, sims=None, bad_edges=(), side="orig"):
    """mapping: node -> node (orig->gen).  side says which end of the mapping G is."""
    mapping, sims = mapping or {}, sims or {}
    match_id, match_sim = {}, {}
    for i, a in enumerate(sorted(mapping), 1):
        b = mapping[a]
        s = sims.get(a, 0.0)
        if side == "orig":
            match_id[a], match_sim[a] = i, s
        else:
            match_id[b], match_sim[b] = i, s
    bad = set(bad_edges)
    out = ['digraph G {', 'rankdir=TB; nodesep=0.25; ranksep=0.35;',
           'node [fontname="Helvetica", fontsize=10, style="filled", margin="0.06,0.03"];',
           'edge [fontname="Helvetica", fontsize=8];']
    for n, d in G.nodes(data=True):
        fill, shape = KIND_STYLE.get(d["kind"], KIND_STYLE["other"])
        lines = [d["label"]]
        meta = []
        if d.get("line") is not None:
            meta.append(f"L{d['line']}")
        if n in match_id:
            meta.append(f"#{match_id[n]}")
        if meta:
            lines.append(" ".join(meta))
        if mapping:
            if n in match_id:
                s = match_sim[n]
                color = "#2e8b57" if s >= 0.75 else "#e0a000" if s >= 0.5 else "#d9534f"
                attrs = f'color="{color}", penwidth=2'
            else:
                attrs = 'color="#d9534f", penwidth=3, style="filled,dashed"'
        else:
            attrs = 'color="#777777"'
        label = "\\n".join(_esc(x) for x in lines)
        tip = _esc(d.get("src") or d["label"])
        out.append(f'n{n} [label="{label}", shape={shape}, fillcolor="{fill}", tooltip="{tip}", {attrs}];')
    for u, v, k, d in G.edges(keys=True, data=True):
        ctl = d["label"].startswith("ctl:")
        is_bad = (u, v, k) in bad
        color = "#d9534f" if is_bad else ("#8a6fd0" if ctl else "#555555")
        style = "dashed" if ctl else "solid"
        pen = 2.2 if is_bad else 1
        out.append(f'n{u} -> n{v} [label="{_esc(d["label"])}", color="{color}", fontcolor="{color}", '
                   f'style={style}, penwidth={pen}];')
    out.append("}")
    return "\n".join(out)


def dot_to_svg(dot_text, timeout=60):
    if not shutil.which("dot"):
        return None
    try:
        p = subprocess.run(["dot", "-Tsvg"], input=dot_text, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None
    return p.stdout if p.returncode == 0 else None


def _inline_svg(svg):
    if not svg:
        return "<p class='warn'>SVG not available (is Graphviz <code>dot</code> installed?)</p>"
    i = svg.find("<svg")
    return svg[i:] if i >= 0 else svg


CSS = """
body{font-family:system-ui,Segoe UI,Helvetica,Arial,sans-serif;margin:16px 24px;color:#1b1b1b;background:#fff}
h1{font-size:1.25rem;margin:0 0 4px} h2{font-size:1rem;margin:18px 0 6px}
a{color:#1a5fb4;text-decoration:none} a:hover{text-decoration:underline}
table{border-collapse:collapse;font-size:.85rem} th,td{border:1px solid #d5d5d5;padding:4px 8px;text-align:left}
th{background:#f3f3f3;cursor:pointer;position:sticky;top:0} td.num{text-align:right;font-variant-numeric:tabular-nums}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px} @media(max-width:1100px){.grid{grid-template-columns:1fr}}
.panel{border:1px solid #d5d5d5;border-radius:6px;padding:8px;min-width:0}
.panel h3{margin:0 0 6px;font-size:.9rem}
pre.code{background:#fafafa;border:1px solid #e6e6e6;padding:8px;overflow:auto;font-size:.8rem;margin:0;max-height:420px}
.ln{color:#999;user-select:none;display:inline-block;width:2.6em;text-align:right;margin-right:.8em}
.svgbox{overflow:auto;max-height:78vh;border:1px solid #eee;background:#fff} .svgbox svg{max-width:none;height:auto}
.high{background:#d8f3dc}.mid{background:#fff3cd}.low{background:#f8d7da}
.flag{background:#ffe2c2;border-radius:4px;padding:1px 6px;margin-right:4px;font-size:.75rem;white-space:nowrap}
.legend span{display:inline-block;padding:1px 8px;margin:2px 3px;border:1px solid #bbb;border-radius:4px;font-size:.75rem}
.warn{color:#a33}.muted{color:#777;font-size:.8rem}
.explanation{max-width:90ch;background:#f8f9fb;border:1px solid #e3e7ed;border-radius:6px;padding:12px 16px;line-height:1.65}
.explanation p{margin:0 0 .8em}.explanation p:last-child{margin-bottom:0}
.explanation h3,.explanation h4{margin:1em 0 .35em}.explanation h3:first-child,.explanation h4:first-child{margin-top:0}
.explanation ul{margin:.35em 0 .85em;padding-left:1.5em}
.explanation code{background:#edf0f4;border-radius:3px;padding:1px 4px;font-size:.92em}
input[type=search]{padding:4px 8px;width:320px;margin:6px 0}
"""

SORT_JS = """
function sortTable(th){const t=th.closest('table'),i=[...th.parentNode.children].indexOf(th);
const dir=th.dataset.dir=th.dataset.dir==='asc'?'desc':'asc';
const rows=[...t.tBodies[0].rows];rows.sort((a,b)=>{const x=a.cells[i].dataset.v??a.cells[i].innerText,y=b.cells[i].dataset.v??b.cells[i].innerText;
const nx=parseFloat(x),ny=parseFloat(y);const c=(!isNaN(nx)&&!isNaN(ny))?nx-ny:x.localeCompare(y);return dir==='asc'?c:-c});
rows.forEach(r=>t.tBodies[0].appendChild(r));}
function filterRows(q){q=q.toLowerCase();document.querySelectorAll('#t tbody tr').forEach(r=>r.style.display=r.innerText.toLowerCase().includes(q)?'':'none');}
"""


def _band(x):
    if x is None:
        return ""
    return "high" if x >= 0.85 else "mid" if x >= 0.6 else "low"


def _code(src):
    lines = src.splitlines() or [""]
    return "<pre class='code'>" + "\n".join(
        f"<span class='ln'>{i}</span>{html.escape(l)}" for i, l in enumerate(lines, 1)) + "</pre>"


def legend():
    items = "".join(f"<span style='background:{c}'>{k}</span>" for k, (c, _) in KIND_STYLE.items() if k != "other")
    return ("<div class='legend'>" + items +
            "<span style='border:2px solid #2e8b57'>matched (strong)</span>"
            "<span style='border:2px solid #e0a000'>matched (partial context)</span>"
            "<span style='border:2px solid #d9534f'>weak match</span>"
            "<span style='border:3px dashed #d9534f'>unmatched node</span>"
            "<span style='color:#d9534f'>red edge = not preserved</span>"
            "<span style='color:#8a6fd0'>purple dashed = control</span></div>")


def task_page(row, orig_src, gen_src, svg_o, svg_g, comparison, behavior):
    m = comparison["metrics"] if comparison else {}
    parts = [f"<!doctype html><meta charset='utf-8'><title>{html.escape(row['task_id'])}</title>",
             f"<style>{CSS}</style>",
             f"<p><a href='../../index.html'>&larr; all tasks</a></p><h1>{html.escape(row['task_id'])}</h1>"]
    if row.get("flags"):
        parts.append("<p>" + "".join(f"<span class='flag'>{html.escape(f)}</span>" for f in row["flags"].split(";") if f) + "</p>")
    if row["status"] != "ok":
        parts.append(f"<p class='warn'>Status: {html.escape(row['status'])} &mdash; {html.escape(row.get('error') or '')}</p>")
    if m:
        keys = ["wl", "align_f1", "edge_jaccard", "node_label_jaccard", "control"]
        labels = ["WL", "Alignment F1", "Edge Jaccard", "Node-Label Jaccard", "Control"]
        parts.append("<table><tr>" + "".join(f"<th>{label}</th>" for label in labels) + "<th>core nodes o/g</th><th>core edges o/g</th>"
                     + ("<th>behaviour match</th>" if behavior else "") + "</tr><tr>")
        parts += [f"<td class='num'>{m[k]:.3f}</td>" for k in keys]
        parts.append(f"<td class='num'>{m['nodes_orig']} / {m['nodes_gen']}</td><td class='num'>{m['edges_orig']} / {m['edges_gen']}</td>")
        if behavior:
            f = behavior["fraction"]
            parts.append(f"<td class='num {_band(f)}'>{behavior['match']}/{behavior['n']}</td>")
        parts.append("</tr></table>")
    parts.append("<h2>Code</h2><div class='grid'>"
                 f"<div class='panel'><h3>Original</h3>{_code(orig_src)}</div>"
                 f"<div class='panel'><h3>Generated</h3>{_code(gen_src)}</div></div>")
    parts.append("<h2>Graphs</h2>" + legend() +
                 "<p class='muted'>Node text: label, source line (L), alignment id (#). The same #id on both sides = the pair the "
                 "comparer matched. Hover a node for the (normalised) source snippet. Line numbers refer to the code above.</p>")
    parts.append("<div class='grid'>"
                 f"<div class='panel'><h3>Original <a class='muted' href='original.svg'>open svg</a></h3><div class='svgbox'>{_inline_svg(svg_o)}</div></div>"
                 f"<div class='panel'><h3>Generated <a class='muted' href='generated.svg'>open svg</a></h3><div class='svgbox'>{_inline_svg(svg_g)}</div></div></div>")
    if comparison:
        o_un = [n for n in comparison.get("unmatched_orig", [])]
        g_un = [n for n in comparison.get("unmatched_gen", [])]
        parts.append("<h2>Unmatched nodes</h2><div class='grid'>"
                     "<div class='panel'><h3>In original only</h3>" + _ul(o_un) + "</div>"
                     "<div class='panel'><h3>In generated only</h3>" + _ul(g_un) + "</div></div>")
    if behavior and behavior["rows"]:
        parts.append("<h2>Behaviour on shared inputs</h2><table><tr><th>input</th><th>original</th><th>generated</th><th>equal</th></tr>")
        for r in behavior["rows"][:60]:
            parts.append("<tr><td>{}</td><td>{}</td><td>{}</td><td class='{}'>{}</td></tr>".format(
                html.escape(json.dumps(r["input"])[:160]), html.escape(_show(r["orig"])),
                html.escape(_show(r["gen"])), "high" if r["equal"] else "low", "yes" if r["equal"] else "NO"))
        parts.append("</table>")
        if len(behavior["rows"]) > 60:
            parts.append(f"<p class='muted'>first 60 of {len(behavior['rows'])} inputs shown; all in behavior.json</p>")
    return "".join(parts)


def _show(r):
    return json.dumps(r["v"])[:160] if r["ok"] else f"raises {r['err']}"


def _ul(items):
    if not items:
        return "<p class='muted'>none</p>"
    return "<ul>" + "".join(f"<li>{html.escape(x)}</li>" for x in items) + "</ul>"


def index_page(rows, title="structural graph utils report"):
    cols = [("task_id", "task"), ("wl", "wl"), ("align_f1", "align_f1"),
            ("edge_jaccard", "edge_jaccard"), ("node_label_jaccard", "node-label Jaccard"), ("control", "control"),
            ("nodes_orig", "nodes o"), ("nodes_gen", "nodes g"),
            ("behavior_match", "behaviour"), ("flags", "flags"), ("status", "status")]
    parts = [f"<!doctype html><meta charset='utf-8'><title>{title}</title><style>{CSS}</style><script>{SORT_JS}</script>",
             f"<h1>{title}</h1>"]
    ok = [r for r in rows if r["status"] == "ok"]
    if ok:
        means = {key: sum(r[key] for r in ok) / len(ok) for key in
                 ("wl", "align_f1", "edge_jaccard", "node_label_jaccard", "control")}
        parts.append(f"<p>{len(rows)} tasks &middot; {len(ok)} compared &middot; mean scores: "
                     + ", ".join(f"{key} {value:.3f}" for key, value in means.items())
                     + f" &middot; {sum(1 for r in rows if r.get('flags'))} flagged. Click a header to sort.</p>")
    parts.append("<input type='search' placeholder='filter (task id, flag, status)…' oninput='filterRows(this.value)'>")
    parts.append("<table id='t'><thead><tr>" + "".join(f"<th onclick='sortTable(this)'>{h}</th>" for _, h in cols) + "</tr></thead><tbody>")
    for r in rows:
        tds = []
        for key, _ in cols:
            v = r.get(key)
            if key == "task_id":
                tds.append(f"<td><a href='{r['dir']}/index.html'>{html.escape(str(v))}</a></td>")
            elif isinstance(v, float):
                cls = _band(v) if key == "behavior_match" else ""
                tds.append(f"<td class='num {cls}' data-v='{v:.4f}'>{v:.3f}</td>")
            elif key == "flags":
                tds.append("<td>" + "".join(f"<span class='flag'>{html.escape(f)}</span>" for f in (v or "").split(";") if f) + "</td>")
            else:
                tds.append(f"<td class='num'>{'' if v is None else html.escape(str(v))}</td>")
        parts.append("<tr>" + "".join(tds) + "</tr>")
    parts.append("</tbody></table>")
    return "".join(parts)
