# Pour and stitch realization reference notes

## Result

Two ground pours, conductor index 1 and index -1, with a square via-stitch grid and a
four-layer antenna keepout, all realized. The numbers below are measured from the captured
design, not authored.

Both pours realized 1270.7821 mm squared. That decomposes: a realized span of
49.380 x 29.380 gives 1450.7844, the 18 x 10 keepout removes 180, and the remaining
0.0023 is corner rounding. Copper to board edge measured 0.3100 against the substrate's
0.3000 floor, so the runtime pulled back 0.010 mm further than the authored buffer. That
extra 0.010 is unexplained and is recorded rather than rationalized.

One `ComputedStitchVia` group on the ground net carried 65 placements: 11 unique x, 7
unique y, every adjacent step exactly 4.0000 mm. The full grid is 77 and exactly the 12
sites inside the keepout are absent, with no emitted-not-predicted and no
predicted-not-emitted. All 65 centres are covered by both realized plane polygons, which
is the only evidence that the two planes are tied to each other.

The keepout void is not expanded by copper clearance: its edge sits on the authored
rectangle.

## Controls, which are the point

Anchors removed and nothing else changed: 65 stitch vias were still emitted, both pours
captured `Empty()`, and the build still reported `status: ok`. This reproduces the
observation in the skill body under a single-variable control. The placed anchor vias are
load-bearing, and neither the via count nor the build status can substitute for measuring
realized pour area.

`KeepOut(via=True)` suppressed the same 12 rule-emitted stitch sites even in the control
where no pour copper realized at all. The suppression therefore comes from the keepout
acting on the stitched region, not from absent copper. This is narrower than reading
`via=True` as blocking only automatic router vias.

Running the generic gate against the no-anchor control gives 7 checks and 7 failures, exit
1, which is the negative test proving the gate is not fail-open.

## Unresolved

The two published readings of `SquareViaStitchGrid.inset`, centre-based and pad-edge, both
predict (11, 7) at pitch 4.0, inset 1.0, pad 0.45. This design cannot discriminate between
them and says so rather than claiming the question closed. Resolving it needs a parameter
set where the two readings differ.

## Versions

Measured with jitx 4.4.3.dev4+gd4a224684, jitxcore 4.4.0, jitxlib-standard 4.4.0 and
jitxlib-jlcpcb 2.0.0 against a runtime binary reporting `jitx_version 4.5.0-develop.15`.
The runtime binary is the version that matters for a realization claim, and it is not the
same as the installed wheel versions.
