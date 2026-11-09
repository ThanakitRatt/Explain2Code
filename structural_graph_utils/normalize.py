"""AST normalization: strip style differences before the graph is built.

Everything here is meant to make two *logically identical* programs produce
identical ASTs, regardless of naming, formatting, comments, annotations or
common syntactic sugar.  Variable names are not handled here: the graph
builder never uses them (variables are replaced by data-flow edges).
"""
import ast
import copy
import itertools

SWAP = {ast.Gt: ast.Lt, ast.GtE: ast.LtE}
NEGATE = {
    ast.Eq: ast.NotEq, ast.NotEq: ast.Eq, ast.In: ast.NotIn, ast.NotIn: ast.In,
    ast.Is: ast.IsNot, ast.IsNot: ast.Is,
    ast.Lt: ast.GtE, ast.GtE: ast.Lt, ast.Gt: ast.LtE, ast.LtE: ast.Gt,
}
STMT_FIELDS = ("body", "orelse", "finalbody")


def _canon_compare(left, op, right, like):
    """a > b  ->  b < a ;  a >= b  ->  b <= a  (single canonical direction)."""
    if type(op) in SWAP:
        left, right = right, left
        op = SWAP[type(op)]()
    return ast.copy_location(ast.Compare(left=left, ops=[op], comparators=[right]), like)


def _is_const(node, value):
    return (isinstance(node, ast.Constant) and not isinstance(node.value, bool)
            and node.value == value)


def _set_locations(nodes, like):
    for root in nodes:
        for n in ast.walk(root):
            if "lineno" in n._attributes and not hasattr(n, "lineno"):
                ast.copy_location(n, like)


class Normalizer(ast.NodeTransformer):
    def __init__(self):
        self.pre = []            # statements hoisted out of the current statement
        self.counter = itertools.count()
        self.no_hoist = 0        # >0 inside lambdas / while-tests: do not hoist comprehensions

    # ------------------------------------------------------------ plumbing
    def visit_stmts(self, stmts):
        out = []
        for s in stmts:
            saved, self.pre = self.pre, []
            new = self.visit(s)
            hoisted, self.pre = self.pre, saved
            out.extend(hoisted)
            if new is None:
                continue
            if isinstance(new, list):
                out.extend(new)
            else:
                out.append(new)
        return out

    def generic_visit(self, node):
        for field, old in ast.iter_fields(node):
            if (field in STMT_FIELDS and isinstance(old, list) and old
                    and isinstance(old[0], ast.stmt)):
                setattr(node, field, self.visit_stmts(old))
            elif isinstance(old, list):
                new = []
                for v in old:
                    if isinstance(v, ast.AST):
                        v = self.visit(v)
                        if v is None:
                            continue
                        if not isinstance(v, ast.AST):
                            new.extend(v)
                            continue
                    new.append(v)
                old[:] = new
            elif isinstance(old, ast.AST):
                nv = self.visit(old)
                if nv is None:
                    delattr(node, field)
                else:
                    setattr(node, field, nv)
        return node

    # ---------------------------------------------------------- definitions
    @staticmethod
    def _strip_args(args):
        for a in (args.posonlyargs + args.args + args.kwonlyargs
                  + [x for x in (args.vararg, args.kwarg) if x]):
            a.annotation = None

    def visit_FunctionDef(self, node):
        node.decorator_list = []
        self.generic_visit(node)
        node.body = node.body or [ast.copy_location(ast.Pass(), node)]
        return node

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node):
        node.decorator_list = []
        self.generic_visit(node)
        node.body = node.body or [ast.copy_location(ast.Pass(), node)]
        return node

    def visit_Lambda(self, node):
        self.no_hoist += 1
        self.generic_visit(node)
        self.no_hoist -= 1
        return node

    # ----------------------------------------------------------- statements
    def visit_Expr(self, node):
        v = node.value
        if isinstance(v, ast.Constant):          # docstrings, bare literals, ...
            return None
        if isinstance(v, ast.Call) and isinstance(v.func, ast.Name) and v.func.id == "print":
            # keep the print call itself (it is an action), ignore the text it prints
            v.args = [a for a in v.args if not isinstance(a, (ast.Constant, ast.JoinedStr))]
        self.generic_visit(node)
        return node

    def visit_Assert(self, node):
        return None

    def visit_AnnAssign(self, node):
        hint = ast.copy_location(ast.AnnAssign(target=node.target, annotation=node.annotation,
                                               value=None, simple=node.simple), node)
        if node.value is None:
            return hint                          # a bare annotation still counts as a type hint
        new = ast.copy_location(ast.Assign(targets=[node.target], value=node.value), node)
        res = self.visit(new)
        return [hint] + (res if isinstance(res, list) else [res])

    def visit_AugAssign(self, node):
        self.generic_visit(node)
        load = copy.deepcopy(node.target)
        load.ctx = ast.Load()
        new = ast.Assign(targets=[node.target],
                         value=ast.BinOp(left=load, op=node.op, right=node.value))
        _set_locations([new], node)
        return ast.copy_location(new, node)

    def visit_Assign(self, node):
        self.generic_visit(node)
        v = node.value
        if (isinstance(v, ast.IfExp) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)):
            name = node.targets[0].id

            def mk(val):
                return ast.copy_location(
                    ast.Assign(targets=[ast.Name(id=name, ctx=ast.Store())], value=val), node)
            new = ast.copy_location(ast.If(test=v.test, body=[mk(v.body)], orelse=[mk(v.orelse)]), node)
            return self._norm_if(new)
        return node

    def visit_Return(self, node):
        self.generic_visit(node)
        v = node.value
        if isinstance(v, ast.IfExp):
            def mk(val):
                return ast.copy_location(ast.Return(value=val), node)
            new = ast.copy_location(ast.If(test=v.test, body=[mk(v.body)], orelse=[mk(v.orelse)]), node)
            return self._norm_if(new)
        return node

    @staticmethod
    def _norm_if(node):
        t = node.test
        if isinstance(t, ast.UnaryOp) and isinstance(t.op, ast.Not) and node.orelse:
            node.test = t.operand
            node.body, node.orelse = node.orelse, node.body
        return node

    def visit_If(self, node):
        self.generic_visit(node)
        return self._norm_if(node)

    def visit_While(self, node):
        self.no_hoist += 1
        node.test = self.visit(node.test)
        self.no_hoist -= 1
        node.body = self.visit_stmts(node.body)
        node.orelse = self.visit_stmts(node.orelse)
        return node

    # ---------------------------------------------------------- expressions
    def visit_Compare(self, node):
        self.generic_visit(node)
        if len(node.ops) == 1:
            return _canon_compare(node.left, node.ops[0], node.comparators[0], node)
        parts, left = [], node.left
        for op, right in zip(node.ops, node.comparators):
            parts.append(_canon_compare(left, op, right, node))
            left = right
        return ast.copy_location(ast.BoolOp(op=ast.And(), values=parts), node)

    def visit_UnaryOp(self, node):
        self.generic_visit(node)
        o = node.operand
        if (isinstance(node.op, (ast.USub, ast.UAdd)) and isinstance(o, ast.Constant)
                and isinstance(o.value, (int, float)) and not isinstance(o.value, bool)):
            v = -o.value if isinstance(node.op, ast.USub) else o.value
            return ast.copy_location(ast.Constant(value=v), node)
        if (isinstance(node.op, ast.Not) and isinstance(o, ast.Compare)
                and len(o.ops) == 1 and type(o.ops[0]) in NEGATE):
            return _canon_compare(o.left, NEGATE[type(o.ops[0])](), o.comparators[0], node)
        return node

    def visit_Call(self, node):
        self.generic_visit(node)
        f = node.func
        if isinstance(f, ast.Name) and f.id == "range" and not node.keywords:
            a = list(node.args)
            if len(a) == 3 and _is_const(a[2], 1):
                a = a[:2]
            if len(a) == 2 and _is_const(a[0], 0):
                a = a[1:]
            node.args = a
        return node

    # --------------------------------------------------------- comprehensions
    def visit_ListComp(self, node):
        return self._comp(node, "list")

    def visit_GeneratorExp(self, node):
        return self._comp(node, "list")      # sum(x for ..) == sum([x for ..])

    def visit_SetComp(self, node):
        return self._comp(node, "set")

    def visit_DictComp(self, node):
        return self._comp(node, "dict")

    def _comp(self, node, kind):
        """Rewrite a comprehension as the explicit loop it stands for.

            [f(x) for x in xs if c(x)]   ->   t = []
                                              for x in xs:
                                                  if c(x): t.append(f(x))
        """
        if self.no_hoist:
            self.generic_visit(node)
            return node
        name = f"_c{next(self.counter)}"

        def load():
            return ast.Name(id=name, ctx=ast.Load())

        if kind == "list":
            init = ast.List(elts=[], ctx=ast.Load())
            inner = ast.Expr(value=ast.Call(
                func=ast.Attribute(value=load(), attr="append", ctx=ast.Load()),
                args=[node.elt], keywords=[]))
        elif kind == "set":
            init = ast.Call(func=ast.Name(id="set", ctx=ast.Load()), args=[], keywords=[])
            inner = ast.Expr(value=ast.Call(
                func=ast.Attribute(value=load(), attr="add", ctx=ast.Load()),
                args=[node.elt], keywords=[]))
        else:
            init = ast.Dict(keys=[], values=[])
            inner = ast.Assign(
                targets=[ast.Subscript(value=load(), slice=node.key, ctx=ast.Store())],
                value=node.value)
        stmts = [inner]
        for gen in reversed(node.generators):
            for cond in reversed(gen.ifs):
                stmts = [ast.If(test=cond, body=stmts, orelse=[])]
            stmts = [ast.For(target=gen.target, iter=gen.iter, body=stmts, orelse=[])]
        all_stmts = [ast.Assign(targets=[ast.Name(id=name, ctx=ast.Store())], value=init)] + stmts
        _set_locations(all_stmts, node)
        saved_pre, self.pre = self.pre, []
        done = self.visit_stmts(all_stmts)
        self.pre = saved_pre + done
        return ast.copy_location(load(), node)


def normalize(tree):
    tree = Normalizer().visit(tree)
    return ast.fix_missing_locations(tree)
