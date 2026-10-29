"""Check how a runner's output writes jitxlib-parts passive queries.

Used by the `constrained-passive-query` and `decoupling-scaled-to-pins` eval
cases. Each check reads the `.py` files directly under the output directory (or
the files named) with `ast`, so nesting, line breaks and comments do not move it.

Why this is a script and not a regex in the case file: whether a key reaches a
passive's query depends on where the query comes from, which a pattern cannot
see. `_Passive.__init__` resolves through `PartQuery.resolve_context`
(jitxlib/parts/query.py): an explicit query argument replaces the context, the
innermost active context replaces any outer one (so a `with CapacitorQuery(...)`
block replaces the Design default for the parts built inside it and covers none
outside it), and keywords in the call apply last.

Subcommands:

    require-key <output> <Part> <key>
        Every <Part>(...) call (Resistor, Capacitor, PolarizedCapacitor,
        Inductor) gets <key> from one of: a keyword in the call; the query
        passed to it, written inline or bound to a name in the same file; else
        the innermost enclosing `with <Query>(...)` of its category; else, with
        no such block, a <Query>(...) assigned as a class attribute of a Design
        subclass. Fails when a call gets it from none, or when there is no call.

    no-key <output> <Part>[,<Part>...] <key>
        No <Part>(...) call, and no call to that part's query class (a query
        passed to it, a `with` block or a Design default), carries <key>.

    no-case <output>
        No `case=` in a ResistorQuery/CapacitorQuery/InductorQuery call or a
        Resistor/Capacitor/PolarizedCapacitor/Inductor call, except a query
        assigned as a class attribute of a Design subclass (the one place a
        minimum package belongs).

    no-insert <output>
        No jitxlib-parts 1.x passive `.insert(`: any `<expr>.insert(` whose first
        argument is not index-like fails. Index-like is an integer literal
        (signed or not), `len(...)`, a `bisect` call, a name such as `i`, `j`,
        `k`, `n`, `idx` or `index`, or arithmetic over those. `sys.path.insert(`
        always passes.

Exits 0 when the check holds, 1 with one line per offending call otherwise, 2 on
a usage error or a file that does not parse.
"""

from __future__ import annotations

import ast
import re
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

PART_QUERY: dict[str, str] = {
    "Resistor": "ResistorQuery",
    "Capacitor": "CapacitorQuery",
    "PolarizedCapacitor": "CapacitorQuery",
    "Inductor": "InductorQuery",
}
QUERIES: frozenset[str] = frozenset(PART_QUERY.values())
INDEX_NAME = re.compile(
    r"^(?:[ijkn]|\w*idx\w*|\w*index\w*|pos|position)$", re.IGNORECASE
)


@dataclass(frozen=True)
class Source:
    path: Path
    tree: ast.Module


def callee(node: ast.Call) -> str | None:
    """The called name: `Resistor` for `Resistor(...)` and `parts.Resistor(...)`."""
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def keywords(node: ast.Call) -> set[str]:
    return {k.arg for k in node.keywords if k.arg is not None}


def load(target: str) -> list[Source]:
    root = Path(target)
    files = sorted(root.glob("*.py")) if root.is_dir() else [root]
    out: list[Source] = []
    for f in files:
        try:
            out.append(Source(f, ast.parse(f.read_text(), filename=str(f))))
        except SyntaxError as e:
            print(f"error: {f} does not parse: {e}", file=sys.stderr)
            raise SystemExit(2) from e
    return out


def design_classes(sources: list[Source]) -> list[ast.ClassDef]:
    """Classes whose bases end in `Design`, or that subclass such a class here."""
    classes = [
        n for s in sources for n in ast.walk(s.tree) if isinstance(n, ast.ClassDef)
    ]
    names: set[str] = set()
    changed = True
    while changed:
        changed = False
        for c in classes:
            if c.name in names:
                continue
            for b in c.bases:
                base = (
                    b.id
                    if isinstance(b, ast.Name)
                    else b.attr
                    if isinstance(b, ast.Attribute)
                    else ""
                )
                if base.endswith("Design") or base in names:
                    names.add(c.name)
                    changed = True
                    break
    return [c for c in classes if c.name in names]


def design_defaults(sources: list[Source]) -> list[ast.Call]:
    """Query calls assigned directly in a Design subclass body."""
    out: list[ast.Call] = []
    for c in design_classes(sources):
        for stmt in c.body:
            value = (
                stmt.value if isinstance(stmt, (ast.Assign, ast.AnnAssign)) else None
            )
            if isinstance(value, ast.Call) and callee(value) in QUERIES:
                out.append(value)
    return out


def parents(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    return {
        child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)
    }


def bindings(tree: ast.Module) -> dict[str, list[ast.expr]]:
    """Every value assigned to a name or attribute, keyed by its source text."""
    out: dict[str, list[ast.expr]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                out.setdefault(ast.unparse(t), []).append(node.value)
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            out.setdefault(ast.unparse(node.target), []).append(node.value)
    return out


def query_has(
    expr: ast.expr, query: str, key: str, bound: dict[str, list[ast.expr]]
) -> bool:
    """True when `expr` is a `query` call carrying `key`, directly or through a name."""
    if isinstance(expr, ast.Call):
        return callee(expr) == query and key in keywords(expr)
    values = bound.get(ast.unparse(expr), [])
    return bool(values) and all(
        isinstance(v, ast.Call) and callee(v) == query and key in keywords(v)
        for v in values
    )


def enclosing_with(
    node: ast.AST, query: str, up: dict[ast.AST, ast.AST]
) -> ast.Call | None:
    """The innermost `with <query>(...)` item lexically enclosing `node`."""
    cur = up.get(node)
    while cur is not None:
        if isinstance(cur, (ast.With, ast.AsyncWith)):
            for item in reversed(cur.items):
                e = item.context_expr
                if isinstance(e, ast.Call) and callee(e) == query:
                    return e
        cur = up.get(cur)
    return None


def require_key(sources: list[Source], part: str, key: str) -> list[str]:
    query = PART_QUERY[part]
    by_default = any(
        callee(d) == query and key in keywords(d) for d in design_defaults(sources)
    )
    bad: list[str] = []
    seen = 0
    for s in sources:
        up = parents(s.tree)
        bound = bindings(s.tree)
        for node in ast.walk(s.tree):
            if not (isinstance(node, ast.Call) and callee(node) == part):
                continue
            seen += 1
            if key in keywords(node):
                continue
            explicit = (
                node.args[0]
                if node.args
                else next((k.value for k in node.keywords if k.arg == "query"), None)
            )
            if explicit is not None:
                ok = query_has(explicit, query, key, bound)
            else:
                block = enclosing_with(node, query, up)
                ok = key in keywords(block) if block is not None else by_default
            if not ok:
                bad.append(f"{s.path}:{node.lineno}: {ast.unparse(node)}")
    if not seen:
        bad.append(f"no {part}(...) call in the output")
    return bad


def no_case(sources: list[Source]) -> list[str]:
    allowed = {id(d) for d in design_defaults(sources)}
    names = QUERIES | PART_QUERY.keys()
    bad: list[str] = []
    for s in sources:
        for node in ast.walk(s.tree):
            if (
                isinstance(node, ast.Call)
                and callee(node) in names
                and "case" in keywords(node)
                and id(node) not in allowed
            ):
                bad.append(f"{s.path}:{node.lineno}: {ast.unparse(node)}")
    return bad


def no_key(sources: list[Source], parts: list[str], key: str) -> list[str]:
    names = {n for p in parts for n in (p, PART_QUERY[p])}
    bad: list[str] = []
    for s, node in calls(sources):
        if callee(node) in names and key in keywords(node):
            bad.append(f"{s.path}:{node.lineno}: {ast.unparse(node)}")
    return bad


def index_like(expr: ast.expr) -> bool:
    if isinstance(expr, ast.Constant):
        return isinstance(expr.value, int) and not isinstance(expr.value, bool)
    if isinstance(expr, ast.UnaryOp) and isinstance(expr.op, (ast.USub, ast.UAdd)):
        return index_like(expr.operand)
    if isinstance(expr, ast.BinOp):
        return index_like(expr.left) and index_like(expr.right)
    if isinstance(expr, ast.Name):
        return bool(INDEX_NAME.match(expr.id))
    if isinstance(expr, ast.Call):
        name = callee(expr) or ""
        return name == "len" or name.startswith("bisect")
    return False


def calls(sources: list[Source]) -> Iterator[tuple[Source, ast.Call]]:
    for s in sources:
        for node in ast.walk(s.tree):
            if isinstance(node, ast.Call):
                yield s, node


def no_insert(sources: list[Source]) -> list[str]:
    bad: list[str] = []
    for s, node in calls(sources):
        f = node.func
        if not (isinstance(f, ast.Attribute) and f.attr == "insert"):
            continue
        if ast.unparse(f.value) == "sys.path":
            continue
        if node.args and index_like(node.args[0]):
            continue
        bad.append(f"{s.path}:{node.lineno}: {ast.unparse(node)}")
    return bad


def main(argv: list[str]) -> int:
    usage = (
        "usage: passive_calls.py require-key <output> <Part> <key>\n"
        "       passive_calls.py no-key <output> <Part>[,<Part>...] <key>\n"
        "       passive_calls.py no-case <output>\n"
        "       passive_calls.py no-insert <output>"
    )
    if len(argv) == 4 and argv[0] == "require-key" and argv[2] in PART_QUERY:
        bad = require_key(load(argv[1]), argv[2], argv[3])
    elif (
        len(argv) == 4
        and argv[0] == "no-key"
        and all(p in PART_QUERY for p in argv[2].split(","))
    ):
        bad = no_key(load(argv[1]), argv[2].split(","), argv[3])
    elif len(argv) == 2 and argv[0] == "no-case":
        bad = no_case(load(argv[1]))
    elif len(argv) == 2 and argv[0] == "no-insert":
        bad = no_insert(load(argv[1]))
    else:
        print(usage, file=sys.stderr)
        return 2
    for line in bad:
        print(line)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
