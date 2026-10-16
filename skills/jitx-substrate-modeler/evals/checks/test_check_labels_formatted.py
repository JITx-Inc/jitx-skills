"""Tests for check_labels_formatted: each shape it reports, and the clean one."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from check_labels_formatted import split_entries

SCRIPT = Path(__file__).with_name("check_labels_formatted.py")
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

    def test_project_line_length_is_honoured(self) -> None:
        label = "# skill default: 3x dielectric height, not a source value"
        body = f"            ).reference(\n                {{\n                    1: 3 * 0.080,  {label}\n"
        source = PREFIX + body + "                }\n            ),\n        }\n    )\n"
        result = run(source, "[tool.ruff]\nline-length = 120\n")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_reference_with_no_label_fails(self) -> None:
        body = "            ).reference(\n                {\n                    1: 0.240,\n"
        source = PREFIX + body + "                }\n            ),\n        }\n    )\n"
        self.assertEqual(run(source).returncode, 1)

    def test_mixed_case_detached_label_is_reported(self) -> None:
        text = "    1: 3 * 0.080,\n)  # Skill default: 3x dielectric height\n"
        self.assertEqual([n for n, _ in split_entries(text)], [2])

    def test_unparseable_file_could_not_run(self) -> None:
        self.assertEqual(run("x = (\n").returncode, 2)


if __name__ == "__main__":
    unittest.main()
