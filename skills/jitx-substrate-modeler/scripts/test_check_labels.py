"""Tests for check_labels: each shape it reports, and the clean one."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from check_labels import split_entries

SCRIPT = Path(__file__).with_name("check_labels.py")
NOTHING = (
    "check_labels: no skill-default label, nothing to check "
    "(a value no source row backs needs one)\n"
)
PREFIX = "class S:\n    x = f(\n        {\n            2: g(\n                a=1,\n"


def run(source: str, pyproject: str = "") -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory() as tmp:
        board = Path(tmp) / "board.py"
        board.write_text(source)
        if pyproject:
            (Path(tmp) / "pyproject.toml").write_text(pyproject)
        return subprocess.run(
            [sys.executable, str(SCRIPT), str(board)],
            check=False,
            capture_output=True,
            text=True,
        )


class SplitEntries(unittest.TestCase):
    def test_split_derivation_is_reported(self) -> None:
        text = "        1: 3\n        * 0.080,  # skill default: 3x dielectric height\n"
        self.assertEqual([n for n, _ in split_entries(text)], [1])

    def test_split_inside_a_sum_is_reported(self) -> None:
        text = "        1: 3 * 0.080\n        + 0.127,  # skill default: 3x dielectric height\n"
        self.assertEqual([n for n, _ in split_entries(text)], [1])

    def test_entry_opening_a_call_is_not_a_split(self) -> None:
        text = "        2: g(\n            + 0.127,  # skill default: 3x dielectric height\n"
        self.assertEqual(split_entries(text), [])

    def test_detached_label_is_reported(self) -> None:
        text = "    1: 3 * 0.080,\n)  # skill default: 3x dielectric height\n"
        self.assertEqual([n for n, _ in split_entries(text)], [2])

    def test_label_after_code_that_is_not_only_closers_is_attached(self) -> None:
        # A labeled keyword or attribute is attached to its value even with no
        # digit on the line.
        for text in (
            "                velocity=VEL,  # skill default: eps_eff\n",
            "        filled = False  # skill default: unfilled unless stated\n",
        ):
            with self.subTest(text=text):
                self.assertEqual(split_entries(text), [])

    def test_split_keyword_derivation_is_reported(self) -> None:
        text = "        loss=3\n        * 0.006,  # skill default: example value\n"
        self.assertEqual([n for n, _ in split_entries(text)], [1])

    def test_split_over_three_lines_is_reported(self) -> None:
        text = (
            "        loss=0.018\n        * 1.1\n"
            "        * 1.05,  # skill default: example value\n"
        )
        self.assertEqual([n for n, _ in split_entries(text)], [1])

    def test_label_anywhere_in_the_comment_is_a_label(self) -> None:
        for text in (
            "        1: 3\n        * 0.068,  # 3x dielectric height (skill default)\n",
            "        loss=3\n        * 0.006,  # example value, skill default\n",
            "    ),  # widths below: skill default\n",
        ):
            with self.subTest(text=text):
                self.assertEqual(len(split_entries(text)), 1)

    def test_split_before_floor_division_or_power_is_reported(self) -> None:
        for text in (
            "        1: 3\n        * 0.068\n        // 1,  # skill default: 3x height\n",
            "        1: 3\n        ** 2,  # skill default: 3x height\n",
        ):
            with self.subTest(text=text):
                self.assertEqual([n for n, _ in split_entries(text)], [1])

    def test_split_under_a_comment_that_is_not_a_label_is_clean(self) -> None:
        for text in (
            "        trace_width=3.5\n        * 0.0254,  # 3.5 mil finished, IMPEDANCE row\n",
            "        1: 3\n        * 0.080,  # dielectric height from the table\n",
        ):
            with self.subTest(text=text):
                self.assertEqual(split_entries(text), [])

    def test_comment_that_is_not_a_label_is_never_detached(self) -> None:
        for text in (
            "            ).reference(  # Ref_layers column: L2\n",
            "            ).reference(  # REF_WIDTH column, not a skill default\n",
        ):
            with self.subTest(text=text):
                self.assertEqual(split_entries(text), [])

    def test_label_on_an_opening_bracket_is_detached(self) -> None:
        for text in (
            "            ).reference(  # skill default: 3x dielectric height\n",
            "                {  # skill default: 3x dielectric height\n",
        ):
            with self.subTest(text=text):
                self.assertEqual([n for n, _ in split_entries(text)], [1])

    def test_standalone_comment_is_not_a_label(self) -> None:
        text = "    # skill default: 3x dielectric height, not a source value\n"
        self.assertEqual(split_entries(text), [])

    def test_whole_entry_is_clean(self) -> None:
        text = "        1: 3 * 0.080,  # skill default: 3x dielectric height\n"
        self.assertEqual(split_entries(text), [])


class Script(unittest.TestCase):
    def test_long_label_at_depth_fails(self) -> None:
        label = "# skill default: 3x dielectric height, not a source value"
        body = f"            ).reference(\n                {{\n                    1: 3 * 0.080,  {label}\n"
        source = PREFIX + body + "                }\n            ),\n        }\n    )\n"
        self.assertEqual(run(source).returncode, 1)

    def test_short_label_at_depth_passes(self) -> None:
        label = "# skill default: 3x dielectric height"
        body = f"            ).reference(\n                {{\n                    1: 3 * 0.080,  {label}\n"
        source = PREFIX + body + "                }\n            ),\n        }\n    )\n"
        result = run(source)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        # The completion block quotes this line, so a clean run prints exactly it.
        self.assertEqual(
            result.stdout,
            "check_labels: 1 labeled lines, none split from their label\n",
        )

    def test_file_with_no_reference_call_has_nothing_to_check(self) -> None:
        result = run("class S:\n    x = 1\n")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(
            result.stdout,
            NOTHING,
        )

    def test_missing_file_could_not_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "board.py"
            result = subprocess.run(
                [sys.executable, str(SCRIPT), str(missing)],
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual(result.stderr, f"check_labels: no file at {missing}\n")

    def test_project_line_length_is_honoured(self) -> None:
        label = "# skill default: 3x dielectric height, not a source value"
        body = f"            ).reference(\n                {{\n                    1: 3 * 0.080,  {label}\n"
        source = PREFIX + body + "                }\n            ),\n        }\n    )\n"
        result = run(source, "[tool.ruff]\nline-length = 120\n")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_reference_with_no_label_has_nothing_to_check(self) -> None:
        # A width from a source row needs no default label; a missing label on
        # a default is the eval's judge assertion, not this check.
        body = "            ).reference(\n                {\n                    1: 0.240,\n"
        source = PREFIX + body + "                }\n            ),\n        }\n    )\n"
        result = run(source)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout, NOTHING)

    def test_mixed_case_detached_label_is_reported(self) -> None:
        text = "    1: 3 * 0.080,\n)  # Skill default: 3x dielectric height\n"
        self.assertEqual([n for n, _ in split_entries(text)], [2])

    def test_label_only_in_a_docstring_or_comment_is_not_a_label(self) -> None:
        body = "            ).reference(\n                {\n                    1: 0.240,\n"
        tail = "                }\n            ),\n        }\n    )\n"
        for head in (
            '"""Widths use the skill default."""\n',
            "# Widths below: skill default, 3x dielectric height\n",
        ):
            with self.subTest(head=head):
                result = run(head + PREFIX + body + tail)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("nothing to check", result.stdout)

    def test_unparseable_file_could_not_run(self) -> None:
        self.assertEqual(run("x = (\n").returncode, 2)


if __name__ == "__main__":
    unittest.main()
