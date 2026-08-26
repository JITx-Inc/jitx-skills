# Direct-connect reference case notes

## Result

The runtime was unavailable for capture. The required scratch package could
not be created because this execution sandbox denied writes to its requested
directory. No build, capture, or legacy ODB++ export ran.

The direct-connect question remains unobserved. Neither candidate is approved
for customer design use:

- Candidate 1 is a higher-priority `DirectConnectTag` unary rule with no
  effect. Local translation produced no effect for that rule, but there is no
  runtime copper result.
- Candidate 2 is a higher-priority thermal relief with the JLCPCBRules
  0.09 mm gap (`jitxlib/jlcpcb/rules.py:9`), a 1.6 mm spoke width (skill default: test-pad diameter), and 4 spokes (skill default). It was not
  submitted because candidate 1 and the observability surface must be tested
  first.

## Surfaces checked in source

- `rd.query(Copper)` and `rd.query(Pour)`: implemented by the check script,
  not run. The installed query surface is at `jitx/run/runtime.py:421`.
- Raw `LayoutOutput.computed_shape`: recorded by the check script before
  reverse-flow apply, not run. Reverse flow reads that field at
  `jitx/_translate/reverse_flow/linker.py:1329`.
- `Route.derived`: inspected in `jitx/circuit.py:564` and
  `jitx/circuit.py:613`. It exposes route-derived pours, not a separate
  board-pour result.
- Legacy ODB++: the installed plugin sends the runtime-side export request at
  `jitx/_runtime/_legacy_plugins.py:83`. The check script parses millimeter
  `features` records near both pads, but no export was available to parse.

## Commands and observed output

Installed version:

```text
$ $JITX_PYTHON -c "from importlib.metadata import version; print(version('jitx').split('+', 1)[0])"
4.4.0rc5.dev2
```

`$REQUESTED_SCRATCH` below is the user-requested job `tmp` directory. The
customer-shipped note does not include its user-specific absolute path.

Required scratch directory creation:

```text
$ mkdir -p "$REQUESTED_SCRATCH/direct_connect"
mkdir: $REQUESTED_SCRATCH/direct_connect: Operation not permitted
```

Runtime probe from the requested scratch parent:

```text
$ $JITX_CLI runtime status
Error: No pyproject.toml found walking up from $REQUESTED_SCRATCH.
```

Local translation probe, not a build:

```text
$ $JITX_PYTHON - <<'PY'
import design
from jitx.run.runtime import _instantiate_design, _package_design
for cls in (design.DirectConnectNoEffectDesign, design.DirectConnectWideSpokeDesign):
    packaged, _ = _package_design(_instantiate_design(cls))
    rules = packaged.v1.design_rules
    print(f"{cls.__name__}: rules={len(rules)} effects={[len(rule.effects) for rule in rules]}")
PY
DirectConnectNoEffectDesign: rules=2 effects=[1, 0]
DirectConnectWideSpokeDesign: rules=2 effects=[1, 1]
```

Build, capture, and ODB++ output:

```text
NOT RUN: the required isolated JITX project could not be created.
```

Pyright, with inherited color and locale noise disabled:

```text
$ env -u FORCE_COLOR LC_ALL=C $JITX_PYTHON -m pyright skills/jitx-layout-constraints/evals/cases/reference/direct-connect/*.py
0 errors, 0 warnings, 0 informations
```

Em-dash check:

```text
$ grep -n $'\u2014' skills/jitx-layout-constraints/references/power-and-pours.md
<no output>
```
