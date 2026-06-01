# Design for Test (DFT) Reference

## When to read this

You are finalizing a board before tapeout, instantiating connectors for debug/programming, or planning bring-up. Policy: authoring intent is recorded in JITX now; visual silkscreen/label verification is out-of-band visual verification; physical placement/accessibility may be `awaiting-introspection`.

## Authoring-time targets

### Test points

- [ ] Test point on every major power rail (≥ 3.3 V, ≥ 5 V, ≥ 12 V) (`DFT_TP_001`)
  - Diameter ≥ 35 mils for oscilloscope probe contact
- [ ] Dedicated ground probe pad accessible for scope reference (`DFT_TP_002`, `DFT_GND_003`)
- [ ] Named test points for key signals: critical clocks, reset, mode-select, error flags (`DFT_TP_003`)
- [ ] Test-point label intent recorded in JITX: `TP1_3V3`, `TP2_GND`, etc. (`DFT_TP_004`; rendered silkscreen is out-of-band visual verification)

### Debug interfaces

- [ ] STM32 / ARM Cortex MCUs: SWD test points or 10-pin header accessible without test fixture (`DFT_SWD_001`)
  - SWDIO, SWCLK, GND minimum; nRESET strongly recommended
- [ ] FPGAs and complex digital: JTAG / boundary-scan header or test pads (`DFT_JTAG_001`)
- [ ] UART bootloader pins broken out if used for programming
- [ ] Boot-mode selection pins exposed if user must change modes during bring-up

### Connector labeling

- [ ] Every connector function-label intent recorded in JITX (`DFT_CONN_LABEL_001`; rendered silkscreen is out-of-band visual verification)
- [ ] Power connector polarity-marking intent recorded in JITX (`DFT_POL_001`; rendered silkscreen is out-of-band visual verification)

### Connectivity DRC (mostly enforced by JITX)

- [ ] Connectivity / electrical-rule check before layout — JITX has no schematic-capture DRC tool; the equivalent is the type system + completion-block grep gates, run against the code (`DFT_DRC_001`)
- [ ] Netlist ↔ layout connectivity — structurally guaranteed by JITX (single source of truth) (`DFT_CONN_001`)

## JITX expressions

> **Illustrative.** The `design_constraint(...).METHOD(...)` patterns below show authoring intent, not exact API. The canonical rule-builder methods exported by `jitx.constraints` today are `trace_width`, `clearance`, `stitch_via`, `fence_via`, and `thermal_relief`. Tag subclasses (`SwTag`, `RFTag`, `ThermalPadTag`, `SensitiveAnalogTag`, etc.) are user-defined per the `Tag` base-class docstring — declare them at module scope in the project's tags module (see `project-builder-flow.md`). When a rule below names a method not in the canonical set, treat it as a placeholder for either a future rule-builder method or a project-local helper that calls the canonical methods.

```python
# Test point with named ref-des — assign TestPoint to self, set designator, THEN insert
# (chained `TestPoint(...).insert(...)` captures the insert return, not the test point)
self.tp_3v3 = TestPoint(diameter=1 * MM)
self.tp_3v3.designator = "TP1_3V3"
self.tp_3v3.insert(power_3v3.vbus)

# Ground probe pad
self.tp_gnd = TestPoint(diameter=1 * MM)
self.tp_gnd.designator = "TP_GND"
self.tp_gnd.insert(gnd)

# SWD header
self.swd = ArmSWD10Pin()
self.swd.swdio += self.mcu.swdio
self.swd.swclk += self.mcu.swclk
self.swd.gnd   += gnd
self.swd.vcc   += vcc_3v3
self.swd.nreset += self.mcu.nrst
```

## Quantitative layout targets (waiting on introspection)

| Rule | Target | Introspection API needed |
|---|---|---|
| `DFT_GND_003` | Ground probe pad accessible for scope tip | `board.probe_access(net)` |
| `DFT_DRC_002` | Layout DRC clean | `board.drc_violations()` |

## Out-of-band

| Rule | Why out-of-band | Suggested verification |
|---|---|---|
| `DFT_TP_004`, `DFT_SILK_001/002`, `DFT_POL_001`, `DFT_CONN_LABEL_001` | Visual silkscreen/label verification | CAD screenshot / board render review; authoring intent should already be recorded in JITX |
| `DFT_BUILD_001` | Prototype assembly | Project process |
| `DFT_MEAS_001` | Design parameter measurement | Project process / bring-up plan |
| `DFT_PROD_001` | Validation before production | Project process |

## Common gotchas

- **Test points only on regulated rails, none on the input** — leaves no way to verify input voltage during bring-up. Add a TP near the connector too.
- **SWD header where the mech enclosure covers it** — the header is theoretically there but unreachable when the board is in its enclosure. Use a hole, magnet, or pogo-pin pad accessible from outside.
- **Boundary-scan chain that loops through DNP'd parts** — when you depopulate a debug-only part, the JTAG chain breaks. Either keep the chain DNP-bypassable or document that test mode requires all parts populated.
- **Test point right under a tall component** — physically inaccessible to a scope tip even though the netlist says it's there.

## Cross-references

- [`external-interfaces.md`](external-interfaces.md) — debug header ESD, connector labels
- [`dfm.md`](dfm.md) — fiducials and assembly support
- [`code-hygiene.md`](code-hygiene.md) — boot-mode pin handling
