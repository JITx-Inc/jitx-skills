#!/usr/bin/env python3
"""Check a generated component module's rail-list lengths against expected counts.

Used by the `component-from-pin-file` eval case. The counts are a property of the
fixture, so they are the one thing about a generated module that can be asserted
deterministically without a reference solution.

Why this is a script and not a regex in the case file: the naive check
(`NAME = [Port() for _ in range(N)]`) rejects correct output. A rail of
no-connects is legitimately written `[Port().no_connect() for _ in range(N)]`,
and a type-annotated declaration is legitimately `NAME: list[Port] = [...]` --
so a pattern pinned to the bare form fails the very solutions the case's other
assertions require. An assertion that cannot pass is worse than no assertion.

What this deliberately does NOT check: that the element expression is a `Port`.
That is the build's job, and pinning it here would re-introduce the brittleness
above.

Usage:
    python3 rail_counts.py <output-dir> NAME=COUNT [NAME=COUNT ...]

Exits 0 when every named rail is declared as an indexed list of the expected
length, 1 with a per-rail explanation otherwise, 2 on usage error.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# NAME, an optional type annotation, `=`, then any bracketed comprehension whose
# range() bound is the length. Tolerates `Port()`, `Port().no_connect()`, line
# breaks after `[`, and an annotated left-hand side.
_DECL = r"^[ \t]*{name}[ \t]*(?::[^=\n]+)?=[ \t]*\[(?:.|\n)*?range\((\d+)\)"


def find_module(root: Path) -> Path | None:
    """The emitted module is the .py file declaring the most of the rails."""
    best, best_hits = None, 0
    for path in sorted(root.rglob("*.py")):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        hits = text.count("range(")
        if hits > best_hits:
            best, best_hits = path, hits
    return best


def check(text: str, expected: dict[str, int]) -> list[str]:
    problems = []
    for name, count in expected.items():
        match = re.search(_DECL.format(name=re.escape(name)), text, re.MULTILINE)
        if match is None:
            problems.append(f"{name}: not declared as an indexed rail list")
        elif int(match.group(1)) != count:
            problems.append(f"{name}: range({match.group(1)}), expected range({count})")
    return problems


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__, file=sys.stderr)
        return 2
    root = Path(argv[1])
    if not root.is_dir():
        print(f"not a directory: {root}", file=sys.stderr)
        return 2

    expected: dict[str, int] = {}
    for arg in argv[2:]:
        if "=" not in arg:
            print(f"expected NAME=COUNT, got {arg!r}", file=sys.stderr)
            return 2
        name, _, raw = arg.partition("=")
        if not raw.isdigit():
            print(f"expected NAME=COUNT with an integer count, got {arg!r}", file=sys.stderr)
            return 2
        expected[name] = int(raw)

    module = find_module(root)
    if module is None:
        print(f"no emitted module found under {root}", file=sys.stderr)
        return 1

    problems = check(module.read_text(encoding="utf-8", errors="replace"), expected)
    if problems:
        print(f"{module}: " + "; ".join(problems), file=sys.stderr)
        return 1
    print(f"{module}: all {len(expected)} rail counts match")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
