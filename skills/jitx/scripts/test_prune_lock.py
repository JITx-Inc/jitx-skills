#!/usr/bin/env python3
"""Tests for prune_lock.py.

The rule under test is the one that makes pruning safe: an entry a design uses is
never removed. The plan tests run anywhere. The project test builds a scratch
JITX project in a temp dir and runs the script as a user would; it needs a Python
with jitx 4.6 and jitxlib-parts 2. Set JITX_PYTHON to one: the project tests then
fail if it cannot import jitx. Without JITX_PYTHON they use the running
interpreter, and are skipped when it has no jitx.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import prune_lock
from prune_lock import Refusal, Usage, entry_key, make_plans, plan_prune, pruned, render

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

    def test_unpin_stays_inside_the_used_chains_and_scopes(self) -> None:
        data = lock(
            entry("a", mpn="IDEAL-R-1k"),
            entry("b"),
            entry("c", chain="chain-2", mpn="IDEAL-R-1k"),
            {**entry("d", mpn="IDEAL-R-1k"), "lock_scope": "other"},
        )
        plan = plan_prune(data, self.claimed, [], ["IDEAL-R-1k"])
        self.assertEqual([e["digest"] for e in plan.unpinned], ["a"])
        self.assertEqual([e["digest"] for e in plan.other_kept], ["c"])
        self.assertEqual([e["digest"] for e in plan.stale], ["d"])


class Write(unittest.TestCase):
    """Refusals that must come before any file is written."""

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="prune-lock-"))
        self.addCleanup(shutil.rmtree, self.root)
        data = lock(entry("a"), entry("stale"))
        self.lock = self.root / "parts.lock.json"
        self.lock.write_text(render(data))
        self.usage = Usage()
        self.usage.add(self.lock, {("a", "main", "")})

    def test_existing_backup_is_refused(self) -> None:
        (self.root / "parts.lock.json.bak").write_text("{}")
        with self.assertRaisesRegex(Refusal, "parts.lock.json.bak exists"):
            make_plans(self.usage, [], [], write=True)

    def test_two_spellings_of_one_lock_are_one_file(self) -> None:
        (self.root / "sub").mkdir()
        alias = self.root / "sub" / ".." / "parts.lock.json"
        self.usage.add(alias, {("stale", "main", "")})
        plans = make_plans(self.usage, [], [], write=True)
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].plan.stale, [])

    def test_unpin_with_stale_entries_needs_apply(self) -> None:
        data = lock(entry("a"), entry("b", mpn="IDEAL-R"), entry("stale"))
        self.lock.write_text(render(data))
        self.usage.add(self.lock, {("b", "main", "")})
        with self.assertRaisesRegex(Refusal, "add --apply"):
            make_plans(self.usage, [], ["IDEAL-R"], write=True)
        plans = make_plans(self.usage, [], ["IDEAL-R"], write=True, apply=True)
        removed = [e["digest"] for e in plans[0].plan.removals]
        self.assertEqual(removed, ["stale", "b"])


class Main(unittest.TestCase):
    """main() over two lockfiles, with discovery and the builds stubbed out."""

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="prune-lock-"))
        self.addCleanup(shutil.rmtree, self.root)
        self.addCleanup(os.chdir, os.getcwd())
        (self.root / "pyproject.toml").write_text('[project]\nname = "x"\n')
        usage = Usage()
        self.locks: list[Path] = []
        for name in ("a", "b"):
            path = self.root / name / "parts.lock.json"
            path.parent.mkdir()
            path.write_text(render(lock(entry("a"), entry("stale"))))
            usage.add(path, {("a", "main", "")})
            self.locks.append(path)
        self.before = [path.read_text() for path in self.locks]
        for name, value in {
            "require_jitx": lambda: None,
            "warn_on_version": lambda: None,
            "discover_designs": lambda project: prune_lock.Discovery(["m.D"], [], {}),
            "collect_usage": lambda designs: usage,
        }.items():
            patcher = mock.patch.object(prune_lock, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_main(self, *args: str) -> tuple[int, str]:
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            status = prune_lock.main(["m.D", "--project", str(self.root), *args])
        return status, err.getvalue()

    def unchanged(self) -> bool:
        return [path.read_text() for path in self.locks] == self.before

    def test_both_locks_are_pruned(self) -> None:
        status, err = self.run_main("--apply")
        self.assertEqual(status, 0, err)
        for path in self.locks:
            self.assertNotIn('"stale"', path.read_text())

    def test_a_refusal_on_one_lock_writes_none(self) -> None:
        prune_lock.backup_path(self.locks[1]).write_text("{}")
        status, err = self.run_main("--apply")
        self.assertEqual(status, 2, err)
        self.assertTrue(self.unchanged())
        self.assertFalse(prune_lock.backup_path(self.locks[0]).exists())

    def test_a_lock_changed_after_planning_stops_every_write(self) -> None:
        plan = prune_lock.make_plans

        def plan_then_build(*args: Any, **kwargs: Any) -> list[prune_lock.FilePlan]:
            plans = plan(*args, **kwargs)
            self.locks[1].write_text(self.before[1] + " ")
            return plans

        with mock.patch.object(prune_lock, "make_plans", plan_then_build):
            status, err = self.run_main("--apply")
        self.assertEqual(status, 2, err)
        self.assertEqual(self.locks[0].read_text(), self.before[0])
        self.assertIn(str(self.locks[1].resolve()), err)

    def test_check_with_no_claims_fails_while_a_lock_holds_entries(self) -> None:
        with mock.patch.object(prune_lock, "collect_usage", lambda designs: Usage()):
            status, _ = self.run_main("--check")
            self.assertEqual(status, 1)
            for path in self.locks:
                path.write_text(render(lock()))
            status, err = self.run_main("--check")
            self.assertEqual(status, 0, err)

    def test_a_failed_write_names_what_was_written(self) -> None:
        write = prune_lock.write_atomic

        def fail_second(path: Path, text: str, expected: str) -> None:
            if path == self.locks[1].resolve():
                raise prune_lock.Refusal("disk full", 2)
            write(path, text, expected)

        with mock.patch.object(prune_lock, "write_atomic", fail_second):
            status, err = self.run_main("--apply")
        self.assertEqual(status, 2, err)
        first = self.locks[0].resolve()
        self.assertIn(f"{first} (backup: {prune_lock.backup_path(first)})", err)


def imports_jitx(python: str) -> bool:
    probe = subprocess.run(
        [python, "-c", "import jitx.run, jitxlib.parts.resolver"],
        capture_output=True,
        check=False,
    )
    return probe.returncode == 0


JITX_PYTHON = os.environ.get("JITX_PYTHON") or (
    sys.executable if imports_jitx(sys.executable) else None
)


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


SECOND = textwrap.dedent(
    """
    import jitx
    from jitx.circuit import Circuit
    from jitx.sample import SampleDesign
    from jitx.units import kohm
    from jitxlib.parts import Resistor


    class Pair(Circuit):
        def __init__(self) -> None:
            self.a = jitx.Port()
            self.b = jitx.Port()
            self.r1 = Resistor(resistance=1 * kohm)
            self.r4 = Resistor(resistance=4.7 * kohm)
            self.nets = [self.a + self.r1.p1 + self.r4.p1, self.b + self.r1.p2 + self.r4.p2]


    class Second(SampleDesign):
        circuit = Pair()
    """
)


@unittest.skipUnless(
    JITX_PYTHON, "set JITX_PYTHON to a Python with jitx 4.6 and jitxlib-parts 2"
)
class Project(unittest.TestCase):
    """The script against a real project: a removed component's entry goes, the
    rest stay, and a rebuild after pruning re-resolves nothing."""

    @classmethod
    def setUpClass(cls) -> None:
        assert JITX_PYTHON is not None
        if not imports_jitx(JITX_PYTHON):
            raise AssertionError(
                f"JITX_PYTHON={JITX_PYTHON} cannot import jitx.run and jitxlib.parts"
            )

    def setUp(self) -> None:
        assert JITX_PYTHON is not None
        self.python = JITX_PYTHON
        self.root = Path(tempfile.mkdtemp(prefix="prune-lock-"))
        self.addCleanup(shutil.rmtree, self.root)
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

    def build(self, design: str = "prunedemo.main.Main") -> None:
        done = self.run_in_project("-c", BUILD, design)
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

    def test_an_entry_two_designs_share_is_kept_for_both(self) -> None:
        (self.root / "prunedemo" / "second.py").write_text(SECOND)
        both = ("prunedemo.main.Main", "prunedemo.second.Second")
        for design in both:
            self.build(design)
        self.design.write_text(
            "\n".join(ln for ln in DESIGN.splitlines() if "# REMOVE" not in ln)
        )
        self.build()
        before = json.loads(self.lock.read_text())
        self.assertEqual(len(before["entries"]), 4)

        # Naming one design is refused: the other's entries would count as unused.
        alone = self.run_in_project(str(SCRIPT), both[0], "--apply")
        self.assertEqual(alone.returncode, 2, alone.stdout + alone.stderr)
        self.assertIn("not named: prunedemo.second.Second", alone.stdout)

        check = self.run_in_project(str(SCRIPT), *both, "--check")
        self.assertEqual(check.returncode, 1, check.stdout + check.stderr)
        applied = self.run_in_project(str(SCRIPT), *both, "--apply")
        self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
        after = json.loads(self.lock.read_text())
        queries = sorted(e["query"] for e in after["entries"])
        self.assertEqual(len(queries), 3, queries)
        self.assertFalse([q for q in queries if "3 kiloohm" in q])
        self.assertEqual(len([q for q in queries if "1 kiloohm" in q]), 1)
        self.assertEqual(len([q for q in queries if "4.7 kiloohm" in q]), 1)

        (self.root / "parts.lock.json.bak").unlink()
        check = self.run_in_project(str(SCRIPT), *both, "--check")
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
        self.assertIn("check: 0 stale", check.stdout)


if __name__ == "__main__":
    unittest.main()
