#!/usr/bin/env python3
"""Fail if a binary-float-noise magnitude is baked in as a numeric literal.

`PlainQuantity.to_compact()` divides by a power of ten, so an exactly specified
`100e-9 F` comes back as `99.99999999999999 nanofarad` and `2.2e6` as
`2.1999999999999997 megaohm`. Nothing else catches it: pyright sees a well-typed
quantity, the build reports ok, and the string goes to the BOM. The tell that
someone met the bug and pinned it instead of fixing it is a literal like
`99.99999999999999` sitting in an assertion.

Tokenizes rather than greps, deliberately. A comment or docstring that
*describes* the trap -- which good code does -- is not a finding, and a plain
regex over the file text flags it, punishing the candidate that documented the
hazard. Only NUMBER tokens are inspected.

Usage:  float_noise.py <dir>
Exit:   0 clean, 1 findings, 2 usage error.
"""

from __future__ import annotations

import io
import re
import sys
import tokenize
from pathlib import Path

# A run of >= 8 identical trailing digits (9s or 0s) after the decimal point is
# representation error, not a number anyone typed on purpose.
NOISE = re.compile(r"\.\d*?(9{8,}|0{8,}\d)")


def findings_in(path: Path) -> list[tuple[int, str]]:
    out = []
    try:
        with path.open("rb") as fh:
            for tok in tokenize.tokenize(fh.readline):
                if tok.type == tokenize.NUMBER and NOISE.search(tok.string):
                    out.append((tok.start[0], tok.string))
    except (tokenize.TokenError, SyntaxError, UnicodeDecodeError):
        return []
    return out


def main(argv: list[str]) -> int:
    if len(argv) != 2 or not Path(argv[1]).is_dir():
        print("usage: float_noise.py <dir>", file=sys.stderr)
        return 2
    total = 0
    for path in sorted(Path(argv[1]).rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        for lineno, literal in findings_in(path):
            print(
                f"{path}:{lineno}: numeric literal {literal} carries binary-float "
                f"noise -- an exact value was rounded through a scaling step and the "
                f"result pinned. Round the scaled magnitude back to significant "
                f"figures instead of asserting the noise."
            )
            total += 1
    if total:
        print(f"\n{total} float-noise literal(s)", file=sys.stderr)
        return 1
    print("no float-noise numeric literals", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
