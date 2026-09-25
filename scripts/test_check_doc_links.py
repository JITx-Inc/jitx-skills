#!/usr/bin/env python3
"""Tests for check_doc_links.py. Stdlib only. Run directly:

    python3 scripts/test_check_doc_links.py
"""

from __future__ import annotations

import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from check_doc_links import (  # noqa: E402
    ALLOWLIST,
    MODULE_ROOTS,
    Doc,
    body_lines,
    check_links,
    check_module_imports,
    collect,
    main,
    module_pointers,
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


class ModuleImportTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        modules = self.root / "modules"
        modules.mkdir()
        fixtures = {
            "jitx/__init__.py": "",
            "jitx/core.py": "class Circuit:\n    count = 3\n",
            "jitxlib/__init__.py": "",
            "jitxlib/verify.py": "print('module import output')\ndef rule_width():\n    pass\n",
            "jitxexamples/__init__.py": "",
            "jitxexamples/patterns/__init__.py": "",
            "jitxexamples/patterns/default_rules.py": "raise RuntimeError('leaf body must not run')\n",
            "jitxexamples/patterns/net_net_clearance.py": "",
            "custompkg/__init__.py": "",
            "custompkg/available.py": "",
            "jitx/broken/__init__.py": "raise RuntimeError('broken parent')\n",
            "jitx/dependency/__init__.py": "import missing_doc_link_test_dependency\n",
            "jitx/exiting/__init__.py": "raise SystemExit(0)\n",
        }
        for rel, content in fixtures.items():
            path = modules / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        # subprocesses do not inherit changes to sys.path; give the chosen
        # interpreter the same fixture directory through PYTHONPATH.
        path_patch = mock.patch.object(sys, "path", [str(modules), *sys.path])
        path_patch.start()
        self.addCleanup(path_patch.stop)
        env_patch = mock.patch.dict(os.environ, {"PYTHONPATH": str(modules)})
        env_patch.start()
        self.addCleanup(env_patch.stop)

    def docs(self, text: str) -> dict[str, Doc]:
        path = self.root / "skills/a/SKILL.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return collect(self.root)

    def run_main(self, text: str, *extra: str) -> tuple[int, str, str]:
        self.docs(text)
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(["check_doc_links.py", str(self.root), *extra])
        return code, stdout.getvalue(), stderr.getvalue()

    def test_resolvable_modules_pass_without_running_leaf_bodies(self):
        docs = self.docs("Use `jitx.core`, `jitxlib.verify`, `jitxexamples.patterns.default_rules`.\n")
        self.assertEqual(check_module_imports(docs, roots=frozenset({"jitx", "jitxlib", "jitxexamples"})), [])

    def test_unresolvable_pointer_is_a_finding(self):
        findings = check_module_imports(self.docs("# A\n\nUse `jitxlib.missing`.\n"), roots=frozenset({"jitxlib"}))
        self.assertEqual(len(findings), 1)
        self.assertIn("skills/a/SKILL.md:3: module pointer does not resolve: jitxlib.missing", findings[0])

    def test_exact_unpublished_marker_exempts_its_pointer(self):
        docs = self.docs("Use `jitxlib.missing` (UNPUBLISHED:jitxlib.missing).\n")
        self.assertEqual(check_module_imports(docs, roots=frozenset({"jitxlib"})), [])

    def test_marker_must_name_exact_pointer_on_its_own_line(self):
        for text in (
            "Use `jitxlib.missing`. UNPUBLISHED\n",
            "Use `jitxlib.missing`. UNPUBLISHED:jitxlib\n",
            "Use `jitxlib.missing`. UNPUBLISHED:jitxlib.missing.attr\n",
            "Use `jitxlib.missing.attr`. UNPUBLISHED:jitxlib.missing\n",
            "Use `jitxlib.missing`. NOT_UNPUBLISHED:jitxlib.missing\n",
            "UNPUBLISHED:jitxlib.missing\nUse `jitxlib.missing`.\n",
        ):
            with self.subTest(text=text):
                self.assertEqual(len(check_module_imports(self.docs(text), roots=frozenset({"jitxlib"}))), 1)

    def test_marker_does_not_exempt_another_pointer_on_same_line(self):
        docs = self.docs("`jitxlib.missing`, `jitxlib.other` (UNPUBLISHED:jitxlib.missing)\n")
        findings = check_module_imports(docs, roots=frozenset({"jitxlib"}))
        self.assertEqual(len(findings), 1)
        self.assertIn("jitxlib.other", findings[0])

    def test_fences_and_frontmatter_are_ignored(self):
        docs = self.docs(
            "---\ndescription: `jitx.missing`\n---\n"
            "```python\n`jitxlib.missing`\n```\n~~~\n`jitxexamples.missing`\n~~~\n"
        )
        with mock.patch("check_doc_links.subprocess.run") as run:
            self.assertEqual(check_module_imports(docs, roots=frozenset({"jitx", "jitxlib", "jitxexamples"})), [])
            run.assert_not_called()

    def test_function_and_nested_attributes_resolve(self):
        docs = self.docs("Use `jitxlib.verify.rule_width` and `jitx.core.Circuit.count`.\n")
        self.assertEqual(check_module_imports(docs, roots=frozenset({"jitx", "jitxlib"})), [])

    def test_missing_attribute_is_a_finding(self):
        findings = check_module_imports(self.docs("Use `jitx.core.Circuit.missing`.\n"), roots=frozenset({"jitx"}))
        self.assertEqual(len(findings), 1)
        self.assertIn("jitx.core.Circuit.missing", findings[0])
        self.assertIn("AttributeError", findings[0])

    def test_broken_imports_are_findings(self):
        for pointer, error in (
            ("jitx.broken.child", "RuntimeError: broken parent"),
            ("jitx.dependency.child", "missing_doc_link_test_dependency"),
            ("jitx.exiting.child", "SystemExit: 0"),
        ):
            with self.subTest(pointer=pointer):
                findings = check_module_imports(self.docs(f"Use `{pointer}`.\n"), roots=frozenset({"jitx"}))
                self.assertEqual(len(findings), 1)
                self.assertIn(error, findings[0])

    def test_continuations_name_siblings_on_same_or_next_line(self):
        docs = self.docs(
            "`jitxexamples.patterns.default_rules`, `.net_net_clearance`,\n"
            "`.missing`, `.other`.\n"
        )
        self.assertEqual(
            module_pointers(docs, roots=frozenset({"jitxexamples.patterns"})),
            [("skills/a/SKILL.md", line, "jitxexamples.patterns." + name) for line, name in (
                (1, "default_rules"), (1, "net_net_clearance"), (2, "missing"), (2, "other"),
            )],
        )
        findings = check_module_imports(docs, roots=frozenset({"jitxexamples.patterns"}))
        self.assertEqual(len(findings), 2)
        self.assertTrue(all("skills/a/SKILL.md:2" in finding for finding in findings))

    def test_continuation_uses_most_recent_full_pointer(self):
        docs = self.docs("`jitx.core.Circuit`, `jitxlib.verify.rule_width`, `.missing`\n")
        self.assertEqual(module_pointers(docs, roots=frozenset({"jitx", "jitxlib"}))[-1][2], "jitxlib.verify.missing")

    def test_continuation_does_not_cross_blank_lines_fences_or_files(self):
        for gap in ("\n", "```\n```\n"):
            with self.subTest(gap=gap):
                docs = self.docs("`jitx.core`\n" + gap + "`.missing`\n")
                other = self.root / "skills/a/other.md"
                other.write_text("`.other`\n", encoding="utf-8")
                docs = collect(self.root)
                self.assertEqual(module_pointers(docs, roots=frozenset({"jitx"})), [("skills/a/SKILL.md", 1, "jitx.core")])

    def test_continuation_marker_uses_full_path_and_does_not_leak(self):
        docs = self.docs(
            "`jitxexamples.patterns.missing` (UNPUBLISHED:jitxexamples.patterns.missing),\n"
            "`.other` (UNPUBLISHED:jitxexamples.patterns.other), `.unmarked`\n"
        )
        self.assertEqual(
            module_pointers(docs, roots=frozenset({"jitxexamples.patterns"})),
            [("skills/a/SKILL.md", 2, "jitxexamples.patterns.unmarked")],
        )

    def test_only_whole_dotted_paths_with_configured_roots_match(self):
        docs = self.docs(
            "`elsewhere.missing` `jitxlib_extra.missing` `jitx` `jitx.core()` "
            "`import jitx.core` `jitx/core.py` `.missing`\n"
            "``jitx.core`` `jitx.core.html`\n"
        )
        self.assertEqual(module_pointers(docs, roots=frozenset({"jitx", "jitxlib"})), [
            ("skills/a/SKILL.md", 2, "jitx.core"),
            ("skills/a/SKILL.md", 2, "jitx.core.html"),
        ])

    def test_custom_roots_replace_defaults(self):
        docs = self.docs("`custompkg.available`, `custompkg.missing`, `jitx.missing`, `jitxlib.verify.missing`\n")
        findings = check_module_imports(docs, roots=frozenset({"custompkg"}))
        self.assertEqual(len(findings), 1)
        self.assertIn("custompkg.missing", findings[0])

    def test_default_roots_are_restructure_destinations(self):
        self.assertEqual(MODULE_ROOTS, frozenset({
            "jitxlib.verify", "jitxexamples.patterns", "jitxexamples.demos",
        }))

    def test_dotted_root_matches_children(self):
        docs = self.docs("`jitxlib.verify.rule_width` `jitxlib.verify.nested.child`\n")
        self.assertEqual(module_pointers(docs, roots=frozenset({"jitxlib.verify"})), [
            ("skills/a/SKILL.md", 1, "jitxlib.verify.rule_width"),
            ("skills/a/SKILL.md", 1, "jitxlib.verify.nested.child"),
        ])

    def test_dotted_root_does_not_match_siblings(self):
        docs = self.docs(
            "`jitxlib.verifier` `jitxlib.verifier.child` "
            "`jitxlib.standard` `jitxlib.standard.child`\n"
        )
        roots = frozenset({"jitxlib.verify"})
        self.assertEqual(module_pointers(docs, roots=roots), [])
        with mock.patch("check_doc_links.subprocess.run") as run:
            self.assertEqual(check_module_imports(docs, roots=roots), [])
            run.assert_not_called()

    def test_dotted_root_matches_exact_pointer(self):
        docs = self.docs("`jitxlib.verify`\n")
        roots = frozenset({"jitxlib.verify"})
        self.assertEqual(module_pointers(docs, roots=roots), [("skills/a/SKILL.md", 1, "jitxlib.verify")])
        self.assertEqual(check_module_imports(docs, roots=roots), [])

    def test_pointer_shorter_than_root_does_not_match(self):
        docs = self.docs("`jitxlib` `jitxlib.verify`\n")
        self.assertEqual(module_pointers(docs, roots=frozenset({"jitxlib.verify.rule_width"})), [])

    def test_repeated_pointers_resolve_once_but_report_each_location(self):
        docs = self.docs("`jitx.missing`\n`jitx.missing`\n")
        with mock.patch("check_doc_links.subprocess.run", wraps=subprocess.run) as run:
            findings = check_module_imports(docs, roots=frozenset({"jitx"}))
        self.assertEqual(len(findings), 2)
        run.assert_called_once()
        self.assertEqual(run.call_args.kwargs["input"], '["jitx.missing"]')

    def test_probe_timeout_is_a_finding(self):
        docs = self.docs("`jitx.core`\n")
        with mock.patch("check_doc_links.subprocess.run", side_effect=subprocess.TimeoutExpired("python", 30)):
            findings = check_module_imports(docs, roots=frozenset({"jitx"}))
        self.assertEqual(len(findings), 1)
        self.assertIn("timed out", findings[0])

    def test_missing_or_invalid_probe_results_fail_closed(self):
        docs = self.docs("`jitx.core`\n")
        for stdout, code in (("", 0), ("{}", 0), ('{"jitx.core": false}', 0), ('{"jitx.core": null}', 1)):
            with self.subTest(stdout=stdout, code=code):
                result = subprocess.CompletedProcess([], code, stdout, "probe diagnostic")
                with mock.patch("check_doc_links.subprocess.run", return_value=result):
                    findings = check_module_imports(docs, roots=frozenset({"jitx"}))
                self.assertEqual(len(findings), 1)
                self.assertIn("probe failed", findings[0])

    def test_cli_defaults_to_checking_module_imports(self):
        code, stdout, stderr = self.run_main("`jitxlib.missing`\n", "--module-root", "jitxlib")
        self.assertEqual(code, 1)
        self.assertIn("jitxlib.missing", stdout)
        self.assertIn("1 finding(s)", stderr)

    def test_skip_flag_skips_and_warns_on_stderr(self):
        with mock.patch("check_doc_links.subprocess.run") as run:
            code, stdout, stderr = self.run_main(
                "`jitxlib.missing`\n", "--skip-module-imports", "--module-root", "jitxlib",
            )
        self.assertEqual(code, 0)
        self.assertEqual(stdout, "")
        self.assertIn("WARNING: check 5 SKIPPED (--skip-module-imports)", stderr)
        self.assertIn("module pointers were not checked", stderr)
        run.assert_not_called()

    def test_skip_keeps_link_checks_enabled(self):
        code, stdout, _ = self.run_main(
            "`jitx.missing` [bad](#missing)\n", "--skip-module-imports", "--module-root", "jitx",
        )
        self.assertEqual(code, 1)
        self.assertIn("anchor matches no heading", stdout)
        self.assertNotIn("module pointer", stdout)

    def test_python_option_selects_subprocess_interpreter(self):
        with mock.patch("check_doc_links.subprocess.run", wraps=subprocess.run) as run:
            code, _, stderr = self.run_main("`jitx.core`\n", "--python", sys.executable, "--module-root", "jitx")
        self.assertEqual(code, 0)
        self.assertEqual(run.call_args.args[0][0], sys.executable)
        self.assertIn("module pointers clean", stderr)

    def test_unavailable_python_is_a_usage_error(self):
        code, _, stderr = self.run_main(
            "`jitx.core`\n", "--python", str(self.root / "no-python"), "--module-root", "jitx",
        )
        self.assertEqual(code, 2)
        self.assertIn("cannot run module import interpreter", stderr)

    def test_module_root_option_is_repeatable(self):
        code, _, _ = self.run_main(
            "`custompkg.available` `jitxlib.verify` `jitx.missing`\n",
            "--module-root", "custompkg", "--module-root", "jitxlib",
        )
        self.assertEqual(code, 0)


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

    def test_missing_or_invalid_option_values_are_usage_errors(self):
        for args in (
            ["--python"], ["--module-root"], ["--module-root", "jitx..module"],
            ["--module-root", "9bad"], ["--module-root", "jitx.9bad"],
            ["--python", "--skip-module-imports"], ["--module-root", ""],
        ):
            with self.subTest(args=args), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(["check_doc_links.py", *args]), 2)

    def test_dotted_module_root_is_accepted(self):
        """A root may be dotted: the default set is dotted, and a CLI root that
        could not be would be unable to express the thing the check is for."""
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(
            io.StringIO()
        ):
            self.assertIn(
                main([
                    "check_doc_links.py", "--skip-module-imports",
                    "--module-root", "jitxlib.verify",
                ]),
                (0, 1),
            )


class NormalizeTests(unittest.TestCase):
    def test_emphasis_and_whitespace_are_collapsed(self):
        self.assertEqual(normalize("**Build**  `Safety`"), "build safety")


if __name__ == "__main__":
    unittest.main(verbosity=2)
