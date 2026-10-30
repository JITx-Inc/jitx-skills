#!/usr/bin/env python3
"""List, and on request remove, the parts.lock.json entries a design does not use.

Run it with the project's Python, from the project root, naming every design the
lock serves (as `jitx build` names them):

    python prune_lock.py my_board.main.MyDesign
    python prune_lock.py my_board.main.MyDesign --apply

The designs are elaborated in-process under the `replay` lock mode, which reads
the lock, asks no provider, and writes nothing. Each lockfile records the keys
its queries claimed; an entry no query claimed is unused. Unused entries under a
chain the designs resolve through are stale. Unused entries under a chain no
named design uses belong to another chain the project may switch back to; they
are listed and kept unless `--remove-chain LABEL` names that chain.

By default nothing changes. `--apply` copies the lock to `<lock>.bak`, then
rewrites it without the stale entries, byte for byte the build's own format, so
`git diff` shows only removals.

It refuses to judge a lock the designs do not match: when any query fails to
replay (a component added or edited since the last build, a renamed chain), it
prints those queries and exits 1. Build first, then rerun.

The keys a run claimed are read from `jitxlib.parts.resolver._active`, a private
name, checked on jitxlib-parts 2.0.0rc2.dev3. If that changes, this exits 2
rather than guess.

Exit codes: 0 listed or removed; 1 the lock does not match the designs; 2 usage,
import, instantiation, or an unreadable lock.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import shutil
import sys
import traceback
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

Key = tuple[str, str, str]
"""An entry's lock key: (query digest, chain label, lock_scope)."""

CHECKED_ON = "2.0.0rc2.dev3"


class Refusal(Exception):
    """A reason to stop before changing anything, with its exit status."""

    def __init__(self, message: str, status: int) -> None:
        super().__init__(message)
        self.status = status


@dataclass
class Usage:
    """What the designs claimed, per lockfile path."""

    claimed: dict[Path, set[Key]] = field(default_factory=dict)


@dataclass
class Plan:
    """One lockfile's entries, sorted by what happens to them."""

    used: list[Mapping[str, Any]] = field(default_factory=list)
    stale: list[Mapping[str, Any]] = field(default_factory=list)
    other_removed: list[Mapping[str, Any]] = field(default_factory=list)
    other_kept: list[Mapping[str, Any]] = field(default_factory=list)
    drop_chains: list[str] = field(default_factory=list)

    @property
    def removals(self) -> list[Mapping[str, Any]]:
        return self.stale + self.other_removed


def entry_key(entry: Mapping[str, Any]) -> Key:
    return (str(entry["digest"]), str(entry["chain"]), str(entry.get("lock_scope", "")))


def render(data: Mapping[str, Any]) -> str:
    """The text the build writes for this lock data (`Lockfile.write`)."""
    return json.dumps(data, indent=1, sort_keys=False) + "\n"


def plan_prune(
    data: Mapping[str, Any], claimed: set[Key], remove_chains: Iterable[str]
) -> Plan:
    """Sort a lock's entries by whether the designs claimed them.

    Pure, so the rule that matters is testable without JITX: a claimed key is
    never removed, and a chain the designs did not use is removed only when named.
    """
    entries: list[Mapping[str, Any]] = list(data.get("entries", []) or [])
    labels = set((data.get("chains", {}) or {}).keys())
    used_chains = {key[1] for key in claimed}
    named = set(remove_chains)
    for label in sorted(named):
        if label in used_chains:
            raise Refusal(
                f"--remove-chain {label}: the designs resolve through chain "
                f"{label}; its unused entries are already listed as stale",
                2,
            )
        if label not in labels and not any(e.get("chain") == label for e in entries):
            raise Refusal(f"--remove-chain {label}: the lock has no such chain", 2)

    present = {entry_key(e) for e in entries}
    missing = sorted(claimed - present)
    if missing:
        raise Refusal(
            f"{len(missing)} claimed key(s) are not in the lock file; it changed "
            f"during the run. Rerun.",
            1,
        )

    plan = Plan()
    for entry in entries:
        key = entry_key(entry)
        if key in claimed:
            plan.used.append(entry)
        elif key[1] in used_chains:
            plan.stale.append(entry)
        elif key[1] in named:
            plan.other_removed.append(entry)
        else:
            plan.other_kept.append(entry)
    kept_chains = {entry_key(e)[1] for e in plan.used + plan.other_kept}
    plan.drop_chains = sorted(label for label in named if label not in kept_chains)
    return plan


def pruned(data: Mapping[str, Any], plan: Plan) -> dict[str, Any]:
    """The lock data without the plan's removals, every other field untouched."""
    gone = {entry_key(e) for e in plan.removals}
    out = dict(data)
    out["entries"] = [e for e in data.get("entries", []) if entry_key(e) not in gone]
    if plan.drop_chains:
        out["chains"] = {
            label: record
            for label, record in (data.get("chains", {}) or {}).items()
            if label not in plan.drop_chains
        }
    return out


def read_lock(path: Path) -> tuple[dict[str, Any], str]:
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
    except (OSError, ValueError) as exc:
        raise Refusal(f"cannot read {path}: {exc}", 2) from exc
    if not isinstance(data, dict) or not isinstance(data.get("entries", []), list):
        raise Refusal(f"{path} is not a parts lockfile", 2)
    return data, text


def write_atomic(path: Path, text: str) -> None:
    """Temp file in the same directory, fsync, rename; keep the file's mode."""
    temp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    mode = path.stat().st_mode & 0o777
    try:
        with temp.open("w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp, mode)
        os.replace(temp, path)
    except BaseException:
        temp.unlink(missing_ok=True)
        raise


def describe(entry: Mapping[str, Any]) -> str:
    identity: Mapping[str, Any] = entry.get("identity", {}) or {}
    maker = identity.get("manufacturer")
    part = f"{identity.get('mpn', '?')}" + (f" ({maker})" if maker else "")
    scope = entry.get("lock_scope") or ""
    where = f"{entry.get('chain', '?')}" + (f" scope={scope}" if scope else "")
    return f"  {where:<12} {part:<34} {entry.get('query', '')}"


def no_dump(ob: Mapping[str, Any] | str, /, file: Any = None) -> None:
    """`DryRunBuilder.build` requires a formatter; nothing is dumped."""


def collect_usage(designs: Sequence[str], project: Path) -> Usage:
    """Elaborate each design under `replay` and return the keys it claimed.

    Raises `Refusal` with status 2 when a design cannot be imported or built, and
    with status 1 when any query does not replay from the lock.
    """
    os.chdir(project)
    sys.path.insert(0, str(project))
    try:
        from jitx.run import DryRunBuilder
        from jitxlib.parts import resolver
        from jitxlib.parts.lock import LockMode, force_mode
        from jitxlib.parts.resolver import EventKind, name_of, parts_verdict
    except ImportError as exc:
        raise Refusal(
            f"cannot import jitx or jitxlib.parts ({exc}); run this with the "
            f"project's Python",
            2,
        ) from exc

    force_mode(LockMode.REPLAY)
    errors: list[str] = []
    for spec in designs:
        module_name, _, class_name = spec.rpartition(".")
        try:
            design = getattr(importlib.import_module(module_name), class_name)
        except Exception as exc:
            raise Refusal(
                f"cannot import design {spec}:\n{traceback.format_exc()}", 2
            ) from exc
        result = DryRunBuilder().build(design, name=spec, formatter=no_dump)
        if result.get("errors"):
            errors.append(f"{spec}: {json.dumps(result['errors'], indent=1)}")

    verdict = parts_verdict()
    misses = [e for e in verdict.events if e.kind is not EventKind.PINNED]
    if misses:
        lines = [
            f"  {name_of(e.kind, verdict.mode)}: {e.description}"
            + (f"\n    at {e.origin}" if e.origin else "")
            for e in misses
        ]
        raise Refusal(
            "the lock does not match the design(s); these queries did not replay:\n"
            + "\n".join(lines)
            + "\nBuild every design first (jitx build), then rerun.",
            1,
        )
    if errors:
        raise Refusal("design(s) failed to build:\n" + "\n".join(errors), 2)

    try:
        lockfiles = resolver._active.run.lockfiles
    except AttributeError as exc:
        raise Refusal(
            f"jitxlib.parts no longer exposes the run's lockfiles where this "
            f"script reads them (checked on {CHECKED_ON}); it cannot tell which "
            f"entries are used",
            2,
        ) from exc

    usage = Usage()
    for path, lockfile in lockfiles.items():
        if path is None:
            continue
        usage.claimed[Path(path)] = set(lockfile.seen_keys)
    if not usage.claimed:
        raise Refusal(
            "the design(s) resolved no parts through a lockfile; name the designs "
            "the lock belongs to",
            1,
        )
    return usage


def prune_one(
    path: Path, claimed: set[Key], remove_chains: Iterable[str], apply: bool
) -> bool:
    """List one lockfile's entries; with `apply`, remove the stale ones.

    Returns whether the file was rewritten.
    """
    data, text = read_lock(path)
    plan = plan_prune(data, claimed, remove_chains)
    print(
        f"{path}: {len(plan.used) + len(plan.removals) + len(plan.other_kept)} "
        f"entries; {len(plan.used)} used, {len(plan.stale)} stale, "
        f"{len(plan.other_removed) + len(plan.other_kept)} under other chains"
    )
    if plan.stale:
        print("stale (no named design uses these):")
        print("\n".join(describe(e) for e in plan.stale))
    if plan.other_removed:
        print("other chains, removed by --remove-chain:")
        print("\n".join(describe(e) for e in plan.other_removed))
    if plan.other_kept:
        labels = sorted({entry_key(e)[1] for e in plan.other_kept})
        print(
            f"other chains, kept (no named design uses {', '.join(labels)}; "
            f"--remove-chain LABEL removes one):"
        )
        print("\n".join(describe(e) for e in plan.other_kept))
    if not plan.removals:
        print("nothing to remove")
        return False
    if not apply:
        print(f"dry run: nothing changed; --apply removes {len(plan.removals)}")
        return False

    if render(data) != text:
        raise Refusal(
            f"{path} is not in the format the build writes, so a rewrite would "
            f"change more than the removals; build to rewrite it, then rerun",
            2,
        )
    out = pruned(data, plan)
    gone = {entry_key(e) for e in plan.removals}
    if gone & claimed:  # plan_prune guarantees this; checked again before writing
        raise Refusal("refusing to remove an entry the design uses", 2)
    backup = path.with_name(path.name + ".bak")
    shutil.copy2(path, backup)
    write_atomic(path, render(out))
    print(f"backup: {backup}")
    count = len(plan.removals)
    print(f"removed {count} {'entry' if count == 1 else 'entries'} from {path}")
    return True


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="List (and with --apply remove) lockfile entries no design uses."
    )
    parser.add_argument(
        "designs",
        nargs="+",
        metavar="DESIGN",
        help="module.path.DesignClass; name every design the lock serves",
    )
    parser.add_argument(
        "--project", default=".", help="project root (default: current directory)"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="remove the listed entries, after copying the lock to <lock>.bak",
    )
    parser.add_argument(
        "--remove-chain",
        action="append",
        default=[],
        metavar="LABEL",
        help="also remove every entry under this chain, which no named design uses",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    project = Path(args.project).resolve()
    if not (project / "pyproject.toml").is_file():
        print(f"error: no pyproject.toml in {project}", file=sys.stderr)
        return 2
    try:
        usage = collect_usage(args.designs, project)
        written = [
            prune_one(path, claimed, args.remove_chain, args.apply)
            for path, claimed in sorted(usage.claimed.items())
        ]
    except Refusal as refusal:
        print(f"error: {refusal}", file=sys.stderr)
        return refusal.status
    if any(written):
        print(
            "next: build, run `jitx design export parts-check <design> --fail all`, "
            "and show the user `git diff` of the lock"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
