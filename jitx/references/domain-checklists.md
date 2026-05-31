# Domain-Specific Validation Checklists

Sub-agents MUST run the relevant checklist after initial implementation and BEFORE returning results. The orchestrator will independently verify high-risk items during acceptance review.

## How to Use

1. Complete your implementation and get an initial `status: ok` build.
2. Read the checklist(s) below that match your task type.
3. For EVERY item, verify against the datasheet or specification. Do not check items from memory.
4. If you find an issue, FIX IT before continuing.
5. If an item does not apply, note why (do not silently skip).
6. Rebuild after fixes and verify `status: ok`.
7. Include checklist results in your task acceptance block (see `references/completion-blocks.md`).

Your initial implementation likely missed something. This is expected and normal. The purpose of this checklist is to catch those misses. Approach it as a critical reviewer, not a rubber stamp.

---

## Component Modeling (All Components)

### Pins and Ports
- [ ] ALL pins from datasheet accounted for — not just signal pins
- [ ] Every VCC/VDD/VDDIO pin has a port
- [ ] Every GND/VSS/AGND pin has a port
- [ ] NC pins: if they have physical pads, they need ports
- [ ] Thermal/exposed pad included if present in package drawing
- [ ] Pin naming matches datasheet convention exactly
- [ ] Pin functions correct (input / output / bidirectional / power / ground)
- [ ] Pin arrays indexed correctly where names increment (e.g., `GND[0]` through `GND[N]`)
- [ ] No duplicate pin names

### Package and Landpattern
- [ ] Package type matches datasheet (QFN vs SON vs DFN vs SOIC, etc.)
- [ ] Body dimensions taken from MECHANICAL DRAWING page (not overview or ordering info)
- [ ] Lead pitch matches datasheet exactly
- [ ] Lead width and length from recommended land pattern or IPC calculation
- [ ] Toleranced values use min/nom/max from datasheet (not nominal only)
- [ ] Thermal pad dimensions from mechanical drawing (usually labeled D2/E2 or Dpad/Epad)
- [ ] Thermal pad has paste subdivision if area > 4mm^2 (prevents solder voids)
- [ ] Pin 1 orientation matches datasheet marking
- [ ] Correct landpattern generator chosen (QFN vs SON for 2-sided vs 4-sided no-lead)

### Symbol
- [ ] All ports appear in BoxSymbol
- [ ] Logical grouping: power pins up, ground pins down, inputs left, outputs right
- [ ] Multi-unit symbol used if pin count > 40 (split by functional group)

### Build Test
- [ ] Test harness created using TestDesign pattern
- [ ] Builds with `status: ok`
- [ ] PadMapping verified (if explicit mapping used — pad names match landpattern)

---

## MCU / FPGA Components (Additional)

Run the base Component checklist above FIRST, then verify these:

### Clock System
- [ ] Crystal/oscillator input pins present (XTAL_IN, XTAL_OUT or HSE_IN, HSE_OUT)
- [ ] External clock input pins present (if supported)
- [ ] PLL reference clock pins present (for FPGAs with transceivers)
- [ ] RTC crystal pins (LSE_IN, LSE_OUT) if RTC is supported
- [ ] Clock distribution requirements identified — protocols like PCIe require shared reference clocks (REFCLK) to all endpoints on the same clock domain. Plan clock tree topology (point-to-point, fanout buffer, clock generator) during decomposition.

### Programming and Debug
- [ ] JTAG pins present: TCK, TMS, TDI, TDO (and optionally nTRST)
- [ ] SWD pins present: SWCLK, SWDIO (for ARM MCUs)
- [ ] UART bootloader pins identified (if applicable)
- [ ] Configuration pins present (nCONFIG, CONF_DONE, nSTATUS for FPGAs)

### Reset
- [ ] Reset pin present with correct polarity documented (nRST = active-low, RST = active-high)
- [ ] Reset pin labeled consistently with datasheet convention

### Power Domains
- [ ] Core supply pins (VCC, VCCINT) — all of them, not just one
- [ ] IO bank supply pins (VCCIO, VDDIO) — every bank, even if same voltage
- [ ] PLL/analog supply pins (VCCA, VCCPLL) — separate from digital
- [ ] Transceiver supply pins (VCC_XCVR, VCCR, VCCT) if applicable
- [ ] Auxiliary supply pins (VCCAUX) if present

### Boot and Configuration
- [ ] Boot mode pins present (BOOT0, BOOT1 for STM32; MSEL for Intel FPGAs)
- [ ] Configuration select pins if applicable
- [ ] Power-on-reset configuration pins if applicable

### IO Banks
- [ ] All IO banks modeled (not just the ones used in the current design)
- [ ] Bank-to-pin mapping documented in comments or docstring

---

## Domain references

Power, high-speed, analog, EMC, thermal, and other domain-specific checks have moved into per-domain reference files. Read the file(s) that apply to your task:

- [`domains/power.md`](domains/power.md) — regulators, decoupling, fuses, flyback, polar caps
- [`domains/high-speed-si.md`](domains/high-speed-si.md) — diff pairs, DDR/PCIe/USB/Ethernet, crystals, length matching
- [`domains/analog-mixed-signal.md`](domains/analog-mixed-signal.md) — op-amps, ADC, mixed-signal partitioning
- [`domains/emc-esd.md`](domains/emc-esd.md) — stitching, plane partitioning, aggressor / victim separation
- [`domains/thermal.md`](domains/thermal.md) — power density, thermal vias, heatsink decisions
- [`domains/component-selection.md`](domains/component-selection.md) — cap dielectric, voltage derating, inductor Isat / SRF, resistor noise / tempco
- [`domains/code-hygiene.md`](domains/code-hygiene.md) — DNP, polarity, FET startup, I2C addressing
- [`domains/external-interfaces.md`](domains/external-interfaces.md) — connector ESD-or-justification, hot-plug protection, retention
- [`domains/dft.md`](domains/dft.md) — test points, debug headers, named TPs
- [`domains/dfm.md`](domains/dfm.md) — fab rules, acid traps, edge clearance, panelization
- [`domains/mechanical.md`](domains/mechanical.md) — mounting, enclosure fit, heatsink mech
- [`domains/safety-critical.md`](domains/safety-critical.md) — aerospace, automotive, medical class-specific
- [`domains/thermal-and-emc-workflow.md`](domains/thermal-and-emc-workflow.md) — cross-artifact orchestration when thermal and EMC concerns both apply (e.g. switching regulators, RF designs, mixed-signal partitioning)

Net classes (switch node, RF, high-speed diff, sensitive analog, high-voltage, high-current, gate drive, Kelvin sense, isolated domain, thermal pad, ESD-exposed) live in [`net-classes.md`](net-classes.md).

The artifact-level Component, MCU/FPGA, and Substrate checklists remain in this file (below). The cross-cutting General Gotcha Scrub is also here.


---

## Substrate

- [ ] **User's fab house confirmed**: if user confirmed JLCPCB, predefined substrates from `jitxlib.jlcpcb` (JLC04161H_1080, JLC04161H_7628, JLC06161H_7628) are available for standard FR-4 + 50/90/100 ohm. Otherwise, create a custom substrate (default)
- [ ] Layer count sufficient for routing density and reference plane continuity
- [ ] Impedance targets achievable with chosen dielectric Dk and geometry
- [ ] Via definitions cover ALL needed layer transitions (not just top-to-bottom)
- [ ] Ground reference planes continuous under all high-speed signal layers
- [ ] No signal layers without an adjacent ground reference plane
- [ ] Routing structures defined for every impedance class in the design
- [ ] Differential routing structures match protocol requirements (100 ohm, 85 ohm, etc.)
- [ ] Fabrication constraints are within manufacturer capabilities:
      - Minimum trace width and spacing
      - Minimum via drill and annular ring
      - Minimum dielectric thickness
      - Copper weight compatibility
- [ ] Microvia span within fab capability (typically 1-2 layers max)
- [ ] Stacked microvias specified correctly if needed (filled and capped)
- [ ] Backdrill specified for through-hole vias in high-speed paths (if needed)
- [ ] Routing structure velocity uses `phase_velocity()` (returns mm/s, NOT m/s)

---

## General Gotcha Scrub (Apply to ALL Tasks)

After the domain-specific checklist, verify these universal items:

### Electrical
- [ ] No floating inputs on any active device
- [ ] No missing ground connections
- [ ] Open-collector/open-drain outputs have pull-up resistors
- [ ] Analog reference pins properly decoupled/filtered
- [ ] Crystal load capacitors match oscillator requirements (if applicable)
- [ ] All voltage dividers use the solver function, not manual values

### JITX Code Correctness
- [ ] All nets stored on `self` — bare `a + b` expressions without assignment are silently dropped
- [ ] All components stored on `self` — anonymous `Component().insert()` fails at build time
- [ ] All topologies stored on `self` — bare `a >> b` without assignment is silently dropped
- [ ] No aliasing of component ports: `self.x = self.r1.p2` causes multiple-parent errors
- [ ] Port definitions at class level (not inside `__init__`) except for PadMapping and dynamically-configured ports set at instantiation time

### Top-Level Only (do NOT put these in subcircuits)
- [ ] `GroundSymbol` on GND net — applied at top-level design only
- [ ] `PowerSymbol` on every power rail — applied at top-level design only
- [ ] SI constraints (`Constrain`, `ConstrainDiffPair`, `ConstrainReferenceDifference`) — applied at top-level within `ReferencePlanes(GND)` context, not inside subcircuits
- [ ] Ground pours on ground plane layers — applied at top-level design only
- [ ] **I2C pull-ups** — placed at the bus-aggregation level (the circuit that composes master + slaves on the bus). Usually the top-level design because most buses span subcircuits; but if one subcircuit fully encloses both ends of a private bus, the pull-ups belong inside that subcircuit. Never local to a single bus participant.
- [ ] **Shared bus termination** (I2C, SPI, CAN) — pull-ups/termination at top-level only, never duplicated in subcircuits

### Datasheet Compliance (CRITICAL for circuit tasks)
- [ ] **Downloaded and read the datasheet** for every IC in this circuit
- [ ] **Application circuit matches datasheet** — every external component shown in the datasheet's typical application circuit is present in the JITX code
- [ ] No missing transistors (PMOS switches, level shifters, discharge FETs)
- [ ] No missing passives (bootstrap caps, snubber circuits, compensation networks)
- [ ] **Voltage domains checked** — every pull-up and pull-down goes to the correct rail (NOT VBUS if VBUS is high-voltage)
- [ ] Dual-function pins use resistors, not hard ties to VCC/GND
- [ ] Pins that should not be connected (NC per datasheet) are actually left unconnected
