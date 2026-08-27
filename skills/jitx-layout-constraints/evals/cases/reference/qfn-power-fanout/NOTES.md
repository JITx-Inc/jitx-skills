# QFN Power Fanout Reference Notes

## Result

- Derived escape geometry: escape width `0.250000 mm`, escape clearance
  `0.100000 mm`, both computed at `Design.Initialized` from queried pad copper
  and `FabricationConstraints`, not typed in as literals.
- Measured after capture: trunk `0.5 mm`, escape `0.25 mm`. Both match their
  intended values (`0.500000 mm` power-class trunk, `0.250000 mm` derived
  escape) within the `1e-6 mm` comparison tolerance.
- Route realization: both routes realized. `trunk_route.traces` and
  `escape_route.traces` are non-empty after `capture()`.

Observed on jitx `4.4.0rc5.dev2` with the runtime that CLI starts.
Two consecutive runs of `check_fanout.py` produced the same numbers and exited
`0`.

## Sources and derived geometry

- Package: generated QFN (skill default: 32 leads) at `0.5 mm` pitch (skill
  default: `0.5 mm` pitch), using `DensityLevel.C`.
- Class trunk: `0.5 mm` width (skill default: `0.5 mm` power-class width),
  applied by the `PowerTag` net rule at priority 2.
- Pad width: `0.250000 mm`, read from placed pad copper with `jitx.query`.
- Row pitch: `0.500000 mm`, read as the tangential spacing to the nearest pad
  in the same row of the queried pad copper.
- Adjacent gap: `0.250000 mm`, the queried `0.500000 mm` row pitch minus the
  queried `0.250000 mm` pad width, cross-checked against
  `target.distance(neighbor)` on the shapely geometry.
- Fabrication floor: `0.090000 mm` copper-to-copper space and `0.090000 mm`
  minimum copper width, from `FabricationConstraints` on `JLC04161H_7628`
  (`jitxlib/jlcpcb/rules.py:8-9`, read in the installed package).
- Escape width: `0.250000 mm`. The centered-channel limit is
  `0.250000 + 2 * (0.250000 - 0.090000) = 0.570000 mm`, so the queried pad
  width is the binding cap here, not the fabrication floor. The escape rule
  sits at priority 4 and wins over the priority-2 power class.
- Escape clearance: `0.100000 mm`, the `0.090000 mm` fabrication floor plus a
  `0.010000 mm` margin (skill default: `0.010000 mm` clearance margin).

## Verification output

`check_fanout.py` copies the reference module into a temporary JITX project,
starts that project's runtime, builds, submits, captures, asserts, and stops
the runtime. It was run from the reference directory. `python` below is the
interpreter of the virtualenv holding jitx `4.4.0rc5.dev2`.

```text
$ cd skills/jitx-layout-constraints/evals/cases/reference/qfn-power-fanout
$ python check_fanout.py
$ python -m jitx runtime start --background
{
  "mode": "background",
  "pid": 43345,
  "uri": "ws://localhost:<port>/<id>",
  "log_path": "<temporary-project>/.jitx/logs/runtime.log",
  "exit_code": null
}
$ python -m jitx build qfn_power_fanout.qfn_power_fanout.QfnPowerFanoutDesign
Failed to parse installer report: Expecting value: line 1 column 1 (char 0)
Error: Failed to check dependencies: Expecting value: line 1 column 1 (char 0)
QFN escape geometry: pad_width=0.250000 mm, adjacent_gap=0.250000 mm, row_pitch=0.500000 mm, escape_width=0.250000 mm, escape_clearance=0.100000 mm
Running design qfn_power_fanout.qfn_power_fanout.QfnPowerFanoutDesign...
A newer version of JITX is available.
Saving stable design and reference designator table
qfn_power_fanout.qfn_power_fanout.QfnPowerFanoutDesign:
  design: qfn_power_fanout.qfn_power_fanout.QfnPowerFanoutDesign
  status: ok
$ python check_fanout.py  # submit, capture, and assertions
QFN escape geometry: pad_width=0.250000 mm, adjacent_gap=0.250000 mm, row_pitch=0.500000 mm, escape_width=0.250000 mm, escape_clearance=0.100000 mm
[PASS] trunk route realized at (0.5,) mm, expected 0.500000 mm
[PASS] escape route realized at (0.25,) mm, expected 0.250000 mm
[PASS] trunk and escape routes have non-empty traces
$ python -m jitx runtime stop
{
  "stopped": true,
  "pid": 43345,
  "signal_sent": "SIGTERM",
  "message": "terminated"
}
```

Process exit status of that run:

```text
EXIT=0
```

The two `Failed to parse installer report` / `Failed to check dependencies`
lines come from the CLI dependency probe in the temporary project, before the
build step. The build proceeded and reported `status: ok`, and the capture
assertions ran, so those lines are not a failure of this reference. The `pid`,
port, and runtime URI change per run.

The `QFN escape geometry:` line prints twice because the module's
`Design.Initialized` hook runs once under `jitx build` and again under the
in-process submit in `capture_and_check`. Both prints agree.

## Fixes

None. The reference module and the check script ran as shipped in this
worktree. No API name, shape transform, event hook, or generator argument
needed changing, and no derived value was replaced with a typed number.

## Decisions

The generated QFN needed a minimal placeholder component and symbol. The
reference maps the power rail to the first generated peripheral pad (skill
default: pad `1`) and uses the next generated peripheral pad for ground (skill
default: pad `2`). The escape route carries the `QfnEscapeTag`, while the
power-class tag stays on the net, so the priority ladder is what resolves the
width at the pad: board default 0, power class 2, QFN escape 4.

Not verified in this run: pyright, the em-dash grep over
`skills/jitx-layout-constraints/references/fanout.md`, and the `NeckDown`
spelling grep. Those checks belong to the skill-development lifecycle and were
outside this run's scope, so no output for them is recorded here.
