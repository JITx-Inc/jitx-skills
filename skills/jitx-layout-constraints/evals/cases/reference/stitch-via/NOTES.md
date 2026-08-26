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
a flat `stitch_via_probe/` package holding `__init__.py` plus byte-identical
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
  "uri": "ws://localhost:63165/vpjfb2",
  "log_path": ".jitx/logs/runtime.log",
  "exit_code": null
}

$ $JITX runtime status
Runtime: reachable at ws://localhost:63165/vpjfb2
  PID:   39699
  Mode:  background

$ PYTHONPATH=. $JITX find
designs:
  stitch_via_probe.stitch_via_design.DirectAttributeViaDesign
  stitch_via_probe.stitch_via_design.MixinViaDesign
  stitch_via_probe.stitch_via_design.ModuleScopeViaDesign
```

The runtime started on the first attempt on its own port, no retry needed.

## Mixin-reached class

Code shape: `JLC04161H_7628.StdViaPreferred`, inherited by the predefined
substrate through `JLCPCBVias`, is passed directly to `stitch_via`.

```text
$ PYTHONPATH=. $JITX build stitch_via_probe.stitch_via_design.MixinViaDesign
Running design stitch_via_probe.stitch_via_design.MixinViaDesign...
Saving stable design and reference designator table
stitch_via_probe.stitch_via_design.MixinViaDesign:
  design: stitch_via_probe.stitch_via_design.MixinViaDesign
  status: ok

$ PYTHONPATH=. $PY -m stitch_via_probe.check_stitch_via mixin
variant=mixin status=ok via_count=9
```

Via count: 9. Result: vias generated.

## Direct substrate attribute

Code shape: `DirectAttributeSubstrate.DirectStitchVia` aliases the same
`JLC04161H_7628.StdViaPreferred` class as a direct substrate-subclass attribute
and is passed to `stitch_via`.

```text
$ PYTHONPATH=. $JITX build stitch_via_probe.stitch_via_design.DirectAttributeViaDesign
Running design stitch_via_probe.stitch_via_design.DirectAttributeViaDesign...
Saving stable design and reference designator table
stitch_via_probe.stitch_via_design.DirectAttributeViaDesign:
  design: stitch_via_probe.stitch_via_design.DirectAttributeViaDesign
  status: ok

$ PYTHONPATH=. $PY -m stitch_via_probe.check_stitch_via direct
variant=direct status=ok via_count=9
```

Via count: 9. Result: vias generated.

## Module-scope class

Code shape: `ModuleScopeStitchVia` is a module-scope subclass of
`JLC04161H_7628.StdViaPreferred` and is passed to `stitch_via`.

```text
$ PYTHONPATH=. $JITX build stitch_via_probe.stitch_via_design.ModuleScopeViaDesign
Running design stitch_via_probe.stitch_via_design.ModuleScopeViaDesign...
Saving stable design and reference designator table
stitch_via_probe.stitch_via_design.ModuleScopeViaDesign:
  design: stitch_via_probe.stitch_via_design.ModuleScopeViaDesign
  status: ok

$ PYTHONPATH=. $PY -m stitch_via_probe.check_stitch_via module
variant=module status=ok via_count=9
```

Via count: 9. Result: vias generated.

## Control: the 9 vias come from the rule

Three identical counts are only evidence if the count is zero without a rule, so
a throwaway probe module in the same project submitted a fourth design, same
`StitchBoard` / `JLC04161H_7628` / `StitchCircuit`, with `self.rules = []`, then
reprinted the mixin variant with each via's composed position:

```text
$ PYTHONPATH=. $PY -m stitch_via_probe.control_probe
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
