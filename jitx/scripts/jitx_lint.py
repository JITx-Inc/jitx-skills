#!/usr/bin/env python3
"""Lint JITX Python files for common hardware design mistakes.

Catches anti-patterns that compile fine but produce incorrect hardware:
rectangular cutouts (should be circle/capsule), hardcoded feedback
dividers, pull-ups to high-voltage rails, missing self. storage, etc.

Usage:
    python jitx_lint.py src/myproject/components/
    python jitx_lint.py src/myproject/circuits/ src/myproject/main.py
    python jitx_lint.py --severity warning .

Run this during acceptance review or as part of the Phase 3b audit.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class LintIssue:
    file: str
    line: int
    severity: str  # "error", "warning", "note"
    code: str
    message: str

    def __str__(self) -> str:
        return f"{self.file}:{self.line}: [{self.severity.upper()}] {self.code}: {self.message}"


# ---------------------------------------------------------------------------
# Lint rules
# ---------------------------------------------------------------------------

def check_square_cutout(path: str, lines: list[str]) -> list[LintIssue]:
    """Square Cutout(rectangle(x, x)) where w==h likely should be circle(r)."""
    issues = []
    for i, line in enumerate(lines, 1):
        m = re.search(r'Cutout\s*\(\s*rectangle\s*\(\s*([\d.]+)\s*,\s*([\d.]+)\s*\)', line)
        if m:
            w, h = float(m.group(1)), float(m.group(2))
            if abs(w - h) < 0.01:
                issues.append(LintIssue(
                    path, i, "warning", "W005",
                    f"Square cutout rectangle({w}, {h}) — if this is a round drill hole, use circle({w/2:.4g}) instead"
                ))
    return issues


def check_hardcoded_feedback_divider(path: str, lines: list[str]) -> list[LintIssue]:
    """Feedback dividers should use voltage_divider_from_constraints(), not manual values."""
    issues = []
    # Look for patterns like: Resistor near FB pin without solver
    fb_context = False
    for i, line in enumerate(lines, 1):
        lower = line.lower()
        if 'fb' in lower or 'feedback' in lower:
            fb_context = True
        if fb_context and re.search(r'Resistor\s*\(\s*resistance\s*=\s*[\d.]+', line):
            # Check if voltage_divider_from_constraints is used nearby
            nearby = '\n'.join(lines[max(0, i-10):min(len(lines), i+10)])
            if 'voltage_divider_from_constraints' not in nearby:
                issues.append(LintIssue(
                    path, i, "warning", "W001",
                    "Resistor near FB/feedback — should this use voltage_divider_from_constraints()?"
                ))
            fb_context = False
        if not ('fb' in lower or 'feedback' in lower):
            fb_context = False
    return issues


def check_vbus_pullup(path: str, lines: list[str]) -> list[LintIssue]:
    """Pull-ups to VBUS or high-voltage rails will damage 3.3V logic."""
    issues = []
    for i, line in enumerate(lines, 1):
        # Look for resistor insert between VBUS/VIN and a signal
        if re.search(r'\.(insert|__iadd__|__add__)', line) or '+=' in line:
            if re.search(r'[Vv][Bb][Uu][Ss]|[Vv][Ii][Nn]|PVDD|net_vbus|net_vin', line):
                # Check if it's a pull-up pattern (resistor between power and signal)
                if re.search(r'[Rr]_?(pull|pu|sda|scl|i2c|spi|int|fault|gpio)', line):
                    issues.append(LintIssue(
                        path, i, "error", "E002",
                        "Pull-up/pull-down to VBUS/VIN — this is likely a high-voltage rail. "
                        "Pull-ups should go to 3.3V or appropriate logic-level rail."
                    ))
    return issues


def check_bare_net_expression(path: str, lines: list[str]) -> list[LintIssue]:
    """Net expressions not stored on self are silently dropped."""
    issues = []
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        # Look for standalone port + port expressions not assigned to anything
        if re.match(r'^self\.\w+\.\w+\s*\+\s*self\.\w+\.\w+\s*$', stripped):
            issues.append(LintIssue(
                path, i, "error", "E003",
                "Net expression not stored — use 'self.net_name += ...' or 'self += ...'. "
                "Bare expressions are silently dropped."
            ))
        # Check for bare >> topology
        if re.match(r'^self\.\w+\.\w+\s*>>\s*self\.\w+\.\w+\s*$', stripped):
            issues.append(LintIssue(
                path, i, "error", "E004",
                "Topology expression not stored — use 'self.topo = ...' or 'self += ...'. "
                "Bare >> expressions are silently dropped."
            ))
    return issues


def check_anonymous_component(path: str, lines: list[str]) -> list[LintIssue]:
    """Components not stored on self fail at build time."""
    issues = []
    for i, line in enumerate(lines, 1):
        # Resistor(...).insert() or Capacitor(...).insert() without self. assignment
        if re.search(r'\b(Resistor|Capacitor|Inductor)\s*\([^)]*\)\s*\.insert\s*\(', line):
            if 'self.' not in line.split('.insert')[0]:
                issues.append(LintIssue(
                    path, i, "error", "E005",
                    "Anonymous component .insert() — store on self first: "
                    "'self.r1 = Resistor(...); self.r1.insert(...)'"
                ))
    return issues


def check_i2c_pullup_in_subcircuit(path: str, lines: list[str]) -> list[LintIssue]:
    """I2C pull-ups should be at top level, not inside subcircuits."""
    issues = []
    # Skip if this looks like a top-level design (has SampleDesign or Board)
    full_text = '\n'.join(lines)
    if 'SampleDesign' in full_text or re.search(r'class\s+\w+.*\bBoard\b', full_text):
        return issues

    for i, line in enumerate(lines, 1):
        if re.search(r'[Rr]_?(sda|scl|i2c).*pull', line, re.IGNORECASE):
            issues.append(LintIssue(
                path, i, "warning", "W002",
                "I2C pull-up in subcircuit — pull-ups for shared buses should be at the top-level design, "
                "not inside individual circuits."
            ))
        if re.search(r'pull.*(sda|scl|i2c)', line, re.IGNORECASE):
            issues.append(LintIssue(
                path, i, "warning", "W002",
                "I2C pull-up in subcircuit — pull-ups for shared buses should be at the top-level design."
            ))
    return issues


def check_missing_si_constraint(path: str, lines: list[str]) -> list[LintIssue]:
    """Top-level designs with >> topologies should have Constrain/ConstrainDiffPair."""
    issues = []
    full_text = '\n'.join(lines)
    # Only check top-level designs
    if 'SampleDesign' not in full_text:
        return issues

    has_topology = '>>' in full_text
    has_constraint = 'Constrain' in full_text or 'ReferencePlanes' in full_text
    if has_topology and not has_constraint:
        issues.append(LintIssue(
            path, 1, "warning", "W003",
            "Design has >> topologies but no SI constraints (Constrain/ConstrainDiffPair). "
            "High-speed interfaces need impedance and timing constraints."
        ))
    return issues


def check_hard_tied_dual_function(path: str, lines: list[str]) -> list[LintIssue]:
    """Dual-function pins hard-tied to GND/VCC instead of using resistors."""
    issues = []
    for i, line in enumerate(lines, 1):
        # Pattern: net += pin + GND where pin name suggests dual function
        if re.search(r'(ADR|FAULT|MODE|CFG|ADDR|SEL).*\+.*GND|GND.*\+.*(ADR|FAULT|MODE|CFG|ADDR|SEL)', line, re.IGNORECASE):
            # Check it's a direct net tie, not through a resistor
            nearby = '\n'.join(lines[max(0, i-3):min(len(lines), i+3)])
            if 'Resistor' not in nearby and 'resistor' not in nearby:
                issues.append(LintIssue(
                    path, i, "warning", "W004",
                    "Dual-function pin appears hard-tied to GND — use a resistor for address/mode "
                    "pins that also serve as outputs (e.g., ADR_FAULT)."
                ))
    return issues


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def check_thermal_pad_aspect(path: str, lines: list[str]) -> list[LintIssue]:
    """Thermal pads on SOIC/TSSOP/QFN should typically be wider than tall (or square).

    HTSSOP/TSSOP/SOIC packages have pins on the long sides, so the package is
    taller than wide. The thermal pad usually follows the body proportion.
    A thermal pad that is wider than tall on a tall package is likely swapped.
    """
    issues = []
    full_text = '\n'.join(lines)
    # Only check files that look like components (have Landpattern/thermal_pad)
    if 'thermal_pad' not in full_text:
        return issues

    # Detect package orientation from body dimensions or pin count clues
    # HTSSOP/TSSOP/SOIC with many pins: body is taller than wide
    is_tall_package = bool(re.search(r'HTSSOP|TSSOP|SOIC|SSOP|DFN.*[12]\d', full_text, re.IGNORECASE))

    # Search across joined text for multi-line thermal_pad calls
    full = '\n'.join(lines)
    for m in re.finditer(r'thermal_pad\s*\([^)]*rectangle\s*\(\s*([\d.]+)\s*,\s*([\d.]+)\s*\)', full, re.DOTALL):
        w, h = float(m.group(1)), float(m.group(2))
        line_num = full[:m.start()].count('\n') + 1
        if is_tall_package and w > h * 1.15:
            issues.append(LintIssue(
                path, line_num, "warning", "W006",
                f"Thermal pad rectangle({w}, {h}) is wider than tall on a tall package — "
                f"check if width/height are swapped. TI convention: D=along pins (Y), E=across (X). "
                f"Use rectangle(E2, D2) not rectangle(D2, E2)."
            ))
    return issues


ALL_CHECKS = [
    check_square_cutout,
    check_thermal_pad_aspect,
    check_hardcoded_feedback_divider,
    check_vbus_pullup,
    check_bare_net_expression,
    check_anonymous_component,
    check_i2c_pullup_in_subcircuit,
    check_missing_si_constraint,
    check_hard_tied_dual_function,
]


def lint_file(path: Path) -> list[LintIssue]:
    """Run all lint checks on a single Python file."""
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return []

    lines = text.splitlines()
    issues: list[LintIssue] = []
    for check in ALL_CHECKS:
        issues.extend(check(str(path), lines))
    return issues


def lint_paths(paths: list[Path], min_severity: str = "note") -> list[LintIssue]:
    """Lint all .py files under the given paths."""
    severity_order = {"error": 0, "warning": 1, "note": 2}
    min_level = severity_order.get(min_severity, 2)

    all_issues: list[LintIssue] = []
    for p in paths:
        if p.is_file() and p.suffix == ".py":
            all_issues.extend(lint_file(p))
        elif p.is_dir():
            for f in sorted(p.rglob("*.py")):
                all_issues.extend(lint_file(f))

    return [i for i in all_issues if severity_order.get(i.severity, 2) <= min_level]


def main():
    parser = argparse.ArgumentParser(
        description="Lint JITX Python files for common hardware design mistakes.",
    )
    parser.add_argument("paths", nargs="+", help="Files or directories to lint")
    parser.add_argument(
        "--severity", default="note", choices=["error", "warning", "note"],
        help="Minimum severity to report (default: note)",
    )
    args = parser.parse_args()

    issues = lint_paths([Path(p) for p in args.paths], args.severity)

    if not issues:
        print("No issues found.")
        sys.exit(0)

    errors = 0
    for issue in sorted(issues, key=lambda i: (i.file, i.line)):
        print(issue)
        if issue.severity == "error":
            errors += 1

    print(f"\n{len(issues)} issue(s) found ({errors} error(s)).")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
