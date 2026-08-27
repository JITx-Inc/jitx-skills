# Stitch-via class discovery, JITX 4.4.0rc5

## Result

- Mixin-reached class (`JLC04161H_7628.StdViaPreferred`): vias generated, 9.
- Direct substrate attribute (`DirectAttributeSubstrate.DirectStitchVia`): vias generated, 9.
- Module-scope class (`ModuleScopeStitchVia`): vias generated, 9.

All three ways of naming the via class work identically for
`design_constraint(...).stitch_via(...)` on this build, so a stitch rule does not
require the via class to be a structural attribute of the substrate: the class
object itself is what the rule resolves.

## How these were run

The package under test reports `4.4.0rc5.dev2` (`jitxcore 4.4.0rc1`,
`jitxlib-jlcpcb 1.0.1.dev7`). An isolated project was staged with a
`pyproject.toml` declaring `jitx`, `jitxlib-standard`, and `jitxlib-jlcpcb`, and
a flat `<project>/` package holding `__init__.py` plus byte-identical
copies of `stitch_via_design.py` and `check_stitch_via.py`. Every command below
was run from that project root. `$JITX` and `$PY` are the `jitx` and `python`
entry points of the venv that has jitx installed.

The project package is not pip-installed into that venv, so `PYTHONPATH=.` is
prepended to each command. Without it, discovery imports the design files as
top-level modules and fails:

```text
$ $JITX find
designs:
  []
errors:
  import failed:
    stitch_via_design: ModuleNotFoundError("No module named 'stitch_via_design'")
    check_stitch_via: ModuleNotFoundError("No module named 'check_stitch_via'")
```

Runtime start and discovery:

```text
$ $JITX runtime start --background
{
  "mode": "background",
  "pid": 39699,
  "uri": "ws://localhost:<port>/<id>",
  "log_path": ".jitx/logs/runtime.log",
  "exit_code": null
}

$ $JITX runtime status
Runtime: reachable at ws://localhost:<port>/<id>
  PID:   39699
  Mode:  background

$ PYTHONPATH=. $JITX find
designs:
  <project>.stitch_via_design.DirectAttributeViaDesign
  <project>.stitch_via_design.MixinViaDesign
  <project>.stitch_via_design.ModuleScopeViaDesign
```

The runtime started on the first attempt on its own port, no retry needed.

## Mixin-reached class

Code shape: `JLC04161H_7628.StdViaPreferred`, inherited by the predefined
substrate through `JLCPCBVias`, is passed directly to `stitch_via`.

```text
$ PYTHONPATH=. $JITX build <project>.stitch_via_design.MixinViaDesign
Running design <project>.stitch_via_design.MixinViaDesign...
Saving stable design and reference designator table
<project>.stitch_via_design.MixinViaDesign:
  design: <project>.stitch_via_design.MixinViaDesign
  status: ok

$ PYTHONPATH=. $PY -m <project>.check_stitch_via mixin
variant=mixin status=ok via_count=9
```

Via count: 9. Result: vias generated.

## Direct substrate attribute

Code shape: `DirectAttributeSubstrate.DirectStitchVia` aliases the same
`JLC04161H_7628.StdViaPreferred` class as a direct substrate-subclass attribute
and is passed to `stitch_via`.

```text
$ PYTHONPATH=. $JITX build <project>.stitch_via_design.DirectAttributeViaDesign
Running design <project>.stitch_via_design.DirectAttributeViaDesign...
Saving stable design and reference designator table
<project>.stitch_via_design.DirectAttributeViaDesign:
  design: <project>.stitch_via_design.DirectAttributeViaDesign
  status: ok

$ PYTHONPATH=. $PY -m <project>.check_stitch_via direct
variant=direct status=ok via_count=9
```

Via count: 9. Result: vias generated.

## Module-scope class

Code shape: `ModuleScopeStitchVia` is a module-scope subclass of
`JLC04161H_7628.StdViaPreferred` and is passed to `stitch_via`.

```text
$ PYTHONPATH=. $JITX build <project>.stitch_via_design.ModuleScopeViaDesign
Running design <project>.stitch_via_design.ModuleScopeViaDesign...
Saving stable design and reference designator table
<project>.stitch_via_design.ModuleScopeViaDesign:
  design: <project>.stitch_via_design.ModuleScopeViaDesign
  status: ok

$ PYTHONPATH=. $PY -m <project>.check_stitch_via module
variant=module status=ok via_count=9
```

Via count: 9. Result: vias generated.

## Control: the 9 vias come from the rule

Three identical counts are only evidence if the count is zero without a rule, so
a throwaway probe module in the same project submitted a fourth design, same
`StitchBoard` / `JLC04161H_7628` / `StitchCircuit`, with `self.rules = []`, then
reprinted the mixin variant with each via's composed position:

```text
$ PYTHONPATH=. $PY -m <project>.control_probe
no_rule via_count=0
mixin via_count=9
  Proxy at (-2.0, -2.0)
  Proxy at (0.0, -2.0)
  Proxy at (2.0, -2.0)
  Proxy at (-2.0, 0.0)
  Proxy at (0.0, 0.0)
  Proxy at (2.0, 0.0)
  Proxy at (-2.0, 2.0)
  Proxy at (0.0, 2.0)
  Proxy at (2.0, 2.0)
```

With no rule the design yields no vias, and the 9 vias of the mixin variant sit
on a 2.0 mm square grid centered on the 8.0 mm pour, matching
`SquareViaStitchGrid(pitch=2.0, inset=0.5)`. The probe was written for this
check only and is not part of the reference case.

## Later run: after review fixes

Re-run after the review edits to this case: `ControlNoRuleDesign` folded into
the reference module as a fourth design (same `StitchBoard`,
`JLC04161H_7628`, and `StitchCircuit`, with `self.rules = []`), and
`check_stitch_via.py` deriving the expected via count from pour size, pitch, and
inset instead of comparing against a typed number, printing one `PASS` or `FAIL`
line and exiting `1` on a mismatch.

Package versions as before: py-jitx 4.4.0rc5.dev2, jitxlib-jlcpcb 1.0.1.dev7. A
fresh scratch project held `stitch_via_design.py`, `check_stitch_via.py`, and an
`__init__.py` in one package, `PYTHONPATH` set to the project root, and its own
runtime started and stopped for the run. All four designs built `status: ok`.

### One fix, in `check_stitch_via.py`

The first pass of the four checks failed on the three rule variants and passed
on the control:

```text
$ python -m stitch_via_ref.check_stitch_via mixin
FAIL variant=mixin via_count=9 expected=16
exit code 1

$ python -m stitch_via_ref.check_stitch_via direct
FAIL variant=direct via_count=9 expected=16
exit code 1

$ python -m stitch_via_ref.check_stitch_via module
FAIL variant=module via_count=9 expected=16
exit code 1

$ python -m stitch_via_ref.check_stitch_via control
PASS variant=control via_count=0 expected=0
exit code 0
```

The runtime produced the same 9 vias as the first run, so the failure was the
new derivation, not the designs. `expected_grid_count` read

```python
per_axis = int((pour_size - 2.0 * inset) // pitch) + 1
```

which treats `inset` as a margin cut from each edge and then steps a grid across
the remaining span from one side, giving `int(7.0 // 2.0) + 1 = 4` per axis and
16 vias. The file's own comment beside `EXPECTED` said 9, so the formula and the
comment disagreed with each other as shipped.

The runtime does the placement, and the installed python package carries only
the field description: `inset` is the "minimum distance from the stitched
region's boundary to the outermost via centers"
(`jitx/constraints.py:145`). Two different formulas reproduce 9 for this one
parameter set, so a throwaway `grid_probe.py` in the scratch project submitted
three extra module-scope designs on the same board and substrate, captured them,
counted `rd.query(Via)`, and read each via's `transform.translation`:

| pour (mm) | pitch (mm) | inset (mm) | via count | measured x positions |
|---|---|---|---|---|
| 8.0 | 2.0 | 0.5 | 9 | -2.0, 0.0, 2.0 |
| 8.0 | 1.5 | 0.5 | 25 | -3.0, -1.5, 0.0, 1.5, 3.0 |
| 10.0 | 2.0 | 0.5 | 25 | not read |
| 8.0 | 2.0 | 1.5 | 9 | not read |

The grid is anchored on the region center: one via at the center, then whole
pitches outward for as long as every center stays at least `inset` inside the
boundary. Per axis that is `2 * floor((pour_size / 2 - inset) / pitch) + 1`,
which is always odd, and it predicts 3, 5, 5, and 3 per axis for the four rows
above, so 9, 25, 25, and 9 vias. All four match. The competing reading,
`floor((pour_size - 2 * inset) / pitch)`, also gives 9 for the reference
parameters but predicts 16 where the probe measured 25, which is why the probe
was worth running rather than picking the formula that fit the one case.

`expected_grid_count` in `check_stitch_via.py` now computes that count, with the
field description and the derivation in its docstring. The reference parameters
still derive 9, the count remains derived rather than typed in, and nothing else
in the case changed. Pyright reports `0 errors, 0 warnings, 0 informations` on
the edited file. The probe module stayed in the scratch project and is not part
of the reference case.

### Commands and observed output

Run from the scratch project root. Output is verbatim except for the runtime
start and stop JSON, which carry a pid, a port, and an absolute path, and the
dependency-probe and update-notice lines the CLI prints before a build.

```text
$ export PYTHONPATH="<project>"

$ jitx runtime start --background
(JSON with mode, pid, uri, log_path, exit_code)
exit code 0

$ jitx find
designs:
  stitch_via_ref.stitch_via_design.ControlNoRuleDesign
  stitch_via_ref.stitch_via_design.DirectAttributeViaDesign
  stitch_via_ref.stitch_via_design.MixinViaDesign
  stitch_via_ref.stitch_via_design.ModuleScopeViaDesign
exit code 0

$ yes | jitx build stitch_via_ref.stitch_via_design.MixinViaDesign
Running design stitch_via_ref.stitch_via_design.MixinViaDesign...
Saving stable design and reference designator table
stitch_via_ref.stitch_via_design.MixinViaDesign:
  design: stitch_via_ref.stitch_via_design.MixinViaDesign
  status: ok
exit code 0

$ yes | jitx build stitch_via_ref.stitch_via_design.DirectAttributeViaDesign
Running design stitch_via_ref.stitch_via_design.DirectAttributeViaDesign...
Saving stable design and reference designator table
stitch_via_ref.stitch_via_design.DirectAttributeViaDesign:
  design: stitch_via_ref.stitch_via_design.DirectAttributeViaDesign
  status: ok
exit code 0

$ yes | jitx build stitch_via_ref.stitch_via_design.ModuleScopeViaDesign
Running design stitch_via_ref.stitch_via_design.ModuleScopeViaDesign...
Saving stable design and reference designator table
stitch_via_ref.stitch_via_design.ModuleScopeViaDesign:
  design: stitch_via_ref.stitch_via_design.ModuleScopeViaDesign
  status: ok
exit code 0

$ yes | jitx build stitch_via_ref.stitch_via_design.ControlNoRuleDesign
Running design stitch_via_ref.stitch_via_design.ControlNoRuleDesign...
Saving stable design and reference designator table
stitch_via_ref.stitch_via_design.ControlNoRuleDesign:
  design: stitch_via_ref.stitch_via_design.ControlNoRuleDesign
  status: ok
exit code 0

$ python -m stitch_via_ref.check_stitch_via mixin
PASS variant=mixin via_count=9 expected=9
exit code 0

$ python -m stitch_via_ref.check_stitch_via direct
PASS variant=direct via_count=9 expected=9
exit code 0

$ python -m stitch_via_ref.check_stitch_via module
PASS variant=module via_count=9 expected=9
exit code 0

$ python -m stitch_via_ref.check_stitch_via control
PASS variant=control via_count=0 expected=0
exit code 0

$ jitx runtime stop
(JSON with stopped, pid, signal_sent, message)
exit code 0

$ jitx runtime status
Runtime: not running
exit code 0
```

The control still separates the rule from the substrate: 0 vias with
`self.rules = []`, 9 with any of the three ways of naming the via class, so the
first run's conclusion stands.
