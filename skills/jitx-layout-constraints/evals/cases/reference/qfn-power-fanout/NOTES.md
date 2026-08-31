# QFN Power Fanout Reference Notes

## Current result

The previous captured result used an escape width equal to the queried pad
width. That result is superseded because equality can silently realize polygon
copper instead of a width-bearing centered trace.

The corrected reference derives the width from every pad selected by the
concrete escape rule. It rounds the narrowest measured width to fixed `1 nm`
precision and subtracts one `1 nm` quantum unconditionally. For the generated
placeholder QFN, the expected result is `0.249999 mm` from a nominal
`0.250000 mm` narrowest selected pad. The checker requires the strict
postcondition, non-empty route traces, width-bearing polyline primitives, and
the expected trunk and escape widths.

## Sources and derived geometry

- Package: generated QFN with 32 leads at `0.5 mm` pitch, both labeled as
  skill defaults in the reference.
- Class trunk: `0.5 mm`, labeled as the skill-default power-class width and
  applied by the `PowerTag` rule at priority 2.
- Pad width, row pitch, and adjacent gap: read from placed pad copper through
  `jitx.query`.
- Fabrication floors: read from `FabricationConstraints` on
  `JLC04161H_7628`.
- Escape width quantum: `1 nm`, labeled as a skill default in the reference.
- Escape clearance margin: `0.010000 mm`, labeled as a skill default in the
  reference and added to the fabrication spacing floor.
- Escape rule: priority 4, above the priority-2 power-class rule.

## Verification status

The pure layout-check helper suite passes, including the regression that
treats a realized shape without a width field as a width-rule failure.

A fresh build and capture was attempted after the correction. The JITX runtime
launcher could not open its user statistics file in the restricted execution
environment, so it exited before the build began. No corrected capture result
is claimed. The reference remains pending a run in an environment where the
runtime can write its user state:

```text
$ python check_fanout.py
$ python -m jitx runtime start --background
Error: launcher exited (rc=1) before announcing itself
[runtime.log] Error occurred when attempting to open the user statistics file.
[FAIL] command exited 1: python -m jitx runtime start --background
```

The next successful run must record a `0.249999 mm` expected escape, reject any
`Polygon` realization, and replace this pending status with its real command
output and exit code.
