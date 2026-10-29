"""Prove on a live runtime that the si-channel reference's constraints bind, or that a mutation fails.

Usage: python3 check_si_channel.py {main,cap-no-model,no-routes,no-via-model}

The script stages a throwaway JITX project (a pyproject.toml and a package
holding a copy of ``si_channel_design.py``) in the system temp directory,
starts that project's runtime in the background, runs

    jitx --format json design issues <pkg>.si_channel_design.<Design> --satisfied --wait 60

for each design the variant needs, stops the runtime, and checks the report.

``main`` checks the reference: four Time and four Loss measurements, two
intra-pair and two bundle Skew measurements, every one satisfied, every path
running through its capacitor, and none of the texts that mean a path was not
followed. It then checks that removing the terminating models lowers each
path's delay and loss by exactly the two terminations, and that zeroing the via
model lowers them by exactly the via model.

Each mutation checks two things: the reference checks reject it, and the report
names the cause (the capacitor without a pin model, the unrouted segments, the
via without a model).

Exits 0 when every assertion holds and 1 otherwise, printing what it saw.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from si_channel_design import (
    BGA_TX_DELAY,
    BGA_TX_LOSS,
    BUNDLE_SKEW,
    CONN_TX_DELAY,
    CONN_TX_LOSS,
    INTRA_PAIR_SKEW,
    LOSS_LIMIT,
    TIMING_LIMIT,
    VIA_DELAY,
    VIA_LOSS,
)

HERE = Path(__file__).resolve().parent
DESIGN_FILE = HERE / "si_channel_design.py"
PACKAGE = "si_channel_check"
WAIT_SECONDS = "60"

LEGS = ("tx0.p", "tx0.n", "tx1.p", "tx1.n")
PATHS = {f"bga.{leg}": f"conn.{leg}" for leg in LEGS}
CAP_OF = {f"bga.{leg}": i for i, leg in enumerate(LEGS)}

INTRA_PAIRS = {
    frozenset({"bga.tx0.p", "bga.tx0.n"}),
    frozenset({"bga.tx1.p", "bga.tx1.n"}),
}
BUNDLE_PAIRS = {
    frozenset({"bga.tx0.p", "bga.tx1.p"}),
    frozenset({"bga.tx0.p", "bga.tx1.n"}),
}

# Texts that mean the runtime did not follow a constrained path end to end, or
# followed it with a placeholder model where the design gave none.
NOT_FOLLOWED = (
    "unconnected topology",
    "no path",
    "missing routing structure",
    "not routed yet",
    "placeholder model",
    "unassigned pin",
    "missing connection",
    "unable to find path",
)
NOT_FOLLOWED_CLASSES = {
    "UnconnectedTopology",
    "UnroutedTopology",
    "MissingPinModel",
    "MissingRoutingStructure",
    "MissingStructureModel",
    "UnassignedPin",
    "MissingRoute",
    "BlockedPath",
    "DroppedRoute",
}
MEASUREMENT_CLASSES = {"UnmetTime", "UnmetLoss", "UnmetTimeDiff"}

TIME_TOL = 1e-14  # 0.01 ps
LOSS_TOL = 1e-6  # dB

ENDS = re.compile(r"from ([\w.\[\]]+) to ([\w.\[\]]+)")


@dataclass(frozen=True)
class Issue:
    category: str
    cls: str
    text: str
    satisfied: bool | None
    measured: float | None
    limit_hi: float | None
    pins: tuple[str, ...]

    @property
    def begins(self) -> tuple[str, ...]:
        """The begin end of every ``from A to B`` in the text, in order."""
        return tuple(m.group(1) for m in ENDS.finditer(self.text))

    @property
    def paths(self) -> tuple[tuple[str, str], ...]:
        """Every ``(A, B)`` of a ``from A to B`` in the text, in order."""
        return tuple((m.group(1), m.group(2)) for m in ENDS.finditer(self.text))


@dataclass(frozen=True)
class Report:
    design: str
    complete: bool
    issues: tuple[Issue, ...]

    def of(self, cls: str) -> list[Issue]:
        return [i for i in self.issues if i.cls == cls]

    def measurements(self) -> list[Issue]:
        return [i for i in self.issues if i.cls in MEASUREMENT_CLASSES]


def parse_report(design: str, payload: dict[str, Any]) -> Report:
    issues: list[Issue] = []
    complete = True
    for category in payload["categories"]:
        if category["status"] != "complete":
            complete = False
        for group in category["groups"]:
            for raw in group["issues"]:
                detail = raw.get("detail") or {}
                si = detail.get("signal_integrity") or {}
                measured = si.get("measured_range", {}).get("hi")
                limit_hi = si.get("acceptable_range", {}).get("hi")
                issues.append(
                    Issue(
                        category=category["category"],
                        cls=raw["class"],
                        text=raw["text"],
                        satisfied=si.get("satisfied") if si else None,
                        measured=float(measured) if measured is not None else None,
                        limit_hi=float(limit_hi) if limit_hi is not None else None,
                        pins=tuple(
                            o["ref"] for o in raw["objects"] if o["role"] == "pin"
                        ),
                    )
                )
    return Report(design=design, complete=complete, issues=tuple(issues))


def find_jitx() -> str:
    beside = Path(sys.executable).parent / "jitx"
    if beside.exists():
        return str(beside)
    found = shutil.which("jitx")
    if found is None:
        raise SystemExit("FAIL no jitx executable beside the interpreter or on PATH")
    return found


def stage_project(root: Path) -> None:
    (root / "pyproject.toml").write_text(
        "[project]\n"
        'name = "si-channel-check"\n'
        'version = "0.1"\n'
        'dependencies = ["jitx>=4.6.0rc10,<5"]\n'
        'requires-python = ">=3.12"\n'
    )
    pkg = root / PACKAGE
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    shutil.copyfile(DESIGN_FILE, pkg / DESIGN_FILE.name)


def run(cmd: list[str], root: Path) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ, PYTHONPATH=str(root))
    return subprocess.run(
        cmd, check=False, cwd=root, env=env, capture_output=True, text=True
    )


def issues_of(jitx: str, root: Path, design: str) -> Report:
    dotted = f"{PACKAGE}.si_channel_design.{design}"
    proc = run(
        [
            jitx,
            "--format",
            "json",
            "design",
            "issues",
            dotted,
            "--satisfied",
            "--wait",
            WAIT_SECONDS,
            "--project",
            str(root),
        ],
        root,
    )
    if proc.returncode != 0:
        raise SystemExit(
            f"FAIL jitx design issues {dotted} exited {proc.returncode}\n"
            f"{proc.stdout}\n{proc.stderr}"
        )
    report = parse_report(design, json.loads(proc.stdout))
    print(f"--- {design} ({len(report.issues)} issues)")
    for issue in report.issues:
        print(f"  [{issue.cls}] {issue.text}")
    return report


def by_begin(issues: list[Issue]) -> dict[str, Issue]:
    return {i.begins[0]: i for i in issues if i.begins}


def check_reference(r: Report) -> list[str]:
    """Problems that stop ``r`` from counting as a fully bound reference."""
    problems: list[str] = []
    if not r.complete:
        problems.append("report incomplete: a category was still pending")

    for cls, limit in (("UnmetTime", TIMING_LIMIT), ("UnmetLoss", LOSS_LIMIT)):
        found = r.of(cls)
        ends = {i.paths[0] for i in found if i.paths}
        if ends != set(PATHS.items()):
            problems.append(
                f"{cls}: measured paths {sorted(ends)}, expected {sorted(PATHS.items())}"
            )
        for i in found:
            if not i.satisfied:
                problems.append(f"{cls} not satisfied: {i.text}")
            if i.limit_hi is None or abs(i.limit_hi - limit) > limit * 1e-9:
                problems.append(f"{cls} limit {i.limit_hi}, expected {limit}: {i.text}")
            if i.begins and i.begins[0] in CAP_OF:
                cap = CAP_OF[i.begins[0]]
                if f"caps[{cap}].a" not in i.pins or f"caps[{cap}].b" not in i.pins:
                    problems.append(
                        f"{cls} path does not run through caps[{cap}]: {i.pins}"
                    )

    skews = r.of("UnmetTimeDiff")
    for expected, limit, label in (
        (INTRA_PAIRS, INTRA_PAIR_SKEW, "intra-pair"),
        (BUNDLE_PAIRS, BUNDLE_SKEW, "bundle"),
    ):
        hits = [
            s
            for s in skews
            if s.limit_hi is not None and abs(s.limit_hi - limit) < limit * 1e-6
        ]
        pairs = {frozenset(s.begins) for s in hits}
        if pairs != expected:
            problems.append(
                f"{label} skew: measured {sorted(map(sorted, pairs))}, "
                f"expected {sorted(map(sorted, expected))}"
            )
        for s in hits:
            if not s.satisfied:
                problems.append(f"{label} skew not satisfied: {s.text}")
    if len(skews) != len(INTRA_PAIRS) + len(BUNDLE_PAIRS):
        problems.append(f"{len(skews)} skew measurements, expected 4")

    for i in r.issues:
        lowered = i.text.lower()
        if i.cls in NOT_FOLLOWED_CLASSES or any(t in lowered for t in NOT_FOLLOWED):
            problems.append(f"path not followed or not modeled: [{i.cls}] {i.text}")
    return problems


def check_delta(
    ref: Report, probe: Report, delay: float, loss: float, what: str
) -> list[str]:
    """Each path in ``probe`` measures ``delay`` and ``loss`` below ``ref``."""
    problems: list[str] = []
    for cls, step, tol in (
        ("UnmetTime", delay, TIME_TOL),
        ("UnmetLoss", loss, LOSS_TOL),
    ):
        a, b = by_begin(ref.of(cls)), by_begin(probe.of(cls))
        for begin in PATHS:
            if begin not in a or begin not in b:
                problems.append(f"{what}: no {cls} for {begin} in both reports")
                continue
            ma, mb = a[begin].measured, b[begin].measured
            if ma is None or mb is None:
                problems.append(f"{what}: {cls} for {begin} has no measured value")
                continue
            drop = ma - mb
            ok = abs(drop - step) <= tol
            print(
                f"  {'ok ' if ok else 'BAD'} {what} {cls} {begin}: "
                f"{ma:.6g} - {mb:.6g} = {drop:.6g}, expected {step:.6g}"
            )
            if not ok:
                problems.append(
                    f"{what}: {cls} {begin} dropped {drop}, expected {step}"
                )
    return problems


def check_main(jitx: str, root: Path) -> list[str]:
    ref = issues_of(jitx, root, "SiChannelDesign")
    no_term = issues_of(jitx, root, "NoTerminationDesign")
    ideal_via = issues_of(jitx, root, "IdealViaDesign")
    problems = check_reference(ref)
    problems += [f"NoTerminationDesign: {p}" for p in check_reference(no_term)]
    problems += [f"IdealViaDesign: {p}" for p in check_reference(ideal_via)]
    print("model deltas:")
    problems += check_delta(
        ref,
        no_term,
        BGA_TX_DELAY + CONN_TX_DELAY,
        BGA_TX_LOSS + CONN_TX_LOSS,
        "terminations",
    )
    problems += check_delta(ref, ideal_via, VIA_DELAY, VIA_LOSS, "via model")
    return problems


def rejected(r: Report) -> list[str]:
    """The reference checks must fail on a mutation."""
    found = check_reference(r)
    print(f"reference checks on {r.design}: {len(found)} problems (expected some)")
    for p in found:
        print(f"  {p}")
    return [] if found else [f"{r.design}: the reference checks accepted a mutation"]


def check_cap_no_model(jitx: str, root: Path) -> list[str]:
    r = issues_of(jitx, root, "CapNoModelDesign")
    problems = rejected(r)
    named = [
        i
        for i in r.issues
        if "no pin model" in i.text.lower()
        and "caps[0].a" in i.text
        and "caps[0].b" in i.text
        and "from bga.tx0.p to conn.tx0.p" in i.text
    ]
    if not named:
        problems.append(
            "no issue names caps[0] as the part without a pin model on bga.tx0.p"
        )
    on_path = [m for m in r.measurements() if "bga.tx0.p" in m.begins]
    if on_path:
        problems.append(f"bga.tx0.p still measures: {[m.text for m in on_path]}")
    others = {i.begins[0] for i in r.of("UnmetTime") if i.begins}
    if others != set(PATHS) - {"bga.tx0.p"}:
        problems.append(
            f"the three unaffected paths should still measure; got {sorted(others)}"
        )
    return problems


def check_no_routes(jitx: str, root: Path) -> list[str]:
    r = issues_of(jitx, root, "NoRoutesDesign")
    problems = rejected(r)
    unrouted = [
        i
        for i in r.issues
        if "unconnected topology" in i.text.lower()
        or "not routed yet" in i.text.lower()
    ]
    if not unrouted:
        problems.append("no Unconnected Topology or not-routed-yet issue")
    if r.measurements():
        problems.append(
            f"unrouted design still measures: {[m.text for m in r.measurements()]}"
        )
    return problems


def check_no_via_model(jitx: str, root: Path) -> list[str]:
    r = issues_of(jitx, root, "NoViaModelDesign")
    problems = rejected(r)
    placeholder = [
        i
        for i in r.issues
        if "placeholder model" in i.text.lower() and '"BareEscapeVia"' in i.text
    ]
    if not placeholder:
        problems.append("no issue reports the placeholder model for BareEscapeVia")
    return problems


CHECKS = {
    "main": check_main,
    "cap-no-model": check_cap_no_model,
    "no-routes": check_no_routes,
    "no-via-model": check_no_via_model,
}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check the si-channel reference or a mutation."
    )
    parser.add_argument("variant", choices=sorted(CHECKS))
    args = parser.parse_args()

    jitx = find_jitx()
    root = Path(tempfile.mkdtemp(prefix="si-channel-check-"))
    started = False
    try:
        stage_project(root)
        start = run(
            [jitx, "runtime", "start", "--background", "--project", str(root)], root
        )
        if start.returncode != 0:
            print(
                f"FAIL runtime start exited {start.returncode}\n{start.stdout}\n{start.stderr}"
            )
            return 1
        started = True
        problems = CHECKS[args.variant](jitx, root)
    finally:
        if started:
            stop = run([jitx, "runtime", "stop", "--project", str(root)], root)
            if stop.returncode != 0:
                print(f"warning: runtime stop exited {stop.returncode}: {stop.stderr}")
        shutil.rmtree(root, ignore_errors=True)

    for p in problems:
        print(f"FAIL {p}")
    status = "FAIL" if problems else "PASS"
    print(f"{status} variant={args.variant} problems={len(problems)}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
