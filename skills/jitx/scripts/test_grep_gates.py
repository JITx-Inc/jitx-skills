#!/usr/bin/env python3
"""Regression tests for fail-closed grep-gate source traversal."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("grep_gates.py")


class GrepGateTraversalTests(unittest.TestCase):
    @unittest.skipIf(
        not hasattr(os, "geteuid") or os.geteuid() == 0,
        "permission errors cannot be induced reliably as root/on this platform",
    )
    def test_unreadable_file_is_environment_error_with_path(self) -> None:
        with tempfile.TemporaryDirectory(prefix="grep-gates-test-") as temporary:
            source = Path(temporary) / "blocked.py"
            source.write_text("print('unreadable')\n", encoding="utf-8")
            source.chmod(0)
            try:
                result = subprocess.run(
                    [sys.executable, str(SCRIPT), temporary],
                    capture_output=True,
                    text=True,
                    check=False,
                )
            finally:
                source.chmod(0o600)

        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn(str(source), result.stderr)
        self.assertIn("source scan incomplete", result.stderr)
        self.assertNotIn("PASS (hard-fail set clean)", result.stdout)

    @unittest.skipIf(
        not hasattr(os, "geteuid") or os.geteuid() == 0,
        "permission errors cannot be induced reliably as root/on this platform",
    )
    def test_unreadable_directory_is_environment_error_with_path(self) -> None:
        with tempfile.TemporaryDirectory(prefix="grep-gates-test-") as temporary:
            blocked = Path(temporary) / "blocked"
            blocked.mkdir()
            (blocked / "hidden.py").write_text("print('hidden')\n", encoding="utf-8")
            blocked.chmod(0)
            try:
                result = subprocess.run(
                    [sys.executable, str(SCRIPT), temporary],
                    capture_output=True,
                    text=True,
                    check=False,
                )
            finally:
                blocked.chmod(0o700)

        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn(str(blocked), result.stderr)
        self.assertIn("source scan incomplete", result.stderr)
        self.assertNotIn("PASS (hard-fail set clean)", result.stdout)


SHORT_TRACE_LABEL = "no ShortTrace("


def run_gates(files: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """Write `files` into a fresh source tree and run the gates over it."""
    with tempfile.TemporaryDirectory(prefix="grep-gates-test-") as temporary:
        for name, text in files.items():
            path = Path(temporary) / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        return subprocess.run(
            [sys.executable, str(SCRIPT), temporary],
            capture_output=True,
            text=True,
            check=False,
        )


def shorttrace_gate_hits(result: subprocess.CompletedProcess[str]) -> list[str]:
    """The hit lines listed under the power-rail capacitor gate, if it fired."""
    lines = result.stdout.splitlines()
    for index, line in enumerate(lines):
        if line.lstrip().startswith("HIT") and SHORT_TRACE_LABEL in line:
            return [
                hit.strip() for hit in lines[index + 1 :] if hit.startswith("      ")
            ]
    return []


DECOUPLED = """\
from jitx.net import Net, ShortTrace
from jitxlib.parts import Capacitor


class Rail(Circuit):
    def __init__(self) -> None:
        self.c_vdd = Capacitor(capacitance=100e-9 * F)
        self.nets = [
            ShortTrace(self.c_vdd.p1, self.ic.VDD),
            Net([self.c_vdd.p2, self.gnd]),
        ]
"""

UNDECOUPLED = """\
from jitx.net import Net
from jitxlib.parts import Capacitor


class Rail(Circuit):
    def __init__(self) -> None:
        self.c_vdd = Capacitor(capacitance=100e-9 * F)
        self.nets = [Net([self.c_vdd.p1, self.ic.VDD]), Net([self.c_vdd.p2, self.gnd])]
"""


class PowerRailCapacitorGateTests(unittest.TestCase):
    def test_capacitor_without_shorttrace_is_review_hit(self) -> None:
        result = run_gates({"rail.py": UNDECOUPLED})
        hits = shorttrace_gate_hits(result)
        self.assertEqual(len(hits), 1, result.stdout)
        self.assertIn("rail.py:7:", hits[0])
        self.assertIn("review-required hits: 1", result.stdout)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_capacitor_with_shorttrace_in_file_passes(self) -> None:
        result = run_gates({"rail.py": DECOUPLED})
        self.assertEqual(shorttrace_gate_hits(result), [], result.stdout)
        self.assertIn("review-required hits: 0", result.stdout)

    def test_shorttrace_only_in_a_comment_does_not_count(self) -> None:
        text = UNDECOUPLED.replace(
            "class Rail", "# decouple with ShortTrace(self.c_vdd.p1, pin)\nclass Rail"
        )
        result = run_gates({"rail.py": text})
        self.assertEqual(len(shorttrace_gate_hits(result)), 1, result.stdout)

    def test_shorttrace_is_judged_per_file(self) -> None:
        result = run_gates({"a_rail.py": DECOUPLED, "b_rail.py": UNDECOUPLED})
        hits = shorttrace_gate_hits(result)
        self.assertEqual(len(hits), 1, result.stdout)
        self.assertIn("b_rail.py:7:", hits[0])

    def test_other_capacitor_names_and_inserts_are_not_hits(self) -> None:
        text = (
            "class BlockingCapacitor(jitx.Component):\n"
            "    pass\n"
            "self.cap = BlockingCapacitor(100e-9)\n"
            "self.bulk = PolarizedCapacitor(capacitance=100e-6 * F)\n"
            "caps = [c for _, c in rd.query(Capacitor)]\n"
            "self.insert(via)\n"
        )
        result = run_gates({"other.py": text})
        self.assertEqual(shorttrace_gate_hits(result), [], result.stdout)
        self.assertNotIn(".insert(", result.stdout)
        self.assertIn("review-required hits: 0", result.stdout)

    def test_no_insert_gate_remains(self) -> None:
        # jitxlib-parts 2.x has no `.insert`; an unassigned passive whose ports
        # join a net fails the build, so a source pattern for it is not a gate.
        text = "Resistor(resistance=10e3).insert(mcu.NRST, v3v3)\n"
        result = run_gates({"legacy.py": text})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("hard-fail hits: 0", result.stdout)
        self.assertNotIn(".insert(", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
