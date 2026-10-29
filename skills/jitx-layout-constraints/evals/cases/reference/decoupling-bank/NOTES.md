# Decoupling Bank Reference Notes

The reference uses a placeholder QFN with four pads (skill default: four pads).
It has two power pins and two ground pins (skill default: two of each). It is
not a production component model.

## Result

Built and checked against jitx 4.6.0rc8 (jitxlib-parts 2.0.0rc2.dev3,
jitxlib-standard 4.6.0rc3.dev12, jitxlib-jlcpcb 4.0.0a4) with a project-local
runtime, substrate `JLC04161H_7628`.

The design carries its own parts chain: `parts =
PartSource([CsvParts(...)])` over `approved-capacitors.csv` beside
`design.py`, with the lock off because the CSV is fixed. The CSV holds three
22 uF rows from the `jitxexamples` example passives, listed largest case first
on purpose. The query's `rank="case"` picks the smallest qualified case code
whatever the row order: in a `jitx.test` probe against this file, the same
query without `rank=` returned the first row, `C3216X5R1V226M160AC` (1206), and
with it returned `CL10A226MP8NUNE` (0603).

The reference passes a whole `CapacitorQuery` with its own `case=` tuple, where
`decoupling.md` passes keywords. `DecouplingReference` sets no Design-level
`CapacitorQuery` default, so the tuple stands in for one. In a project, the
case codes belong to the Design default, and an explicit query would replace
that default instead of adding to it.

Selected capacitor, from `CapacitorQuery(capacitance=22e-6 * F,
rated_voltage_dc=AtLeast(10.0 * V), type="ceramic", mounting="smd",
case=("0402", "0603", "0805", "1206"), rank="case")`:

- MPN `CL10A226MP8NUNE`, Samsung Electro-Mechanics, `case = 0603`,
  `rated_voltage_dc = 10.0 volt`.
- Both bank capacitors resolved to the same part and the same landpattern.

Landpattern values read back from the selected part, not from a case-code
table:

- pad centers `(0.0, 0.843933982822018)` and `(0.0, -0.843933982822018)`, so
  `pad_pitch = 1.687867965644036` mm on the Y axis;
- pad size `0.95` mm across the pitch axis by `0.7621320343559642` mm along it;
- courtyard `1.65` mm by `3.15` mm.

Solver input: `CapacitorGeometry(body_length=3.1500000000000004,
body_width=1.6500000000000001, pad_length=0.7621320343559642,
pad_width=0.9500000000000001, pad_pitch=1.687867965644036)`,
`via_pad_diameter` from `JLC04161H_7628.StdViaPreferred.diameter`,
`clearance_floor` from `min_copper_copper_space`, `capacitor_spacing=0.25`,
`grid_step=0.25`, `search_radius=3.0`, `escape_width=0.3` (the narrowest
served pad: `min(capacitor pad width 0.95, placeholder IC pad width 0.30)`),
one IC-body keepout. Derived `package_rotation = 90`, the rotation that puts
the part's `p1` on the solver's local negative X.

Solver output, in hint order:

| hint | center (mm) | rotation | power via (mm) | return via (mm) | loop area (mm^2) |
|---|---|---|---|---|---|
| core | (-0.25, -2.25) | 90 | (-0.25, -3.7) | (-0.25, -0.8) | 0.9431801948466053 |
| io | (-0.25, 2.25) | 270 | (-0.25, 3.7) | (-0.25, 0.8) | 0.9431801948466053 |

`solution.total_loop_area = 1.8863603896932106` mm^2. These are geometric
proxies in square millimeters, not measured inductances. A different query
result changes the landpattern and therefore these numbers, so re-run the
check after any capacitor substitution.

Each capacitor's `p1` joins the IC power pin it serves through
`ShortTrace(cap.p1, hint.power_ports[0])` and its `p2` joins the shared
`GND` net. After capture, `rd.nets.find(cap.p1)` and `rd.nets.find(pin)` are
the same net for both hints.

Check outcome: every assertion passed. Eight of eight escape routes realized
at the `0.3` mm escape width (the priority 4 escape rule wins over the
priority 1 power and ground width of `0.4` mm), both queried capacitor
geometries matched the solver input, both placements read back within the
0.000001 mm tolerance, all four vias landed on their solver coordinates and
resolved to the intended nets, and both power puddles resolved to their rail
nets.

## Commands and observed output

The scratch project holds `design.py`, `check.py`, `__init__.py`, and
`approved-capacitors.csv` in one package, `decoupling_ref`, with copies of
`scripts/decoupling_solver.py` and `scripts/layout_checks.py` in a `scripts/`
directory beside it. `PYTHONPATH` covers the project root (for the package)
and the `scripts/` directory (`design.py` imports `decoupling_solver` as a
top-level module). `jitx` and `python` are the entry points of the
environment holding the packages above; a `jitx` CLI from a different
environment fails `jitx find` with `ModuleNotFoundError: No module named
'jitxlib'`. Output is verbatim except for the dependency-check line the CLI
prints before a build, the absolute path in the runtime's `log_path`, and the
object ids in the `route-width` lines, shown as `<id>`.

```text
$ export PYTHONPATH="<project>:<project>/scripts"

$ jitx runtime start --background
{
  "mode": "background",
  "pid": 79978,
  "uri": "ws://localhost:<port>/<id>",
  "log_path": "<project>/.jitx/logs/runtime.log",
  "exit_code": null
}
exit code 0

$ jitx find
designs:
  decoupling_ref.design.DecouplingReference
  decoupling_ref.design.DecouplingReference
exit code 0

$ yes | jitx build decoupling_ref.design.DecouplingReference
decoupling_ref.design.DecouplingReference:
  design: decoupling_ref.design.DecouplingReference
  status: ok
exit code 0

$ python -m decoupling_ref.check
[PASS] escape routes realized: 8/8
[PASS] queried capacitor geometry: 2
[PASS] solver placements read back with jitx.query: 2/2
[PASS] solver vias and net membership: 4
PASS route-width: measured=0.3000 expected=0.3000 route=Proxied(Route)[<id>] tol=0.0000 mm
PASS route-width: measured=0.3000 expected=0.3000 route=Proxied(Route)[<id>] tol=0.0000 mm
PASS route-width: measured=0.3000 expected=0.3000 route=Proxied(Route)[<id>] tol=0.0000 mm
PASS route-width: measured=0.3000 expected=0.3000 route=Proxied(Route)[<id>] tol=0.0000 mm
PASS route-width: measured=0.3000 expected=0.3000 route=Proxied(Route)[<id>] tol=0.0000 mm
PASS route-width: measured=0.3000 expected=0.3000 route=Proxied(Route)[<id>] tol=0.0000 mm
PASS route-width: measured=0.3000 expected=0.3000 route=Proxied(Route)[<id>] tol=0.0000 mm
PASS route-width: measured=0.3000 expected=0.3000 route=Proxied(Route)[<id>] tol=0.0000 mm
summary: checks=8 failures=0
[PASS] power puddles on their rail nets: 2
[PASS] solver loop areas: 0.943180 mm^2, 0.943180 mm^2
exit code 0

$ jitx runtime stop
{
  "stopped": true,
  "pid": 79978,
  "signal_sent": "SIGTERM",
  "message": "terminated"
}
exit code 0

$ jitx runtime status
Runtime: not running
exit code 0
```

`jitx find` lists the design twice because `check.py` imports `design.py`, so
discovery sees the class through both modules. Both entries are the same
class.

Static and unit checks, run from the skill repository root. Pyright ran outside
the JITX environment, so it was pointed at that interpreter with
`--pythonpath`; without it every `jitx` and `jitxlib` import reports
`reportMissingImports` and almost nothing is type-checked. `check.py`
narrows `rd.root.circuit` to `ReferenceCircuit` before reading
`.decoupling`: the installed `jitx` types it as `Circuit`, and pyright
rejects the attribute without the narrowing. It imports `design` as a
top-level module (its `_add_paths` puts this directory first on `sys.path`), so
one import serves both a direct run and `python -m <package>.check`.

```text
$ python -m pyright --pythonpath <jitx-venv>/bin/python \
    skills/jitx-layout-constraints/scripts/decoupling_solver.py \
    skills/jitx-layout-constraints/evals/cases/reference/decoupling-bank/*.py
0 errors, 0 warnings, 0 informations

$ python skills/jitx-layout-constraints/scripts/test_decoupling_solver.py
Ran 11 tests in 1.844s
OK
```

### Realized escape-route copper

Recorded from a capture probe, as a geometric cross-check that `p1` (the power
pad) sits on the solver's power side after rotation. Bounds are design-global,
from `route.traces[*].shapes[*].to_shapely().g.bounds`, and net names come
from `rd.nets.find(trace)` (the rail nets carry no `name=`, so they report
their attribute path):

```text
route[0] net=rail_nets[0] bounds=(-0.4000, -3.8500, -0.1000, -2.9439)
route[1] net=rail_nets[0] bounds=(-1.2040, -3.8500, -0.1000, -0.3501)
route[2] net=GND bounds=(-0.4000, -1.5561, -0.1000, -0.6500)
route[3] net=GND bounds=(-0.3999, -0.9499, 0.9999, -0.3501)
route[4] net=rail_nets[1] bounds=(-0.4000, 2.9439, -0.1000, 3.8500)
route[5] net=rail_nets[1] bounds=(-1.2040, 0.3501, -0.1000, 3.8500)
route[6] net=GND bounds=(-0.4000, 0.6500, -0.1000, 1.5561)
route[7] net=GND bounds=(-0.3999, 0.3501, 0.9999, 0.9499)
```

The core capacitor sits at `(-0.25, -2.25)` with a total rotation of 180
degrees, so its `p1` pad center lands at y = -3.0939 and its `p2` pad center at
y = -1.4061. Route 0 covers the power via at y = -3.7 and the `p1` pad; route
2 covers the `p2` pad and the return via at y = -0.8. Power and return sit on
the sides the solver assigned them.

## Fixes this reference carries

Four changes made while the reference was first built, on an earlier
installation whose capacitor query returned a different 0603 part (`p1` at
local `(0, +0.6689)`). Item 1 blocked the build, items 2 and 4 blocked the
check, and item 3 was a pyright error only.

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
