# Design for Manufacturability (DFM) Reference

## When to read this

You are finalizing substrate fabrication rules, choosing a fab house's process class, panelizing for assembly, or auditing a board for cost. The bulk of DFM rules are encoded in the substrate's `FabricationConstraints` — this reference catalogs which DFM rules are covered by which constraint, and which require layout introspection.

## Authoring-time targets

### Trace and space (covered by substrate fab rules)

- [ ] Minimum trace width ≥ 6 mils (standard process), ≥ 4 mils (advanced) (`DFM_TRACE_001`, `DFM_TRACE_004`)
- [ ] Trace / space ≥ board tolerance + 2 mils
- [ ] Trace width sized for current: voltage drop `I · R ≤ 20 mV` at full load current; derate IPC current capacity to 50% (`DFM_TRACE_005`, `PWR_TRACE_002`)

### Vias (covered by substrate Via definitions)

- [ ] Via annular ring ≥ 10 mils; via pad size ≥ drill + 10 mils (`DFM_VIA_001`)
- [ ] Via diameter ≥ 0.25 mm for cost (`DFM_VIA_003`)
- [ ] Avoid smallest via size throughout PCB; use ≥ 0.25 mm by default (`DFM_VIA_004`)
- [ ] Microvia span within fab capability (typically 1–2 layers)
- [ ] Backdrill specified for through-hole vias in high-speed paths (if needed)

### Layer and stackup

- [ ] Stackup layer markers identifying F.Cu, B.Cu, inner layers (`DFM_LAYER_001`) — JITX substrate stackup includes these by construction

### Mask and silkscreen

- [ ] Solder mask web ≥ 4 mils (green), ≥ 5 mils (other colors); mask clearance 2–4 mils (`DFM_MASK_001`)
- [ ] Silkscreen ≥ 6 mils clearance from pads; line width ≥ 4 mils; font height ≥ 40 mils (`DFM_SILK_001` — silkscreen graphic is `out-of-band`)

### Edge and clearances

- [ ] Copper ≥ 10 mils from board edge (`DFM_EDGE_001`) — `partial`, exact distance needs introspection
- [ ] Components ≥ 100 mils (2.5 mm) from board edge (`DFM_COMP_EDGE_001`) — `awaiting-introspection`
- [ ] Components ≥ 1 mm from V-score (`DFM_PANEL_001` — panel-level; `filtered`, set at the fab/panelizer, see below)
- [ ] MLCCs ≥ 6 mm from breakaway tabs

### Library quality (covered by component-modeler)

- [ ] Footprint verified against datasheet; 1:1 print-and-fit (`DFM_LIB_001`)
- [ ] Symbol pinouts match datasheet exactly (`DFM_LIB_002`)
- [ ] Connector orientations and keying verified (`DFM_LIB_003`)

### BOM and sourcing

- [ ] BOM includes LCSC / Digikey / approved distributor part numbers for all components (`DFM_BOM_001`)
- [ ] Alternate parts documented for likely shortage candidates

## JITX expressions

> **Illustrative.** The `design_constraint(...).METHOD(...)` patterns below show authoring intent, not exact API. The canonical rule-builder methods exported by `jitx.constraints` today are `trace_width`, `clearance`, `stitch_via`, `fence_via`, and `thermal_relief`. Tag subclasses (`SwTag`, `RFTag`, `ThermalPadTag`, `SensitiveAnalogTag`, etc.) are user-defined per the `Tag` base-class docstring — declare them at module scope in the project's tags module (see `project-builder-flow.md`). When a rule below names a method not in the canonical set, treat it as a placeholder for either a future rule-builder method or a project-local helper that calls the canonical methods.

```python
# Substrate fabrication constraints (most DFM lives here)
substrate.fabrication_constraints = FabricationConstraints(
    min_trace_width=6 * MIL,
    min_clearance=6 * MIL,
    min_via_drill=0.25 * MM,
    min_annular_ring=10 * MIL,
    min_dielectric_thickness=...,
    copper_weight=1 * OZ,
    edge_to_copper=10 * MIL,
)
```

## Quantitative layout targets (waiting on introspection)

| Rule | Target | Introspection API needed |
|---|---|---|
| `DFM_SLIVER_001` | Copper features < 6 mils removed | `board.copper_slivers()` |
| `DFM_COMP_EDGE_001` | Components ≥ 100 mils from edge | `board.component_to_edge()` |
| `DFM_PASTE_001` | Paste layer correct pad coverage | `board.paste_coverage(pad)` |
| `DFM_COPPER_001` | Copper balance across layers for warp prevention | `board.copper_balance(layer)` |
| `DFM_COURT_001` | Component courtyards don't overlap | `board.courtyard_overlap()` |

## Out-of-band

| Rule | Why out-of-band | Suggested verification |
|---|---|---|
| `DFM_SILK_001` | Silkscreen graphic content | Visual review in CAD |
| `DFM_LABEL_001` | Board ID silkscreen content | Visual review |

## Filtered — not applicable to a JITX-authored design

These rules belong to the fab's CAM/panelizer step (or are obsolete on modern processes), not to the JITX board design. The Phase 3b audit **filters them out** (they are not in the applicable-rule set); the rationale is recorded in `phase-3b-coverage-matrix.csv` under the `not-applicable` status.

| Rule | Why filtered |
|---|---|
| `DFM_ACID_001` | Acid traps are auto-resolved by the fab CAM/DFM step on modern processes |
| `DFM_PANEL_001` | Panelization (V-score / breakaway) is defined by the fab/panelizer, not in the JITX board design |
| `DFM_FID_001`, `DFT_FID_001` | Panel fiducials are added by the panelizer at the fab |
| `DFM_FID_002` | Fiducial first-article photo is a fab/QA process step, not a design artifact |

## Common gotchas

- **Substrate fab rules from one fab house used at another** — JLC's 0.15 mm trace/space is fine at JLC but borderline elsewhere. Tag the substrate with the fab house and confirm during the build acceptance block.
- **Edge clearance vs. routing tolerance** — fab routing tolerance ±4 mils means a 10-mil edge clearance is really 6 mils worst-case. For RF or controlled-impedance traces, use 20 mils.
- **Slivers in pours** — a pour with a small isolated island < 6 mils can flake off during fab. Most pour engines have a sliver removal pass; verify it's enabled.
- **Component on a V-score line** — even at 1 mm clearance, MLCCs crack during depanelization. Use 6 mm + or breakaway routes instead of V-score.

## Cross-references

- [`net-classes.md`](../net-classes.md) — net-class width and clearance overrides
- [`thermal.md`](thermal.md) — thermal via design
- [`mechanical.md`](mechanical.md) — board outline, mounting holes
