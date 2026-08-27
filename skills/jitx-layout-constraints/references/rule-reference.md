# Rule Reference

Conditions, effects, and signatures of the JITX design-rule system, cited to
the installed 4.4 source (`jitx/constraints.py`, `jitx/si.py`,
`jitx/substrate.py`, `jitx/copper.py`, `jitx/circuit.py`). Line numbers are
from the `jitx 4.4.0rc5.dev2` build; on another install, open the file and confirm before
relying on a signature. The public PyPI line (4.2.2) has the same class and
method names for everything on this page except where marked.

## Conditions

| Condition | Import | Notes | Source |
|---|---|---|---|
| `Tag` (subclass it) | `jitx.constraints` or `jitx` | Hierarchy by class inheritance: a rule on a base tag matches every subclass tag. `MyTag().assign(obj, *objs)` returns the tag. `Tag.any(*tags)`, `Tag.all(*tags)`. | `constraints.py:344-435` |
| `Tags(a, b, ...)` | same | Assignment vehicle for several tags at once: `Tags(A(), B()).assign(obj, ...)`. | `constraints.py:495-623` |
| Builtin tags: `IsCopper`, `IsTrace`, `IsPour`, `IsVia`, `IsPad`, `IsBoardEdge`, `IsThroughHole`, `IsNeckdown`, `IsHole` | same | Conditions only; `assign()` raises `TypeError`. Their order in the source is coupled to the runtime's selection algorithm. `IsNeckdown` matches copper the engine classifies as a neckdown region; no API creates one. | `constraints.py:444-468`, `:552-554` |
| `OnLayer(index)` | `jitx.constraints` only (not re-exported) | `OnLayer.external()` is `OnLayer(0) \| OnLayer(-1)`; `OnLayer.internal()` is its negation. Negative indices count from the bottom. | `constraints.py:471-492` |
| `AnyObject` | `jitx.constraints` | Matches everything; the usual second condition of a binary rule. | `constraints.py:689` |
| Expressions | | `&` and, `\|` or, `~` not, on tags and expressions alike. Bare `True`/`False` are accepted as conditions. | `constraints.py:391-402`, `:641-796` |

Which objects can carry a tag, container propagation, and the assignment
warnings are owned by `jitx-physical-layout`, "Layout-intent tags" (source:
`constraints.py:504-623`).

## Rule classes

```python
design_constraint(condition, /, *, priority=0, name=None)             # -> UnaryDesignConstraint
design_constraint(first, second, /, *, priority=0, name=None)         # -> BinaryDesignConstraint
UnaryDesignConstraint(condition, *, priority=0, name=None)
BinaryDesignConstraint(first, second, *, priority=0, name=None)
```

`design_constraint` is a factory over the two public classes
(`constraints.py:70-111`); conditions are positional-only. Direct construction
is equally valid and is what the base skill's default rules use.
`priority`: "higher numbers take precedence if multiple rules apply"
(`:861`); equal priority is not defined in the Python source. `name` labels
the rule at runtime; unset, translation substitutes the object's tree path
(`_translate/rules.py:146-149`).

Rules reach the engine by tree traversal: `visit(design, DesignConstraint)`
in `_translate/design.py:187`. Any structural attribute under the `Design`
counts, including entries of a list; there is no reserved `rules` field on
`Design` (`design.py:35-37`).

## Effects

Unary rules chain any of these and return `Self`; one rule may set several.

| Method | Signature | Effect object | Source |
|---|---|---|---|
| `trace_width` | `(width: float)` mm | `TraceWidth` | `constraints.py:910` |
| `stitch_via` | `(definition: type[Via], pattern)` where pattern is `SquareViaStitchGrid(pitch=, inset=)` or `TriangularViaStitchGrid(pitch=, inset=)`; `inset` is boundary to outermost via center | `StitchVia` | `:924`, `:136-168` |
| `fence_via` | `(definition: type[Via], pattern: ViaFencePattern)`; `ViaFencePattern(pitch=, offset=, num_rows=None, min_pitch=None, max_pitch=None, initial_offset=None, input_shape_only=None)` | `FenceVia` | `:944`, `:185-235` |
| `thermal_relief` | `(gap_distance: float, spoke_width: float, num_spokes: int)` | `ThermalRelief` | `:960` |
| `serpentine_params` | `(min_radius=None, min_pitch=None)` | `SerpentineParams` | `:982` |
| `coupled_pair_params` | `(deskew_bump_radius=None, skew_tolerance=None, min_bump_spacing=None, max_bump_length=None, long_lookahead=None)`; `skew_tolerance` is a distance in mm | `CoupledPairParams` | `:1001` |
| `pour_feature_size` | `(min_width: float)`: clips pour regions not coverable by a circle of that diameter | `PourFeatureSize` | `:1038` |
| `routing_structure` | `(rs, *, ref_net: Net = None, ref_layer_nets: dict[int, Net] = None)`; both raises `ValueError`, neither requires an active `jitx.si.ReferencePlanes` | `RoutingStructureConstraint` | `:1074-1127` |

Binary rules have exactly one effect:

| Method | Signature | Source |
|---|---|---|
| `clearance` | `(clearance: float)` mm | `constraints.py:1160` |

The engine's effect union has the same nine members and nothing else
(`jitxcore/_proto/design_rules_pb2.pyi`, `ConstraintEffect`). Absent, and
not expressible as an effect: per-route width, pour isolation, keepout,
via or annular-ring rules, a neckdown region, a "direct connect". Those
intents are built from the effects above plus predicates, or belong to
`FabricationConstraints`, `RoutingStructure.Layer`, or `KeepOut`.

Canonical shapes:

```python
design_constraint(PowerTag(), GroundTag(), priority=2).clearance(0.25)          # net to net
design_constraint(IsTrace, IsPour, priority=1).clearance(0.2)                   # trace to pour
design_constraint(IsPour, IsHole, priority=1).clearance(0.3)                    # pour to hole
design_constraint(IsCopper & OnLayer(2), IsCopper, priority=1).clearance(0.2)   # one layer
design_constraint(HighSpeedTag() & OnLayer.external()).trace_width(0.15)        # outer layers
design_constraint(GndPourTag()).stitch_via(GndVia, SquareViaStitchGrid(pitch=2.0, inset=0.5))
design_constraint(IsPour).pour_feature_size(min_width=0.3)
```

## What the rules sit on

`FabricationConstraints` (`substrate.py:154-211`): "Unless otherwise
specified, these constraints are not enforced by the jitx engine. They are
used for documentation purposes and can be queried by user code." The four
that are enforced, each documented as taking precedence over rules:
`min_copper_width`, `min_copper_copper_space`, `min_copper_hole_space`,
`min_copper_edge_space` (`:161-176`). The fifteen documentation fields:
`min_annular_ring`, `min_drill_diameter`, `min_pitch_leaded`,
`min_pitch_bga`, `max_board_width`, `max_board_height`,
`min_silkscreen_width`, `min_silk_solder_mask_space`,
`min_silkscreen_text_height`, `solder_mask_registration`,
`min_soldermask_opening`, `min_soldermask_bridge`,
`min_th_pad_expand_outer`, `min_hole_to_hole`,
`min_pth_pin_solder_clearance` (`:178-209`). Read them from
`current.design.substrate.constraints`.

`RoutingStructure.Layer` (`si.py:562-574`) carries a per-layer
`clearance: float | None` and a `neck_down: RoutingStructure.NeckDown`
(`:553-560`, all fields optional). Neckdown parameters take effect only when
a region is activated in the UI; no code path creates one. This skill does
not use them; see SKILL.md, Fanout.

`Pour(shape, layer: int, *, isolate=0, rank=0, orphans=True)`
(`copper.py:71-79`). `isolate` is deprecated in 4.4 ("Use a design
constraint instead", `:56-58`); `orphans` is documented as not respected
(`:65-69`). A pour joins a net by membership (`net += Pour(...)`). Single
integer layer; no layer set.

`Route` carries no width or clearance parameter (`circuit.py:569`); its
constructor, control points, and sketch behavior are owned by
`jitx-physical-layout` `references/control-points.md` and
`references/geometry-verification.md`. What the checks read: after
`capture()`, `route.traces` is a sequence of `Route.Trace` wrappers
(`circuit.py:545-556`; one entry for a normal route, two for a differential
pair), each with `.shapes` holding the realized `ArcPolyline` or `Polyline`
primitives, each with `.width` (`shapes/primitive.py:285-317`); it is `None`
or empty when the route did not realize.

Copper weight: `Conductor.thickness` in mm is the only field
(`stackup.py:112`); JLCPCB's 1 oz is `Conductor(thickness=0.035)`. Nothing
couples thickness to a rule; heavy-copper spacing is a per-layer binary
clearance you write with the fab's value.

## 4.2 differences

- `Pour.isolate` is not marked deprecated on 4.2.2 but the same binary
  clearance rules work there; write the rules, not `isolate=`.
- Fenced differential structures applied through a rule fail on 4.2 when
  built with `symmetric_routing_layers` (see `jitx-substrate-modeler`,
  "Substrate sharp edges"); enumerate the layers explicitly.
- The control-point accessors changed in 4.3 (`PairPoint.pair` became
  `.front`/`.back`); see `jitx-physical-layout` `references/control-points.md`.

## Verified behaviors

Each entry is backed by a built design against the named version; the
reference design lives under `evals/cases/reference/`. Entries are added as
the work packages record them.

| Question | Version | Result | Where recorded |
|---|---|---|---|
| Does `stitch_via` find a via class declared on the substrate through a mixin? | 4.4.0rc5.dev2 | Yes. Mixin-reached, direct-attribute, and module-scope via classes each generated 9 vias on a 2.0 mm grid in an 8 mm pour; the same design with no rule generated 0. | `evals/cases/reference/stitch-via/NOTES.md` |
| Does a two-condition clearance rule move code-authored routes, and does the fab floor? | 4.4.0rc5.dev2, runtime 4.4.0-rc.9 | Neither. Two tagged routes authored 0.100 mm apart under a 0.25 mm rule realized at 0.1001 mm; authored 0.020 mm apart they realized at 0.0202 mm, below the 0.09 mm floor; both builds `status: ok`. The width rule on the same nets applied (0.2000 mm). Clearance rules act on router-generated copper and pour voiding; authored geometry is realized as authored and nothing at build checks it. | `evals/cases/reference/net-net-clearance/NOTES.md` |
| Can a direct pad-to-pour connection (no relief) be expressed? | 4.4.0rc5.dev2 | Yes, by a higher-priority `thermal_relief(fab floor gap, spoke width = pad diameter, 4)` on the tagged pad: its void disappears from the computed pour while the default pad keeps four spokes. A higher-priority rule with no effect changes nothing. Visible in the ODB++ export and the runtime's raw layout output, not on the captured `Pour`. | `evals/cases/reference/direct-connect/NOTES.md` |
| Does a width rule apply to a code-authored `Route`, and does a higher-rung escape rule beat the class rule on the same net? | 4.4.0rc5.dev2, runtime 4.4.0-rc.9 | Yes to both: a 0.5 mm class trunk and a 0.25 mm tagged escape on the same net realized at 0.5 and 0.25 mm; both routes realized. | `evals/cases/reference/qfn-power-fanout/NOTES.md` |
| Do solver-placed capacitors, vias, puddles, and tagged escape routes realize as placed? | 4.4.0rc5.dev2, runtime 4.4.0-rc.9 | Yes: 8 of 8 escape routes realized, placements and via nets matched the solver, loop area 1.30 mm2 per capacitor. A floating bank with no interactive placement was parked off-board and none realized. | `evals/cases/reference/decoupling-bank/NOTES.md` |
| Does the thermal-pad via stitcher build a pad on the runtime? | 4.4.0rc5.dev2 | Not yet built in a reference design; unit tests only. | `scripts/test_thermal_via_stitch.py` |
| Does a fresh agent route to this skill from the descriptions and produce a checked artifact? | 4.4.0rc5.dev2, runtime 4.4.0-rc.9 | Yes: 7 of 7 checks including the 12 V to ground inner-layer clearance read from capture (0.300 mm) and from the ODB++ export of the voided plane (0.304 mm). Also seen: an unstitched inner pour is dropped as orphan copper. | `evals/receipts/raw/e2e/REPORT.md` (local run log) |
| Does a rule declared on a child `Circuit` apply board-wide or only within that circuit? | 4.4.0rc5.dev2, runtime 4.4.0-rc.9 | Board-wide. A width rule stored only on one child applied to the tagged net's copper in a sibling (0.3000 mm against a 0.12 mm default) and to a tagged net in a circuit that never connects to the rule owner; an untagged net kept the default. | `evals/cases/reference/default-rules/NOTES.md` |
