# QFN Power Fanout Reference Notes

## Result

The recorded build derived the escape width from every pad selected by the
concrete escape rule, rounding the narrowest measured width to fixed `1 nm`
precision and subtracting one `1 nm` quantum: `0.249999 mm` from a nominal
`0.250000 mm` narrowest selected pad. The checker requires the strict
postcondition, non-empty route traces, width-bearing polyline primitives, and
the expected trunk and escape widths.

An escape width equal to the queried pad width can silently realize polygon
copper instead of a width-bearing centered trace, so the escape sits strictly
inside the pad. The reference module derives the escape width with the pad
inset and grid in `fanout.md`; this record has no build at that width.

## Sources and derived geometry

- Package: generated QFN with 32 leads at `0.5 mm` pitch, both labeled as
  skill defaults in the reference.
- Class trunk: `0.5 mm`, labeled as the skill-default power-class width and
  applied by the `PowerTag` rule at priority 2.
- Pad width, row pitch, and adjacent gap: read from placed pad copper through
  `jitx.query`.
- Fabrication floors: read from `FabricationConstraints` on
  `JLC04161H_7628`.
- Escape width: one `1 nm` quantum inside the narrowest selected pad.
- Escape clearance margin: `0.010000 mm`, labeled as a skill default in the
  reference and added to the fabrication spacing floor.
- Escape rule: priority 4, above the priority-2 power-class rule.

## Build and capture

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
`0.250000 mm`, one 1 nm quantum inside the narrowest pad the rule selects.

Both routes realize as traces with a width, so the Polygon branch of the width
check is not exercised by this reference.
