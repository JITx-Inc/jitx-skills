"""Check that every via in a substrate file runs top to bottom.

Verify step 1 runs it on the substrate file. Layer indexes are absolute in the
board (the `jitx.via.Via` docstring), and `ViaDiameter.stack()` walks from
`start_layer` down to `stop_layer`, so `start_layer` is the upper layer and
`stop_layer` the lower, whichever side the via is drilled from. A via written the
other way (`start_layer = -1, stop_layer = -2`) spans nothing: the stack and the
via's copper come out empty, with no build warning.

Reads the files with `ast`, so nothing is imported or built. A layer is an int
literal, a negated one, `Side.Top` / `Side.Bottom` (0 and -1), or a name the
file binds exactly once to one of those (`IDX_L11 = -2`). A negative index counts
from the bottom, so on N copper layers index i is layer N + i, as jitx normalizes
it. With `--layers N` every span is decided that way. Without it, a span whose
indexes share a sign, or that starts at 0 or stops at -1, is decided; any other
span depends on the layer count and is listed as unchecked. So is a via whose layers are other expressions, and a class that
sets only one of `start_layer` and `stop_layer`.

Usage: via_order.py [--layers N] <board.py> [...]
  --layers N  the board's copper layer count
Exit: 0 every via was checked and runs top to bottom; 1 a reversed via, an
unchecked via, or no via found; 2 a usage error or a file that does not parse.
"""

import argparse
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


def reversed_span(start: int, stop: int, layers: int | None = None) -> bool | None:
    """True for a bottom-to-top span, False for top to bottom, None when it
    depends on a layer count not given, or an index falls outside `layers`."""
    if layers is not None:
        a = start if start >= 0 else layers + start
        b = stop if stop >= 0 else layers + stop
        if not (0 <= a < layers and 0 <= b < layers):
            return None
        return a > b
    if (start >= 0) == (stop >= 0):
        return start > stop
    if start == 0 or stop == -1:
        return False
    return None


def main(paths: list[str], layers: int | None) -> int:
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
            if not values:
                continue
            where = f"{path}:{cls.lineno} {cls.name}"
            if len(values) < 2:
                unchecked.append(f"{where}: sets only {next(iter(values))}")
                continue
            start = layer(values["start_layer"], names)
            stop = layer(values["stop_layer"], names)
            if start is None or stop is None:
                unchecked.append(f"{where}: a layer is not a literal")
                continue
            verdict = reversed_span(start, stop, layers)
            span = f"start_layer = {start}, stop_layer = {stop}"
            if verdict is None:
                why = (
                    f"outside {layers} layers"
                    if layers is not None
                    else "order depends on the layer count; pass --layers"
                )
                unchecked.append(f"{where}: {span}: {why}")
                continue
            checked += 1
            if verdict:
                bad.append(f"{where}: {span}")
    for line in bad:
        print(f"REVERSED  {line}")
    for line in unchecked:
        print(f"UNCHECKED {line}")
    print(f"{checked} via(s) checked, {len(bad)} reversed, {len(unchecked)} unchecked")
    return 1 if bad or unchecked or not checked else 0


def positive(text: str) -> int:
    n = int(text)
    if n < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return n


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Check that every via in a substrate file runs top to bottom."
    )
    parser.add_argument(
        "--layers", type=positive, help="the board's copper layer count"
    )
    parser.add_argument("paths", nargs="+", metavar="board.py")
    args = parser.parse_args()
    sys.exit(main(args.paths, args.layers))
