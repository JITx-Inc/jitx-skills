#!/usr/bin/env python3
"""Fail if a component is constructed inside a plain `unittest.TestCase`.

The failure this catches: outside a JITX instantiation context a component
constructor returns a deferred `Instantiable` proxy and `__init__` never runs,
so every fail-fast check in the class silently passes. A negative test written
on a plain `unittest.TestCase` --

    class T(unittest.TestCase):
        def test_bad_size(self):
            with self.assertRaises(ValueError):
                MyPart(size="0505")     # never constructs; never raises

-- fails for the wrong reason, and its positive-case siblings pass while
constructing nothing at all.

What this does NOT flag, deliberately: a plain `unittest.TestCase` that only
exercises pure logic -- a value-code encoder, a table cross-check, a classmethod
that validates arguments without instantiating. Moving validation into a pure
classmethod so it runs everywhere is a legitimate design, and a blunt
"no unittest.TestCase anywhere" grep punishes it. The rule is about
*construction*, not about the base class on its own.

Usage:  construction_context.py <dir> [--component-prefix PREFIX]...
Exit:   0 clean, 1 findings, 2 usage error.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

JITX_CONTEXT_BASES = {"TestCase", "jitx.test.TestCase", "JitxTestCase"}
PLAIN_BASES = {"unittest.TestCase", "TestCase"}  # disambiguated by import below


def _plain_unittest_classes(tree: ast.Module) -> list[ast.ClassDef]:
    """Classes whose base resolves to stdlib unittest.TestCase, not jitx.test's."""
    # `from jitx.test import TestCase` makes a bare `TestCase` the JITX one;
    # `from unittest import TestCase` makes it the stdlib one. Track which.
    bare_testcase_is_jitx = False
    bare_testcase_is_plain = False
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                if (alias.asname or alias.name) != "TestCase":
                    continue
                if node.module.startswith("jitx"):
                    bare_testcase_is_jitx = True
                elif node.module == "unittest":
                    bare_testcase_is_plain = True

    out = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        for base in node.bases:
            rendered = ast.unparse(base)
            if rendered == "unittest.TestCase":
                out.append(node)
                break
            if rendered == "TestCase" and bare_testcase_is_plain and not bare_testcase_is_jitx:
                out.append(node)
                break
    return out


def component_class_names(root: Path) -> set[str]:
    """Names declared anywhere under `root` as a jitx.Component subclass.

    Resolved from the tree rather than guessed from capitalization: constructing
    a `Toleranced` or a `PlainQuantity` in a plain test is entirely fine, and a
    capitalization heuristic flags those too.
    """
    names: set[str] = set()
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text())
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and any(
                ast.unparse(b) in {"jitx.Component", "Component"} for b in node.bases
            ):
                names.add(node.name)
    return names


def _constructions(
    cls: ast.ClassDef, components: set[str], prefixes: tuple[str, ...]
) -> list[tuple[int, str]]:
    hits = []
    for node in ast.walk(cls):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
        if not name:
            continue
        if name in components or (prefixes and name.startswith(prefixes)):
            hits.append((node.lineno, name))
    return hits


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if not a.startswith("--")]
    prefixes = tuple(
        argv[i + 1] for i, a in enumerate(argv) if a == "--component-prefix" and i + 1 < len(argv)
    )
    if len(args) != 1 or not Path(args[0]).is_dir():
        print(__doc__.strip().splitlines()[-3], file=sys.stderr)
        return 2

    root = Path(args[0])
    components = component_class_names(root)
    if not components and not prefixes:
        print(
            "no jitx.Component subclass found under the target; nothing to check "
            "(pass --component-prefix to name them explicitly)",
            file=sys.stderr,
        )
        return 0

    findings = 0
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text())
        except SyntaxError as exc:
            print(f"{path}: does not parse ({exc})", file=sys.stderr)
            findings += 1
            continue
        for cls in _plain_unittest_classes(tree):
            for lineno, name in _constructions(cls, components, prefixes):
                print(
                    f"{path}:{lineno}: {name}(...) constructed in "
                    f"{cls.name}(unittest.TestCase) -- outside a JITX instantiation "
                    f"context __init__ never runs, so this asserts nothing. Subclass "
                    f"jitx.test.TestCase, or move the logic under test into a pure "
                    f"function that does not instantiate."
                )
                findings += 1

    if findings:
        print(f"\n{findings} construction(s) outside a JITX instantiation context", file=sys.stderr)
        return 1
    print("no component construction inside a plain unittest.TestCase", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
