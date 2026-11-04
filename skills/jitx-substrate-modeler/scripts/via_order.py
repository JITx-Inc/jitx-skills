"""Check that every via in a substrate file runs top to bottom.

Verify step 1 runs it on the substrate file. `Via` layer indexes are
absolute and do not flip (the `jitx.via.Via` docstring), so `start_layer` is the
upper layer and `stop_layer` the lower, whichever side the via is drilled from.
A via written the other way (`start_layer = -1, stop_layer = -2`) spans nothing:
`ViaDiameter.stack()` and the via's copper come out empty, with no build warning.

Reads the files with `ast`, so nothing is imported or built. A layer is an int
literal, a negated one, `Side.Top` / `Side.Bottom` (0 and -1), or a name the
file binds exactly once to one of those (`IDX_L11 = -2`). The order of
two layers is known without the layer count when both have the same sign, or when
the start is non-negative and the stop negative; a negative start with a
non-negative stop is always reversed. A via whose layers are other expressions is
listed as unchecked.

Usage: via_order.py <board.py> [...]
Exit: 0 every checked via runs top to bottom and at least one via was checked;
1 a reversed via, or no via checked; 2 a file that does not parse.
"""

import ast
import sys

SIDES = {"Top": 0, "Bottom": -1}


def layer(node: ast.expr, names: dict[str, int] | None = None) -> int | None:
    if isinstance(node, ast.Name) and names is not None:
        return names.get(node.id)
    if isinstance(node, ast.Constant) and type(node.value) is int:
        return node.value
    if (
        isinstance(node, ast.UnaryOp)
        and isinstance(node.op, ast.USub)
        and isinstance(node.operand, ast.Constant)
        and type(node.operand.value) is int
    ):
        return -node.operand.value
    if (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "Side"
    ):
        return SIDES.get(node.attr)
    return None


def layer_names(tree: ast.Module) -> dict[str, int]:
    """Names bound exactly once in the file, each to a layer literal."""
    bound: dict[str, list[ast.expr]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            pairs = [(t, node.value) for t in node.targets]
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            pairs = [(node.target, node.value)]
        else:
            continue
        for target, value in pairs:
            if isinstance(target, ast.Name):
                bound.setdefault(target.id, []).append(value)
    names = {}
    for name, values in bound.items():
        if len(values) == 1 and (value := layer(values[0])) is not None:
            names[name] = value
    return names


def reversed_span(start: int, stop: int) -> bool:
    if (start >= 0) == (stop >= 0):
        return start > stop
    return start < 0


def main(paths: list[str]) -> int:
    checked = 0
    bad = []
    unchecked = []
    for path in paths:
        try:
            with open(path, encoding="utf-8") as f:
                tree = ast.parse(f.read(), path)
        except (OSError, SyntaxError) as e:
            print(f"cannot parse {path}: {e}")
            return 2
        names = layer_names(tree)
        for cls in ast.walk(tree):
            if not isinstance(cls, ast.ClassDef):
                continue
            values = {}
            for stmt in cls.body:
                if isinstance(stmt, ast.Assign):
                    targets, value = stmt.targets, stmt.value
                elif isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
                    targets, value = [stmt.target], stmt.value
                else:
                    continue
                for t in targets:
                    if isinstance(t, ast.Name) and t.id in (
                        "start_layer",
                        "stop_layer",
                    ):
                        values[t.id] = value
            if len(values) < 2:
                continue
            start = layer(values["start_layer"], names)
            stop = layer(values["stop_layer"], names)
            where = f"{path}:{cls.lineno} {cls.name}"
            if start is None or stop is None:
                unchecked.append(where)
                continue
            checked += 1
            if reversed_span(start, stop):
                bad.append(f"{where}: start_layer = {start}, stop_layer = {stop}")
    for line in bad:
        print(f"REVERSED  {line}")
    for line in unchecked:
        print(f"UNCHECKED {line}")
    print(f"{checked} via(s) checked, {len(bad)} reversed, {len(unchecked)} unchecked")
    return 1 if bad or not checked else 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1:]))
