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

A fresh build and capture was run after the correction:

```text
$ python check_fanout.py
QFN escape geometry: pad_width=0.250000 mm, narrowest_rule_pad_width=0.250000 mm,
  adjacent_gap=0.250000 mm, row_pitch=0.500000 mm, escape_width=0.249999 mm,
  escape_clearance=0.100000 mm
qfn_power_fanout.qfn_power_fanout.QfnPowerFanoutDesign:
  design: qfn_power_fanout.qfn_power_fanout.QfnPowerFanoutDesign
  status: ok
[PASS] trunk route realized at (0.5,) mm, expected 0.500000 mm
[PASS] escape route realized at (0.249999,) mm, expected 0.249999 mm
[PASS] trunk and escape routes have non-empty traces
```

The escape realizes at `0.249999 mm` against a queried pad width of
`0.250000 mm`, one 1 nm quantum inside the narrowest pad the rule selects. The
withdrawn receipt recorded `0.250000 mm` for both, which is the defect this
correction addresses: a trace at the pad width is not strictly inside it.

Both routes realize as traces with a width, so the Polygon branch of the width
check is not exercised by this reference. Its own unit test covers it.
