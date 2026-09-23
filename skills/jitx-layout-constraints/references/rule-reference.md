# Rule Reference

The rule system itself is documented and published:
[Design Constraints](https://docs.jitx.com/en/latest/essentials/physical_design/design-constraints.html).
That page owns the anatomy of a constraint, tags and inheritance, conditions, effects,
constraint selection and its algorithm, global and local logical specificity, the pitfalls,
and binary constraints. It is more complete than a restatement here can stay, so this file
no longer carries one.

What stays is the table below, because it is the one thing a documentation page should not
carry: measured answers to specific questions, each against a named version, with where the
evidence lives. A doc page says how the system works. This says what it did when someone
built it.

## Verified behaviors

Each entry is backed by a built design against the named version; the
reference design lives under `evals/cases/reference/`. Entries are added as
the work packages record them.

| Question | Version | Result | Where recorded |
|---|---|---|---|
| Does `stitch_via` find a via class declared on the substrate through a mixin? | 4.4.0rc5.dev2 | Yes. Mixin-reached, direct-attribute, and module-scope via classes each generated 9 vias on a 2.0 mm grid in an 8 mm pour; the same design with no rule generated 0. | `evals/cases/reference/stitch-via/NOTES.md` |
| Does a two-condition clearance rule move code-authored routes, and does the fab floor? | 4.4.0rc5.dev2, runtime 4.4.0-rc.9 | Neither. Two tagged routes authored 0.100 mm apart under a 0.25 mm rule realized at 0.1001 mm; authored 0.020 mm apart they realized at 0.0202 mm, below the 0.09 mm floor; both builds `status: ok`. The width rule on the same nets applied (0.2000 mm). Clearance rules act on router-generated copper and pour voiding; authored geometry is realized as authored and nothing at build checks it. | `evals/cases/reference/net-net-clearance/NOTES.md` |
| Can a direct pad-to-pour connection (no relief) be expressed? | 4.4.0rc5.dev2 | Yes, by a higher-priority `thermal_relief(fab floor gap, spoke width = pad diameter, 4)` on the tagged pad: its void disappears from the computed pour while the default pad keeps four spokes. A higher-priority rule with no effect changes nothing. Visible on the pad's captured `computed_shape`, where the void disappears; the historical run also read it from the fabrication export, which is no longer a verification surface. | `evals/cases/reference/direct-connect/NOTES.md` |
| Does a width rule apply to a code-authored `Route`, and does a higher-rung escape rule beat the class rule on the same net? | 4.4.0rc5.dev2, runtime 4.4.0-rc.9 | Yes to both: a 0.5 mm class trunk and a 0.25 mm tagged escape on the same net realized at 0.5 and 0.25 mm; both routes realized. | `evals/cases/reference/qfn-power-fanout/NOTES.md` |
| Do solver-placed capacitors, vias, puddles, and tagged escape routes realize as placed? | 4.4.0rc5.dev2, runtime 4.4.0-rc.9 | Yes: 8 of 8 escape routes realized, placements and via nets matched the solver, loop area 1.30 mm2 per capacitor. A floating bank with no interactive placement was parked off-board and none realized. The solver was removed on 2026-09-22; the finding about floating circuits stands on its own and the receipt is kept. | `encore/archive/decoupling-solver/decoupling-bank-NOTES.md` |
| Does the thermal-pad via stitcher build a pad on the runtime? | 4.4.0rc5.dev2 | Not yet built in a reference design; unit tests only. | `../jitx-physical-layout/scripts/test_thermal_via_stitch.py` |
| Does a fresh agent route to this skill from the descriptions and produce a checked artifact? | 4.4.0rc5.dev2, runtime 4.4.0-rc.9 | Yes: 7 of 7 checks including the 12 V to ground inner-layer clearance read from capture (0.300 mm); the historical run also read 0.304 mm from the fabrication export, which is no longer a verification surface. Also seen: an unstitched inner pour is dropped as orphan copper. | `evals/receipts/raw/e2e/REPORT.md` (local run log) |
| Does a rule declared on a child `Circuit` apply board-wide or only within that circuit? | 4.4.0rc5.dev2, runtime 4.4.0-rc.9 | Board-wide. A width rule stored only on one child applied to the tagged net's copper in a sibling (0.3000 mm against a 0.12 mm default) and to a tagged net in a circuit that never connects to the rule owner; an untagged net kept the default. | `evals/cases/reference/default-rules/NOTES.md` |
