"""Tests for via_order: each verdict it gives, and its exit codes."""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from via_order import reversed_span

SCRIPT = Path(__file__).with_name("via_order.py")


def via(name: str, start: str, stop: str) -> str:
    return f"class {name}(Via):\n    start_layer = {start}\n    stop_layer = {stop}\n"


def indexes(n: int) -> range:
    """Every index jitx accepts on an n-layer board, from the top and the bottom."""
    return range(-n, n)


def physical(i: int, n: int) -> int:
    """Layer number from the top, 0-based, as jitx normalizes an index."""
    return i if i >= 0 else n + i


class ReversedSpan(unittest.TestCase):
    def test_named_layers(self):
        # (layers, start, stop, reversed), each read as physical layers.
        cases = [
            (4, -2, 3, False),  # L3 to L4
            (4, 3, -2, True),  # L4 to L3
            (12, -2, 3, True),  # L11 to L4
            (12, 3, -2, False),  # L4 to L11
            (12, -2, -1, False),  # L11 to L12
            (12, -1, -2, True),  # L12 to L11
            (6, -3, 4, False),  # L4 to L5
            (2, 1, -2, True),  # L2 to L1
            (8, 0, -1, False),  # through hole
        ]
        for n, start, stop, expected in cases:
            with self.subTest(layers=n, start=start, stop=stop):
                self.assertIs(reversed_span(start, stop, n), expected)

    def test_with_layers_matches_physical_order(self):
        for n in range(1, 13):
            for start in indexes(n):
                for stop in indexes(n):
                    with self.subTest(layers=n, start=start, stop=stop):
                        expected = physical(start, n) > physical(stop, n)
                        self.assertIs(reversed_span(start, stop, n), expected)

    def test_without_layers_never_wrong(self):
        # A verdict given without the layer count must hold on every board the
        # indexes fit; anything that differs between boards must be None.
        for start in range(-12, 12):
            for stop in range(-12, 12):
                fits = [n for n in range(1, 13) if -n <= start < n and -n <= stop < n]
                if not fits:
                    continue
                truths = {physical(start, n) > physical(stop, n) for n in fits}
                verdict = reversed_span(start, stop)
                with self.subTest(start=start, stop=stop):
                    if verdict is not None:
                        self.assertEqual(truths, {verdict})

    def test_without_layers_decides_the_common_spans(self):
        for start, stop, expected in [
            (0, 1, False),
            (-2, -1, False),
            (0, -1, False),
            (2, -1, False),
            (-1, -2, True),
            (2, 0, True),
        ]:
            with self.subTest(start=start, stop=stop):
                self.assertIs(reversed_span(start, stop), expected)
        # -1 to 3 is one layer on a 4-layer board and reversed on any larger one.
        for start, stop in [(-2, 3), (3, -2), (-1, 3), (-4, 0)]:
            with self.subTest(start=start, stop=stop):
                self.assertIsNone(reversed_span(start, stop))

    def test_out_of_range(self):
        self.assertIsNone(reversed_span(0, 4, 4))
        self.assertIsNone(reversed_span(-5, 0, 4))


try:
    from jitx.via import ViaDiameter
except ImportError:
    ViaDiameter = None


@unittest.skipIf(ViaDiameter is None, "jitx is not installed")
class AgainstJitx(unittest.TestCase):
    def test_verdict_matches_via_stack(self):
        # jitx gives a reversed via an empty stack: no layers, no copper.
        assert ViaDiameter is not None
        for n in (2, 4, 6, 12):
            for start in indexes(n):
                for stop in indexes(n):
                    stand_in = SimpleNamespace(
                        start_layer=start, stop_layer=stop, diameter=0.3, diameters={}
                    )
                    empty = not list(ViaDiameter.stack(cast(Any, stand_in), n))
                    with self.subTest(layers=n, start=start, stop=stop):
                        self.assertIs(reversed_span(start, stop, n), empty)


class Script(unittest.TestCase):
    def run_on(self, source: str, *flags: str) -> subprocess.CompletedProcess[str]:
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(source)
        self.addCleanup(os.unlink, f.name)
        return subprocess.run(
            [sys.executable, str(SCRIPT), *flags, f.name],
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

    def test_mixed_sign_needs_layers(self):
        source = via("BV", "-2", "3")
        r = self.run_on(source)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("pass --layers", r.stdout)
        r = self.run_on(source, "--layers", "4")
        self.assertEqual(r.returncode, 0, r.stdout)
        r = self.run_on(source, "--layers", "12")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("REVERSED", r.stdout)

    def test_outside_layers(self):
        r = self.run_on(via("UV", "0", "5"), "--layers", "4")
        self.assertEqual(r.returncode, 1)
        self.assertIn("outside 4 layers", r.stdout)

    def test_named_layers(self):
        consts = "IDX_L5 = -2\nIDX_L6 = -1\n"
        r = self.run_on(consts + via("UV2", "IDX_L6", "IDX_L5"))
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("REVERSED", r.stdout)
        r = self.run_on(consts + via("UV2", "IDX_L5", "IDX_L6"))
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_unchecked_fails(self):
        # An unchecked via fails even beside a checked one.
        consts = "L = 0\nL = -1\n"
        r = self.run_on(consts + via("UV1", "0", "1") + via("UV2", "L", "-2"))
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("UNCHECKED", r.stdout)
        self.assertIn("a layer is not a literal", r.stdout)

    def test_one_sided_class_unchecked(self):
        r = self.run_on(
            via("UV1", "0", "1") + "class UV2(UV1):\n    start_layer = -1\n"
        )
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("sets only start_layer", r.stdout)

    def test_no_via(self):
        r = self.run_on("x = 1\n")
        self.assertEqual(r.returncode, 1)
        self.assertIn("0 via(s) checked", r.stdout)

    def test_unparseable(self):
        r = self.run_on("class (:\n")
        self.assertEqual(r.returncode, 2)

    def test_bad_layers(self):
        r = self.run_on(via("UV1", "0", "1"), "--layers", "0")
        self.assertEqual(r.returncode, 2)


if __name__ == "__main__":
    unittest.main()
