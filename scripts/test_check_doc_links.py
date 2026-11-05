#!/usr/bin/env python3
"""Tests for check_doc_links.py. Stdlib only. Run directly:

    python3 scripts/test_check_doc_links.py
"""

from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from check_doc_links import (  # noqa: E402
    ALLOWLIST,
    Doc,
    body_lines,
    check_links,
    collect,
    main,
    normalize,
    slug,
    truncated_citations,
)


class SlugTests(unittest.TestCase):
    def test_em_dash_leaves_a_double_hyphen(self):
        # The case the whole sweep turns on: punctuation is dropped, not replaced,
        # so the space either side of the em dash collapses to two hyphens.
        self.assertEqual(
            slug("Component completeness check — run before calling it done"),
            "component-completeness-check--run-before-calling-it-done",
        )

    def test_parentheses_and_slashes_are_dropped(self):
        self.assertEqual(slug("Layout-intent tags (object selection)"), "layout-intent-tags-object-selection")
        self.assertEqual(slug("MCU / FPGA Components (Additional)"), "mcu--fpga-components-additional")

    def test_apostrophes_and_backticks_are_dropped(self):
        self.assertEqual(slug("Build Safety — Don't Parallelize"), "build-safety--dont-parallelize")
        self.assertEqual(slug("`FAB_RULES` mapping"), "fab_rules-mapping")


class BodyLineTests(unittest.TestCase):
    def test_fenced_code_blocks_are_skipped(self):
        text = "# Real\n\n```bash\n# Not a heading\n```\n\n## Also real\n"
        self.assertEqual([n for n, _ in body_lines(text)], [1, 2, 6, 7, 8])

    def test_tilde_fences_are_skipped(self):
        text = "# Real\n~~~\n# Not a heading\n~~~\n"
        self.assertNotIn("# Not a heading", [line for _, line in body_lines(text)])

    def test_yaml_frontmatter_is_skipped(self):
        text = '---\nname: x\ndescription: "create a component"\n---\n\n# Real\n'
        self.assertEqual([n for n, _ in body_lines(text)], [5, 6, 7])

    def test_headings_inside_fences_do_not_become_anchors(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.md"
            path.write_text("# Title\n\n```sh\n# Sync project deps from public PyPI\n```\n")
            doc = Doc(path, "a.md")
            self.assertIn("title", doc.headings)
            self.assertNotIn("sync-project-deps-from-public-pypi", doc.headings)


class LinkCheckTests(unittest.TestCase):
    def build(self, files: dict[str, str]) -> tuple[Path, dict[str, Doc]]:
        tmp = Path(tempfile.mkdtemp()).resolve()
        for rel, text in files.items():
            path = tmp / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        return tmp, collect(tmp)

    def test_clean_tree_has_no_findings(self):
        root, docs = self.build(
            {
                "skills/a/SKILL.md": "# A\n\nSee [B — the rule](../b/SKILL.md#b--the-rule).\n",
                "skills/b/SKILL.md": "# B — the rule\n",
            }
        )
        self.assertEqual(check_links(root, docs), [])

    def test_missing_file_is_reported(self):
        root, docs = self.build({"skills/a/SKILL.md": "# A\n\n[gone](../b/SKILL.md)\n"})
        findings = check_links(root, docs)
        self.assertEqual(len(findings), 1)
        self.assertIn("skills/a/SKILL.md:3", findings[0])
        self.assertIn("link target does not exist", findings[0])

    def test_missing_anchor_is_reported(self):
        root, docs = self.build({"skills/a/SKILL.md": "# A\n\n[x](#no-such-heading)\n"})
        findings = check_links(root, docs)
        self.assertEqual(len(findings), 1)
        self.assertIn("anchor matches no heading", findings[0])

    def test_ambiguous_anchor_is_reported(self):
        root, docs = self.build({"skills/a/SKILL.md": "# A\n\n[x](#process)\n\n## Process\n\n## Process\n"})
        findings = check_links(root, docs)
        self.assertEqual(len(findings), 1)
        self.assertIn("anchor is ambiguous", findings[0])
        self.assertIn("L5", findings[0])

    def test_external_links_are_ignored(self):
        root, docs = self.build({"skills/a/SKILL.md": "# A\n\n[x](https://example.com#frag)\n"})
        self.assertEqual(check_links(root, docs), [])

    def test_links_inside_fences_are_ignored(self):
        root, docs = self.build({"skills/a/SKILL.md": "# A\n\n```\n[x](./nope.md)\n```\n"})
        self.assertEqual(check_links(root, docs), [])


class CitationTests(unittest.TestCase):
    def build(self, files: dict[str, str]) -> dict[str, Doc]:
        tmp = Path(tempfile.mkdtemp()).resolve()
        for rel, text in files.items():
            path = tmp / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        return collect(tmp)

    def test_truncated_self_citation_is_flagged(self):
        md = "# A\n\nFill the **Component check** below.\n\n## Component check — do it first\n"
        docs = self.build({"skills/a/SKILL.md": md})
        rows = truncated_citations(docs)
        self.assertEqual(len(rows), 1)
        rel, lineno, phrase, targets, allowed = rows[0]
        self.assertEqual((rel, lineno, phrase, allowed), ("skills/a/SKILL.md", 3, "component check", False))
        self.assertEqual(targets[0][2], "Component check — do it first")

    def test_quoted_citation_is_flagged(self):
        md = '# A\n\nSee "Build Safety" first.\n\n## Build Safety — no parallel\n'
        docs = self.build({"skills/a/SKILL.md": md})
        self.assertEqual(len(truncated_citations(docs)), 1)

    def test_word_boundary_guard_rejects_a_longer_word(self):
        # "Reference Design" is a datasheet section; it must not match the heading
        # "Reference Designator Prefixes" just because it is a character prefix.
        md = '# A\n\nCheck for "Reference Design" sections.\n\n## Reference Designator Prefixes\n'
        docs = self.build({"skills/a/SKILL.md": md})
        self.assertEqual(truncated_citations(docs), [])

    def test_exact_citation_is_not_flagged(self):
        docs = self.build({"skills/a/SKILL.md": "# A\n\nSee **Build Safety** first.\n\n## Build Safety\n"})
        self.assertEqual(truncated_citations(docs), [])

    def test_already_linked_citation_is_not_flagged(self):
        docs = self.build(
            {"skills/a/SKILL.md": "# A\n\nSee **[Build Safety](#build-safety--x)**.\n\n## Build Safety — x\n"}
        )
        self.assertEqual(truncated_citations(docs), [])

    def test_single_word_phrases_are_ignored(self):
        docs = self.build({"skills/a/SKILL.md": "# A\n\nA **Polygon** here.\n\n## Polygon and friends\n"})
        self.assertEqual(truncated_citations(docs), [])

    def test_allowlisted_phrase_is_marked_and_does_not_fail(self):
        md = "# A\n\nThese are **top-level only** here.\n\n## Top-level only (not nested)\n"
        docs = self.build({"skills/a/SKILL.md": md})
        entry = {"skills/a/SKILL.md": {"top-level only": "prose emphasis, not a citation"}}
        with mock.patch.dict(ALLOWLIST, entry, clear=True):
            rows = truncated_citations(docs)
            self.assertEqual(len(rows), 1)
            self.assertTrue(rows[0][4], "allowlisted phrase should be marked allowed")

    def test_allowlist_is_scoped_to_one_file(self):
        files = {
            "skills/a/SKILL.md": "# A\n\nThese are **top-level only** here.\n",
            "skills/b/SKILL.md": "# B\n\nThese are **top-level only** here.\n\n## Top-level only (not nested)\n",
        }
        docs = self.build(files)
        entry = {"skills/a/SKILL.md": {"top-level only": "allowed here only"}}
        with mock.patch.dict(ALLOWLIST, entry, clear=True):
            flagged = [r for r in truncated_citations(docs) if not r[4]]
        self.assertEqual([r[0] for r in flagged], ["skills/b/SKILL.md"])


class MainTests(unittest.TestCase):
    def run_main(self, files: dict[str, str], *extra: str) -> int:
        tmp = Path(tempfile.mkdtemp()).resolve()
        for rel, text in files.items():
            path = tmp / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        sink = io.StringIO()
        with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            return main(["check_doc_links.py", str(tmp), *extra])

    def test_clean_tree_exits_zero(self):
        self.assertEqual(self.run_main({"skills/a/SKILL.md": "# A\n\nPlain prose.\n"}), 0)

    def test_broken_link_exits_one(self):
        self.assertEqual(self.run_main({"skills/a/SKILL.md": "# A\n\n[x](#nope)\n"}), 1)

    def test_truncated_citation_exits_one(self):
        md = "# A\n\nSee **Build Safety** now.\n\n## Build Safety — no parallel\n"
        self.assertEqual(self.run_main({"skills/a/SKILL.md": md}), 1)

    def test_report_mode_exits_zero_despite_findings(self):
        files = {"skills/a/SKILL.md": "# A\n\nSee **Build Safety** now.\n\n## Build Safety — no parallel\n"}
        self.assertEqual(self.run_main(files, "--report-citations"), 0)

    def test_missing_skills_dir_is_a_usage_error(self):
        sink = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stderr(sink):
            self.assertEqual(main(["check_doc_links.py", tmp]), 2)

    def test_too_many_arguments_is_a_usage_error(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(["check_doc_links.py", ".", "."]), 2)

    def test_unknown_flag_is_a_usage_error(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(["check_doc_links.py", "--nope"]), 2)


class NormalizeTests(unittest.TestCase):
    def test_emphasis_and_whitespace_are_collapsed(self):
        self.assertEqual(normalize("**Build**  `Safety`"), "build safety")


if __name__ == "__main__":
    unittest.main(verbosity=2)
