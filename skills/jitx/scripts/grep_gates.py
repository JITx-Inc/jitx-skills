#!/usr/bin/env python3
# grep_gates.py — JITX skill grep-gate enforcement (cross-platform: bash + PowerShell)
#
# Runs the pattern set defined in jitx/references/completion-blocks.md.
# Reports hard-fail and review-required hits in the project's Python source.
#
# Pure stdlib (os/re/sys), so one file runs from bash AND PowerShell on every OS —
# no `bash`, `grep`, or `ripgrep` dependency.
#
# Usage:
#   python grep_gates.py <src-dir>
#   python grep_gates.py <src-dir> --quiet
#   TOP_LEVEL_PATH=designs python grep_gates.py <src-dir>      # bash — default 'designs'
#   $env:TOP_LEVEL_PATH="top"; python grep_gates.py <src-dir>; Remove-Item Env:TOP_LEVEL_PATH   # PowerShell override (one-shot)
#
# Exit codes:
#   0  — no hard-fail hits (review-required hits don't fail; they need disposition in task acceptance block)
#   1  — at least one hard-fail hit
#   2  — usage or environment error (including an incomplete source scan)
#
# Output format mirrors completion-blocks.md "Grep gates" reporting:
#   ok    no hits: <label>
#   HIT N <label>
#       <file:line:match>
#
# Scanning model: line-oriented — one regex search per source line, reproducing the
# line semantics of `grep -rEn` / `rg -n`: `^`/`$` anchor per source line, and the hit
# count is the number of matching LINES (a line matching twice counts once). File
# SELECTION is a deliberate contract change from the old script: it scans every *.py
# and does NOT honor .gitignore (the rg branch did, the grep branch didn't — so the
# old gate's coverage depended on whether rg was installed; this removes that drift).
# The file list is sorted, so output is deterministic.

import os
import re
import sys

TOP_LEVEL_PATH = os.environ.get("TOP_LEVEL_PATH", "designs")

hard_fail = 0
review = 0


def usage_error():
    prog = os.path.basename(sys.argv[0])
    print(f"Usage: python {prog} <src-dir> [--quiet]", file=sys.stderr)
    print(
        "  TOP_LEVEL_PATH (env, default 'designs'): top-level design dir name "
        "to exclude from top-level-only checks",
        file=sys.stderr,
    )
    sys.exit(2)


def print_help():
    prog = os.path.basename(sys.argv[0])
    print(f"Usage: python {prog} <src-dir> [--quiet]")
    print()
    print("Run the JITX grep-gate pattern set against Python source files.")
    print()
    print("Options:")
    print("  --quiet  print only hits, counts, and the final verdict")
    print("  -h, --help  show this help message and exit")


def iter_py_files(root, errors):
    """Yield Python paths and retain every directory traversal error."""

    def onerror(error):
        errors.append(error)

    for dirpath, dirnames, filenames in os.walk(root, onerror=onerror):
        dirnames.sort()
        for fn in sorted(filenames):
            if fn.endswith(".py"):
                yield os.path.join(dirpath, fn)


def scan_sources(src_dir):
    """Read the source tree once, returning files and every traversal/open error."""

    files = {}
    errors = []
    for path in iter_py_files(src_dir, errors):
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                files[path] = [raw.rstrip("\r\n") for raw in fh]
        except OSError as error:
            errors.append(error)
    return files, errors


def excluded_from_top_level_check(path, src_dir):
    """Return whether a file is below a directory named TOP_LEVEL_PATH."""

    relative = os.path.relpath(path, src_dir)
    return TOP_LEVEL_PATH in relative.split(os.sep)[:-1]


def run_search(pattern, exclude_top, src_dir, source_files):
    """Return [(path, lineno, line), ...] — mirrors `grep -rEn` / `rg -n`."""
    rx = re.compile(pattern)
    hits = []
    for path, lines in source_files.items():
        if exclude_top and excluded_from_top_level_check(path, src_dir):
            continue
        for lineno, line in enumerate(lines, start=1):
            if rx.search(line):
                hits.append((path, lineno, line))
    return hits


def report(label, hits, severity, quiet):
    global hard_fail, review
    if not hits:
        if not quiet:
            print(f"  ok    no hits: {label}")
        return
    count = len(hits)  # matching LINES, == `wc -l` on grep output
    print(f"  HIT {count} {label}")
    for path, lineno, line in hits:
        print(f"      {path}:{lineno}:{line}")
    if severity == "hard-fail":
        hard_fail += count
    else:
        review += count


def run_check(
    label,
    pattern,
    exclude_top,
    severity,
    src_dir,
    source_files,
    quiet,
    skip=None,
):
    hits = run_search(pattern, exclude_top, src_dir, source_files)
    if skip:
        hits = [h for h in hits if not skip(h[0])]
    report(label, hits, severity, quiet)


def is_si_definition_site(path):
    """Paths where an SI constructor call is a definition or a harness, not a
    misplaced application.

    The pattern below cannot tell `Constrain(...)` inside a SignalConstraint
    class from `Constrain(...)` misapplied inside an ordinary subcircuit, and a
    hard-fail that fires on correct code teaches agents to route around the gate.
    Narrowing where it looks is the fix; dropping its severity would leave the
    rule enforced only by self-reported prose.
    """
    norm = path.replace(os.sep, "/")
    parts = norm.split("/")
    base = parts[-1]
    return (
        "constraints" in parts
        or base == "main.py"
        or base.startswith("test_")
        or base.endswith("_test.py")
        or "tests" in parts
    )


def report_insert(hits, quiet):
    # Special case keeps the .sh's two slightly different labels (ok vs HIT line).
    global review
    if not hits:
        if not quiet:
            print(
                "  ok    no hits: .insert(...) missing short_trace= (power-rail cap default)"
            )
        return
    count = len(hits)
    print(
        f"  HIT {count} .insert(...) calls missing short_trace= (power-rail cap default)"
    )
    for path, lineno, line in hits:
        print(f"      {path}:{lineno}:{line}")
    review += count


def main():
    args = sys.argv[1:]
    if "-h" in args or "--help" in args:
        print_help()
        sys.exit(0)
    quiet = "--quiet" in args
    positional = [arg for arg in args if arg != "--quiet"]
    if (
        len(positional) != 1
        or not positional[0]
        or any(arg.startswith("-") for arg in positional)
    ):
        usage_error()
    src_dir = positional[0]
    if not os.path.isdir(src_dir):
        usage_error()

    source_files, scan_errors = scan_sources(src_dir)
    if scan_errors:
        for error in scan_errors:
            path = getattr(error, "filename", None) or src_dir
            detail = getattr(error, "strerror", None) or str(error)
            print(f"ERROR scanning {path}: {detail}", file=sys.stderr)
        print(
            "ERROR — source scan incomplete; grep gates did not run.",
            file=sys.stderr,
        )
        sys.exit(2)

    if not quiet:
        print(f"grep_gates: scanning {src_dir} (top-level dir = {TOP_LEVEL_PATH})")
        print()
        print("=== hard-fail patterns ===")

    # SI / top-level applications outside designs/, excluding the paths where
    # such a call is a definition or a harness rather than a misplaced
    # application. Imports are not caught (no `(` after the name).
    run_check(
        f"SI/top-level applications outside {TOP_LEVEL_PATH}/",
        r"\b(ReferencePlanes|Constrain|ConstrainDiffPair|ConstrainReferenceDifference)\s*\(",
        True,
        "hard-fail",
        src_dir,
        source_files,
        quiet,
        skip=is_si_definition_site,
    )

    # Net symbols outside designs/
    run_check(
        f"Net symbols (GroundSymbol/PowerSymbol) outside {TOP_LEVEL_PATH}/",
        r"\b(GroundSymbol|PowerSymbol)\s*\(",
        True,
        "hard-fail",
        src_dir,
        source_files,
        quiet,
    )

    # setattr/getattr on self anywhere — JITX convention violation
    run_check(
        "setattr/getattr on self (JITX convention)",
        r"\b(setattr|getattr)\s*\(\s*self\b",
        False,
        "hard-fail",
        src_dir,
        source_files,
        quiet,
    )

    # Anonymous structural insert anywhere — silent-drop pattern 1
    # Misses nested constructor args (e.g., Resistor(resistance=Toleranced.percent(...)).insert(...))
    # but catches the most common form.
    run_check(
        "Anonymous structural .insert(...) — silent-drop pattern 1",
        r"\b(Capacitor|Resistor|Inductor)\s*\([^)]*\)\s*\.insert\s*\(",
        False,
        "hard-fail",
        src_dir,
        source_files,
        quiet,
    )

    if not quiet:
        print()
        print("=== review-required patterns ===")

    # Module-scope for-loops — anti-string-hacking theme 9. Module-import-time
    # logic populating global tables is the named failure mode.
    run_check(
        "Module-scope for-loop — review for module-import-time logic",
        r"^for\s+\w+\s+in\s+",
        False,
        "review",
        src_dir,
        source_files,
        quiet,
    )

    # Pour(..., isolate=...) — legacy parameter, Pass 3 deprecates in favor of design_constraint with Tags
    run_check(
        "Pour(..., isolate=...) — legacy parameter (see Pass 3 deprecation)",
        r"\bPour\s*\([^)]*\bisolate\s*=",
        False,
        "review",
        src_dir,
        source_files,
        quiet,
    )

    # Bare net/topology expression — silent-drop pattern 2
    # Allows trailing comments and bracket indexes (self.mcu.PA[5]).
    run_check(
        "Bare net/topology expression — silent-drop pattern 2",
        r"^\s*self\.\w+(\.\w+|\[[^\]]+\])*\s*(\+|>>)\s*self\.\w+(\.\w+|\[[^\]]+\])*(\s*#.*)?$",
        False,
        "review",
        src_dir,
        source_files,
        quiet,
    )

    # Dynamic type(...) call — JITX disallows runtime type construction; isinstance is the right check
    run_check(
        "type(...) call — verify not used for runtime type construction",
        r"\btype\s*\(",
        False,
        "review",
        src_dir,
        source_files,
        quiet,
    )

    # Tag-like f-string construction — anti-string-hacking theme 1. f-strings
    # starting with an uppercase letter and building names with a brace
    # substitution (f"TX_b{i}", f"L{n}_via") are the canonical failure mode.
    run_check(
        "Tag-like f-string (anti-string-hacking — string-keyed names)",
        r"""[fF]["'][A-Z][A-Za-z0-9_]*\{""",
        False,
        "review",
        src_dir,
        source_files,
        quiet,
    )

    # Broader getattr( call — the narrower hard-fail above catches getattr(self, ...).
    # This wider review-required catches getattr(other, "...") string-indirection cases.
    run_check(
        "getattr( — review for string-keyed indirection on non-self objects",
        r"\bgetattr\s*\(",
        False,
        "review",
        src_dir,
        source_files,
        quiet,
    )

    # I2C pull-ups outside designs/ — shared-bus components belong at the
    # bus-aggregation level (usually the top-level design).
    run_check(
        f"I2C pull-up (r_sda/r_scl) outside {TOP_LEVEL_PATH}/ — review bus-aggregation level",
        r"\br_(sda|scl)\b",
        True,
        "review",
        src_dir,
        source_files,
        quiet,
    )

    # .insert(...) calls missing short_trace= — Phase 2 power-rail cap gate.
    # Search .insert( then drop lines whose code text already passes short_trace=
    # (substring test is on the matched line, not the file path). False
    # positives on resistor/inductor inserts and non-power-rail caps (AC coupling,
    # RC, RF, crystal load) — agent dispositions each per
    # jitx-circuit-builder/SKILL.md "short_trace=True is the default for power-rail capacitors".
    insert_hits = [
        (p, n, t)
        for (p, n, t) in run_search(r"\.insert\s*\(", False, src_dir, source_files)
        if "short_trace" not in t
    ]
    report_insert(insert_hits, quiet)

    if not quiet:
        print()
        print("=== summary ===")
    print(f"hard-fail hits: {hard_fail}")
    print(f"review-required hits: {review} (need disposition in task acceptance block)")

    if hard_fail > 0:
        if not quiet:
            print()
        print("FAIL — fix hard-fail hits before emitting the task acceptance block.")
        sys.exit(1)

    if not quiet:
        print()
    print("PASS (hard-fail set clean)")
    sys.exit(0)


if __name__ == "__main__":
    main()
