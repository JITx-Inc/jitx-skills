#!/usr/bin/env python3
"""check_routing_fixtures.py — cross-file consistency for skills/*/evals/routing.jsonl.

A routing fixture states where an intent should route. The same intent is
deliberately repeated across skill files — a positive in the skill that owns it,
a negative in each sibling that nearly does — which makes it a fact with several
copies and no owner. The copy nobody updates is the copy that goes stale, and a
routing suite that disagrees with itself scores whichever file it read last.

This script is the owner. It checks, across every fixture file:

  1. every non-comment line is valid JSON with an `intent` key
  2. `expected_skill` names a skill directory that exists, or is null
  3. `ambiguous_with` entries name skill directories that exist
  4. a skill never lists itself in its own `ambiguous_with`
  5. an intent appearing in two files carries the SAME expected_skill and the
     SAME ambiguous_with set in both
  6. every skill carrying a routing.jsonl has at least one positive and one
     negative — a fixture file of positives only cannot detect over-triggering

Exit codes:
  0  — consistent
  1  — at least one finding
  2  — usage error

Usage:
  python3 scripts/check_routing_fixtures.py [repo-root]
"""

from __future__ import annotations

import collections
import json
import sys
from pathlib import Path


def load(path: Path) -> list[tuple[int, dict]]:
    rows = []
    for lineno, raw in enumerate(path.read_text().splitlines(), 1):
        text = raw.strip()
        if not text or text.startswith("//"):
            continue
        try:
            rows.append((lineno, json.loads(text)))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{lineno}: invalid JSON — {exc}") from exc
    return rows


def main(argv: list[str]) -> int:
    if len(argv) > 2:
        print(__doc__, file=sys.stderr)
        return 2
    root = Path(argv[1] if len(argv) == 2 else ".").resolve()
    skills_dir = root / "skills"
    if not skills_dir.is_dir():
        print(f"no skills/ directory under {root}", file=sys.stderr)
        return 2

    known = {p.name for p in skills_dir.iterdir() if p.is_dir()}
    findings: list[str] = []
    seen: dict[str, list[tuple[str, int, object, tuple[str, ...]]]] = collections.defaultdict(list)
    files = sorted(skills_dir.glob("*/evals/routing.jsonl"))

    for path in files:
        owner = path.relative_to(skills_dir).parts[0]
        try:
            rows = load(path)
        except ValueError as exc:
            findings.append(str(exc))
            continue

        positives = negatives = 0
        for lineno, row in rows:
            where = f"{path.relative_to(root)}:{lineno}"
            intent = row.get("intent")
            if not isinstance(intent, str) or not intent:
                findings.append(f"{where}: missing or empty `intent`")
                continue

            expected = row.get("expected_skill", "__absent__")
            if expected == "__absent__":
                findings.append(f"{where}: missing `expected_skill` (use null for out-of-bundle)")
                continue
            if expected is not None and expected not in known:
                findings.append(f"{where}: expected_skill '{expected}' is not a skill directory")

            ambiguous = row.get("ambiguous_with") or []
            if not isinstance(ambiguous, list):
                findings.append(f"{where}: `ambiguous_with` must be a list")
                ambiguous = []
            for name in ambiguous:
                if name not in known:
                    findings.append(f"{where}: ambiguous_with '{name}' is not a skill directory")
                if name == expected:
                    findings.append(
                        f"{where}: ambiguous_with repeats expected_skill '{name}'"
                    )

            if expected == owner:
                positives += 1
            else:
                negatives += 1

            seen[intent].append((owner, lineno, expected, tuple(sorted(ambiguous))))

        if rows and positives == 0:
            findings.append(f"{path.relative_to(root)}: no positives — nothing routes TO this skill")
        if rows and negatives == 0:
            findings.append(
                f"{path.relative_to(root)}: no negatives — a positives-only file "
                "cannot detect over-triggering"
            )

    for intent, occurrences in sorted(seen.items()):
        if len(occurrences) < 2:
            continue
        verdicts = {(exp, amb) for _, _, exp, amb in occurrences}
        if len(verdicts) > 1:
            detail = "; ".join(
                f"{owner}:{lineno} -> expected={exp} ambiguous_with={list(amb)}"
                for owner, lineno, exp, amb in occurrences
            )
            findings.append(f"intent disagrees across files: {intent!r} — {detail}")

    print(f"checked {len(files)} fixture file(s), {len(seen)} distinct intent(s)", file=sys.stderr)
    if findings:
        for f in findings:
            print(f)
        print(f"\n{len(findings)} finding(s)", file=sys.stderr)
        return 1
    print("routing fixtures consistent", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
