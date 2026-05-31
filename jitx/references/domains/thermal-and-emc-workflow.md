# Thermal + EMC Cross-Artifact Workflow

> **All JITX expression blocks in this file are illustrative, not exact API.** The canonical rule-builder methods exported by `jitx.constraints` today are `trace_width`, `clearance`, `stitch_via`, `fence_via`, and `thermal_relief`. Tag subclasses (`SwTag`, `RFTag`, `ThermalPadTag`, `SensitiveAnalogTag`, etc.) are user-defined per the `Tag` base-class docstring — declare them at module scope in the project's tags module (see `project-builder-flow.md`). When a code block names a method not in the canonical set, treat it as a placeholder for either a future rule-builder method or a project-local helper that calls the canonical methods.

## When to read this

Thermal and EMC are not single-artifact concerns: they span component (thermal pad annotation, decoupling cap placement), circuit (TVS placement, ferrite bead at boundary), substrate (thermal via density, stitching grid, plane partitioning), and constraint (return path, aggressor / victim separation). When working on a design with thermal-dissipative components (> 1 W continuous) or EMC-critical signals (switching regulators, RF, sensitive analog), the per-artifact references alone are not enough — you also need an end-to-end picture. This file gives that picture.

The detailed quantitative rules live in:
- [`thermal.md`](thermal.md) — power density, thermal via diameter / density, heatsink decisions
- [`emc-esd.md`](emc-esd.md) — return paths, stitching, aggressor separation, TVS GND vias
- [`power.md`](power.md) — switch-node net class, decoupling, regulator selection
- [`external-interfaces.md`](external-interfaces.md) — connector TVS placement, EMI filtering
- [`../net-classes.md`](../net-classes.md) — `SwTag`, `ThermalPadTag`, `RFTag`, `ClockTag`, `SensitiveAnalogTag`

## Cross-artifact responsibility table

| Concern | Component | Circuit | Substrate | Constraint |
|---|---|---|---|---|
| Thermal pad subdivision | landpattern paste mask | — | — | — |
| Power-rail decoupling | — | `short_trace=True` | — | — |
| Thermal via density | — | — | `ThermalPadTag` rule | — |
| Stitching via grid | — | — | global fab rule | — |
| TVS placement near connector | — | EMI filter inserted | — | placement constraint |
| Aggressor / victim separation | — | — | — | net-class min-distance |
| Return path for high dI/dt | — | — | reference plane choice | `ReferencePlanes(GND)` |
| Mixed-signal supply separation | — | LDO + ferrite bead | plane partition | net-class clearance |

## Thermal workflow

1. **Identify dissipative components.** Walk the BOM. Anything > 0.5 W continuous gets a thermal evaluation. Anything > 1 W gets a thermal pad + thermal via plan.

2. **Compute power-density budget** per [`thermal.md`](thermal.md). For each dissipative component:
   - Adequate copper on adjacent layers for heat spreading (`THM_PWR_001`); size at ≥ 15.3 cm²/W for a 40 °C rise, ≈ 7.7 cm²/W with airflow (`THM_PWR_002`)
   - If copper area unavailable: escalate to heatsink (`THM_HEAT_001`) or component reselection

3. **Tag the component's thermal pad with `ThermalPadTag()`.** This drives the substrate's thermal via density rule (see [`../net-classes.md`](../net-classes.md) → Thermal Pad).

4. **Verify thermal pad paste subdivision.** Pads > 4 mm² need 2×2 or 3×3 paste subdivision to prevent reflow voids. The `jitx-component-modeler` skill handles this; verify it was done during the Phase 3b audit Pass 4 (Power and Thermal).

5. **Decide forced-air vs passive.** If passive thermal budget is insufficient, the system needs forced cooling — flag as an out-of-band requirement for the system designer.

6. **Spread dissipative components.** Cluster of three hot ICs in one corner saturates locally even if total area is sufficient. Place dissipators apart; this is enforced post-layout via `THM_SPREAD_001` (Phase 3b `awaiting-introspection` check).

## EMC workflow

1. **Tag noise sources.** Every switching regulator's switch node gets `SwTag()`. Every clock distribution net gets `ClockTag()`. Every RF feed gets `RFTag()`. Tags drive net-class rules — see [`../net-classes.md`](../net-classes.md).

2. **Tag victim circuits.** Sensitive analog (high-impedance sensor, precision ADC input) gets `SensitiveAnalogTag()`. RF receive paths get `RFTag()` + appropriate isolation.

3. **Apply aggressor / victim separation.**

   ```python
   design_constraint(SwTag(), SensitiveAnalogTag()).min_distance(50 * MM)
   design_constraint(ClockTag(), RFTag()).min_distance(20 * MM)
   ```

4. **Choose reference plane strategy.**
   - Single solid ground unless mixed-signal or isolation barrier requires otherwise.
   - Mixed-signal: separate analog supply (LDO or filtered rail); a single solid ground with careful return-current management usually beats split planes for modern designs.
   - Isolated domain: explicit barrier with creepage / clearance per regulatory class (see [`safety-critical.md`](safety-critical.md)).

5. **Specify stitching via grid** at the substrate level.

   ```python
   design_constraint(GlobalTag()).via_stitch_grid(spacing=20 * MM)
   design_constraint(LayerTransitionTag()).via_stitch_grid(spacing=10 * MM)
   ```

6. **Place EMI filtering at boundaries.** Ferrite bead or RC filter at every external connector signal pin (`EMC_ESD_002`). TVS on the connector side of the filter, ferrite on the system side.

## JITX expressions (combined)

> Illustrative; see the banner at the top of this file for the canonical-API reminder.

```python
# Thermal pad tag drives substrate via density rule
self.buck.thermal_pad += gnd
design_constraint(ThermalPadTag()).thermal_via_density(
    density=10 * PER_CM2,
    via_diameter=0.3 * MM,
    # Center-to-center spacing >= 2 mm to prevent solder reflow wicking
    # (THM_VIA_003); rely on density to constrain staggered offset.
    via_spacing=2.0 * MM,
)

# Aggressor / victim separation
design_constraint(SwTag(), SensitiveAnalogTag()).min_distance(50 * MM)
design_constraint(ClockTag(), RFTag()).min_distance(20 * MM)

# Stitching grid
design_constraint(GlobalTag()).via_stitch_grid(spacing=20 * MM)
design_constraint(LayerTransitionTag()).via_stitch_grid(spacing=10 * MM)

# TVS placement intent (layout-time check via Phase 3b awaiting-introspection)
class UsbConnector(Circuit):
    def __init__(self):
        self.j_usb = USB_C_Receptacle()
        self.tvs = USBLC6_2()  # low-cap TVS for high-speed
        self.tvs.d1 += self.j_usb.dp
        self.tvs.d2 += self.j_usb.dn
        # Layout-time: TVS within 10 mm of connector (EMC_ESD_001)
        design_constraint(self.tvs, self.j_usb).max_distance(10 * MM)
```

## Out of scope (defer to external tools)

- **Thermal simulation** — JITX does not run FEA. Authoring-time targets give a good first-pass; full thermal verification needs FEA or measured prototype.
- **EMC chamber compliance** — final EMC compliance is a measurement activity, not a design-time check. The authoring-time targets reduce the risk of compliance failure but do not guarantee it.
- **Pre-layout SI simulation** — covered by the constraint system in `jitx-interconnect-constraints`; this doc covers *physical* signal-integrity adjacencies (stitching, return path), not s-parameter modeling.

## Cross-references

- [`thermal.md`](thermal.md) — quantitative thermal targets
- [`emc-esd.md`](emc-esd.md) — return paths, stitching, aggressor separation
- [`power.md`](power.md) — switch-node net class, decoupling
- [`external-interfaces.md`](external-interfaces.md) — connector TVS placement, EMI filtering
- [`../net-classes.md`](../net-classes.md) — `SwTag`, `ThermalPadTag`, `RFTag`, `ClockTag`, `SensitiveAnalogTag`
