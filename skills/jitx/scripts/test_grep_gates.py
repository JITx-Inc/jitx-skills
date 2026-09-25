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


if __name__ == "__main__":
    unittest.main(verbosity=2)
