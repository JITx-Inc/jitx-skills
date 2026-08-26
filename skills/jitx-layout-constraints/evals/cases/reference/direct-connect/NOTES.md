# Direct-connect reference case notes

## Result

Direct connect is expressible on jitx 4.4.0rc5.dev2 via candidate 2. A
higher-priority `thermal_relief` whose spoke width equals the pad diameter
removes the tagged pad's relief void completely: the runtime's computed pour
copper has no gap and no spokes at that pad, while the default-thermal pad on
the same net keeps its four 0.2 mm spokes.

Candidate 1, a higher-priority tagged rule carrying no effect, changes nothing.
Both pads come back identical to the inherited default relief.

Two surfaces expose the computed (voided, spoked) pour copper: the raw
`LayoutOutput.computed_shape` recorded before reverse-flow apply, and the legacy
ODB++ `features` file for the pour's layer. `rd.query(Pour)` and
`rd.query(Copper)` return the pre-voiding input outline only, so they cannot
answer this question.

## Scratch project used

Both files were copied unmodified into a throwaway project:

```text
<scratch>/pyproject.toml            # name = "direct_connect", deps jitx, jitxlib-standard, jitxlib-jlcpcb
<scratch>/direct_connect/__init__.py
<scratch>/direct_connect/design.py  # copy of this case's design.py
<scratch>/direct_connect/check.py   # copy of this case's check.py
```

The project needs its own runtime (`jitx runtime start --background`) and the
project root has to be importable. The package was not pip-installed, so
`PYTHONPATH=<project root>` was exported for every command below. Without it
`jitx find` reports `designs: []` and two `ModuleNotFoundError` import failures,
because `DesignFinder.find_by_file` falls back to bare module names when the
package itself is not on `sys.path` (`jitx/run/discover.py:222`).

No changes were made to `design.py` or `check.py`. Both ran as shipped.

One known wart, not a blocker: `check.py` uses `from design import ...`, which
resolves when the file is run as a script (its own directory lands on
`sys.path`) but not when a project tool imports it as `direct_connect.check`.
So `jitx find` lists both designs and additionally reports
`direct_connect.check: ModuleNotFoundError("No module named 'design'")`. Per-design
`jitx build` and `jitx design export` are unaffected; `jitx build-all` would
report that import failure.

## Surfaces

Read against the same design and capture, on both candidates.

| Surface | Computed pour copper visible | Evidence |
| --- | --- | --- |
| `rd.query(Pour)` | not seen | 1 pour, `area=59.997627` against a 10.0 x 6.0 mm authored outline (60.0 mm2), `holes=0`, gap-band coverage 1.000000 at both pads on both candidates |
| `rd.query(Copper)` | not seen | 3 results, and `Pour` is a `Copper` subclass, so those 3 are the 2 pad coppers plus the same un-voided pour. 2 shapes land within 1.2 mm of each pad (that pad's copper plus the pour outline) |
| raw `LayoutOutput.computed_shape` | seen | `computed-holes=2` on candidate 1 and `computed-holes=1` on candidate 2; gap-band coverage 0.155342 vs 1.000000 discriminates the two pads on candidate 2 |
| `Route.derived` | nothing to see here | 0 groups. This design authors no `Route`, so the surface is empty by construction. It is not evidence that route-derived pours are invisible |
| legacy ODB++ `features` | seen | `steps/pcb/layers/l1/features` carries one island contour (`I`) for the pour plus one hole contour (`H`) per relieved pad: 2 holes on candidate 1, 1 hole on candidate 2 |

The gap band the script measures is the annulus from the pad edge (0.8 mm
radius, the 1.6 mm test pad) out to half the 0.09 mm `JLCPCBRules`
copper-to-copper gap (0.845 mm radius). Coverage 1.000000 means solid copper
right up against the pad, so no relief. Coverage 0.155342 is consistent with
four 0.2 mm spokes crossing that annulus: 4 x 0.2 / (2 * pi * 0.8225) = 0.1548
(arithmetic done here, not printed by the script).

## Candidates

**Candidate 1, `DirectConnectNoEffectDesign`: not a direct connect.** The
higher-priority `design_constraint(DirectConnectTag(), priority=1)` with no
effect does not suppress the lower-priority `IsPad` thermal relief. Raw computed
gap-band coverage is 0.155342 at both the default-thermal pad and the tagged
pad, the computed pour keeps 2 holes, and the ODB++ `l1/features` file keeps a
hole contour with the 0.2 mm spoke notches at both (-2.5, 0) and (2.5, 0).

**Candidate 2, `DirectConnectWideSpokeDesign`: a direct connect.** The
higher-priority `thermal_relief(0.09, 1.6, 4)` (fab-floor gap, spoke width equal
to the 1.6 mm pad diameter, 4 spokes) collapses the relief. Raw computed
gap-band coverage is 1.000000 at the tagged pad and still 0.155342 at the
default-thermal pad, the computed pour drops to 1 hole, and the ODB++
`l1/features` file has a hole contour only at (-2.5, 0). At the tagged pad the
only nearby record is the pad placement itself.

There is still no dedicated direct-connect effect in the rule surface. Candidate
2 gets the result by making the spokes as wide as the pad, so the relief
geometry degenerates into solid copper.

## Commands and observed output

All commands run from the scratch project root with
`PATH` and `PYTHONPATH` pointing at the installed interpreter and that root.

Installed version:

```text
$ python -c "from importlib.metadata import version; print(version('jitx'))"
4.4.0rc5.dev2
```

Runtime:

```text
$ jitx runtime start --background
{
  "mode": "background",
  "pid": 40620,
  "uri": "ws://localhost:63248/rgt274",
  "log_path": "<scratch>/.jitx/logs/runtime.log",
  "exit_code": null
}

$ jitx runtime status
Runtime: reachable at ws://localhost:63248/rgt274
  PID:   40620
  Mode:  background
```

Discovery:

```text
$ jitx find
designs:
  direct_connect.design.DirectConnectNoEffectDesign
  direct_connect.design.DirectConnectWideSpokeDesign
errors:
  import failed:
    direct_connect.check: ModuleNotFoundError("No module named 'design'")
```

Builds:

```text
$ yes | jitx build direct_connect.design.DirectConnectNoEffectDesign
Running design direct_connect.design.DirectConnectNoEffectDesign...
Saving stable design and reference designator table
direct_connect.design.DirectConnectNoEffectDesign:
  design: direct_connect.design.DirectConnectNoEffectDesign
  status: ok

$ yes | jitx build direct_connect.design.DirectConnectWideSpokeDesign
Running design direct_connect.design.DirectConnectWideSpokeDesign...
Saving stable design and reference designator table
direct_connect.design.DirectConnectWideSpokeDesign:
  design: direct_connect.design.DirectConnectWideSpokeDesign
  status: ok
```

Capture, candidate 1:

```text
$ python direct_connect/check.py --candidate no-effect
capture Pour count: 1
capture Copper count: 3
capture pour[0]: area=59.997627 holes=0 bounds=(-4.999999984372407, -2.9999999938346447, 4.999999984372407, 2.9999999938346438)
capture pour gap-band coverage at default-thermal: 1.000000
capture pour gap-band coverage at tagged-candidate: 1.000000
capture copper near default-thermal at (-2.5, 0.0): 2 shape(s)
capture copper near tagged-candidate at (2.5, 0.0): 2 shape(s)
raw LayoutOutput pours: 1
raw pour[0]: input=arc_polygon computed-components=1 computed-holes=2
raw computed pour gap-band coverage at default-thermal: 0.155342
raw computed pour gap-band coverage at tagged-candidate: 0.155342
Route.derived pour/feature groups: 0
```

Capture, candidate 2:

```text
$ python direct_connect/check.py --candidate wide-spoke
capture Pour count: 1
capture Copper count: 3
capture pour[0]: area=59.997627 holes=0 bounds=(-4.999999984372407, -2.9999999938346447, 4.999999984372407, 2.9999999938346438)
capture pour gap-band coverage at default-thermal: 1.000000
capture pour gap-band coverage at tagged-candidate: 1.000000
capture copper near default-thermal at (-2.5, 0.0): 2 shape(s)
capture copper near tagged-candidate at (2.5, 0.0): 2 shape(s)
raw LayoutOutput pours: 1
raw pour[0]: input=arc_polygon computed-components=1 computed-holes=1
raw computed pour gap-band coverage at default-thermal: 0.155342
raw computed pour gap-band coverage at tagged-candidate: 1.000000
Route.derived pour/feature groups: 0
```

What the three `rd.query(Copper)` results actually are, from a one-off probe on
candidate 1:

```text
Copper circuit.test.landpattern.thermal_pad layer= 0
Copper circuit.test.landpattern.tagged_pad layer= 0
Pour circuit.ground_pour layer= 0
```

Legacy ODB++ export. Both exports exit 0 and print nothing; they write
`designs/<design>/odb/` and `designs/<design>/outputs/odb.zip`:

```text
$ yes | jitx design export legacy-odb++ direct_connect.design.DirectConnectNoEffectDesign
$ echo $?
0
$ yes | jitx design export legacy-odb++ direct_connect.design.DirectConnectWideSpokeDesign
$ echo $?
0
```

The pour is on layer 0, which the export writes as `l1`. Structural records of
that layer, candidate 1 (`I` is the pour island, `H` a hole contour, `P` a pad
placement):

```text
$ grep -n "^OB\|^OE\|^P \|^S \|^F \|^UNITS" \
    designs/direct_connect.design.DirectConnectNoEffectDesign/odb/steps/pcb/layers/l1/features
1:UNITS=MM
3:F 3
8:S P 0;ID=2
9:OB 5.0000000 2.9550000 I
22:OE
23:OB -1.6031650 0.1000000 H
80:OE
81:OB 3.3968350 0.1000000 H
138:OE
140:P 2.5000000 0.0000000 0 P 0 0 ;0=0,1=0;ID=1
141:P -2.5000000 0.0000000 0 P 0 0 ;0=0,1=0;ID=0
```

Candidate 2, same command against its own export. The second hole contour is
gone:

```text
1:UNITS=MM
3:F 3
8:S P 0;ID=2
9:OB 5.0000000 2.9550000 I
22:OE
23:OB -1.6031650 0.1000000 H
80:OE
82:P 2.5000000 0.0000000 0 P 0 0 ;0=0,1=0;ID=1
83:P -2.5000000 0.0000000 0 P 0 0 ;0=0,1=0;ID=0
```

Each hole contour reaches 0.8968 mm from its pad center (for the pad at -2.5,
the contour runs from -3.3968350 to -1.6031650), which is the 0.8 mm pad radius
plus the 0.09 mm gap with arc-to-polygon overshoot. The repeated 0.1000000 and
-0.1000000 vertices are the 0.2 mm spoke notches.

Feature records near each pad, from the check script with `--odb-root`.
Candidate 1:

```text
$ python direct_connect/check.py --candidate no-effect \
    --odb-root designs/direct_connect.design.DirectConnectNoEffectDesign/odb
...
ODB features: designs/direct_connect.design.DirectConnectNoEffectDesign/odb/steps/pcb/layers/l1/features
  default-thermal: 58 nearby record(s)
    OB -1.6031650 0.1000000 H
    ... 56 contour vertices ...
    P -2.5000000 0.0000000 0 P 0 0 ;0=0,1=0;ID=0
  tagged-candidate: 58 nearby record(s)
    OB 3.3968350 0.1000000 H
    ... 56 contour vertices ...
    P 2.5000000 0.0000000 0 P 0 0 ;0=0,1=0;ID=1
```

Candidate 2:

```text
$ python direct_connect/check.py --candidate wide-spoke \
    --odb-root designs/direct_connect.design.DirectConnectWideSpokeDesign/odb
...
ODB features: designs/direct_connect.design.DirectConnectWideSpokeDesign/odb/steps/pcb/layers/l1/features
  default-thermal: 58 nearby record(s)
    OB -1.6031650 0.1000000 H
    ... 56 contour vertices ...
    P -2.5000000 0.0000000 0 P 0 0 ;0=0,1=0;ID=0
  tagged-candidate: 1 nearby record(s)
    P 2.5000000 0.0000000 0 P 0 0 ;0=0,1=0;ID=1
```

`l1` is the only layer whose `features` file has any records near the pads. The
soldermask and paste layers export `F 0` for this landpattern, because `TestPad`
declares a copper shape only.

Pyright, with inherited color and locale noise disabled, run from the skills
repo root:

```text
$ env -u FORCE_COLOR LC_ALL=C python -m pyright \
    --pythonpath <venv>/bin/python \
    skills/jitx-layout-constraints/evals/cases/reference/direct-connect/design.py \
    skills/jitx-layout-constraints/evals/cases/reference/direct-connect/check.py
0 errors, 0 warnings, 0 informations
```
