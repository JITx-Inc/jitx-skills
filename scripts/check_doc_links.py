#!/usr/bin/env python3
"""check_doc_links.py — link and citation integrity across skills/**/*.md.

A skill cites its own sections and its siblings' sections constantly, and for a
long time it did so in prose: **Bold Section Name** plus a positional hint like
"near the end of this skill" or "below". Two things go wrong with that, and both
went wrong here.

The prose name is usually a *truncation*. `## Component completeness check — run
before calling it done` gets cited as "the Component completeness check block",
which drops the clause carrying the rule. And the positional hint is a claim
about file layout that nothing maintains: reorganize the file and "below" points
at nothing, silently, forever.

A link is the repair, because a link is checkable. This script is what makes it
checkable. It checks, across every markdown file under skills/:

  1. every relative link target file exists
  2. every `#anchor` resolves to a heading in the target file, under GitHub's
     slug rules (lowercase, punctuation dropped entirely, spaces to hyphens —
     so an em dash leaves a DOUBLE hyphen)
  3. no link resolves to an ambiguous anchor — a slug carried by two or more
     headings in the same file, where GitHub silently appends `-1` and the link
     lands on whichever one came first
  4. no bolded or quoted phrase is a strict truncated prefix of a real heading,
     outside the allowlist below — this is the original defect, and it stays
     gateable only because the sweep that introduced this script emptied it
  5. every backticked dotted Python path under a configured destination root
     resolves in the selected interpreter, unless its own line names it with
     the literal marker UNPUBLISHED:<full.path>

Check 4 needs an escape hatch, because the class genuinely contains non-citations:
"Reference Design" names a datasheet section, not a heading. Word-boundary
matching rejects most of those automatically; what survives goes in ALLOWLIST
with a reason, keyed by path so allowlisting one file does not blind the others.
Add a line and say why — do not disable the check.

Check 5 uses module specs where possible, importing parent packages as needed;
attribute pointers import the longest module prefix and walk its attributes.
It checks availability in that interpreter, not publication on a package index,
and does not execute a leaf module just to verify its spec. Use --python PATH
to select the interpreter (default: sys.executable). Repeat --module-root ROOT
to replace the default roots; a root may be dotted, and matches itself plus
everything beneath it, so jitxlib.verify gates that package alone. Imports run in one subprocess per check, with a
30-second timeout; probe failures are findings, never a silent skip.

The marker must name the exact full pointer on the same line, for example
`jitxlib.verify` (UNPUBLISHED:jitxlib.verify). A bare UNPUBLISHED token or a
marker for a parent or another pointer does not exempt it. A backticked `.name`
continues the parent of the most recent full pointer on its line or the line
before: `jitxexamples.patterns.default_rules`, `.net_net_clearance` names two
sibling modules. Mark a continuation with its expanded full path on its own
line. Only whole code spans that are dotted paths are checked, not calls or
slash-separated paths. Matching is syntactic: dotted filenames and examples
of wrong imports also match; surrounding prose does not silently exempt them.
--skip-module-imports disables check 5 and prints a warning on stderr. Citation
report mode only reports check 4 and duplicate slugs, as before.

Fenced code blocks and YAML frontmatter are skipped. Without that, shell comments
(`# Sync project deps from public PyPI...`) parse as headings and the output is
garbage: 16 bogus duplicate-slug hits against 3 real ones, measured.

NOTE ON ENFORCEMENT: this repo has no CI. This script binds only when a reviewer
runs it — it is a documented command in README.md's Validation section, not an
automated gate. Treat a green run as evidence someone checked, not as evidence
the tree was never broken.

Exit codes:
  0  — clean
  1  — at least one finding
  2  — usage error

Usage:
  python3 scripts/check_doc_links.py [repo-root]
  python3 scripts/check_doc_links.py [repo-root] --report-citations
  python3 scripts/check_doc_links.py [repo-root] --python PATH [--module-root ROOT ...]
  python3 scripts/check_doc_links.py [repo-root] --skip-module-imports
"""

from __future__ import annotations

import collections
import json
import re
import subprocess
import sys
from pathlib import Path

# Phrases that look like truncated heading citations but are not, keyed by the
# repo-relative path of the file containing them. Each entry states why.
ALLOWLIST: dict[str, dict[str, str]] = {
    "skills/jitx-circuit-builder/references/advanced-patterns.md": {
        "top-level only": (
            "prose emphasis on a rule, not a citation of the "
            "'Top-Level Only (do NOT put these in subcircuits)' heading"
        ),
    },
    "skills/jitx/references/outside-voice-review.md": {
        "mcu / fpga components": (
            "left-hand label of a task-class table row, not a citation of "
            "domains/component-modeling.md's 'MCU / FPGA Components (Additional)'"
        ),
    },
    "skills/jitx/references/plan-template.md": {
        "data sources": (
            "label for this file's own guidance on the PLAN.md 'Data Sources' section "
            "(the template lives inside a fenced block, so its headings are invisible "
            "to this check) — not a citation of parts-sourcing.md"
        ),
    },
}

FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)\s]+)\)")
# **bold** or "quoted" or “smart-quoted” — the three shapes prose citations take
CITATION_RE = re.compile(r'\*\*([^*\n]{5,90})\*\*|["“]([^"”\n]{5,90})["”]')
# Destinations the restructure moved knowledge to. A root is matched as a dotted
# PREFIX, so "jitxlib.verify" gates that package without dragging in every
# jitxlib.* name a skill mentions in passing. The default set is deliberately not
# {jitx, jitxlib, jitxexamples}: a skill legitimately names modules that do NOT
# exist, in anti-pattern lists ("there is no jitx.bundle, jitx.passives"), and a
# check that cannot tell a pointer from a named counterexample produced 106
# findings against 11 real ones when it was first run. Widen with --module-root
# for a one-off sweep; add a line here when the restructure creates a
# destination that a skill routes to.
MODULE_ROOTS = frozenset({"jitxlib.verify", "jitxexamples.patterns", "jitxexamples.demos"})


def _under_root(pointer: str, roots: frozenset[str]) -> bool:
    """True when a root equals the pointer or is one of its dotted prefixes."""
    return any(pointer == root or pointer.startswith(root + ".") for root in roots)
INLINE_CODE_RE = re.compile(r"(?<!`)(`+)([^`\n]+)\1(?!`)")
DOTTED_PATH = r"[^\W\d]\w*(?:\.[^\W\d]\w*)+"
MODULE_PATH_RE = re.compile(DOTTED_PATH)
UNPUBLISHED_RE = re.compile(r"(?<![\w:])UNPUBLISHED:(" + DOTTED_PATH + r")(?![\w.])")

# Keep the selected interpreter's own sys.path. A caller can use PYTHONPATH to
# add fixtures or packages without injecting this process's site-packages.
MODULE_PROBE = r'''
import contextlib
import importlib
import importlib.util
import json
import sys


def resolve(name):
    parts = name.split(".")
    for size in range(len(parts), 0, -1):
        prefix = ".".join(parts[:size])
        try:
            spec = importlib.util.find_spec(prefix)
        except ModuleNotFoundError as exc:
            if exc.name == prefix or prefix.startswith(str(exc.name) + "."):
                continue
            raise
        if spec is None:
            continue
        if size < len(parts):
            value = importlib.import_module(prefix)
            for attr in parts[size:]:
                value = getattr(value, attr)
        return
    raise ModuleNotFoundError("no importable module prefix")


results = {}
for name in json.load(sys.stdin):
    try:
        with contextlib.redirect_stdout(sys.stderr):
            resolve(name)
    except (Exception, SystemExit) as exc:
        results[name] = type(exc).__name__ + ": " + " ".join(str(exc).split())
    else:
        results[name] = None
json.dump(results, sys.stdout)
'''


def slug(title: str) -> str:
    """Convert a heading to its GitHub anchor.

    Punctuation is dropped, not replaced, which is why `A — B` slugs to `a--b`.
    """
    text = re.sub(r"<[^>]+>", "", title.strip().lower())
    text = re.sub(r"[`*~]", "", text)
    text = re.sub(r"[^\w\s\-]", "", text, flags=re.UNICODE)
    return text.replace(" ", "-")


def normalize(title: str) -> str:
    """Heading text reduced to what a prose citation of it would look like."""
    return re.sub(r"\s+", " ", re.sub(r"[`*]", "", title)).strip().lower()


def body_lines(text: str) -> list[tuple[int, str]]:
    """Numbered lines outside fenced code blocks and outside YAML frontmatter."""
    lines = text.split("\n")
    out: list[tuple[int, str]] = []
    fence: str | None = None
    start = 0
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                start = i + 1
                break
    for i in range(start, len(lines)):
        line = lines[i]
        match = FENCE_RE.match(line)
        if match:
            token = match.group(1)[0] * 3
            if fence is None:
                fence = token
                continue
            if line.strip().startswith(fence):
                fence = None
                continue
        if fence is None:
            out.append((i + 1, line))
    return out


class Doc:
    def __init__(self, path: Path, rel: str) -> None:
        self.path = path
        self.rel = rel
        self.lines = body_lines(path.read_text(encoding="utf-8"))
        self.headings: dict[str, list[tuple[int, str]]] = collections.defaultdict(list)
        self.titles: dict[str, tuple[str, int]] = {}
        for lineno, line in self.lines:
            match = HEADING_RE.match(line)
            if not match:
                continue
            title = match.group(2)
            self.headings[slug(title)].append((lineno, title))
            self.titles.setdefault(normalize(title), (title, lineno))


def collect(root: Path) -> dict[str, Doc]:
    docs: dict[str, Doc] = {}
    for path in sorted((root / "skills").rglob("*.md")):
        rel = path.relative_to(root).as_posix()
        docs[rel] = Doc(path, rel)
    return docs


def check_links(root: Path, docs: dict[str, Doc]) -> list[str]:
    findings: list[str] = []
    for doc in docs.values():
        for lineno, line in doc.lines:
            for match in LINK_RE.finditer(line):
                target = match.group(2)
                if target.startswith(("http://", "https://", "mailto:")):
                    continue
                path_part, _, anchor = target.partition("#")
                where = f"{doc.rel}:{lineno}"
                if path_part:
                    resolved = (doc.path.parent / path_part).resolve()
                    if not resolved.exists():
                        findings.append(f"{where}: link target does not exist — {target}")
                        continue
                    try:
                        rel = resolved.relative_to(root).as_posix()
                    except ValueError:
                        findings.append(f"{where}: link escapes the repo — {target}")
                        continue
                else:
                    rel = doc.rel
                if not anchor:
                    continue
                if rel not in docs:
                    findings.append(f"{where}: anchor into a non-markdown target — {target}")
                    continue
                headings = docs[rel].headings.get(anchor)
                if not headings:
                    findings.append(f"{where}: anchor matches no heading — {target}")
                elif len(headings) > 1:
                    lines = ", ".join(f"L{n}" for n, _ in headings)
                    findings.append(
                        f"{where}: anchor is ambiguous, {len(headings)} headings share "
                        f"slug #{anchor} in {rel} ({lines}) — {target}"
                    )
    return findings


def truncated_citations(docs: dict[str, Doc]) -> list[tuple[str, int, str, list[tuple[str, int, str]], bool]]:
    """Every bolded/quoted phrase that strictly truncates a real heading.

    Returns (rel, lineno, phrase, [(target_rel, target_line, target_title)], allowlisted).
    """
    index: dict[str, list[tuple[str, int, str]]] = collections.defaultdict(list)
    for doc in docs.values():
        for norm, (title, lineno) in doc.titles.items():
            index[norm].append((doc.rel, lineno, title))

    rows = []
    for doc in docs.values():
        allowed = ALLOWLIST.get(doc.rel, {})
        for lineno, line in doc.lines:
            if HEADING_RE.match(line):
                continue
            for match in CITATION_RE.finditer(line):
                raw = match.group(1) or match.group(2)
                if "](" in raw:  # already a link; the link checker owns it
                    continue
                phrase = normalize(raw)
                if len(phrase.split()) < 2 or phrase in index:
                    continue
                targets = []
                for norm, entries in index.items():
                    if not norm.startswith(phrase) or len(norm) <= len(phrase):
                        continue
                    if re.match(r"\w", norm[len(phrase)]):  # word-boundary guard
                        continue
                    targets.extend(entries)
                if targets:
                    rows.append((doc.rel, lineno, phrase, sorted(set(targets)), phrase in allowed))
    return rows


def module_pointers(
    docs: dict[str, Doc], roots: frozenset[str] = MODULE_ROOTS,
) -> list[tuple[str, int, str]]:
    """Return (rel, line, full pointer) for each pointer without its own marker."""
    rows = []
    for doc in docs.values():
        last_full = ""
        last_line = -2
        for lineno, line in doc.lines:
            unpublished = set(UNPUBLISHED_RE.findall(line))
            for match in INLINE_CODE_RE.finditer(line):
                pointer = match.group(2)
                if pointer.startswith(".") and lineno - last_line <= 1:
                    pointer = last_full.rpartition(".")[0] + pointer
                elif MODULE_PATH_RE.fullmatch(pointer) and _under_root(pointer, roots):
                    last_full, last_line = pointer, lineno
                else:
                    continue
                if MODULE_PATH_RE.fullmatch(pointer) and pointer not in unpublished:
                    rows.append((doc.rel, lineno, pointer))
    return rows


def check_module_imports(
    docs: dict[str, Doc], python: str | None = None,
    roots: frozenset[str] = MODULE_ROOTS,
) -> list[str]:
    rows = module_pointers(docs, roots)
    names = sorted({pointer for _, _, pointer in rows})
    if not names:
        return []
    try:
        probe = subprocess.run(
            [python or sys.executable, "-c", MODULE_PROBE],
            input=json.dumps(names), capture_output=True, text=True, timeout=30,
        )
    except subprocess.TimeoutExpired:
        errors = dict.fromkeys(names, "module import probe timed out after 30 seconds")
    else:
        try:
            errors = json.loads(probe.stdout)
            if (
                probe.returncode != 0 or not isinstance(errors, dict)
                or set(errors) != set(names)
                or any(value is not None and not isinstance(value, str) for value in errors.values())
            ):
                raise ValueError("incomplete probe results")
        except ValueError:
            detail = " ".join(probe.stderr.split())
            errors = dict.fromkeys(
                names, f"module import probe failed (exit {probe.returncode}, invalid results): {detail}",
            )
    return [
        f"{rel}:{lineno}: module pointer does not resolve: {pointer} ({errors[pointer]})"
        for rel, lineno, pointer in rows
        if errors[pointer] is not None
    ]


def report(docs: dict[str, Doc]) -> int:
    rows = truncated_citations(docs)
    for rel, lineno, phrase, targets, allowed in sorted(rows):
        tag = "ALLOWED" if allowed else "CITATION"
        print(f"[{tag}] {rel}:{lineno}  {phrase!r}")
        for trel, tline, title in targets:
            print(f"           -> {trel}:{tline}  {title!r}")
    dupes = [
        (doc.rel, s, [n for n, _ in occ])
        for doc in docs.values()
        for s, occ in sorted(doc.headings.items())
        if len(occ) > 1
    ]
    if dupes:
        print("\nduplicate heading slugs (anchors into these are ambiguous):")
        for rel, s, lines in sorted(dupes):
            print(f"  {rel}: #{s} at lines {lines}")
    flagged = sum(1 for r in rows if not r[4])
    print(
        f"\n{len(rows)} truncated citation(s), {flagged} not allowlisted; "
        f"{len(dupes)} duplicate slug(s)",
        file=sys.stderr,
    )
    return 0


def main(argv: list[str]) -> int:
    args = []
    report_only = False
    skip_module_imports = False
    python = sys.executable
    roots = set()
    tokens = iter(argv[1:])
    try:
        for arg in tokens:
            if arg == "--report-citations":
                report_only = True
            elif arg == "--skip-module-imports":
                skip_module_imports = True
            elif arg in {"--python", "--module-root"}:
                value = next(tokens)
                if not value or value.startswith("-"):
                    raise ValueError("missing option value")
                if arg == "--python":
                    python = value
                elif all(part.isidentifier() for part in value.split(".")):
                    roots.add(value)
                else:
                    raise ValueError("module root must be a Python identifier")
            elif arg.startswith("-"):
                raise ValueError("unknown option")
            else:
                args.append(arg)
        if len(args) > 1:
            raise ValueError("too many arguments")
    except (StopIteration, ValueError):
        print(__doc__, file=sys.stderr)
        return 2
    root = Path(args[0] if args else ".").resolve()
    if not (root / "skills").is_dir():
        print(f"no skills/ directory under {root}", file=sys.stderr)
        return 2

    docs = collect(root)
    if skip_module_imports:
        print("WARNING: check 5 SKIPPED (--skip-module-imports); module pointers were not checked", file=sys.stderr)
    if report_only:
        return report(docs)

    findings = check_links(root, docs)
    findings.extend(
        f"{rel}:{lineno}: prose cites a truncated heading {phrase!r} — link it instead "
        f"({'; '.join(f'{t[0]}:{t[1]} {t[2]!r}' for t in targets)})"
        for rel, lineno, phrase, targets, allowed in truncated_citations(docs)
        if not allowed
    )
    if not skip_module_imports:
        try:
            findings.extend(check_module_imports(docs, python, frozenset(roots) if roots else MODULE_ROOTS))
        except OSError as exc:
            print(f"cannot run module import interpreter {python!r}: {exc}", file=sys.stderr)
            return 2

    print(f"checked {len(docs)} markdown file(s) under skills/", file=sys.stderr)
    if findings:
        for finding in sorted(findings):
            print(finding)
        print(f"\n{len(findings)} finding(s)", file=sys.stderr)
        return 1
    print("doc links and citations clean", file=sys.stderr)
    if not skip_module_imports:
        print("module pointers clean", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
