#!/usr/bin/env python3
"""Tests for prune_lock.py.

The rule under test is the one that makes pruning safe: an entry a design uses is
never removed. The plan tests run anywhere. The project test builds a scratch
JITX project in a temp dir and runs the script as a user would; it needs a Python
with jitx 4.6 and jitxlib-parts 2, named by JITX_PYTHON or found as the running
interpreter, and is skipped without one.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from prune_lock import Refusal, entry_key, plan_prune, pruned, render

SCRIPT = Path(__file__).resolve().with_name("prune_lock.py")


def entry(digest: str, chain: str = "main", mpn: str = "X") -> dict[str, Any]:
    return {
        "digest": digest,
        "chain": chain,
        "lock_scope": "",
        "query": f"resistor({digest})",
        "identity": {"mpn": mpn},
    }


def lock(*entries: dict[str, Any]) -> dict[str, Any]:
    chains = {e["chain"]: {"digest": e["chain"] + "-d"} for e in entries}
    return {"schema_version": 1, "chains": chains, "entries": list(entries)}


class Plan(unittest.TestCase):
    def setUp(self) -> None:
        self.data = lock(
            entry("a"), entry("b"), entry("stale"), entry("old", chain="chain-2")
        )
        self.claimed = {("a", "main", ""), ("b", "main", "")}

    def test_claimed_entries_are_never_removed(self) -> None:
        for named in ([], ["chain-2"]):
            plan = plan_prune(self.data, self.claimed, named)
            removed = {entry_key(e) for e in plan.removals}
            self.assertFalse(removed & self.claimed)
            kept = {entry_key(e) for e in pruned(self.data, plan)["entries"]}
            self.assertTrue(self.claimed <= kept)

    def test_unclaimed_entry_on_a_used_chain_is_stale(self) -> None:
        plan = plan_prune(self.data, self.claimed, [])
        self.assertEqual([e["digest"] for e in plan.stale], ["stale"])

    def test_other_chain_is_kept_unless_named(self) -> None:
        plan = plan_prune(self.data, self.claimed, [])
        self.assertEqual([e["digest"] for e in plan.other_kept], ["old"])
        self.assertIn("chain-2", pruned(self.data, plan)["chains"])
        plan = plan_prune(self.data, self.claimed, ["chain-2"])
        self.assertEqual([e["digest"] for e in plan.other_removed], ["old"])
        self.assertNotIn("chain-2", pruned(self.data, plan)["chains"])

    def test_naming_a_used_chain_is_refused(self) -> None:
        with self.assertRaises(Refusal):
            plan_prune(self.data, self.claimed, ["main"])

    def test_claimed_key_missing_from_the_file_is_refused(self) -> None:
        with self.assertRaises(Refusal):
            plan_prune(self.data, self.claimed | {("gone", "main", "")}, [])


def jitx_python() -> str | None:
    """An interpreter that can import jitx.run and jitxlib.parts, or None."""
    candidates = [os.environ.get("JITX_PYTHON"), sys.executable]
    for candidate in candidates:
        if not candidate:
            continue
        probe = subprocess.run(
            [candidate, "-c", "import jitx.run, jitxlib.parts.resolver"],
            capture_output=True,
            check=False,
        )
        if probe.returncode == 0:
            return candidate
    return None


BUILD = textwrap.dedent(
    """
    import importlib, sys
    sys.path.insert(0, ".")
    from jitx.run import DryRunBuilder
    spec = sys.argv[1]
    module, _, name = spec.rpartition(".")
    design = getattr(importlib.import_module(module), name)
    result = DryRunBuilder().build(design, name=spec, formatter=lambda ob, /, file=None: None)
    sys.exit(1 if result.get("errors") else 0)
    """
)

DESIGN = textwrap.dedent(
    """
    import jitx
    from jitx.circuit import Circuit
    from jitx.sample import SampleDesign
    from jitx.units import kohm
    from jitxlib.parts import Resistor


    class Board(Circuit):
        def __init__(self) -> None:
            self.a = jitx.Port()
            self.b = jitx.Port()
            self.r1 = Resistor(resistance=1 * kohm)
            self.r2 = Resistor(resistance=2 * kohm)
            self.r3 = Resistor(resistance=3 * kohm)  # REMOVE
            self.nets = [self.a + self.r1.p1 + self.r2.p1, self.b + self.r1.p2 + self.r2.p2]


    class Main(SampleDesign):
        circuit = Board()
    """
)


@unittest.skipUnless(
    jitx_python(), "needs JITX_PYTHON with jitx 4.6 and jitxlib-parts 2"
)
class Project(unittest.TestCase):
    """The script against a real project: a removed component's entry goes, the
    rest stay, and a rebuild after pruning re-resolves nothing."""

    def setUp(self) -> None:
        python = jitx_python()
        assert python is not None
        self.python = python
        self.root = Path(tempfile.mkdtemp(prefix="prune-lock-"))
        (self.root / "pyproject.toml").write_text(
            '[project]\nname = "prunedemo"\nversion = "0.1.0"\n\n'
            '[tool.jitx.parts]\nchain = ["ideal"]\n'
        )
        package = self.root / "prunedemo"
        package.mkdir()
        (package / "__init__.py").write_text("")
        self.design = package / "main.py"
        self.design.write_text(DESIGN)
        self.lock = self.root / "parts.lock.json"

    def run_in_project(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [self.python, *args],
            cwd=self.root,
            # The design file is rewritten within one second at the same size,
            # which a cached .pyc would not notice.
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            capture_output=True,
            text=True,
            check=False,
        )

    def build(self) -> None:
        done = self.run_in_project("-c", BUILD, "prunedemo.main.Main")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)

    def mpns(self) -> list[str]:
        data = json.loads(self.lock.read_text())
        return sorted(e["identity"]["mpn"] for e in data["entries"])

    def test_removed_component_entry_is_pruned_and_nothing_else(self) -> None:
        self.build()
        self.assertEqual(len(self.mpns()), 3)
        self.design.write_text(
            "\n".join(ln for ln in DESIGN.splitlines() if "# REMOVE" not in ln)
        )
        self.build()
        before_text = self.lock.read_text()
        before = json.loads(before_text)
        self.assertEqual(len(before["entries"]), 3)  # the lock never prunes itself

        listed = self.run_in_project(str(SCRIPT), "prunedemo.main.Main")
        self.assertEqual(listed.returncode, 0, listed.stdout + listed.stderr)
        self.assertIn("1 stale", listed.stdout)
        self.assertIn("3 kiloohm", listed.stdout)
        # A listing changes nothing.
        self.assertEqual(self.lock.read_text(), before_text)

        applied = self.run_in_project(str(SCRIPT), "prunedemo.main.Main", "--apply")
        self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
        self.assertEqual((self.root / "parts.lock.json.bak").read_text(), before_text)
        after_text = self.lock.read_text()
        after = json.loads(after_text)
        expected = [e for e in before["entries"] if "3 kiloohm" not in e["query"]]
        self.assertEqual(after["entries"], expected)
        self.assertEqual(after_text, render({**before, "entries": expected}))

        # The two used entries were kept, so a rebuild replays them and the lock
        # is not rewritten.
        self.build()
        self.assertEqual(self.lock.read_text(), after_text)

    def test_unbuilt_edit_is_refused_and_changes_nothing(self) -> None:
        self.build()
        before_text = self.lock.read_text()
        self.design.write_text(DESIGN.replace("2 * kohm", "5 * kohm"))
        done = self.run_in_project(str(SCRIPT), "prunedemo.main.Main", "--apply")
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn("did not replay", done.stderr)
        self.assertEqual(self.lock.read_text(), before_text)


if __name__ == "__main__":
    unittest.main()
