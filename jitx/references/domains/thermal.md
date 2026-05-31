# Thermal Reference

## When to read this

You have a component dissipating > 1 W, a regulator with a thermal pad, a high-current FET or motor driver, an LED with significant continuous current, or an enclosure with passive cooling. Also read [`power.md`](power.md) for regulator selection and [`mechanical.md`](mechanical.md) for heatsink mechanical fit.

## Authoring-time targets

### Component-level thermal

- [ ] Thermal / exposed pad connected to ground copper, never floating
- [ ] Power dissipation Pd estimated for worst-case operating point
- [ ] Junction temperature target: Tj ≤ Tj_max − 20 °C margin (`THM_RISE_001` — verified post-layout)
- [ ] Calculation: estimate `Tj = Ta + Pd · θja` from the component's actual worst-case dissipation `Pd`, using the datasheet `θja` for the package on the chosen board class; verify `Tj ≤ Tj_max − 20 °C` margin. The allowable headroom is `Pd_max_allowed = (Tj_max − Ta) / θja`; the component's `Pd` must stay below it (`THM_DISS_001`)

### Substrate-level thermal

- [ ] Power-density budget: components dissipating > 1 W need adequate copper area on adjacent layers for heat spreading (`THM_PWR_001`); size it at ≥ 15.3 cm²/W for a 40 °C rise, ≈ 7.7 cm²/W with airflow (`THM_PWR_002`)
- [ ] Thermal via diameter 0.2–0.4 mm (smaller wicks solder away during reflow) (`THM_VIA_002`)
- [ ] Thermal via array under hot pads: 8–12 vias / cm² typical (`THM_VIA_001`, `THM_VIA_004`)
- [ ] Thermal via spacing > 2 mm to prevent reflow wicking; staggered grid (`THM_VIA_003`)
- [ ] 4-layer board preferred over 2-layer for power dissipation — ~30% better θja with inner-plane access (`THM_VIA_005`)

### Heatsink and forced cooling

- [ ] Heatsink required when Pd × θja exceeds passive board budget — specify aluminum + TIM, document mechanical clearance (`THM_HEAT_001`)
- [ ] Forced-air cooling: required CFM calculated for high-power designs (`THM_COOL_001`)
- [ ] Component height does not block airflow channel; tall components placed away from heatsink airflow path

## JITX expressions

> **Illustrative.** The `design_constraint(...).METHOD(...)` patterns below show authoring intent, not exact API. The canonical rule-builder methods exported by `jitx.constraints` today are `trace_width`, `clearance`, `stitch_via`, `fence_via`, and `thermal_relief`. Tag subclasses (`SwTag`, `RFTag`, `ThermalPadTag`, `SensitiveAnalogTag`, etc.) are user-defined per the `Tag` base-class docstring — declare them at module scope in the project's tags module (see `project-builder-flow.md`). When a rule below names a method not in the canonical set, treat it as a placeholder for either a future rule-builder method or a project-local helper that calls the canonical methods.

```python
# Thermal pad with paste subdivision (component-level)
class TPS54331(Component):
    landpattern = QFN_8_3x3(thermal_pad=ThermalPad(
        size=(2.2, 2.2),
        paste_subdivision=2,  # 2x2 grid prevents voids
    ))

# Thermal via density (substrate-level — proposed extension)
design_constraint(ThermalPadTag()).thermal_via_density(8 * PER_CM2, diameter=0.3 * MM)

# Power-density tagging (substrate-level — proposed extension)
# >= 15.3 cm²/W for a 40 °C rise (THM_PWR_002); ~7.7 cm²/W with airflow
design_constraint(HighDissTag()).copper_area_min_per_watt(15.3 * CM2)
```

## Quantitative layout targets (waiting on introspection)

| Rule | Target | Introspection API needed |
|---|---|---|
| `THM_VIA_001` | Thermal via array 8–12 / cm² under hot pads | `board.thermal_via_density(component)` |
| `THM_VIA_003` | Thermal via spacing > 2 mm | `board.thermal_via_spacing(component)` |
| `THM_VIA_004` | Thermal via density 8–12 / cm² | `board.thermal_via_density(component)` |
| `THM_SPREAD_001` | Heat-dissipating components spread across PCB, not clustered | `board.thermal_distribution()` |

## Out-of-band (not enforceable by JITX)

| Rule | Why out-of-band | Suggested verification |
|---|---|---|
| `THM_RISE_001` | Junction-temperature margin needs the real θja and operating point | Thermal simulation or measured prototype |
| `THM_HEAT_001` | Heatsink mech fit | MCAD tool |
| `THM_COOL_001` | Forced-air CFM | Mech / system engineer |

## Common gotchas

- **Thermal via filled vs unfilled** — unfilled vias under a thermal pad let solder wick through to the back side, leaving voids and reducing thermal contact. Use filled-and-capped vias or in-pad vias for components > 5 W.
- **Inner ground plane is *not* free thermal mass** — heat still has to get from the component through the dielectric to the plane via the thermal vias. Plane area helps spread, not pull.
- **θja from the datasheet is for the JEDEC reference board** — real boards with smaller copper area can be 1.5–3× worse. Derate accordingly.
- **Power resistor in a tight package (0402, 0603)** — even though I²R is below the rated power, the package surface temperature can exceed PCB substrate Tg. Use 0805+ for any continuous > 100 mW.

## Cross-references

- [`power.md`](power.md) — regulator selection, junction temperature in regulator datasheets
- [`emc-esd.md`](emc-esd.md) — thermal vias often double as stitching vias
- [`mechanical.md`](mechanical.md) — heatsink mechanical fit, enclosure ventilation
- [`net-classes.md`](../net-classes.md) — `ThermalPadTag`, `HighDissTag`, `HighCurrentTag`
