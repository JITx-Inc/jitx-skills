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

## Behavior evidence

Rows with linked receipts are backed by built designs against the named
version. Unrecorded rows have no available receipt and remain unverified;
a unit-test link does not establish runtime behavior.

| Question | Version | Result | Where recorded |
|---|---|---|---|
| Does `stitch_via` find a via class declared on the substrate through a mixin? | 4.4.0rc5.dev2 | Yes. Mixin-reached, direct-attribute, and module-scope via classes each generated 9 vias on a 2.0 mm grid in an 8 mm pour; the same design with no rule generated 0. | [Receipt](../evals/cases/reference/stitch-via/NOTES.md) |
| Does a two-condition clearance rule move code-authored routes, and does the fab floor? | 4.4.0rc5.dev2, runtime 4.4.0-rc.9 | Neither. Two tagged routes authored 0.100 mm apart under a 0.25 mm rule realized at 0.1001 mm; authored 0.020 mm apart they realized at 0.0202 mm, below the 0.09 mm floor; both builds `status: ok`. The width rule on the same nets applied (0.2000 mm). Clearance rules act on router-generated copper and pour voiding; authored geometry is realized as authored and nothing at build checks it. | [Receipt](../evals/cases/reference/net-net-clearance/NOTES.md) |
| Can a direct pad-to-pour connection (no relief) be expressed? | 4.4.0rc5.dev2 | Yes, by a higher-priority `thermal_relief(fab floor gap, spoke width = pad diameter, 4)` on the tagged pad: its void disappears from the computed pour while the default pad keeps four spokes. A higher-priority rule with no effect changes nothing. Visible on the pad's captured `computed_shape`, where the void disappears; the historical run also read it from the fabrication export, which is no longer a verification surface. | [Receipt](../evals/cases/reference/direct-connect/NOTES.md) |
| Does a width rule apply to a code-authored `Route`, and does a higher-rung escape rule beat the class rule on the same net? | 4.4.0rc5.dev2, runtime 4.4.0-rc.9 | Yes to both: a 0.5 mm class trunk and a 0.25 mm tagged escape on the same net realized at 0.5 and 0.25 mm; both routes realized. | [Receipt](../evals/cases/reference/qfn-power-fanout/NOTES.md) |
| Do solver-placed capacitors, vias, puddles, and tagged escape routes realize as placed? | 4.4.0rc5.dev2, runtime 4.4.0-rc.9 | Unrecorded here. The solver was removed on 2026-09-22; its placement claims cannot be verified from a shipped receipt. | Unrecorded: archived solver receipt is not included in this bundle. |
| Does the thermal-pad via stitcher build a pad on the runtime? | 4.4.0rc5.dev2 | Not yet built in a reference design; unit tests only. | [Unit tests](../../jitx-physical-layout/scripts/test_thermal_via_stitch.py) |
| Does a fresh agent route to this skill from the descriptions and produce a checked artifact? | 4.4.0rc5.dev2, runtime 4.4.0-rc.9 | Unrecorded. The claimed end-to-end measurements cannot be verified without the run log. | Unrecorded: no end-to-end run log is included in this bundle. |
| Does `routing_structure` apply to a code-authored `Route`, and does it compete with a `trace_width` rule? | 4.4.3.dev4, runtime 4.5.0-develop.15 | Yes to the first: a feed realized at the structure's 0.3244 mm against a 0.1500 mm default. It requires `ref_net` or `ref_layer_nets`. It does not compete with `trace_width`: selection runs one effect type at a time, so both apply and no priority orders them. A neck rule at priority 20 and at 100 both lost to the structure; excluding the escape tag from the structure's condition is the fix. | unrecorded |
| Does a rule declared on a child `Circuit` apply board-wide or only within that circuit? | 4.4.0rc5.dev2, runtime 4.4.0-rc.9 | Board-wide. A width rule stored only on one child applied to the tagged net's copper in a sibling (0.3000 mm against a 0.12 mm default) and to a tagged net in a circuit that never connects to the rule owner; an untagged net kept the default. | [Receipt](../evals/cases/reference/default-rules/NOTES.md) |
