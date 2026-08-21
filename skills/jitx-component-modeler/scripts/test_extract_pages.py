#!/usr/bin/env python3
"""Tests for extract_pages.py's datasheet-integrity check.

Stdlib only, and deliberately importable without PyMuPDF: `check_is_pdf` sits
above the optional `fitz` import precisely so the guard can be tested in an
environment that has no pymupdf. Run directly: python3 test_extract_pages.py
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from extract_pages import PDF_MAGIC, check_is_pdf  # noqa: E402


class CheckIsPdfTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def write(self, name: str, payload: bytes) -> Path:
        path = self.tmp / name
        path.write_bytes(payload)
        return path

    def test_real_pdf_passes(self) -> None:
        pdf = self.write("ds.pdf", PDF_MAGIC + b"1.7\n%\xe2\xe3\xcf\xd3\n" + b"0" * 512)
        self.assertIsNone(check_is_pdf(pdf))

    def test_missing_file_is_reported(self) -> None:
        problem = check_is_pdf(self.tmp / "absent.pdf")
        assert problem is not None
        self.assertIn("file not found", problem)

    def test_bot_block_html_under_pdf_name_is_caught(self) -> None:
        """The failure that motivated this check: HTTP 200, .pdf name, HTML body."""
        html = b"<!DOCTYPE html>\n<html><body>Checking your browser...</body></html>"
        problem = check_is_pdf(self.write("mirror.pdf", html))
        assert problem is not None
        self.assertIn("HTML", problem)
        self.assertIn("bot-block", problem)

    def test_leading_whitespace_before_html_still_caught(self) -> None:
        problem = check_is_pdf(self.write("m.pdf", b"\n\n  <html><body>nope</body></html>"))
        assert problem is not None
        self.assertIn("HTML", problem)

    def test_xml_error_document_is_caught(self) -> None:
        problem = check_is_pdf(self.write("m.pdf", b'<?xml version="1.0"?><Error/>'))
        assert problem is not None
        self.assertIn("HTML/XML", problem)

    def test_other_binary_reports_first_bytes(self) -> None:
        problem = check_is_pdf(self.write("m.pdf", b"PK\x03\x04zipnotpdf"))
        assert problem is not None
        self.assertIn("does not start with %PDF-", problem)
        self.assertIn("PK", problem)

    def test_empty_file_is_not_a_pdf(self) -> None:
        self.assertIsNotNone(check_is_pdf(self.write("empty.pdf", b"")))

    def test_magic_must_be_at_offset_zero(self) -> None:
        """A PDF preceded by junk is not something to hand to a reader unchecked."""
        self.assertIsNotNone(check_is_pdf(self.write("m.pdf", b"junk" + PDF_MAGIC + b"1.4")))

    def test_accepts_str_path_as_well_as_path(self) -> None:
        pdf = self.write("ds.pdf", PDF_MAGIC + b"1.4\n")
        self.assertIsNone(check_is_pdf(str(pdf)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
