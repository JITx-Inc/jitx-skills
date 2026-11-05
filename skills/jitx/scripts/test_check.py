#!/usr/bin/env python3
"""Tests for check.py's build witness.

The witness exists because a jitx command has been observed exiting 0 while
printing a failure, so a zero exit alone is not evidence the build succeeded.
"""

import contextlib
import importlib.util
import io
import pathlib
import unittest

_spec = importlib.util.spec_from_file_location(
    "check_mod", pathlib.Path(__file__).with_name("check.py")
)
check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check)


def witness(status, output, returncode, detail=""):
    return check.confirm_build_witness(
        check.Result("build", status, output, detail, returncode)
    )


class BuildWitness(unittest.TestCase):
    def test_zero_exit_with_status_ok_passes(self):
        self.assertEqual(witness("PASS", "  status: ok\n", 0).status, "PASS")

    def test_zero_exit_printing_status_error_fails(self):
        # The case the witness exists for: the exit code claims success and the
        # output says otherwise.
        r = witness("PASS", "  status: error\n", 0)
        self.assertEqual(r.status, "FAIL")
        self.assertEqual(r.detail, "status: error")

    def test_zero_exit_with_no_status_line_is_error_not_pass(self):
        # Cannot confirm what happened. That is not the same as being fine.
        self.assertEqual(witness("PASS", "chatter\n", 0).status, "ERROR")

    def test_nonzero_exit_stays_fail(self):
        # A real failed build prints `errors:` and a traceback, no `status:`
        # line. The nonzero exit is already sufficient evidence.
        self.assertEqual(witness("FAIL", "errors:\n  translation failed\n", 1).status, "FAIL")

    def test_already_error_is_left_alone(self):
        r = witness("ERROR", "", None, detail="command not found: jitx")
        self.assertEqual(r.status, "ERROR")
        self.assertEqual(r.detail, "command not found: jitx")


class ImportErrors(unittest.TestCase):
    def test_pyright_unresolved_import_is_import_error(self):
        out = '/p/x.py:3:6 - error: Import "jitx" could not be resolved (reportMissingImports)\n'
        self.assertTrue(check.is_import_error(out))

    def test_ordinary_pyright_type_error_is_not_import_error(self):
        out = '/p/x.py:9:1 - error: "foo" is not a known attribute (reportAttributeAccessIssue)\n'
        self.assertFalse(check.is_import_error(out))


class GrepGateOutput(unittest.TestCase):
    def _printed(self, detail):
        r = check.Result("grep gates", "PASS", "x.py:4: hit\nreview-required hits: 2\n", detail, 0)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            check.print_result(r, verbose=False)
        return buf.getvalue()

    def test_review_required_hits_print_on_pass(self):
        self.assertIn("x.py:4: hit", self._printed("0 hard-fail, 2 review-required"))

    def test_clean_pass_stays_one_line(self):
        self.assertNotIn("x.py:4: hit", self._printed("0 hard-fail, 0 review-required"))


class Placeholders(unittest.TestCase):
    def test_missing_tool_is_error_not_pass(self):
        r = check.run_command("nope", ["definitely-not-a-real-binary-xyz"])
        self.assertEqual(r.status, "ERROR")
        self.assertIn("command not found", r.detail)


if __name__ == "__main__":
    unittest.main()
