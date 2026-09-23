---
name: jitx-layout-constraints
description: "Use when the user asks to set default trace width or clearance, write design rules, set net-to-net, trace-to-pour, trace-to-hole, or per-layer clearance, size power trace width by net class or current, keep one net's copper away from another, tag nets into classes with their own width and spacing, place and route decoupling capacitors, set pour rules (inner or outer layer, heavy copper, sliver removal, thermal relief, direct connect), express pour stitching as a rule, step a wide power trace down to fit a QFN, BGA, or passive pad (fanout or escape width), verify widths and clearances after build, or find out why a design rule did not apply. Covers Tag, design_constraint, UnaryDesignConstraint, BinaryDesignConstraint, builtin tags, OnLayer, AnyObject, priority, all rule effects, FabricationConstraints floors, the Bogatin power and decoupling habits, and after-build checks. Fab minimums, stackups, vias, and routing-structure definitions belong to jitx-substrate-modeler ('set fabrication rules' means the fab floor; design rules above the floor live here). Drawing copper, diagnosing realized pours or stitch vias, control-point mechanics, and the geometry-verification loop belong to jitx-physical-layout. Topology and timing constraints belong to jitx-interconnect-constraints."
---

# JITX Layout Constraints

Own design rules above fabrication floors: defaults, net classes, power,
pour rules, package escapes, decoupling, and checks of applied rules.

## Routing and sources

- Start with [jitx](../jitx/SKILL.md) for environment setup. On an unfamiliar
  install, confirm signatures in installed `jitx/constraints.py`; run
  `pyright` on the project and require zero import/type errors.
- [Design Constraints](https://docs.jitx.com/en/latest/essentials/physical_design/design-constraints.html)
  owns the rule system itself: anatomy, tags and inheritance, conditions,
  effects, constraint selection and its algorithm, global and local logical
  specificity, the pitfalls, and binary constraints. Read it before writing a
  rule.
- [Rule reference](references/rule-reference.md) owns only the evidence table:
  what each behavior did when it was built, against a named version, and where
  the receipt lives. Its pending behaviors remain unverified.
- [Power and pours](references/power-and-pours.md) owns Bogatin tiers,
  power-as-traces policy, pad-to-via sizing, Kelvin lines, layer selection,
  heavy copper, sliver removal, direct connect, and fill between traces.
- [Fanout](references/fanout.md) owns the rule ladder, placed-pad measurements,
  QFN/BGA/passive derivations, and the prohibition on code-side NeckDown.
- [Substrate modeler](../jitx-substrate-modeler/SKILL.md) owns fab floors,
  stackups, vias, routing structures, and fenced pour outlines.
- [Physical layout](../jitx-physical-layout/SKILL.md) owns copper drawing,
  placement, taggable objects, control points, realized pours/stitch vias,
  and geometry verification. Component landpatterns belong to
  [component modeler](../jitx-component-modeler/SKILL.md).
- [Interconnect constraints](../jitx-interconnect-constraints/SKILL.md) owns
  topology, timing, skew, insertion loss, and differential constraints;
  [circuit builder](../jitx-circuit-builder/SKILL.md) owns wiring, passives,
  and basic top-level pours.

Read working designs and their measured receipts in module docstrings:
`jitxexamples.patterns.default_rules`, `.net_net_clearance`,
`.qfn_power_fanout`, `.direct_connect`, and `.stitch_via`.
Use installed `jitxlib.verify` for `rule_width`, `rule_clearance`,
`rule_coverage`, `min_clearance`, `centreline_length`, `shape_geometry`,
`unique_by_specificity`, and `holds_circle`.

## Workflow

1. Read the selected substrate's floors. Resolve missing copper-weight or
   via capability data with substrate modeler before deriving rules.
2. Put four defaults on the `Design`: trace width, copper clearance, pad
   thermal relief, and power/ground width. Adapt the working default-rules
   design to the actual substrate.
3. Enumerate non-default net classes, their width/clearance sources, tags,
   and rules, or record "no non-default net classes" with a reason.
   Label each number at its declaration with a fab field, a datasheet/standard
   revision and page/table/figure, a Bogatin tier, or `skill default` and value.
   Unsourced clearances must be derived from a sourced value and labeled
   `skill default`, or remain open items that fail the check script.
4. Declare tag classes at module scope. Store rules as structural attributes
   beside their objects; follow the rule reference for collection and scope.
   Share common behavior through base tags. Write the priority ladder beside
   the rules: defaults, power/ground and layer-wide rules, classes,
   layer-scoped class overrides, escapes. Give competing overrides distinct
   priorities in that order.
5. Apply the relevant power/pour reference. For every pad reached by a
   tagged class width, measure whether width and clearance fit. Keep the
   class rule when they do; otherwise derive the escape width/clearance pair
   from the fanout reference or fail. Do not hand-pick only conspicuous pads.
6. Put escape rules on the owning circuit; split width transitions at
   `RoutePoint`s, including near vias/layer changes. Follow
   [control-point mechanics](../jitx-physical-layout/references/control-points.md)
   for tag placement and binding. Net each single-ended point through
   `rp.port`; store each route once, never both in a list and an attribute.
   Prefer pad-to-point trunks: via-to-point trunks have realized alone but
   failed inside a full design.
7. Build, capture, and run the project verification gate below. Fix failed
   measurements before completion; name unavailable evidence explicitly.

## Guidance without another complete owner

- Existing JLC04161H-class skill defaults: 0.125 mm trace width and copper
  clearance, thermal relief with 0.125 mm gap, 0.2 mm spokes and four spokes,
  and 0.4 mm power/ground width. Calibrate against the selected substrate.
- Additional class guidance: switch nodes use rail width and EMI-budget
  pour pullback; sensitive analog keeps wider clearance to digital/power;
  high-voltage/mains uses cited creepage clearance to `AnyObject`, optionally
  layer-scoped; isolated domains use cited barrier clearance plus a keepout;
  gate-drive width follows the driver datasheet, with default clearance and
  circuit-owned placement. RF and high-speed differential classes use their
  routing structure's width/clearance; high-current rails may need wider
  ground clearance. Extend the class catalog as the design requires.
- Pending claim, reported from a shipped board but not reproduced here:
  same-tag binary clearance separates differential pairs without changing
  their internal `pair_spacing`, because a coupled span is one trace object.
  Verify the captured pair gap before relying on it.

## Decoupling

Bogatin habits 5 and 7 prioritize loop inductance between IC power/return
pins and capacitors over capacitor count or values. Place capacitors close
as the package permits, with a via at each capacitor pad to the return layer
and short, wide connections. The datasheet decides count, value, and package.
Give headless decoupling blocks explicit positions; follow
[placement prerequisites](../jitx-physical-layout/references/geometry-verification.md#placement-state-is-a-prerequisite)
for interactive placement.

## Verification

After every build, follow the
[capture loop](../jitx-physical-layout/references/geometry-verification.md).
Use [layout_checks.py](scripts/layout_checks.py) for the constraint checks;
it is a library, not the project gate.

- Enumerate expected routes for every override and pass them to `check_routes`.
  Require non-empty traces before width comparisons; a losing override can
  silently leave a route unrealized.
- Check every realized polyline width against its winning rule with a labeled
  tolerance. Wider and narrower both fail. Use `check_route_width` when a
  net/layer carries both trunk and escape widths. A polygon without a width
  field fails; never skip it. A via-to-via route at the via-pad diameter
  fails if it misses the rule: use pad-to-point routing or a matching via pad.
- Measure minimum copper distance between the two nets on the relevant
  layer; require at least the binary clearance. Authored routes need these
  checks too: rules and fab floors do not repair their geometry.
- Read expected values from rule objects with `rule_width` and
  `rule_clearance`; end with `rule_coverage(rules, witnessed)`. Count
  unwitnessed rules separately. Never pass an unexercised rule or substitute
  a second table of expected values.
- For trace-to-pour clearance, thermal relief, and sliver removal, follow
  [pour realization semantics](../jitx-physical-layout/SKILL.md#pour-realization-semantics).
  Report each as unverified from `rd.query`, with its reason; fabrication
  export cannot close those items.

Run the project's check script, for example `python3 -m <project>.check`,
ending it with `raise SystemExit(run_checks([...]))`. Output must show
nonzero checks, zero failures, route counts, measured/expected values, and
rule coverage; exit 0 is required for measured completion. Empty checks,
unrealized routes, wrong widths/clearances, or unwitnessed rules fail.
Record the actual command, exit code, and open items in the
[completion block](../jitx/references/completion-blocks.md), including a
missing runtime. `status: ok` never proves a rule applied.

## Why a rule did not fire

Check reachability, competing priorities, arity and selectors in the
[rule reference](references/rule-reference.md); tag assignment and stitch
materialization in physical layout; routing-structure ownership and floors
in substrate modeler; escape geometry in fanout. Re-run the verification
gate after correction. Consult the evidence table and working-design
receipts before treating a reported behavior as established.

## Completion

Follow [architectural patterns](../jitx/references/architectural-patterns.md)
and run [jitx-code-review](../jitx-code-review/SKILL.md) for self-critique.
Record the four defaults, net-class table or explicit absence, measurement
commands/results, and unverified items in the completion block.
