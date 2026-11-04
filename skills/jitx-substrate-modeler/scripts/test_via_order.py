"""Tests for via_order: each verdict it gives, and its exit codes."""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from via_order import reversed_span

SCRIPT = Path(__file__).with_name("via_order.py")


def via(name: str, start: str, stop: str) -> str:
    return f"class {name}(Via):\n    start_layer = {start}\n    stop_layer = {stop}\n"


class ReversedSpan(unittest.TestCase):
    def test_top_to_bottom(self):
        for start, stop in [(0, 1), (0, 2), (-2, -1), (-3, -2), (0, -1), (1, -2)]:
            with self.subTest(start=start, stop=stop):
                self.assertFalse(reversed_span(start, stop))

    def test_bottom_to_top(self):
        # L6 to L5 of a 6-layer board, written in drill direction.
        for start, stop in [(1, 0), (-1, -2), (-2, -3), (-1, 0), (-2, 3)]:
            with self.subTest(start=start, stop=stop):
                self.assertTrue(reversed_span(start, stop))


class Script(unittest.TestCase):
    def run_on(self, source: str) -> subprocess.CompletedProcess[str]:
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(source)
        self.addCleanup(os.unlink, f.name)
        return subprocess.run(
            [sys.executable, str(SCRIPT), f.name],
            check=False,
            capture_output=True,
            text=True,
        )

    def test_clean(self):
        r = self.run_on(
            via("TH", "Side.Top", "Side.Bottom")
            + via("UV1", "0", "1")
            + via("UV2", "-2", "-1")
        )
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("3 via(s) checked, 0 reversed, 0 unchecked", r.stdout)

    def test_reversed(self):
        r = self.run_on(via("UV1", "0", "1") + via("UV2", "-1", "-2"))
        self.assertEqual(r.returncode, 1)
        self.assertIn("REVERSED", r.stdout)
        self.assertIn("start_layer = -1, stop_layer = -2", r.stdout)

    def test_named_layers(self):
        consts = "IDX_L5 = -2\nIDX_L6 = -1\n"
        r = self.run_on(consts + via("UV2", "IDX_L6", "IDX_L5"))
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("REVERSED", r.stdout)
        r = self.run_on(consts + via("UV2", "IDX_L5", "IDX_L6"))
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_rebound_name_unchecked(self):
        consts = "L = 0\nL = -1\n"
        r = self.run_on(consts + via("UV1", "0", "1") + via("UV2", "L", "-2"))
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("UNCHECKED", r.stdout)

    def test_unchecked_alone_fails(self):
        r = self.run_on(via("UV", "TOP", "BOTTOM"))
        self.assertEqual(r.returncode, 1)
        self.assertIn("UNCHECKED", r.stdout)

    def test_no_via(self):
        r = self.run_on("x = 1\n")
        self.assertEqual(r.returncode, 1)
        self.assertIn("0 via(s) checked", r.stdout)

    def test_unparseable(self):
        r = self.run_on("class (:\n")
        self.assertEqual(r.returncode, 2)


if __name__ == "__main__":
    unittest.main()
