---
name: jitx-physical-layout
description: "Use when the user asks to author PCB physical layout from code: draw copper, antennas, filters, net ties, custom shapes, board outlines, custom pads, soldermask or paste openings, thermal pads with vias, code-placed vias, fanout or escape tags, direct-connect or thermal-relief tags, control points, code-based routes, diff-pair fans/trunks, escape routing, or deskew, or to inspect or verify realized geometry from Python (jitx.query, RuntimeDesign capture, missing or Empty pours, missing stitch vias, route realization checks). Covers shapely geometry, Copper, OverlappableCopper, Pour realization semantics, pad features, PortAttachment, explicit placement, layout-intent tags, Route/control-point APIs, and the 4.3 reverse-flow geometry-verification workflow. Use jitx-layout-constraints to author pour and via-stitching rules, jitx-substrate-modeler for stackups, via definitions, routing structures, fence-via rules, and fenced pours, and jitx-circuit-builder for net wiring, passives, and basic pours."
---

# JITX Physical Layout

## Routing

Use this skill for authored geometry, placement, layout-object selection, code
routes, and captured-geometry verification. Start environment setup with
[jitx](../jitx/SKILL.md). Route these tasks to:

- Rules, clearances, widths, net classes, thermal relief, and stitching rules:
  [jitx-layout-constraints](../jitx-layout-constraints/SKILL.md).
- Stackups, via definitions, routing structures, and fence rules:
  [jitx-substrate-modeler](../jitx-substrate-modeler/SKILL.md).
- Net wiring, passives, basic pours: [jitx-circuit-builder](../jitx-circuit-builder/SKILL.md).
- Datasheet-derived packages: [jitx-component-modeler](../jitx-component-modeler/SKILL.md).
- Topology and SI constraints: [jitx-interconnect-constraints](../jitx-interconnect-constraints/SKILL.md).

## Workflow and owners

1. Inspect installed source before choosing imports or signatures. Search the
   project's package directory with `rg -n 'class NAME|def NAME' PACKAGE_DIR`;
   confirm the definition, then run `pyright` below.
2. Choose the relevant owner:
   - Installed `jitx.run.runtime.RuntimeDesign`, `jitx.query`, and `jitx.inspect`:
     capture, query versus visit, and net lookup; the
     [realization checker](scripts/check_realization.py) demonstrates the loop.
     `jitxlib.verify.geometry` owns shape conversion and its frame/void traps;
     [geometry evidence](references/geometry-verification.md) retains observations
     without a code owner.
   - [Control points](references/control-points.md): `Route`, binding, chirality,
     ownership, and deskew routing.
   - `jitxexamples.demos.si_bga_optimization`: `deskew.py` owns arc-polyline
     construction and `deskew_connections` (left-to-p, right-to-n);
     `bga_escape.py` demonstrates control points, virtual connections, and fence
     pours; `si_geometry.py` owns keepout/antipad geometry. Check these against
     installed APIs and the control-point reference before reuse.
   - `jitxlib.landpatterns.pads`: `SMDPadConfig`, `ThermalPadGeneratorMixin`,
     `WindowSubdivide` own pad-feature generation. [Example owners](references/layout-examples.md)
     route thermal-pad CSG, custom-pad mask/paste, and the pending antenna example.
   - `jitxlib.verify`: reuse `shape_geometry`, `unique_by_specificity`,
     `min_clearance`, `holds_circle`, `centreline_length`, and rule readers.
3. Store vias, copper, routes, and keepouts structurally on the circuit before
   connecting them. Treat the build warning about objects not assigned to a
   circuit as failure. Join ground/power vias directly to nets; reserve
   `PortAttachment` for signal topologies. Keepouts never join nets.
4. Place direct descendants with `.at()`; reserve `Circuit.place(relative_to=...)`
   for placement relative to another instance; installed `jitx.circuit.Circuit`
   owns the deferred-placement and force-floating semantics. Pin geometry-dependent anchors
   with `.at(0, 0)` in the geometry's frame. Let other reusable-circuit components
   use solver/interactive placement instead of nominal-package offsets.
   Record explicit subsystem positions or confirmed stored interactive placements
   before interpreting capture.
   Put board-wide pours at the top level; keep local pours/keepouts inside the
   circuit they must follow.
5. Write capture assertions before iterating; build sequentially per design.
   Follow [architectural patterns](../jitx/references/architectural-patterns.md)
   for structural collections, then run [jitx-code-review](../jitx-code-review/SKILL.md)
   on layout code.

## Pour realization semantics

Read the [construction and placement observations](references/geometry-verification.md#construction-and-placement)
before diagnosing missing geometry. For capture overwrites, `Empty()`, and
hole-preserving conversion, read the realization checker and `jitxlib.verify.geometry`.
Apply the
[remaining runtime observations](#pour-and-stitch-runtime-observations), then run
[verification](#verification); build success and emitted-via counts cannot prove
realized pour area.

## Layout-intent tags (object selection)

Read installed `jitx.constraints.Tag`, `Tags`, and `Tags.assign` for supported
objects, container propagation, assignment context, and warnings. Rule effects
and fanout/direct-connect policies belong to
[jitx-layout-constraints](../jitx-layout-constraints/SKILL.md); route-versus-net
selection for differential structures belongs to [control points](references/control-points.md).

## Verification

Run in the design project:

```bash
pyright path/to/layout.py
ruff format path/to/layout.py
python -m my_project.checks
```

Require no type errors and capture assertions reporting `[PASS]/[FAIL]`, with
nonzero exit on failure: every route/control point realized, coupled trunks
have two traces, polarity/net membership correct, bounds and clearances measured.
For EDB/HFSS exports, reopen `.aedb` read-only and assert copper/via presence:
netless copper uses `<NO-NET>`, primitive bboxes are in meters, and vias are
`layout.padstack_instances`. Objects reachable only through `Net` or
`PortAttachment` can disappear from EDB; structural storage is required.
For direct Python export, follow installed `jitx/_cli/design/export.py::_run_export`
for the disposable instantiation frame and design/substrate contexts; omitting
the active frame raises "Structure not active".

Use `jitxlib.verify` for the checks it owns. If it is unavailable, name the
missing installation and leave those checks open; do not substitute a bundled
fallback. For pour, keepout, and edge checks it does not yet cover, run the
bundled [realization checker](scripts/check_realization.py) from the project,
using the resolved skill directory:

```bash
python "<skill-directory>/scripts/check_realization.py" my_project.designs.Design \
  --stitch-target circuit.thermal_ground \
  --board-wide-pour circuit.ground_return
```

Repeat options for all named targets, including every board-wide pour. Require
exit 0 and witness paths for authored pours, selected stitch targets, and
board-wide spacing. Exit 1 means failed checks; exit 2 means missing capture or
unreadable evidence. Record the exact command and checked names in task/Phase 4
Physical realization rows; missing commands or nonzero exits block completion.

For square stitch grids, also use `jitxlib.verify.stitch_via_count` to check
counts, sites, keepout exclusions, and coverage by every intended pour. Its
docstring owns input requirements and limits; read it before selecting captured
geometry. The bundled checker's stitch-presence check does not establish these.

Use the production substrate, passive-query defaults, and board rules in any
`SampleDesign` harness. The checker cannot validate that equivalence or placement
provenance; record mismatches and withhold shipping-board claims. Report trace-to-pour clearance, thermal spokes,
and sliver removal individually as unwitnessed by this checker. Fabrication
exports do not close those checks.

Configure thermal pads inside `Component.__init__`, after assigning the
landpattern and before creating mappings. For the
[thermal-via helper](scripts/thermal_via_stitch.py), verify mask/paste openings
in fabrication output on first use;
`ValueError` means revise the grid, never bypass validation.

## Knowledge without a complete owner

### Custom shapes with shapely (general)

Prefer exact built-in composites (`jitx.shapes.composites`) for common shapes; use shapely for CSG,
buffering, fillets, and arbitrary polygons on any shape-taking feature.
`ShapelyGeometry(raw_geometry)` wraps the result; `.to_shapely()` and `.buffer()`
return wrappers whose `.g` holds raw geometry. Installed `jitx.shapes.shapely`
owns set operators and conversion APIs. Morphological opening
`buffer(-r).buffer(r)` rounds inside corners. Arc conversion polygonizes at a
tolerance, so watch vertex counts.

`jitx.Point` is a tuple alias: use `(x, y)`. `.at(scale=(1, -1))` crashes;
reflect the geometry with shapely affine transforms or negated arc math.
Before feeding a fabrication feature, assert
`not g.is_empty and g.geom_type in ("Polygon", "MultiPolygon")`.

### Copper selection

`Pour` requests runtime fill; `Copper` is explicit on-net geometry. Neither is
overlap-exempt. `OverlappableCopper` is netless, ignored by routing/overlap checks,
and not taggable; its physical connectivity comes from overlapped pads.
`Copper(exempt=True)` does not exist. Constructor details live in installed
`jitx.copper` and `jitx.feature`. See `deskew.py` and the antenna example
above for demonstrations; virtual declarations supply connectivity the topology
walker cannot infer from overlap.

### VirtualConnection production rules

Read installed `jitx.virtual` for the experimental API and single-target endpoint
validation. `deskew_connections` declares connectivity without a pin model;
constrained timing/skew/loss needs `PinModel(delay=..., loss=...)` per leg.
Every constrained segment must use `>>` topology: a plain `+` segment makes
the whole path invalid. The interconnect skill owns topology, via/control-point
elements, tags, and `BridgingPinModel` across series components.

Production observations from saturn-ethernet (4.3.0-rc.3): model measured delay,
not drawn skew. One wrapped hook measured about 0.07 ps
versus about 2 ps inferred from length. Use equal mean delays with measured
residual as a `Toleranced` spread; drawn length informs loss and mean only.
Constraint endpoints must be component ports; control-point `.port` bundles
fail topology begin/end translation. Keep control points mid-path.

### Pour and stitch runtime observations

Place a same-net pad or via reaching each pour layer before stitching. Top-side
pads cannot anchor inner/bottom pours, and solver-emitted stitches cannot keep
pours alive. On 4.4.0, an unanchored inner pour emitted nine vias yet captured
`Empty()`; one placed through via made it realize. `orphans` is not respected.

`KeepOut(pour=True)` wins at every pour rank; rank prioritizes competing pours.
`via=True` blocks automatic vias, not explicitly placed ones. Read installed
`jitx.feature.KeepOut` for flags; all false is a no-op. Board outlines receive no
automatic pullback: use the [inward-buffer recipe](../jitx-circuit-builder/references/advanced-patterns.md#pours)
and check against `min_copper_edge_space`.

Stitch rules require a `Pour`, not `Pad`/`Copper`/`IsPad`; create a tagged,
net-connected pour from thermal-pad geometry when using those rules.
On 4.4.0, `SquareViaStitchGrid.inset` measures to the via pad edge. The field
description says via centres and is being corrected, so trust the measurement
over the text on any release that still reads that way. An 8 mm square, pitch 2.0, pad 0.45 produced nine
vias at inset 1.5/1.75 and one at 1.8/1.9/2.1: the drop is 1.775, not 2.0
(centre) or 1.85 (hole). Plan per-axis counts with
`2 * floor((size / 2 - inset - pad_diameter / 2) / pitch) + 1`, which counts
how many sites fit a region centred on the lattice. Where the grid starts is not
established: a pour centred at -3.25 on a 1.5 pitch realized vias on whole
multiples of the pitch, not on its own centre, so a count mismatch on an offset
region is inconclusive by itself. Measure achieved margin from captured centres,
boundary, and pad diameter; capture provides neither rule-to-group binding nor an
inset-satisfied flag.
