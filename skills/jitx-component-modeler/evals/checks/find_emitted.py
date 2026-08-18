#!/usr/bin/env python3
"""Print the path of the emitted component module under an output tree.

Used by the `component-from-pin-file` eval case so its assertions can address the
emitted module without hardcoding where it sits.

Why this exists: the case originally pinned `<output>/components/acme_fx500.py`.
A run then placed it at `components/fpgas/acme_fx500.py` — which is *more*
correct, because the skill's "Output Location" asks for
`components/<category>/<manufacturer>_<mpn>.py`. Pinning the flat path would
have marked a skill-compliant layout as wrong. That is the same over-specifying
mistake the CLI assertions made three runs running: the harness asserting an
incidental choice instead of the property it actually cares about.

Heuristic: among `*.py` under the tree, the emitted module is the one declaring
the most `Port()`s. That is what "emitted module" means here, and it does not
depend on filename, directory, or category.

Usage:
    python3 find_emitted.py <output-dir>

Prints the path on success and exits 0; exits 1 with a reason if no candidate is
found, so a caller can `set -e` on it.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_PORT = re.compile(r"\bPort\(\)")
# Directories that never hold the emitted module.
_SKIP = {".ruff_cache", ".pytest_cache", "__pycache__", ".git", "tests"}


def find(root: Path) -> tuple[Path | None, int]:
    best: Path | None = None
    best_count = 0
    for path in sorted(root.rglob("*.py")):
        if any(part in _SKIP for part in path.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        count = len(_PORT.findall(text))
        if count > best_count:
            best, best_count = path, count
    return best, best_count


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    root = Path(argv[1])
    if not root.is_dir():
        print(f"not a directory: {root}", file=sys.stderr)
        return 2
    module, count = find(root)
    if module is None:
        print(f"no module declaring Port() found under {root}", file=sys.stderr)
        return 1
    print(module)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
