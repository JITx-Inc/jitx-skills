# Analog and Mixed-Signal Reference

## When to read this

You are designing an op-amp circuit, an ADC / DAC interface, a sensor front-end, or any board with both digital switching and sensitive analog (CODEC, ADC, instrumentation amplifier). Also read [`emc-esd.md`](emc-esd.md) for AGND/DGND strategy and [`component-selection.md`](component-selection.md) for capacitor and resistor choices in precision circuits.

## Authoring-time targets

### Op-amp circuits

- [ ] Op-amp inputs stay within common-mode range across all operating conditions (`AN_OPAMP_001`)
  - Rail-to-rail input op-amp if signal swings near supply rails
  - Single-supply op-amp: confirm input doesn't violate VCM_min ≥ V- + V_OS
- [ ] Feedback network topology matches the intended function (inverting / non-inverting / integrator / differential) (`AN_OPAMP_003`)
  - Verify resistor placement against the textbook topology — easy to swap inverting and non-inverting nodes
- [ ] Large capacitive loads (> 100 pF, including scope-probe loading): add 10–100 Ω series isolation resistor at op-amp output (`AN_OPAMP_002`)
- [ ] Unused op-amp / comparator inputs: tie to GND or VCC per datasheet, never floating (`SCH_PULLUP_001`)
- [ ] Unused op-amp sections: non-inverting input to mid-rail, output left open

### ADC interfaces

- [ ] ADC input has clamp protection (Schottky to rails or integrated clamps) and RC anti-alias filter (`AN_ADC_001`)
- [ ] ADC driver bandwidth ≥ 3–5× sampling frequency (or signal bandwidth, whichever greater) (`AN_ADC_002`)
- [ ] RC anti-alias filter cutoff tuned to Nyquist (Fs/2), accounting for ADC input impedance (`AN_ADC_003`)
- [ ] High-resolution ADC (≥ 16-bit): minimum 4-layer stackup for plane continuity (`AN_ADC_007`)
- [ ] VREF pin properly decoupled (typically 10 µF + 100 nF, low-ESR)

### Mixed-signal partitioning

- [ ] Separate power supplies for analog and digital sections (`MX_PWR_001`)
  - LDO or filtered rail for analog supply; never tap analog supply off a switcher output directly
- [ ] Ferrite bead between digital and analog ground if a single board ground is used
- [ ] Star-ground at the ADC if AGND and DGND are kept distinct (`AN_ADC_005`)

### Sensor front-ends

- [ ] High-impedance sensor nodes documented in the code (net/instance docstring or comment) with a note about leakage requirements (`AN_SENSOR_001`)
- [ ] Bias current path defined (otherwise input floats over time even with apparent DC path)

## JITX expressions

> **Illustrative.** The `design_constraint(...).METHOD(...)` patterns below show authoring intent, not exact API. The canonical rule-builder methods exported by `jitx.constraints` today are `trace_width`, `clearance`, `stitch_via`, `fence_via`, and `thermal_relief`. Tag subclasses (`SwTag`, `RFTag`, `ThermalPadTag`, `SensitiveAnalogTag`, etc.) are user-defined per the `Tag` base-class docstring — declare them at module scope in the project's tags module (see `project-builder-flow.md`). When a rule below names a method not in the canonical set, treat it as a placeholder for either a future rule-builder method or a project-local helper that calls the canonical methods.

```python
# Anti-alias filter — pattern only, not yet a solver
self.aa_filter = LowpassRC(cutoff=Fs/2.5, source_z=op_amp.r_out)
self.aa_filter.input += op_amp.out
self.aa_filter.output += adc.ain

# Voltage divider with explicit tolerance
r_top, r_bot = voltage_divider_from_constraints(
    v_in=Toleranced.percent(5.0, 1.0),
    v_out=Toleranced.percent(2.5, 0.5),
    ...
)
```

## Quantitative layout targets (waiting on introspection)

| Rule | Target | Introspection API needed |
|---|---|---|
| `AN_ADC_004` | ADC placed at analog/digital boundary | `board.placement_zone(component)` |
| `AN_ADC_005` | AGND/DGND star-ground at ADC | `board.ground_topology()` |
| `AN_ADC_006` | Digital switching return currents bypass ADC ground | `board.return_path(net)` |
| `AN_SENSOR_001` | High-impedance sensor: guard ring around trace | `board.guard_ring(net)` |
| `MX_ROUTE_001` | Digital/analog traces routed separately; cross at 90° | `board.trace_crossings_angle()` |

## Common gotchas

- **Op-amp running rail-to-rail on a single 3.3 V supply** — the input common-mode range typically excludes the bottom rail; non-rail-to-rail op-amps need headroom both sides.
- **ADC anti-alias too tight** — if cutoff = Fs/2 exactly, the signal at Nyquist is attenuated by only 3 dB. Use Fs/2.5 or steeper filter.
- **Ferrite bead between AGND and DGND on a high-current digital board** — the bead can saturate and stop providing isolation. For high digital currents, fully separate planes with a single bridge point are safer.
- **Sigma-Delta ADCs have built-in anti-alias** but still need an RC for charge-kickback rejection.

## Cross-references

- [`emc-esd.md`](emc-esd.md) — return paths, ground bounce, AGND/DGND strategy
- [`component-selection.md`](component-selection.md) — C0G/NP0 for precision filters, low-noise resistors
- [`power.md`](power.md) — analog rail filtering, LDO selection for sensitive supplies
- [`code-hygiene.md`](code-hygiene.md) — unused-input termination
