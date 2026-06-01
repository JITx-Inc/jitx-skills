# Power Domain Reference

## When to read this

You are working on a power-regulator circuit (LDO, buck, boost, charge pump), a power distribution network (input filter, fuse, ORing diode, eFuse), or sizing decoupling for a digital/analog IC. Also read [`emc-esd.md`](emc-esd.md) for return-path strategy and [`thermal.md`](thermal.md) for thermal via planning on regulators dissipating > 1 W.

## Authoring-time targets

### Decoupling discipline

- [ ] 100 nF on every power pin of every active IC
- [ ] One bulk cap (10 µF typical) per power domain
- [ ] Multiple smaller caps preferred over one large cap for HF decoupling (`PWR_DECPL_002`)
- [ ] 0402 / 0603 packages preferred over 0805 for HF — lower ESL (`PWR_DECPL_004`)
- [ ] Power-rail capacitors carry explicit placement intent; use the canonical `short_trace=True` rule and exception/disposition flow in `jitx-circuit-builder/SKILL.md`.

### Regulator electrical correctness

- [ ] Input voltage range covers actual source voltage with tolerance
- [ ] Output current rating ≥ 1.2× expected load (20%+ headroom)
- [ ] Enable pin **not floating** — tied through resistor, controlled signal, or pulled up
- [ ] Adjustable output: voltage divider via `voltage_divider_from_constraints()`, never manual values
- [ ] Reference voltage matches datasheet (0.6 V / 0.8 V / 1.0 V / etc.)
- [ ] `v_out` uses `Toleranced.percent()`, not `Toleranced.exact()`
- [ ] Soft-start cap included if pin available
- [ ] PGOOD pin: open-drain gets pull-up; push-pull doesn't

### Switching regulator specifics

- [ ] Inductor saturation current Isat ≥ 1.2–1.5× peak operating current (`PWR_RATING_001`)
- [ ] FET / diode Vds rating ≥ 1.2–1.5× max transient voltage (`PWR_RATING_002`)
- [ ] Type II/III compensation network matches datasheet (`PWR_COMP_001`)
- [ ] Bootstrap cap present if required
- [ ] Frequency-setting resistor correct if Fsw is programmable

### Power-tree hygiene

- [ ] Relay / solenoid coil has flyback diode (cathode to positive) (`PWR_RELAY_001`)
- [ ] Fuse rating sized to protect wire gauge AND connector, not just the load (`PWR_FUSE_001`)
- [ ] Polar cap voltage rating ≥ 1.5–2× applied voltage (`SCH_POL_001`)

## JITX expressions

> **Illustrative.** The `design_constraint(...).METHOD(...)` patterns below show authoring intent, not exact API. The canonical rule-builder methods exported by `jitx.constraints` today are `trace_width`, `clearance`, `stitch_via`, `fence_via`, and `thermal_relief`. Tag subclasses (`SwTag`, `RFTag`, `ThermalPadTag`, `SensitiveAnalogTag`, etc.) are user-defined per the `Tag` base-class docstring — declare them at module scope in the project's tags module (see `project-builder-flow.md`). When a rule below names a method not in the canonical set, treat it as a placeholder for either a future rule-builder method or a project-local helper that calls the canonical methods.

```python
# Net classes — power
design_constraint(SwTag(), priority=HIGH).clearance(0.5)  # pour pullback from switch node
design_constraint(HighCurrentTag()).width(...)            # see references/net-classes.md

# Decoupling implementation patterns live in jitx-circuit-builder/SKILL.md;
# use that canonical short_trace=True rule and exception policy.

# Adjustable LDO feedback
r_top, r_bot = voltage_divider_from_constraints(
    v_in=Toleranced.percent(3.3, 2.0),
    v_out=Toleranced.exact(0.8),    # the FB reference, NOT the regulator output
    ...
)
```

## Quantitative layout targets (waiting on introspection)

These targets cannot be enforced at authoring time. The Phase 3b audit stubs them for activation once `jitx-client` introspection lands.

| Rule | Target | Introspection API needed |
|---|---|---|
| `PWR_DECPL_001` | 100 nF cap within 5 mm of IC power pin | `board.distance(pin, component)` |
| `PWR_DECPL_003` | Via-in-pad for BGA decoupling | `board.via_in_pad(component)` |
| `PWR_DECPL_005` | Dedicated GND via per decoupling cap pad | `board.ground_vias_near(pad)` |
| `PWR_BUCK_001` | Input-cap → switch-FET → GND loop area ≤ 20 mm² | `board.loop_area(net_set)` |
| `PWR_BUCK_002` | Input/output caps on same side as IC, adjacent to pads | `board.placement_side()`, `board.distance()` |
| `PWR_BUCK_003` | Input cap on same copper layer as buck IC | `board.placement_side()` |
| `PWR_BUCK_004` | No pour or signal routing under inductor | `board.copper_under(component)` |
| `PWR_BUCK_005` | Switching node copper area minimized | `board.copper_area(net)` |
| `PWR_BUCK_006` | Input and output cap groups physically separated | `board.distance(component, component)` |
| `PWR_TRACE_002` | Power trace width sized for ≤ 20 mV drop at full current | `board.trace_resistance(net)` |
| `PWR_RES_001` | Calculate DC resistance of supply traces | `board.trace_resistance(net)` |

## Common gotchas

- **PGOOD pull-up voltage** — confirm rail voltage matches the IC monitoring PGOOD; don't pull up to VBUS if PGOOD feeds a 3.3 V GPIO.
- **EN pin voltage divider** — if used for UVLO, verify EN max voltage is not exceeded across input voltage range.
- **Soft-start vs. inrush** — soft-start prevents output ringing but does not limit input-side inrush; add inrush limiter for large bulk caps.

## Cross-references

- [`emc-esd.md`](emc-esd.md) — return paths for switch-node current
- [`thermal.md`](thermal.md) — power dissipation, thermal vias under regulator pad
- [`component-selection.md`](component-selection.md) — cap dielectric, inductor Isat, electrolytic lifetime
- [`net-classes.md`](../net-classes.md) — `SwTag`, `HighCurrentTag`, `KelvinSenseTag`
