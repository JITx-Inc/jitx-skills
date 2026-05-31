# EMC and ESD Reference

## When to read this

You are deciding return-path strategy, ground-stitching density, plane partitioning, aggressor / victim placement, or ESD protection. The connector-side rules (TVS placement, connector ground bonding, low-cap TVS selection) are in [`external-interfaces.md`](external-interfaces.md). The thermal-via overlap is in [`thermal.md`](thermal.md).

## Authoring-time targets

### Ground partitioning

- [ ] Single contiguous ground unless mixed-signal or isolation barrier requires otherwise
- [ ] If split: bridge at a single point near the boundary component (typically ADC or isolator)
- [ ] No "moats" cut in the ground that high-speed return currents must hop over
- [ ] Plane stitching tagged in the substrate for the layer transitions

### TVS / ESD components (also see `external-interfaces.md`)

- [ ] TVS at every external-facing pin or accessible conductor (the ESD-or-justification table)
- [ ] TVS capacitance compatible with signaling speed: < 10 pF for USB / Ethernet / DisplayPort (`EMC_ESD_006`)
- [ ] TVS ground pad has ≥ 2 dedicated vias; no thermal reliefs (`EMC_ESD_004`)
- [ ] EMI filter (ferrite bead or RC) at connector boundary for signal lines (`EMC_ESD_002`)
- [ ] Own via per ground connection (no via sharing for ground bounce paths) (`EMC_VIA_003`)

### Net classes for EMC-critical nets

- [ ] Switch nodes tagged with `SwTag()` — drives clearance and via fence rules
- [ ] RF / antenna feeds tagged with `RFTag()` — drives return-plane keepout rules
- [ ] High dI/dt nets tagged with `HighCurrentTag()` — drives width and stitching rules

## JITX expressions

> **Illustrative.** The `design_constraint(...).METHOD(...)` patterns below show authoring intent, not exact API. The canonical rule-builder methods exported by `jitx.constraints` today are `trace_width`, `clearance`, `stitch_via`, `fence_via`, and `thermal_relief`. Tag subclasses (`SwTag`, `RFTag`, `ThermalPadTag`, `SensitiveAnalogTag`, etc.) are user-defined per the `Tag` base-class docstring — declare them at module scope in the project's tags module (see `project-builder-flow.md`). When a rule below names a method not in the canonical set, treat it as a placeholder for either a future rule-builder method or a project-local helper that calls the canonical methods.

```python
# Stitching via grid (substrate-level)
design_constraint(GlobalTag()).via_stitch_grid(spacing=20 * MM)

# Pour pullback from switch node
design_constraint(SwTag(), priority=HIGH).clearance(0.5)

# Aggressor separation between switcher and analog ADC region
design_constraint(SwTag(), SensitiveAnalogTag()).min_distance(50 * MM)
```

## Quantitative layout targets (waiting on introspection)

| Rule | Target | Introspection API needed |
|---|---|---|
| `EMC_ESD_003` | TVS placed as close to connector as possible | `board.distance(component, component)` |
| `EMC_ESD_005` | No sensitive signals routed parallel to ESD-exposed traces | `board.parallel_traces(net1, net2)` |
| `EMC_PATH_001` | Wide, short return paths for high dI/dt | `board.return_path(net)` |
| `EMC_STITCH_001` | Stitching vias at edges and layer transitions (rule is qualitative; ≤ 20 mm spacing is a JITX engineering default) | `board.stitch_via_spacing(layer)` |
| `EMC_STITCH_002` | Ground-stitching via grid across copper pours (rule is qualitative; 10–20 mm pitch is a JITX engineering default) | `board.pour_via_density(net)` |
| `EMC_AGG_001` | Noise sources ≥ 50 mm from sensitive circuits | `board.distance(component_set, component_set)` |
| `EMC_PLANE_002` | Plane splits minimized; stitching across required splits | `board.plane_splits(layer)` |

## Common gotchas

- **Stitching only at the edges** — you also need stitching at every signal-layer-to-signal-layer transition for high-speed return currents (e.g., when a diff pair changes routing layer through a via).
- **TVS on the wrong side of the EMI filter** — TVS goes on the connector side (sees the strike directly), ferrite goes on the system side. Reversing them lets the strike couple past the TVS into the load.
- **"AGND must be isolated from DGND"** — sometimes wrong. For modern high-speed mixed-signal, a single solid ground with careful return-current management beats split planes. Follow the IC datasheet's recommended ground.
- **Ground bounce on a high-current FET source** — Kelvin connect the gate driver's return to the FET source pad, not to the ground plane some distance away.

## Cross-references

- [`high-speed-si.md`](high-speed-si.md) — diff pair plane continuity, via stub control
- [`power.md`](power.md) — switch-node return path, decoupling
- [`external-interfaces.md`](external-interfaces.md) — connector ESD, hot-plug protection
- [`thermal.md`](thermal.md) — thermal vias often double as stitching vias
- [`net-classes.md`](../net-classes.md) — `SwTag`, `RFTag`, `HighCurrentTag`, `GateDriveTag`
