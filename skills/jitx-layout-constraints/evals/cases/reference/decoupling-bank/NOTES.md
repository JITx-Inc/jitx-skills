# Decoupling Bank Reference Notes

The reference uses a placeholder QFN with four pads (skill default: four pads).
It has two power pins and two ground pins (skill default: two of each). It is
not a production component model.

## Result

Built and checked against py-jitx 4.4.0rc5.dev2 (jitxlib-standard
4.4.0rc2.dev14, jitxlib-jlcpcb 1.0.1.dev7, jitxlib-parts 1.3.0a0) with a
project-local runtime, substrate `JLC04161H_7628`.

Selected capacitor, from `CapacitorQuery(capacitance=22e-6,
rated_voltage=10.0, type="ceramic", mounting="smd", case=["0402", "0603",
"0805", "1206"], sort=SortKey("area", SortDir.INCREASING))`:

- MPN `C0603X5R100-226MNE`, VENKEL CORP, `data.case = 0603`,
  `data.capacitance = 2.2e-05`, `data.rated_voltage = 10.0`.
- Both bank capacitors resolved to the same part and the same landpattern.

Landpattern values read back from the selected part, not from a case-code
table:

- pad centers `(0.0, 0.668933982822018)` and `(0.0, -0.668933982822018)`, so
  `pad_pitch = 1.337867965644036` mm on the Y axis;
- pad size `0.95` mm across the pitch axis by `0.412129999...` mm along it;
- courtyard bounds `(-0.625, -1.025)` to `(0.625, 1.025)`, so `1.25` mm by
  `2.05` mm.

Solver input: `CapacitorGeometry(body_length=2.05, body_width=1.25,
pad_length=0.41212999999999994, pad_width=0.95,
pad_pitch=1.337867965644036)`, `via_pad_diameter=0.45`
(`JLC04161H_7628.StdViaPreferred.diameter`), `clearance_floor=0.09`
(`min_copper_copper_space`), `capacitor_spacing=0.25`, `grid_step=0.25`,
`search_radius=3.0`, one IC-body keepout. Derived `package_rotation = 90`, the
rotation that puts the part's `p1` on the solver's local negative X.

Solver output, in hint order:

| hint | center (mm) | rotation | power via (mm) | return via (mm) | loop area (mm^2) |
|---|---|---|---|---|---|
| core | (-0.75, -1.25) | 0 | (-1.849998982822018, -1.25) | (0.349998982822018, -1.25) | 1.3008498621165137 |
| io | (-0.75, 1.25) | 0 | (-1.849998982822018, 1.25) | (0.349998982822018, 1.25) | 1.3008498621165137 |

`solution.total_loop_area = 2.6016997242330273` mm^2. These are geometric
proxies in square millimeters, not measured inductances. A different query
result changes the landpattern and therefore these numbers, so re-run the
check after any capacitor substitution.

Check outcome: all five assertions passed. Eight of eight escape routes
realized, both queried capacitor geometries matched the solver input, both
placements read back within the 0.000001 mm tolerance, and all four vias
landed on their solver coordinates and resolved to the intended nets.

## Commands and observed output

Run from the scratch project root, with `PYTHONPATH` covering the project root
and the package directory (`design.py` imports `decoupling_solver` as a
top-level module and the solver is copied beside it). `jitx` and `python` are
the ones from the environment where `jitx`, `jitxlib-jlcpcb`, and
`jitxlib-parts` are installed; a `jitx` CLI from a different environment fails
`jitx find` with `ModuleNotFoundError: No module named 'jitxlib'`. The only
edit to the transcript below is the absolute scratch-project path in the
runtime's `log_path`, shown as `<project>`.

```text
$ export PYTHONPATH="$PWD:$PWD/<project>"
$ jitx runtime start --background
{
  "mode": "background",
  "pid": 46946,
  "uri": "ws://localhost:<port>/<id>",
  "log_path": "<project>/.jitx/logs/runtime.log",
  "exit_code": null
}

$ jitx find
designs:
  <project>.design.DecouplingReference
  <project>.design.DecouplingReference

$ yes | jitx build <project>.design.DecouplingReference
Dependencies recently checked, skipping. Will check again in 51 minutes.
Running design <project>.design.DecouplingReference...
A newer version of JITX is available.
Saving stable design and reference designator table
<project>.design.DecouplingReference:
  design: <project>.design.DecouplingReference
  status: ok

$ python -m <project>.check
[PASS] escape routes realized: 8/8
[PASS] queried capacitor geometry: 2
[PASS] solver placements read back with jitx.query: 2/2
[PASS] solver vias and net membership: 4
[PASS] solver loop areas: 1.300850 mm^2, 1.300850 mm^2

$ jitx runtime stop
{
  "stopped": true,
  "pid": 46946,
  "signal_sent": "SIGTERM",
  "message": "terminated"
}

$ jitx runtime status
Runtime: not running
```

`jitx find` lists the design twice because `check.py` imports `design.py`, so
discovery sees the class through both modules. Both entries are the same
class.

Static and unit checks, run from the skill repository root. Pyright ran outside
the JITX environment, so it was pointed at that interpreter with
`--pythonpath`; without it every `jitx` and `jitxlib` import reports
`reportMissingImports` and almost nothing is type-checked.

```text
$ python -m pyright --pythonpath <jitx-venv>/bin/python \
    skills/jitx-layout-constraints/scripts/decoupling_solver.py \
    skills/jitx-layout-constraints/evals/cases/reference/decoupling-bank/design.py \
    skills/jitx-layout-constraints/evals/cases/reference/decoupling-bank/check.py
0 errors, 0 warnings, 0 informations

$ python skills/jitx-layout-constraints/scripts/test_decoupling_solver.py
Ran 8 tests in 0.424s
OK
```

### Realized escape-route copper

Recorded once from a capture probe, as a geometric cross-check that `p1` (the
power pad) sits on the solver's power side after the rotation fix. Bounds are
design-global, from `route.traces[*].shapes[*].to_shapely().g.bounds`, and net
names come from `rd.nets().find(trace)`:

```text
route[0] net=VCORE bounds=(-2.0000, -1.4000, -1.2689, -1.1000)
route[1] net=VCORE bounds=(-1.9999, -1.3999, -0.7001, -0.3501)
route[2] net=GND   bounds=(-0.2311, -1.4000, 0.5000, -1.1000)
route[3] net=GND   bounds=(0.2000, -1.4000, 1.0000, -0.3500)
route[4] net=VIO   bounds=(-2.0000, 1.1000, -1.2689, 1.4000)
route[5] net=VIO   bounds=(-1.9999, 0.3501, -0.7001, 1.3999)
route[6] net=GND   bounds=(-0.2311, 1.1000, 0.5000, 1.4000)
route[7] net=GND   bounds=(0.2000, 0.3500, 1.0000, 1.4000)
```

Route 0 covers the power via at x = -1.85 and the capacitor power pad centered
at x = -1.4189; route 2 covers the capacitor return pad centered at
x = -0.0811 and the return via at x = 0.35. Power and return sit on the sides
the solver assigned them.

## Changes recorded during the run

Four changes. Item 1 blocked the build, items 2 and 4 blocked the check, and
item 3 was a pyright error only. The solver and `check.py` are unchanged.

1. `query_capacitor_geometry` used `jitx.query.query(capacitor, ...)`. That
   entry point opens `SubstrateContext(root.substrate)` (`jitx/query.py:247`),
   so its root has to be design-rooted; a `Capacitor` root fails
   instantiation with `AttributeError: 'Capacitor' object has no attribute
   'substrate'`. Changed to `jitx.inspect.visit`. `Pad` and `Courtyard` are
   authored objects, so `query` would collapse the transformer graph to
   identity for these targets anyway (`jitx/query.py:209`) and `visit` reads
   the same `trace.transform * element.transform` frames.

2. `package_rotation` had its two vertical branches inverted. Rotation is
   counter-clockwise, so at 90 degrees `(x, y)` maps to `(-y, x)`. For the
   selected part `p1` is at local `(0, +0.6689)`, which needs 90 degrees to
   land on the solver's negative-X power side; the old expression produced
   270, which put `p1` on the return side. Observed: with 270 and the bank
   placed on the board, routes 0, 1, 4, and 6 had empty `traces` and the
   runtime logged `Route targets not in router: ... is damaged on layer 0`;
   with 90 all eight realized. The likely mechanism is that the power puddle
   and the power via were drawn against the return pad, but the runtime does
   not say which target it considered damaged. Changed `90 if dy > 0 else 270`
   to `270 if dy > 0 else 90`.

3. `via_pad_diameter = via_cls.diameter` is typed `float | ViaDiameter`
   (`jitx/via.py:60`) and pyright rejected it as the solver's `float` field.
   Wrapped in `float(...)`; `ViaDiameter` defines `__float__`
   (`jitx/via.py:328`).

4. `ReferenceCircuit` placed the bank with `at(floating=True)`. A floating
   circuit is "subject to interactive placement" (`jitx/circuit.py:314`), and
   with no interactive placement stored the runtime parked the bank at
   `(15.074998982822018, -3.105)`, outside the 16 mm by 12 mm board. All eight
   escape routes then failed with `Route targets not in router: ... is off the
   board on layer 0` and `route.traces` stayed `None` after `capture()`, while
   `jitx build` still reported `status: ok`. Changed to `at(0.0, 0.0)`. A
   headless reference has to place the bank on the board; `floating=True` needs
   a human placement or a stored one to route.

The bank keeps its structure through all four changes: the placements still
come from the pure solver, the hints are still keyed by `Port` objects, and the
routes, puddles, nets, and priority 4 rules still live on the bank.
