#!/usr/bin/env python3
"""Tests for the construction-context check.

The check's whole value is discrimination: it must catch a component built in a
plain `unittest.TestCase` (where `__init__` never runs, so the assertion is
vacuous) WITHOUT flagging a plain test that only exercises pure logic. A blunt
"no unittest.TestCase anywhere" grep fails a correct solution, which is worse
than no check at all -- these tests pin both directions.

Stdlib only. Run directly: python3 test_construction_context.py
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from construction_context import component_class_names, main  # noqa: E402

COMPONENT = """
import jitx

class MyPart(jitx.Component):
    def __init__(self, size: str) -> None:
        if size not in {"0402"}:
            raise ValueError(f"bad size {size!r}; valid: ['0402']")
"""


class ConstructionContextTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        (self.root / "components").mkdir()
        (self.root / "components" / "part.py").write_text(COMPONENT)

    def run_check(self, test_source: str) -> int:
        (self.root / "test_it.py").write_text(test_source)
        return main(["construction_context.py", str(self.root)])

    def test_component_built_in_plain_testcase_is_caught(self) -> None:
        self.assertEqual(1, self.run_check("""
import unittest
from components.part import MyPart

class T(unittest.TestCase):
    def test_bad(self):
        with self.assertRaises(ValueError):
            MyPart(size="0505")
"""))

    def test_bare_TestCase_imported_from_unittest_is_caught(self) -> None:
        self.assertEqual(1, self.run_check("""
from unittest import TestCase
from components.part import MyPart

class T(TestCase):
    def test_bad(self):
        MyPart(size="0402")
"""))

    def test_same_test_under_jitx_testcase_passes(self) -> None:
        self.assertEqual(0, self.run_check("""
from jitx.test import TestCase
from components.part import MyPart

class T(TestCase):
    def test_bad(self):
        with self.assertRaises(ValueError):
            MyPart(size="0505")
"""))

    def test_pure_logic_in_plain_testcase_is_not_flagged(self) -> None:
        """The legitimate design: validation in a pure classmethod, tested plainly."""
        self.assertEqual(0, self.run_check("""
import unittest
from components.part import MyPart

class T(unittest.TestCase):
    def test_encoder_carries_a_decade(self):
        self.assertEqual(MyPart.build_mpn(9995), "1002")
"""))

    def test_non_component_construction_is_not_flagged(self) -> None:
        """Toleranced / PlainQuantity in a plain test is fine; capitalization is not the rule."""
        self.assertEqual(0, self.run_check("""
import unittest
from jitx.toleranced import Toleranced
from jitx.units import PlainQuantity

class T(unittest.TestCase):
    def test_units(self):
        self.assertEqual(Toleranced(1.0, 0.1).typ, 1.0)
        self.assertIsNotNone(PlainQuantity(1.0, "ohm"))
"""))

    def test_component_names_are_resolved_from_the_tree(self) -> None:
        names = component_class_names(self.root)
        self.assertIn("MyPart", names)

    def test_no_components_found_is_a_pass_not_a_crash(self) -> None:
        empty = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: [p.unlink() for p in empty.rglob("*")] and None)
        (empty / "t.py").write_text("import unittest\n")
        self.assertEqual(0, main(["construction_context.py", str(empty)]))

    def test_missing_directory_is_a_usage_error(self) -> None:
        self.assertEqual(2, main(["construction_context.py", str(self.root / "nope")]))

    def test_unparseable_file_is_reported_as_a_finding(self) -> None:
        (self.root / "broken.py").write_text("def (:\n")
        self.assertEqual(1, self.run_check("import unittest\n"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
