"""Build a semantic program graph (control + data dependence) from Python source.

Design goals
------------
* Same builder for the original and the AI-generated code, so graphs are comparable.
* Nothing in a node label depends on user-chosen names: variables disappear and are
  replaced by data-flow edges; only operations, constants, called library/builtin
  functions and method names remain.
* Every node keeps the source line it came from, so a human can check it quickly.

Nodes (attribute ``label`` is what the comparer uses, ``kind`` is only for colouring)
    Func(main|helper|inner)  Param(i)  Const(v)  BinOp(+)  Cmp(<)  Bool(and)  Unary(-)
    Index  Slice  Attr(...)  Call(len) Call(.append) Call(math.sqrt) Call(local) Call(self)
    List Tuple Set Dict  Lambda LParam(i)  FStr
    Branch  Loop(for)  Loop(while)  Phi  Elem  Unpack  SubStore  AttrStore(x)
    Return  Raise  Break  Continue  Yield

Edges (attribute ``label``)
    data      op | l r | a0 a1 .. | kw:name | recv | base idx | val | cond | iter | init carry | then else ...
    control   ctl:T / ctl:F (branch arms), ctl:L (loop body), ctl:B (function body), ctl:M (merge)
"""
import ast
import builtins

import networkx as nx

from .normalize import normalize

BUILTINS = set(dir(builtins))
BIN_SYM = {ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/", ast.FloorDiv: "//",
           ast.Mod: "%", ast.Pow: "**", ast.LShift: "<<", ast.RShift: ">>", ast.BitOr: "|",
           ast.BitXor: "^", ast.BitAnd: "&", ast.MatMult: "@"}
CMP_SYM = {ast.Eq: "==", ast.NotEq: "!=", ast.Lt: "<", ast.LtE: "<=", ast.Gt: ">",
           ast.GtE: ">=", ast.Is: "is", ast.IsNot: "is not", ast.In: "in", ast.NotIn: "not in"}
UN_SYM = {ast.UAdd: "+", ast.USub: "-", ast.Not: "not", ast.Invert: "~"}
COMMUTATIVE = (ast.Add, ast.Mult, ast.BitAnd, ast.BitOr, ast.BitXor)
SYMMETRIC_CMP = (ast.Eq, ast.NotEq, ast.Is, ast.IsNot)
MUTATORS = {"append", "extend", "add", "insert", "pop", "remove", "sort", "reverse", "update",
            "clear", "appendleft", "popleft", "extendleft", "setdefault", "discard", "popitem",
            "difference_update", "intersection_update", "symmetric_difference_update",
            "heappush", "heappop", "rotate"}


# --------------------------------------------------------------------- helpers
def root_name(node):
    while isinstance(node, (ast.Subscript, ast.Attribute)):
        node = node.value
    return node.id if isinstance(node, ast.Name) else None


def modified_vars(stmts):
    out = set()
    for st in stmts:
        for n in ast.walk(st):
            if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
                out.add(n.id)
            elif isinstance(n, (ast.Subscript, ast.Attribute)) and isinstance(n.ctx, (ast.Store, ast.Del)):
                r = root_name(n)
                if r:
                    out.add(r)
            elif (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                  and n.func.attr in MUTATORS):
                r = root_name(n.func.value)
                if r:
                    out.add(r)
    return out


def terminates(stmts):
    if not stmts:
        return False
    last = stmts[-1]
    if isinstance(last, (ast.Return, ast.Raise, ast.Break, ast.Continue)):
        return True
    if isinstance(last, ast.If):
        return terminates(last.body) and terminates(last.orelse)
    return False


def _is_literal(node):
    try:
        ast.literal_eval(node)
        return True
    except Exception:
        return False


def _is_main_guard(test):
    names = [x for x in ast.walk(test) if isinstance(x, ast.Name)]
    return any(n.id == "__name__" for n in names) and "__main__" in ast.unparse(test)


def _functions(tree):
    """Top-level functions and methods of top-level classes."""
    out = []
    for st in tree.body:
        if isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.append(st)
        elif isinstance(st, ast.ClassDef):
            out.extend(x for x in st.body if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef)))
    return out


def resolve_entry(tree, entry_point=None):
    """The function under test: the named one if it exists, else the last one defined."""
    names = [f.name for f in _functions(tree)]
    if entry_point in names:
        return entry_point
    return names[-1] if names else None


def entry_found(tree, entry_point):
    """False when an entry name was given but no such function exists (a fallback was used)."""
    return not entry_point or entry_point in [f.name for f in _functions(tree)]


# --------------------------------------------------------------------- builder
class GraphBuilder:
    def __init__(self, source, entry_point=None):
        self.src = source
        self.entry_point = entry_point
        self.G = nx.MultiDiGraph()
        self.n = 0
        self.ctl = []            # stack of (node_id, arm)
        self.env = {}            # variable name -> producing node id
        self.imports = {}        # alias -> dotted module / object path
        self.funcs = {}          # function name -> Func node id
        self.cur_func = None
        self.unsupported = 0
        self.entry = None

    # -------------------------------------------------------------- low level
    @staticmethod
    def u(a, n=70):
        try:
            s = ast.unparse(a)
        except Exception:
            s = type(a).__name__
        s = " ".join(s.split())
        return s if len(s) <= n else s[:n] + "…"

    def node(self, label, kind, src=None, line=None):
        nid = self.n
        self.n += 1
        self.G.add_node(nid, label=label, kind=kind, line=line, src=src, depth=len(self.ctl))
        return nid

    def edge(self, u, v, label):
        if u is None or v is None:
            return
        if not self.G.has_edge(u, v, key=label):
            self.G.add_edge(u, v, key=label, label=label)

    def link_ctl(self, nid):
        if self.ctl:
            c, arm = self.ctl[-1]
            self.edge(c, nid, f"ctl:{arm}")

    # ------------------------------------------------------------------ build
    def build(self):
        tree = normalize(ast.parse(self.src))
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                for a in n.names:
                    self.imports[a.asname or a.name.split(".")[0]] = a.name if a.asname else a.name.split(".")[0]
            elif isinstance(n, ast.ImportFrom) and n.module:
                for a in n.names:
                    self.imports[a.asname or a.name] = f"{n.module}.{a.name}"
        self.entry = resolve_entry(tree, self.entry_point)
        funcs = _functions(tree)
        pending = []
        for fd in funcs:
            role = "main" if fd.name == self.entry else "helper"
            fid = self.node(f"Func({role})", "func", src=f"def {fd.name}", line=fd.lineno)
            self.funcs.setdefault(fd.name, fid)
            pending.append((fd, fid, role))
        for st in tree.body:                      # module-level constants and imports
            if isinstance(st, ast.Assign) and _is_literal(st.value):
                self.s_Assign(st)
            elif isinstance(st, (ast.Import, ast.ImportFrom)):
                getattr(self, "s_" + type(st).__name__)(st)
        for fd, fid, role in sorted(pending, key=lambda x: x[2] == "main"):   # helpers first
            self.build_function(fd, fid)
        for st in tree.body:                      # if __name__ == "__main__": ...
            if isinstance(st, ast.If) and _is_main_guard(st.test):
                self.build_main_guard(st)
        self.G.graph.update(entry=self.entry, entry_found=entry_found(tree, self.entry_point),
                            unsupported=self.unsupported)
        return self.G

    def build_main_guard(self, st):
        saved = (self.env, self.ctl, self.cur_func)
        self.env = dict(self.env)
        g = self.node("MainGuard", "branch", src=self.u(st.test), line=st.lineno)
        self.ctl = [(g, "T")]
        self.cur_func = "<module>"
        self.block(st.body)
        self.env, self.ctl, self.cur_func = saved

    def build_function(self, fd, fid):
        saved = (self.env, self.ctl, self.cur_func)
        self.env = dict(self.env)
        self.ctl = [(fid, "B")]
        self.cur_func = fd.name
        a = fd.args
        pos = list(a.posonlyargs) + list(a.args)
        defaults = [None] * (len(pos) - len(a.defaults)) + list(a.defaults)
        params = ([(p, f"Param({i})", d) for i, (p, d) in enumerate(zip(pos, defaults))])
        params += [(a.vararg, "Param(*)", None)] if a.vararg else []
        params += [(p, "Param(kw)", d) for p, d in zip(a.kwonlyargs, a.kw_defaults)]
        params += [(a.kwarg, "Param(**)", None)] if a.kwarg else []
        for p, label, dflt in params:
            pid = self.node(label, "param", src=p.arg, line=getattr(p, "lineno", None))
            self.edge(fid, pid, "param")
            self.env[p.arg] = pid
            if dflt is not None:
                self.edge(self.eval(dflt), pid, "default")
            if p.annotation is not None:
                self.edge(self.node("Hint(param)", "hint", src=self.u(p.annotation),
                                    line=getattr(p, "lineno", None)), pid, "hint")
        if fd.returns is not None:
            self.edge(self.node("Hint(return)", "hint", src=self.u(fd.returns), line=fd.lineno),
                      fid, "hint")
        self.block(fd.body)
        self.env, self.ctl, self.cur_func = saved

    # ------------------------------------------------------------- statements
    def block(self, stmts):
        base = len(self.ctl)
        for s in stmts:
            m = getattr(self, "s_" + type(s).__name__, None)
            if m is None:
                self.unsupported += 1
            else:
                m(s)
        del self.ctl[base:]

    def s_Pass(self, s): pass
    s_Global = s_Nonlocal = s_Assert = s_ClassDef = s_Pass

    def s_Import(self, s):
        for a in s.names:
            self.node(f"Import({a.name})", "import", src=self.u(s), line=s.lineno)

    def s_ImportFrom(self, s):
        for a in s.names:
            self.node(f"Import({s.module or '.'}.{a.name})", "import", src=self.u(s), line=s.lineno)

    def s_AnnAssign(self, s):                    # bare annotation: counts as a type hint
        self.link_ctl(self.node("Hint(var)", "hint", src=self.u(s), line=s.lineno))

    def s_Expr(self, s):
        v = self.eval(s.value)
        if isinstance(s.value, (ast.Call, ast.Await)):
            self.link_ctl(v)

    def s_Return(self, s):
        n = self.node("Return", "return", src=self.u(s), line=s.lineno)
        if s.value is not None:
            self.edge(self.eval(s.value), n, "val")
        self.link_ctl(n)

    def s_Raise(self, s):
        n = self.node("Raise", "term", src=self.u(s), line=s.lineno)
        if s.exc is not None:
            self.edge(self.eval(s.exc), n, "val")
        self.link_ctl(n)

    def s_Break(self, s):
        self.link_ctl(self.node("Break", "term", src="break", line=s.lineno))

    def s_Continue(self, s):
        self.link_ctl(self.node("Continue", "term", src="continue", line=s.lineno))

    def s_Delete(self, s):
        for t in s.targets:
            n = self.node("Del", "store", src=self.u(t), line=s.lineno)
            if not isinstance(t, ast.Name):
                self.edge(self.eval(t.value), n, "base")
            self.link_ctl(n)

    def s_Assign(self, s):
        t0 = s.targets[0]
        if (len(s.targets) == 1 and isinstance(t0, (ast.Tuple, ast.List))
                and isinstance(s.value, (ast.Tuple, ast.List))
                and len(t0.elts) == len(s.value.elts)
                and not any(isinstance(x, ast.Starred) for x in t0.elts + s.value.elts)):
            vals = [self.eval(e) for e in s.value.elts]          # evaluate all RHS first (swap!)
            for t, v in zip(t0.elts, vals):
                self.assign_target(t, v)
            return
        v = self.eval(s.value)
        for t in s.targets:
            self.assign_target(t, v)

    def assign_target(self, t, v):
        if isinstance(t, ast.Name):
            self.env[t.id] = v
        elif isinstance(t, (ast.Tuple, ast.List)):
            for k, e in enumerate(t.elts):
                if isinstance(e, ast.Starred):
                    un = self.node("Unpack*", "elem", src=self.u(e), line=getattr(e, "lineno", None))
                    self.edge(v, un, f"u{k}")
                    self.assign_target(e.value, un)
                else:
                    un = self.node("Unpack", "elem", src=self.u(e), line=getattr(e, "lineno", None))
                    self.edge(v, un, f"u{k}")
                    self.assign_target(e, un)
        elif isinstance(t, ast.Subscript):
            st = self.node("SubStore", "store", src=self.u(t), line=t.lineno)
            self.edge(self.eval(t.value), st, "base")
            self.edge(self.eval(t.slice), st, "idx")
            self.edge(v, st, "val")
            self.link_ctl(st)
            r = root_name(t.value)
            if r:
                self.env[r] = st
        elif isinstance(t, ast.Attribute):
            st = self.node(f"AttrStore({t.attr})", "store", src=self.u(t), line=t.lineno)
            self.edge(self.eval(t.value), st, "base")
            self.edge(v, st, "val")
            self.link_ctl(st)
            r = root_name(t.value)
            if r:
                self.env[r] = st
        elif isinstance(t, ast.Starred):
            self.assign_target(t.value, v)
        else:
            self.unsupported += 1

    # ---- branches
    def s_If(self, s):
        cond = self.eval(s.test)
        br = self.node("Branch", "branch", src=f"if {self.u(s.test)}", line=s.lineno)
        self.edge(cond, br, "cond")
        self.link_ctl(br)
        self.branch_body(br, s.body, s.orelse, implicit=True)

    def s_Try(self, s):
        br = self.node("Branch(try)", "branch", src="try", line=s.lineno)
        self.link_ctl(br)
        handlers = [st for h in s.handlers for st in h.body]
        self.branch_body(br, s.body + s.orelse, handlers, implicit=False)
        self.block(s.finalbody)

    s_TryStar = s_Try

    def branch_body(self, br, body, orelse, implicit):
        env0 = self.env
        self.env = dict(env0)
        self.ctl.append((br, "T"))
        self.block(body)
        env_t = self.env
        self.ctl.pop()
        self.env = dict(env0)
        self.ctl.append((br, "F"))
        self.block(orelse)
        env_f = self.env
        self.ctl.pop()
        t_term, f_term = terminates(body), terminates(orelse)
        if implicit and (t_term or f_term):
            if t_term and not f_term:        # rest of the block runs only when the branch was not taken
                self.env = env_f
                self.ctl.append((br, "F"))
            elif f_term and not t_term:
                self.env = env_t
                self.ctl.append((br, "T"))
            else:
                self.env = env_t
            return
        merged = {}
        for k in set(env_t) | set(env_f):
            a, b = env_t.get(k), env_f.get(k)
            if a == b:
                merged[k] = a
                continue
            if a is None or b is None:
                # defined on one path only and not before the branch: a branch-local
                # temporary. It is not a merge of two values, so no Phi (style, not logic).
                merged[k] = b if a is None else a
                continue
            phi = self.node("Phi", "phi", line=self.G.nodes[br]["line"])
            self.edge(a, phi, "then")
            self.edge(b, phi, "else")
            self.edge(br, phi, "ctl:M")
            merged[k] = phi
        self.env = merged

    # ---- loops
    def s_For(self, s):
        it = self.eval(s.iter)
        lp = self.node("Loop(for)", "loop", src=f"for {self.u(s.target)} in {self.u(s.iter)}", line=s.lineno)
        self.edge(it, lp, "iter")
        self.link_ctl(lp)
        self.loop_common(lp, s, is_for=True)

    def s_While(self, s):
        lp = self.node("Loop(while)", "loop", src=f"while {self.u(s.test)}", line=s.lineno)
        self.link_ctl(lp)
        self.loop_common(lp, s, is_for=False)

    s_AsyncFor = s_For

    def loop_common(self, lp, s, is_for):
        target_names = set()
        if is_for:
            for n in ast.walk(s.target):
                if isinstance(n, ast.Name):
                    target_names.add(n.id)
        # loop-carried values: variables that exist before the loop and are changed inside it
        carried = sorted(v for v in modified_vars(s.body) - target_names if v in self.env)
        phis = {}
        for v in carried:
            p = self.node("Phi", "phi", line=s.lineno)
            self.edge(self.env[v], p, "init")
            self.edge(lp, p, "ctl:L")
            self.env[v] = p
            phis[v] = p
        self.ctl.append((lp, "L"))
        if is_for:
            el = self.node("Elem", "elem", src=self.u(s.target), line=s.lineno)
            self.edge(lp, el, "elem")
            self.assign_target(s.target, el)
        else:
            self.edge(self.eval(s.test), lp, "cond")
        self.block(s.body)
        self.ctl.pop()
        for v, p in phis.items():
            fin = self.env.get(v)
            if fin is not None and fin != p:
                self.edge(fin, p, "carry")
            self.env[v] = p
        self.block(s.orelse)

    # ---- misc
    def s_With(self, s):
        for item in s.items:
            v = self.eval(item.context_expr)
            if item.optional_vars is not None:
                self.assign_target(item.optional_vars, v)
        self.block(s.body)

    s_AsyncWith = s_With

    def s_FunctionDef(self, s):
        fid = self.node("Func(inner)", "func", src=f"def {s.name}", line=s.lineno)
        self.link_ctl(fid)
        self.funcs[s.name] = fid
        self.build_function(s, fid)

    s_AsyncFunctionDef = s_FunctionDef

    # ------------------------------------------------------------ expressions
    def eval(self, e):
        return getattr(self, "e_" + type(e).__name__, self.e_default)(e)

    def e_default(self, e):
        self.unsupported += 1
        n = self.node(f"Expr({type(e).__name__})", "other", src=self.u(e), line=getattr(e, "lineno", None))
        for i, c in enumerate(ast.iter_child_nodes(e)):
            if isinstance(c, ast.expr):
                self.edge(self.eval(c), n, f"c{i}")
        return n

    def e_Constant(self, e):
        v = e.value
        # string/bytes *content* is behaviour (left to the test-based assessment); only "a string is here" counts
        r = "str" if isinstance(v, str) else "bytes" if isinstance(v, bytes) else repr(v)
        return self.node(f"Const({r})", "const", src=self.u(e), line=e.lineno)

    def e_Name(self, e):
        n = e.id
        if n in self.env:
            return self.env[n]
        if n in self.funcs:
            return self.funcs[n]
        if n in self.imports:
            return self.node(f"Module({self.imports[n]})", "const", src=n, line=e.lineno)
        if n in BUILTINS:
            return self.node(f"Builtin({n})", "const", src=n, line=e.lineno)
        return self.node("Free", "const", src=n, line=e.lineno)

    def dotted(self, e):
        """'math.sqrt' when the attribute chain is rooted in an imported module, else None."""
        parts = []
        while isinstance(e, ast.Attribute):
            parts.append(e.attr)
            e = e.value
        if isinstance(e, ast.Name) and e.id in self.imports and e.id not in self.env:
            return ".".join([self.imports[e.id]] + parts[::-1])
        return None

    def e_Attribute(self, e):
        d = self.dotted(e)
        if d:
            return self.node(f"Attr({d})", "const", src=self.u(e), line=e.lineno)
        n = self.node(f"Attr(.{e.attr})", "op", src=self.u(e), line=e.lineno)
        self.edge(self.eval(e.value), n, "base")
        return n

    def e_Call(self, e):
        f = e.func
        recv = callee = fn = None
        mutates = None
        if isinstance(f, ast.Attribute):
            d = self.dotted(f)
            if d:
                label = f"Call({d})"
            else:
                label = f"Call(.{f.attr})"
                recv = self.eval(f.value)
                if f.attr in MUTATORS:
                    mutates = root_name(f.value)
        elif isinstance(f, ast.Name):
            nm = f.id
            if nm in self.funcs and nm not in self.env:
                label = "Call(self)" if nm == self.cur_func else "Call(local)"
                callee = self.funcs[nm]
            elif nm in self.env:
                label, fn = "Call(?)", self.env[nm]
            elif nm in self.imports:
                label = f"Call({self.imports[nm]})"
            elif nm in BUILTINS:
                label = f"Call({nm})"
            else:
                label = "Call(?)"
        else:
            label, fn = "Call(?)", self.eval(f)
        n = self.node(label, "call", src=self.u(e), line=e.lineno)
        self.edge(recv, n, "recv")
        self.edge(callee, n, "callee")
        self.edge(fn, n, "fn")
        for i, a in enumerate(e.args):
            if isinstance(a, ast.Starred):
                self.edge(self.eval(a.value), n, "a*")
            else:
                self.edge(self.eval(a), n, f"a{i}")
        for kw in e.keywords:
            self.edge(self.eval(kw.value), n, f"kw:{kw.arg}" if kw.arg else "kw**")
        if mutates:
            self.link_ctl(n)
            self.env[mutates] = n
        return n

    def e_BinOp(self, e):
        n = self.node(f"BinOp({BIN_SYM.get(type(e.op), '?')})", "op", src=self.u(e), line=e.lineno)
        l, r = self.eval(e.left), self.eval(e.right)
        if isinstance(e.op, COMMUTATIVE):
            self.edge(l, n, "op")
            self.edge(r, n, "op")
        else:
            self.edge(l, n, "l")
            self.edge(r, n, "r")
        return n

    def e_UnaryOp(self, e):
        n = self.node(f"Unary({UN_SYM.get(type(e.op), '?')})", "op", src=self.u(e), line=e.lineno)
        self.edge(self.eval(e.operand), n, "o")
        return n

    def e_BoolOp(self, e):
        n = self.node(f"Bool({'and' if isinstance(e.op, ast.And) else 'or'})", "op", src=self.u(e), line=e.lineno)
        for v in e.values:
            self.edge(self.eval(v), n, "op")
        return n

    def e_Compare(self, e):
        # normalizer leaves single comparisons; chains are turned into `and`
        n = self.node(f"Cmp({CMP_SYM.get(type(e.ops[0]), '?')})", "op", src=self.u(e), line=e.lineno)
        l, r = self.eval(e.left), self.eval(e.comparators[0])
        if isinstance(e.ops[0], SYMMETRIC_CMP):
            self.edge(l, n, "op")
            self.edge(r, n, "op")
        else:
            self.edge(l, n, "l")
            self.edge(r, n, "r")
        return n

    def e_Subscript(self, e):
        n = self.node("Index", "op", src=self.u(e), line=e.lineno)
        self.edge(self.eval(e.value), n, "base")
        self.edge(self.eval(e.slice), n, "idx")
        return n

    def e_Slice(self, e):
        n = self.node("Slice", "op", src=self.u(e), line=getattr(e, "lineno", None))
        for part, lab in ((e.lower, "lo"), (e.upper, "hi"), (e.step, "st")):
            if part is not None:
                self.edge(self.eval(part), n, lab)
        return n

    def e_Tuple(self, e):
        return self._container(e, "Tuple")

    def e_List(self, e):
        return self._container(e, "List")

    def e_Set(self, e):
        return self._container(e, "Set")

    def _container(self, e, label):
        n = self.node(label, "op", src=self.u(e), line=getattr(e, "lineno", None))
        for i, x in enumerate(e.elts):
            self.edge(self.eval(x), n, "e" if label == "Set" else f"e{i}")
        return n

    def e_Dict(self, e):
        n = self.node("Dict", "op", src=self.u(e), line=e.lineno)
        for i, (k, v) in enumerate(zip(e.keys, e.values)):
            if k is None:
                self.edge(self.eval(v), n, "dv")
            else:
                self.edge(self.eval(k), n, f"k{i}")
                self.edge(self.eval(v), n, f"v{i}")
        return n

    def e_Starred(self, e):
        n = self.node("Star", "op", src=self.u(e), line=e.lineno)
        self.edge(self.eval(e.value), n, "o")
        return n

    def e_JoinedStr(self, e):
        n = self.node("FStr", "op", src=self.u(e), line=e.lineno)
        for i, v in enumerate(e.values):
            self.edge(self.eval(v.value if isinstance(v, ast.FormattedValue) else v), n, f"p{i}")
        return n

    def e_FormattedValue(self, e):
        return self.eval(e.value)

    def e_NamedExpr(self, e):
        v = self.eval(e.value)
        self.env[e.target.id] = v
        return v

    def e_IfExp(self, e):      # only reached where the normalizer could not make it a statement
        cond = self.eval(e.test)
        br = self.node("Branch", "branch", src=f"if {self.u(e.test)}", line=e.lineno)
        self.edge(cond, br, "cond")
        self.link_ctl(br)
        self.ctl.append((br, "T"))
        a = self.eval(e.body)
        self.ctl.pop()
        self.ctl.append((br, "F"))
        b = self.eval(e.orelse)
        self.ctl.pop()
        phi = self.node("Phi", "phi", src=self.u(e), line=e.lineno)
        self.edge(a, phi, "then")
        self.edge(b, phi, "else")
        self.edge(br, phi, "ctl:M")
        return phi

    def e_Lambda(self, e):
        lam = self.node("Lambda", "op", src=self.u(e), line=e.lineno)
        saved, self.env = self.env, dict(self.env)
        a = e.args
        for i, p in enumerate(list(a.posonlyargs) + list(a.args) + ([a.vararg] if a.vararg else [])
                              + list(a.kwonlyargs) + ([a.kwarg] if a.kwarg else [])):
            pid = self.node(f"LParam({i})", "param", src=p.arg, line=e.lineno)
            self.edge(lam, pid, "param")
            self.env[p.arg] = pid
        self.edge(self.eval(e.body), lam, "body")
        self.env = saved
        return lam

    def _comp(self, e, kind):  # only inside lambdas; elsewhere the normalizer produced loops
        saved, self.env = self.env, dict(self.env)
        comp = self.node(f"Comp({kind})", "call", src=self.u(e), line=e.lineno)
        for g in e.generators:
            it = self.eval(g.iter)
            self.edge(it, comp, "iter")
            el = self.node("Elem", "elem", src=self.u(g.target), line=e.lineno)
            self.edge(it, el, "elem")
            self.assign_target(g.target, el)
            for c in g.ifs:
                self.edge(self.eval(c), comp, "if")
        if kind == "dict":
            self.edge(self.eval(e.key), comp, "k")
            self.edge(self.eval(e.value), comp, "v")
        else:
            self.edge(self.eval(e.elt), comp, "elt")
        self.env = saved
        return comp

    def e_ListComp(self, e): return self._comp(e, "list")
    def e_SetComp(self, e): return self._comp(e, "set")
    def e_GeneratorExp(self, e): return self._comp(e, "list")
    def e_DictComp(self, e): return self._comp(e, "dict")

    def e_Yield(self, e):
        n = self.node("Yield", "return", src=self.u(e), line=e.lineno)
        if e.value is not None:
            self.edge(self.eval(e.value), n, "val")
        self.link_ctl(n)
        return n

    def e_YieldFrom(self, e):
        n = self.node("YieldFrom", "return", src=self.u(e), line=e.lineno)
        self.edge(self.eval(e.value), n, "val")
        self.link_ctl(n)
        return n

    def e_Await(self, e):
        return self.eval(e.value)


# ------------------------------------------------------------------ public API
def build_graph(source, entry_point=None):
    """Parse ``source`` and return a networkx.MultiDiGraph. Raises SyntaxError on bad code."""
    return GraphBuilder(source, entry_point).build()


def graph_to_dict(G):
    return {
        "meta": dict(G.graph),
        "nodes": [{"id": n, **{k: v for k, v in d.items()}} for n, d in G.nodes(data=True)],
        "edges": [{"source": u, "target": v, "label": d["label"]} for u, v, d in G.edges(data=True)],
    }
