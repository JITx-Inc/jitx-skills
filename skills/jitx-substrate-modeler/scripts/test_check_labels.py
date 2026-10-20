"""Tests for check_labels: each shape it reports, and the clean one."""

import os
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


BRACKET_ENTRIES = (
    "                {{\n"
    "                    1: 3 * 0.080,{first}\n"
    "                    3: 3 * 0.127,{second}\n"
    "                }}\n"
    "            ),\n"
)
ENTRY_LABEL = "  # skill default: 3x dielectric height"


def run(
    source: str | bytes,
    pyproject: str = "",
    flags: tuple[str, ...] = (),
    path: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run the script on ``source``; ``flags`` go to the interpreter, and
    ``path`` replaces PATH in the script's environment."""
    env = dict(os.environ) if path is None else {**os.environ, "PATH": path}
    with tempfile.TemporaryDirectory() as tmp:
        board = Path(tmp) / "board.py"
        if isinstance(source, bytes):
            board.write_bytes(source)
        else:
            board.write_text(source)
        if pyproject:
            (Path(tmp) / "pyproject.toml").write_text(pyproject)
        return subprocess.run(
            [sys.executable, *flags, str(SCRIPT), str(board)],
            check=False,
            capture_output=True,
            text=True,
            env=env,
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
        for text in (
            "    1: 3 * 0.080,\n)  # skill default: 3x dielectric height\n",
            "    1: 3 * 0.080,\n)  # Skill default: 3x dielectric height\n",
        ):
            with self.subTest(text=text):
                self.assertEqual([n for n, _ in split_entries(text)], [2])

    def test_hyphenated_or_plural_label_is_a_label(self) -> None:
        for comment in (
            "# skill-default: 3x dielectric height",
            "# Skill defaults: 3x dielectric height",
            "# SKILL-DEFAULTS, 3x dielectric height",
        ):
            text = f"        1: 3\n        * 0.080,  {comment}\n"
            with self.subTest(comment=comment):
                self.assertEqual([n for n, _ in split_entries(text)], [1])

    def test_split_under_any_dict_key_is_reported(self) -> None:
        # The shapes ruff format leaves a long labeled entry in.
        label = "# skill default: 3x dielectric height to each reference plane"
        for head in (
            '1: H["D-PP"]\n                    * 3,',
            "1: between(1, 3)\n                    * 3,",
            "L2_IDX: 3\n                    * 0.080,",
            "H.top: 3\n                    * 0.080,",
            'H["a", "b"]: 3\n                    * 0.080,',
        ):
            text = f"                    {head}  {label}\n"
            with self.subTest(head=head):
                self.assertEqual([n for n, _ in split_entries(text)], [1])

    def test_head_ending_in_a_comma_or_opening_bracket_is_not_a_split(self) -> None:
        for head in ("1: 0.240,", "L2_IDX: f(", "loss=["):
            text = f"        {head}\n        * 0.080,  # skill default: 3x height\n"
            with self.subTest(head=head):
                self.assertEqual(split_entries(text), [])

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
            "            ).reference(  # REF_WIDTH column, not skill default\n",
            "            ).reference(  # REF_WIDTH column, not the skill default\n",
            "            ).reference(  # REF_WIDTH column, not any skill default\n",
            "            ).reference(  # 3.5 mil per IMPEDANCE row, no skill default\n",
            "        1: 3\n        * 0.080,  # REF_WIDTH row, not the skill default\n",
        ):
            with self.subTest(text=text):
                self.assertEqual(split_entries(text), [])

    def test_label_on_an_opening_bracket_is_detached(self) -> None:
        for text in (
            "            ).reference(  # skill default: 3x dielectric height\n",
            "                {  # skill default: 3x dielectric height\n",
            "            ).reference(  # skill default: 3x dielectric height\n"
            + BRACKET_ENTRIES.format(first="", second=""),
        ):
            with self.subTest(text=text):
                self.assertEqual([n for n, _ in split_entries(text)], [1])

    def test_bracket_label_over_labeled_entries_is_clean(self) -> None:
        entries = BRACKET_ENTRIES.format(first=ENTRY_LABEL, second=ENTRY_LABEL)
        for text in (
            "            ).reference(  # skill default: 3x dielectric height to each plane\n"
            + entries,
            "            ).reference(  # Ref_layers L1, L3; widths per the skill default\n"
            + entries,
            "            ).reference(\n"
            + entries.replace("            ),\n", "            ),  # skill default\n"),
        ):
            with self.subTest(text=text):
                self.assertEqual(split_entries(text), [])

    def test_closing_label_over_unlabeled_entries_is_detached(self) -> None:
        entries = BRACKET_ENTRIES.format(first="", second="")
        text = "            ).reference(\n" + entries.replace(
            "            ),\n", "            ),  # skill default\n"
        )
        self.assertEqual([n for n, _ in split_entries(text)], [6])

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

    def test_hyphenated_or_plural_label_split_by_ruff_fails(self) -> None:
        for label in (
            "# skill-default: 3x dielectric height, not a source value",
            "# skill defaults: 3x dielectric height, not a source value",
        ):
            body = f"            ).reference(\n                {{\n                    1: 3 * 0.080,  {label}\n"
            source = (
                PREFIX + body + "                }\n            ),\n        }\n    )\n"
            )
            with self.subTest(label=label):
                result = run(source)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

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

    def test_file_with_no_label_has_nothing_to_check(self) -> None:
        # A width from a source row needs no default label; a missing label on
        # a default is the eval's judge assertion, not this check.
        body = "            ).reference(\n                {\n                    1: 0.240,\n"
        tail = "                }\n            ),\n        }\n    )\n"
        denied = "            ).reference(  # REF_WIDTH column, not the skill default\n"
        for source in (
            "class S:\n    x = 1\n",
            PREFIX + body + tail,
            '"""Widths use the skill default."""\n' + PREFIX + body + tail,
            "# Widths below: skill default, 3x dielectric height\n"
            + PREFIX
            + body
            + tail,
            PREFIX + denied + body.partition("\n")[2] + tail,
        ):
            with self.subTest(source=source):
                result = run(source)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(result.stdout, NOTHING)

    def test_unparseable_file_could_not_run(self) -> None:
        self.assertEqual(run("x = (\n").returncode, 2)

    def test_file_that_is_not_utf8_could_not_run(self) -> None:
        result = run(b"x = 1  # \xff\xfe\n")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual(len(result.stderr.splitlines()), 1, result.stderr)
        self.assertIn("could not read", result.stderr)

    def test_ruff_on_path_runs_when_the_interpreter_has_none(self) -> None:
        # -S leaves site-packages off, so ruff does not import in the script's
        # interpreter; the ruff on PATH formats instead.
        # The ruff binary beside this interpreter, not a PATH shim that needs a
        # shell the emptied PATH no longer has.
        ruff = Path(sys.executable).with_name("ruff")
        if not ruff.is_file():
            self.skipTest("no ruff executable beside this interpreter")
        result = run("class S:\n    x = 1\n", flags=("-S",), path=str(ruff.parent))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout, NOTHING)

    def test_no_ruff_anywhere_could_not_run(self) -> None:
        with tempfile.TemporaryDirectory() as empty:
            result = run("class S:\n    x = 1\n", flags=("-S",), path=empty)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("nor is on PATH", result.stderr)


if __name__ == "__main__":
    unittest.main()
