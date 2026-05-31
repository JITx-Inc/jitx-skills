# Mechanical Integration Reference

## When to read this

You are placing connectors that mate with an enclosure, sizing mounting holes, planning component-height clearances against a lid or moving part, or integrating a heatsink. JITX can ingest and emit mechanical CAD — board outline, cutouts, and STEP handoff — through the `jitx-mechanical` skill (import DXF/EMN/IDF/IDX/BDF, set board outline from mechanical, attach STEP models, export board STEP/DXF). What JITX does **not** do is verify 3D fitment: enclosure-cutout alignment, lid/moving-part clearance, and heatsink assembly fit remain MCAD-owned checks. This reference catalogs what can be authored in JITX (with `jitx-mechanical` for the geometry handoff) vs. what must be verified in mechanical CAD.

## Authoring-time targets

### Mounting

- [ ] At least 2 mounting holes, preferably ≥ 3 for board stability (`MEC_MOUNT_001`)
- [ ] Mounting holes sized for fastener class (M2, M3, #4-40, #6-32, #8-32 typical)
- [ ] Mounting holes NPTH (non-plated) unless chassis bond is intentional
- [ ] If chassis bond required (e.g., aerospace single-point ground): one PTH or pad-and-finger pattern at the designated location; copper keepout elsewhere (`AERO_GND_001`)

### Connectors (mechanical)

- [ ] Connector mechanical retention matches expected handling (`MEC_CONN_001`)
  - High-current: strain relief or locking tabs
  - Hot-pluggable: through-hole or screw-down preferred over SMT
  - User-facing: keyed or polarity-foolproof

### Heatsink integration

- [ ] Heatsink clearance from adjacent components verified (`MEC_HEATSINK_001` — STEP handoff via `jitx-mechanical`; fitment check in MCAD, see "Geometry handoff" below)
- [ ] Thermal interface material (TIM) gap ≤ 0.1 mm
- [ ] Heatsink mounting holes / clips planned in the board outline

## Geometry handoff (JITX via `jitx-mechanical`)

These rules have a JITX-authorable half — get the enclosure geometry into (or out of) the design — and an MCAD-owned verification half. Use `jitx-mechanical` for the handoff; verify fitment in MCAD.

| Rule | JITX authoring / handoff (`jitx-mechanical`) | MCAD verification |
|---|---|---|
| `MEC_OUTLINE_001` | Import enclosure outline (DXF/EMN/IDF/IDX/BDF); set board outline from it | Board outline vs. enclosure-cutout 3D fitment |
| `MEC_UI_001` | Place buttons / displays / connectors against the imported outline | Cutout-alignment fitment in the enclosure assembly |
| `MEC_HEATSINK_001` | Attach STEP model of the heatsink; export board STEP for the assembly | Heatsink-vs-component mechanical fit in MCAD |

## Out-of-band — MCAD / analysis required

| Rule | Why out-of-band | Suggested verification |
|---|---|---|
| `THM_HEAT_001` | Heatsink material / TIM spec | Thermal / mechanical analysis |
| `THM_COOL_001` | Forced-air CFM | System / mechanical engineering |

## Quantitative layout targets (waiting on introspection)

| Rule | Target | Introspection API needed |
|---|---|---|
| `MEC_HEIGHT_001` | Tall components away from edges and moving parts | `board.component_height(component)`, `board.placement_zone(component)` |
| `AERO_GND_001` | 4 mm copper keepout around chassis-bond mount holes | `board.copper_keepout(net)`, `board.distance_to_hole(component)` |
| `AERO_VIB_001` | Components > 3 g have staking provisions | `board.staked_components()`, `board.component_mass()` |

## Common gotchas

- **Mounting hole keepout forgotten on inner layers** — top and bottom copper pulled back from a NPTH but inner planes still encroach, risking shorting on the standoff threads.
- **Connector through-hole tabs on a 4-layer board with embedded planes** — make sure plane clearances around the connector tabs match the connector's required isolation (e.g., USB-C shield tabs).
- **Component height assumed from 2D footprint** — courtyards don't include vertical extent. Tall caps, crystals, connectors can collide with the enclosure lid.
- **Heatsink position assumed to be where the IC is** — heatsink mounting often shifts to use enclosure features (screw bosses). Confirm mounting topology with mechanical before fixing the IC location.

## Cross-references

- [`thermal.md`](thermal.md) — heatsink decision, forced cooling
- [`safety-critical.md`](safety-critical.md) — aerospace single-point chassis ground, vibration staking
- [`dfm.md`](dfm.md) — component-to-edge clearance
