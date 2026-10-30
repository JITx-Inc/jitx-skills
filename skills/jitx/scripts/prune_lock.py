#!/usr/bin/env python3
"""List, and on request remove, the parts.lock.json entries no design uses.

Run it with the project's Python, from the project root, naming every design that
writes the lock (as `jitx build` names them):

    python prune_lock.py my_board.main.MyDesign
    python prune_lock.py my_board.main.MyDesign --apply
    python prune_lock.py my_board.main.MyDesign --check
    python prune_lock.py my_board.main.MyDesign --unpin IDEAL-R-1.27e+06-0402

It finds the project's designs as `jitx design find` does and says which were not
named. `--apply`, `--check` and `--unpin` refuse until every one is named or
excluded with `--exclude DESIGN`, and while any module fails to import; an
excluded design's entries count as unused. A design that needs constructor
arguments is skipped, as `jitx build-all` skips it.

The named designs are elaborated in-process under the `replay` lock mode, which
reads the lock, asks no provider, and writes nothing. Each lockfile records the
keys its queries claimed, read after each design. An entry no query claimed is
unused. Unused entries under a chain the designs resolve through are stale.
Unused entries under a chain no named design uses belong to another chain the
project may switch back to; they are listed and kept unless `--remove-chain
LABEL` names that chain.

By default nothing changes. `--apply` removes the stale entries. `--unpin MPN`
removes the entries pinning that part under the chains and scopes the designs
use, so the next build resolves them again; it refuses while stale entries
remain unless `--apply` removes them in the same write. Both plan every lockfile first, refuse if `<lock>.bak` exists, copy the
lock there, and rewrite it in the build's own format, so `git diff` shows only
removals. `--check` exits 1 when any stale entry exists, and 0 when the
designs resolve no parts through a lockfile.

It refuses to judge a lock the designs do not match: when any query fails to
replay (a component added or edited since the last build, a renamed chain), it
prints those queries and exits 1. Build first, then rerun.

The keys a run claimed are read from `jitxlib.parts.resolver._active`, a private
name, checked on jitxlib-parts 2.0.0rc2.dev3. Another version prints a warning;
if the name is gone, this exits 2 rather than guess.

Exit codes: 0 listed, checked clean, or removed; 1 the lock does not match the
designs, or `--check` found stale entries; 2 usage, discovery, import, build, an
unreadable lock, or a refused write.
"""

from __future__ import annotations

import argparse
import importlib
import importlib.metadata
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
    """What the named designs claimed, per lockfile, keyed by resolved path."""

    claimed: dict[Path, set[Key]] = field(default_factory=dict)

    def add(self, path: Path, keys: Iterable[Key]) -> None:
        self.claimed.setdefault(path.resolve(), set()).update(keys)


@dataclass
class Plan:
    """One lockfile's entries, sorted by what happens to them."""

    used: list[Mapping[str, Any]] = field(default_factory=list)
    stale: list[Mapping[str, Any]] = field(default_factory=list)
    other_removed: list[Mapping[str, Any]] = field(default_factory=list)
    other_kept: list[Mapping[str, Any]] = field(default_factory=list)
    unpinned: list[Mapping[str, Any]] = field(default_factory=list)
    drop_chains: list[str] = field(default_factory=list)

    @property
    def removals(self) -> list[Mapping[str, Any]]:
        return self.stale + self.other_removed + self.unpinned


@dataclass
class FilePlan:
    """A lockfile, the text the plan was made from, and what to write."""

    path: Path
    text: str
    plan: Plan
    out_text: str | None = None


def entry_key(entry: Mapping[str, Any]) -> Key:
    return (str(entry["digest"]), str(entry["chain"]), str(entry.get("lock_scope", "")))


def entry_mpn(entry: Mapping[str, Any]) -> str:
    identity: Mapping[str, Any] = entry.get("identity", {}) or {}
    return str(identity.get("mpn", ""))


def render(data: Mapping[str, Any]) -> str:
    """The text the build writes for this lock data (`Lockfile.write`)."""
    return json.dumps(data, indent=1, sort_keys=False) + "\n"


def plan_prune(
    data: Mapping[str, Any],
    claimed: set[Key],
    remove_chains: Iterable[str],
    unpin: Iterable[str] = (),
) -> Plan:
    """Sort a lock's entries by whether the designs claimed them.

    Pure, so the rule that matters is testable without JITX: a claimed key is
    never removed as stale, a chain the designs did not use is removed only when
    named, and an unpinned part is removed only under a chain and scope the
    designs use.
    """
    entries: list[Mapping[str, Any]] = list(data.get("entries", []) or [])
    labels = set((data.get("chains", {}) or {}).keys())
    used_chains = {key[1] for key in claimed}
    used_scopes = {(key[1], key[2]) for key in claimed}
    named = set(remove_chains)
    unpins = set(unpin)
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
        if entry_mpn(entry) in unpins and (key[1], key[2]) in used_scopes:
            plan.unpinned.append(entry)
        elif key in claimed:
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


def backup_path(path: Path) -> Path:
    return path.with_name(path.name + ".bak")


def write_atomic(path: Path, text: str, expected: str) -> None:
    """Temp file in the same directory, fsync, rename; keep the file's mode.

    Refuses if the file no longer holds `expected`, the text the plan was made
    from, so a build that wrote the lock meanwhile keeps its pins.
    """
    temp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    mode = path.stat().st_mode & 0o777
    try:
        with temp.open("w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp, mode)
        if path.read_text(encoding="utf-8") != expected:
            raise Refusal(
                f"{path} changed while this ran; nothing was written to it. Rerun.", 2
            )
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


def warn_on_version() -> None:
    try:
        installed = importlib.metadata.version("jitxlib-parts")
    except importlib.metadata.PackageNotFoundError:
        return
    if installed.split("+")[0] != CHECKED_ON:
        print(
            f"warning: jitxlib-parts {installed} is installed; this script reads "
            f"its run state and was checked on {CHECKED_ON}",
            file=sys.stderr,
        )


@dataclass
class Discovery:
    """The project's designs as `jitx design find` lists them."""

    found: list[str]
    parameterized: list[str]
    """Designs that need constructor arguments, which `jitx build-all` skips too."""
    failures: dict[str, str]
    """Modules that did not import, with the error."""


def needs_arguments(design: type) -> bool:
    """The test `jitx build-all` uses to skip a design it cannot build alone."""
    signature = getattr(design, "__signature__", None)
    if signature is None or not signature.parameters:
        return False
    try:
        signature.bind()
    except TypeError:
        return True
    return False


def discover_designs(project: Path) -> Discovery:
    from jitx.run import DesignFinder

    finder = DesignFinder(str(project))
    found: set[str] = set()
    parameterized: set[str] = set()
    for design in finder.find_all():
        name = f"{design.__module__}.{design.__name__}"
        (parameterized if needs_arguments(design) else found).add(name)
    failures = {name: repr(exc) for name, exc in finder.exceptions.items()}
    return Discovery(sorted(found), sorted(parameterized), failures)


def require_jitx() -> None:
    try:
        importlib.import_module("jitx.run")
        importlib.import_module("jitxlib.parts.resolver")
    except ImportError as exc:
        raise Refusal(
            f"cannot import jitx or jitxlib.parts ({exc}); run this with the "
            f"project's Python",
            2,
        ) from exc


def claimed_now(usage: Usage) -> None:
    """Add every lockfile's claimed keys in the current run to `usage`."""
    from jitxlib.parts import resolver

    try:
        lockfiles = resolver._active.run.lockfiles
        snapshot = [
            (path, set(lockfile.seen_keys))
            for path, lockfile in lockfiles.items()
            if path is not None
        ]
    except AttributeError as exc:
        raise Refusal(
            f"jitxlib.parts no longer exposes the run's claimed keys where this "
            f"script reads them (checked on {CHECKED_ON}); it cannot tell which "
            f"entries are used",
            2,
        ) from exc
    for path, keys in snapshot:
        usage.add(Path(path), keys)


def collect_usage(designs: Sequence[str]) -> Usage:
    """Elaborate each design under `replay` and return the keys it claimed.

    Claims are read after each design and unioned per resolved lock path, so two
    spellings of one file are one lockfile. Raises `Refusal` with status 2 when a
    design cannot be imported or built, and with status 1 when any query does not
    replay from the lock.
    """
    from jitx.run import DryRunBuilder
    from jitxlib.parts.lock import LockMode, force_mode
    from jitxlib.parts.resolver import EventKind, name_of, parts_verdict

    force_mode(LockMode.REPLAY)
    usage = Usage()
    errors: list[str] = []
    misses: list[str] = []
    for spec in designs:
        module_name, _, class_name = spec.rpartition(".")
        try:
            design = getattr(importlib.import_module(module_name), class_name)
        except Exception as exc:
            raise Refusal(
                f"cannot import design {spec}:\n{traceback.format_exc()}", 2
            ) from exc
        before = parts_verdict()
        start = len(before.events)
        result = DryRunBuilder().build(design, name=spec, formatter=no_dump)
        after = parts_verdict()
        events = after.events[start:] if after is before else after.events
        misses.extend(
            f"  {spec}: {name_of(e.kind, after.mode)}: {e.description}"
            + (f"\n    at {e.origin}" if e.origin else "")
            for e in events
            if e.kind is not EventKind.PINNED
        )
        if result.get("errors"):
            errors.append(f"{spec}: {json.dumps(result['errors'], indent=1)}")
        claimed_now(usage)

    if misses:
        raise Refusal(
            "the lock does not match the design(s); these queries did not replay:\n"
            + "\n".join(misses)
            + "\nBuild every design first (jitx build), then rerun.",
            1,
        )
    if errors:
        raise Refusal("design(s) failed to build:\n" + "\n".join(errors), 2)
    return usage


def report(fp: FilePlan) -> None:
    plan = fp.plan
    total = len(plan.used) + len(plan.removals) + len(plan.other_kept)
    print(
        f"{fp.path}: {total} entries; {len(plan.used)} used, {len(plan.stale)} "
        f"stale, {len(plan.other_removed) + len(plan.other_kept)} under other chains"
    )
    if plan.stale:
        print("stale (no named design uses these):")
        print("\n".join(describe(e) for e in plan.stale))
    if plan.unpinned:
        print("unpinned by --unpin (the next build resolves these again):")
        print("\n".join(describe(e) for e in plan.unpinned))
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


def make_plans(
    usage: Usage,
    remove_chains: Sequence[str],
    unpin: Sequence[str],
    write: bool,
    apply: bool = False,
) -> list[FilePlan]:
    """Plan every lockfile, and refuse before any write if one cannot be written."""
    plans: list[FilePlan] = []
    for path, claimed in sorted(usage.claimed.items()):
        data, text = read_lock(path)
        plan = plan_prune(data, claimed, remove_chains, unpin)
        fp = FilePlan(path, text, plan)
        plans.append(fp)
        if not write or not plan.removals:
            continue
        if render(data) != text:
            raise Refusal(
                f"{path} is not in the format the build writes (a formatter or a "
                f"hand edit changed it), so a rewrite would change more than the "
                f"removals. Rewrite it in the build's format, commit that, then "
                f'rerun: python -c "from jitxlib.parts.lock import Lockfile; '
                f"Lockfile.read('{path}').write()\"",
                2,
            )
        if backup_path(path).exists():
            raise Refusal(
                f"{backup_path(path)} exists from an earlier run; delete it once "
                f"that run's rebuild and parts-check passed, then rerun",
                2,
            )
        if {entry_key(e) for e in plan.stale + plan.other_removed} & claimed:
            raise Refusal("refusing to remove an entry the design uses", 2)
        fp.out_text = render(pruned(data, plan))

    stale = sum(len(fp.plan.stale) for fp in plans)
    if unpin and stale and not apply:
        raise Refusal(
            f"--unpin: {stale} stale entries remain, and the unpinned query could "
            f"adopt one; add --apply to remove them in the same write",
            2,
        )
    if unpin:
        found = {entry_mpn(e) for fp in plans for e in fp.plan.unpinned}
        absent = sorted(set(unpin) - found)
        if absent:
            raise Refusal(
                f"--unpin: no entry pins {', '.join(absent)} under a chain and "
                f"scope the named designs use",
                2,
            )
    return plans


def check_coverage(
    discovery: Discovery, named: Sequence[str], excluded: Sequence[str], acting: bool
) -> None:
    """Say which discovered designs were not named; refuse to act until all are."""
    found, failures = discovery.found, discovery.failures
    unknown = sorted(set(excluded) - set(found) - set(discovery.parameterized))
    if unknown:
        raise Refusal(f"--exclude names no discovered design: {', '.join(unknown)}", 2)
    both = sorted(set(excluded) & set(named))
    if both:
        raise Refusal(f"named and excluded: {', '.join(both)}", 2)
    unnamed = [d for d in found if d not in named and d not in excluded]
    print(f"designs found: {', '.join(found) or 'none'}")
    if excluded:
        print(f"excluded (their entries count as unused): {', '.join(excluded)}")
    if discovery.parameterized:
        print(
            "skipped, needs constructor arguments (`jitx build-all` skips it too): "
            f"{', '.join(discovery.parameterized)}"
        )
    if unnamed:
        print(f"not named: {', '.join(unnamed)}")
    for module, why in sorted(failures.items()):
        print(f"warning: module {module} did not import: {why}", file=sys.stderr)
    if failures and acting:
        raise Refusal(
            f"module(s) did not import, so their designs cannot be counted: "
            f"{', '.join(sorted(failures))}. Fix the import, or, if it holds no "
            f"design, list its file or directory under [tool.jitx] exclude in "
            f"pyproject.toml",
            2,
        )
    if unnamed and acting:
        raise Refusal(
            "name every design that writes this lock, or exclude it with "
            "--exclude DESIGN; an unnamed design's entries would count as unused",
            2,
        )


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="List (and with --apply remove) lockfile entries no design uses."
    )
    parser.add_argument(
        "designs",
        nargs="+",
        metavar="DESIGN",
        help="module.path.DesignClass; name every design that writes the lock",
    )
    parser.add_argument(
        "--project", default=".", help="project root (default: current directory)"
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--apply",
        action="store_true",
        help="remove the stale entries, after copying the lock to <lock>.bak",
    )
    mode.add_argument(
        "--check",
        action="store_true",
        help="change nothing; exit 1 if any stale entry exists",
    )
    parser.add_argument(
        "--unpin",
        action="append",
        default=[],
        metavar="MPN",
        help="remove the entries pinning this part, so the next build resolves it",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="DESIGN",
        help="a discovered design whose entries count as unused, such as a test",
    )
    parser.add_argument(
        "--remove-chain",
        action="append",
        default=[],
        metavar="LABEL",
        help="also remove every entry under this chain, which no named design uses",
    )
    args = parser.parse_args(argv)
    if args.check and args.unpin:
        parser.error("--check changes nothing; it does not take --unpin")
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    project = Path(args.project).resolve()
    if not (project / "pyproject.toml").is_file():
        print(f"error: no pyproject.toml in {project}", file=sys.stderr)
        return 2
    os.chdir(project)
    sys.path.insert(0, str(project))
    write = bool(args.apply or args.unpin)
    try:
        require_jitx()
        warn_on_version()
        discovery = discover_designs(project)
        check_coverage(discovery, args.designs, args.exclude, write or args.check)
        usage = collect_usage(args.designs)
        if not usage.claimed:
            if args.check:
                print("check: the named designs resolved no parts through a lockfile")
                return 0
            raise Refusal(
                "the design(s) resolved no parts through a lockfile; name the "
                "designs the lock belongs to",
                1,
            )
        plans = make_plans(usage, args.remove_chain, args.unpin, write, args.apply)
        for fp in plans:
            report(fp)
        removals = sum(len(fp.plan.removals) for fp in plans)
        stale = sum(len(fp.plan.stale) for fp in plans)
        if args.check:
            print(f"check: {stale} stale")
            return 1 if stale else 0
        if not removals:
            print("nothing to remove")
            return 0
        if not write:
            print(f"dry run: nothing changed; --apply removes {removals}")
            return 0
        writes = [fp for fp in plans if fp.out_text is not None]
        changed = [fp.path for fp in writes if fp.path.read_text("utf-8") != fp.text]
        if changed:
            raise Refusal(
                f"changed while this ran, so nothing was written: "
                f"{', '.join(map(str, changed))}. Rerun.",
                2,
            )
        written: list[Path] = []
        for fp in writes:
            assert fp.out_text is not None
            try:
                shutil.copy2(fp.path, backup_path(fp.path))
                write_atomic(fp.path, fp.out_text, fp.text)
            except (Refusal, OSError) as exc:
                done = "".join(
                    f"\n  {path} (backup: {backup_path(path)})" for path in written
                )
                raise Refusal(
                    f"{exc}\nAlready written, each with its backup:{done or ' none'}"
                    f"\nThe backup of {fp.path}, if made, is "
                    f"{backup_path(fp.path)}.",
                    2,
                ) from exc
            written.append(fp.path)
            count = len(fp.plan.removals)
            print(f"backup: {backup_path(fp.path)}")
            print(
                f"removed {count} {'entry' if count == 1 else 'entries'} from {fp.path}"
            )
    except Refusal as refusal:
        print(f"error: {refusal}", file=sys.stderr)
        return refusal.status
    print(
        "next: build every named design, run `jitx design export parts-check "
        "<design> --fail all` on each, show the user `git diff` of the lock, then "
        "delete the backup"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
