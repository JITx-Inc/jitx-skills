# Stitch-via class discovery

## Result

- Mixin-reached class (`JLC04161H_7628.StdViaPreferred`): vias generated, 9.
- Direct substrate attribute (`DirectAttributeSubstrate.DirectStitchVia`): vias generated, 9.
- Module-scope class (`ModuleScopeStitchVia`): vias generated, 9.

All three ways of naming the via class work identically for
`design_constraint(...).stitch_via(...)`, so a stitch rule does not
require the via class to be a structural attribute of the substrate: the class
object itself is what the rule resolves.

## How these were run

An isolated project was staged with a
`pyproject.toml` declaring `jitx`, `jitxlib-standard`, and `jitxlib-jlcpcb`, and
a flat `<project>/` package holding `__init__.py` plus byte-identical
copies of `stitch_via_design.py` and `check_stitch_via.py`. The `$JITX find`
and control-probe commands below were run from that project root. `$JITX` and
`$PY` are the `jitx` and `python` entry points of the venv that has jitx
installed.

The project package is not pip-installed into that venv, so `PYTHONPATH=.` is
prepended to each of those commands. Without it, discovery imports the design
files as top-level modules and fails:

```text
$ $JITX find
designs:
  []
errors:
  import failed:
    stitch_via_design: ModuleNotFoundError("No module named 'stitch_via_design'")
    check_stitch_via: ModuleNotFoundError("No module named 'check_stitch_via'")
```

## Mixin-reached class

Code shape: `JLC04161H_7628.StdViaPreferred`, inherited by the predefined
substrate through `JLCPCBVias`, is passed directly to `stitch_via`.

Via count: 9. Result: vias generated.

## Direct substrate attribute

Code shape: `DirectAttributeSubstrate.DirectStitchVia` aliases the same
`JLC04161H_7628.StdViaPreferred` class as a direct substrate-subclass attribute
and is passed to `stitch_via`.

Via count: 9. Result: vias generated.

## Module-scope class

Code shape: `ModuleScopeStitchVia` is a module-scope subclass of
`JLC04161H_7628.StdViaPreferred` and is passed to `stitch_via`.

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

## Grid anchoring

A probe module in the scratch project submitted three extra module-scope
designs on the same board and substrate, captured them, counted
`rd.query(Via)`, and read each via's `transform.translation`:

| pour (mm) | pitch (mm) | inset (mm) | via count | measured x positions |
|---|---|---|---|---|
| 8.0 | 2.0 | 0.5 | 9 | -2.0, 0.0, 2.0 |
| 8.0 | 1.5 | 0.5 | 25 | -3.0, -1.5, 0.0, 1.5, 3.0 |
| 10.0 | 2.0 | 0.5 | 25 | not read |
| 8.0 | 2.0 | 1.5 | 9 | not read |

These pours were centred on the design origin, and the read positions sit
symmetric about it: one via at the center, then whole pitches outward, an odd
count per axis. The count law therefore assumes a region centred on the lattice;
where the grid starts for an offset region is not established. All four rows
match the count law in `expected_grid_count` in `check_stitch_via.py`, which
`test_check_stitch_via.py` checks against these rows. The margin-then-step
reading, `floor((pour_size - 2 * inset) / pitch)` per axis, also gives 9 for the
reference parameters but predicts 16 where the probe measured 25.

## Commands and observed output

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

The control separates the rule from the substrate: 0 vias with
`self.rules = []`, 9 with any of the three ways of naming the via class.
