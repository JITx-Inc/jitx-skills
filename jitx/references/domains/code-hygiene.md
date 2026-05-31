# Code Hygiene Reference

## When to read this

You have a complete circuit and want a pre-build sanity pass, or you are wrapping a non-trivial IC and want to make sure no connectivity-level rules are missed. In JITX the schematic is generated from the code, so these are code-hygiene rules. JITX already enforces most circuit-graph correctness by construction (no orphan nets, no duplicate net names) — this reference is about the rules that *need designer intent* to verify.

## Authoring-time targets

### Net hygiene (mostly enforced by JITX type system)

- [ ] No floating inputs on any active device (`SCH_FLOAT_001`) — verified by JITX completion-block grep on every Port
- [ ] No single-pin (orphan) nets (`SCH_NET_002`) — structurally impossible in JITX if all nets stored on `self`
- [ ] Cross-sheet net labels match (`SCH_NET_001`) — JITX uses Python attribute names, case-sensitive by construction
- [ ] Net naming consistency: `vcc_3v3` and `vcc_5v0`, not generic `vcc` everywhere (`SCH_NET_003`, `SCH_NET_004`)
- [ ] Unused op-amp / comparator / digital inputs tied to a defined level (`SCH_PULLUP_001`)

### Component values and ratings

- [ ] Component value transcription sanity (10 vs 10k, 4.7 vs 47, pF vs nF) (`SCH_VAL_001`)
- [ ] Polar capacitor polarity correct and voltage rating ≥ 1.5–2× applied (`SCH_POL_001`)
- [ ] DNP (do-not-populate) status matches BOM and intended variant configuration (`SCH_DNP_001`)
- [ ] Experimental / uncertain circuits: include DNP footprints for series-R, parallel-C, alternate parts (`SCH_OPT_001`)

### IC-level checks

- [ ] Symbol pinouts verified against the manufacturer's datasheet (`SCH_SYMBOL_001`)
  - Especially for parts with multiple package variants — pinouts may differ
  - Check errata for late pinout changes
- [ ] IC datasheet read: app circuit, errata, abs-max ratings, pin configurations (`SCH_IC_001`)
- [ ] FET gate has defined level at startup — pull-up or pull-down — to prevent undefined state (`SCH_FET_001`)
- [ ] Reset pin: polarity and assertion path explicit (`MS_RST_001`)
- [ ] Boot mode pins (BOOT0/1, MSEL) tied to the intended boot source

### Bus and protocol annotations

- [ ] I2C device addresses annotated in the code (component docstring or comment, e.g., `U5: 0x48`); pin-strappable addresses show their state (`SCH_I2C_001`)
- [ ] I2C address conflicts: no two devices with the same address on the same bus; verified during decomposition (`SCH_I2C_002`, `MS_I2C_001`)
- [ ] UART TX/RX crossover verified — TX out → RX in (`SCH_UART_001`)
- [ ] SPI chip-select unique per device

## JITX expressions

> **Illustrative.** The `design_constraint(...).METHOD(...)` patterns below show authoring intent, not exact API. The canonical rule-builder methods exported by `jitx.constraints` today are `trace_width`, `clearance`, `stitch_via`, `fence_via`, and `thermal_relief`. Tag subclasses (`SwTag`, `RFTag`, `ThermalPadTag`, `SensitiveAnalogTag`, etc.) are user-defined per the `Tag` base-class docstring — declare them at module scope in the project's tags module (see `project-builder-flow.md`). When a rule below names a method not in the canonical set, treat it as a placeholder for either a future rule-builder method or a project-local helper that calls the canonical methods.

```python
# Pull-up to defined logic level — assign Resistor to self, THEN insert
# (chained `Resistor(...).insert(...)` captures the insert return, not the resistor)
self.reset_pullup = Resistor(10 * KOHM)
self.reset_pullup.insert(mcu.nrst, vcc_3v3)

# DNP variant
self.snubber_r = Resistor(100 * OHM)
self.snubber_r.insert(net_a, net_b, dnp=True)

# I2C address annotation in the component spec
@component
class TempSensor(Component):
    """TMP102 — I2C address 0x48 (ADD0 = GND); options 0x49/0x4A/0x4B."""
    ...
```

## Common gotchas

- **Pull-up to a non-existent rail at startup** — if the rail is enabled later in the boot sequence, the pin floats until the rail comes up. Use the always-on rail for boot-critical pull-ups.
- **DNP footprint with mandatory net connections** — DNP'd resistors that are part of a current path leave that path open; check that DNP is truly optional, not load-bearing.
- **I2C addresses with pin-strapped suffixes** — datasheets often show "address = 0x48 + ADD0" without making it obvious that ADD0 = VCC adds 1, ADD0 = SDA adds 2. Read the full address pin truth table.
- **"NC" pins that have copper pads** — must still get a Port (otherwise the pad is floating during assembly inspection); leave the Port unconnected at the circuit level.

## Cross-references

- [`power.md`](power.md) — polar cap polarity, voltage derating, regulator EN-pin handling
- [`analog-mixed-signal.md`](analog-mixed-signal.md) — unused op-amp / comparator inputs
- [`external-interfaces.md`](external-interfaces.md) — connector pin labeling
- [`component-selection.md`](component-selection.md) — voltage rating margins
