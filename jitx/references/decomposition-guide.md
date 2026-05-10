# Hardware Design Decomposition Guide

How to analyze requirements and break a hardware design into a parallelizable task graph for the project builder.

## Step 0: Requirements Lock (do this before any decomposition)

Before proposing subsystems or components, force the user to answer the requirements that drive part selection, mechanical fit, and assembly cost. Without these locked, every later proposal is guesswork and will need rework when the user pushes back. The Encore audit found the agent designed an ESP32 + USB-C input only to be told "no, that triggers the assembly cost I wanted to avoid" — the assembly-cost target wasn't locked before parts were chosen.

Lock these answers in PLAN.md before Phase 0 closes:

| Lock item | Why it matters | Example answers |
|-----------|---------------|-----------------|
| **Programming / debug path** | Drives MCU choice, connector, board area | "USB-C programming via on-chip bootloader", "JTAG via TC2050 pads", "pre-programmed module, no debug" |
| **User interface (UI) count and class** | Drives connector list, board area, edge geometry | "0 (sealed)", "1 button + 1 LED", "OLED + 4 buttons", "rotary encoder + audio jack" |
| **Power rails needed (count + voltage + load)** | Drives regulator topology, BOM, sequencing | "3.3V @ 200 mA", "3.3V + 1.8V + 5V analog, sequenced", "single 5V from USB-PD" |
| **Assembly cost target / tier** | Eliminates whole part categories before proposing | "JLCPCB economy (basic parts only)", "JLCPCB standard (extended OK)", "hand-build prototype", "production-volume custom assembly" |
| **RF / wireless module policy** | RF integration is a major design decision | "no RF", "BLE module (pre-certified)", "WiFi+BLE SoC (DIY antenna)", "external antenna module via U.FL" |
| **Connector UX** | Drives footprint, mechanical, ESD strategy | "USB-C edge-mount, plug from end", "USB-C top-mount, plug from above", "screw terminals", "internal-only board-to-board" |
| **Fab house / process** | Drives substrate choice (predefined vs custom), DRC | "JLCPCB 4-layer FR-4", "JLCPCB 6-layer 7628", "custom fab (Rogers)", "TBD — orchestrator asks" |
| **Mechanical / enclosure constraint** | Drives board outline, height, mounting | "fits an Adafruit 1.4\" case", "DXF outline at <path>", "no enclosure constraint", "must mount to existing PCB via M3 holes" |

The Phase 0 → 1 gate block requires that each of these is answered or explicitly marked "no constraint". Bare or hand-waved answers ("we'll figure out programming later") block the gate — they reliably become rework cycles.

## Step 1: Identify Subsystems

Parse the requirements and categorize everything needed:

### Components (each becomes a modeling task)

| Category | Examples | Task Granularity |
|----------|----------|-----------------|
| Central IC | MCU, FPGA, SoC | One task per IC |
| Memory | DDR, Flash, SRAM, EEPROM | One task per device |
| Power | LDO, buck, boost, PMIC | One task per regulator or per family from same manufacturer |
| Connectors | USB-C, QSFP, SMA, headers | One task per connector type (group similar ones) |
| Peripherals | Sensors, drivers, transceivers, ADC/DAC | One task per IC |
| Passives | Resistors, caps, inductors | No task needed — these come from jitxlib at circuit build time |

### Substrate (one task — or use SampleDesign / predefined substrate)
- If the design has **no SI constraints** (no differential pairs, no impedance control) **and** the layer count is appropriate for the routing density: `SampleDesign` from jitx.sample may be sufficient — skip the substrate task. However, `SampleDesign` uses a fixed layer count that may not match the design's complexity. A high-pin-count BGA or dense routing topology will require more layers than SampleDesign provides.
- If the design has **SI constraints** (USB, Ethernet, DDR, PCIe, etc.): a substrate with routing structures is required. **Ask the user which fab house they are targeting:**

  **If user confirms JLCPCB**, predefined substrates from `jitxlib.jlcpcb` are available:
  | Class | Layers | Prepreg | Routing Structures | Import |
  |-------|--------|---------|-------------------|--------|
  | `JLC04161H_1080` | 4 | 1080 | RS_50, DRS_90, DRS_100 | `from jitxlib.jlcpcb import JLC04161H_1080` |
  | `JLC04161H_7628` | 4 | 7628 | RS_50, DRS_90, DRS_100 | `from jitxlib.jlcpcb import JLC04161H_7628` |
  | `JLC06161H_7628` | 6 | 7628 | RS_50, DRS_100 | `from jitxlib.jlcpcb import JLC06161H_7628` |

  These include stackup, fabrication constraints, vias (11 via definitions including tented/filled for via-in-pad), and impedance-matched routing structures:
  ```python
  from jitxlib.jlcpcb import JLC04161H_1080
  substrate = JLC04161H_1080()
  ```

  **When to create custom (default path):** User has not confirmed JLCPCB, non-FR-4 materials (Rogers, Megtron), unusual layer count, non-standard impedance targets, or additional routing structures needed. In this case, invoke `jitx-substrate-modeler` and define:
  - Layer count and material class (FR-4, low-loss, RF)
  - Routing structures (single-ended and differential) for each impedance class
  - Via types needed (through-hole, microvia, blind, buried, backdrilled)
  - Fabrication constraints

  **Note:** Substrate choice is not always independent of component selection. A high-pin-count BGA will require a substrate with enough layers and microvia capability that a simple 4-layer FR-4 cannot provide. Consider component package complexity when assessing substrate needs.

### Interfaces (each becomes a circuit task in Phase 2)
- Memory interfaces (DDR5, LPDDR, SRAM bus)
- High-speed serial (PCIe, USB3, Ethernet SerDes, HDMI, DisplayPort)
- Low-speed serial (I2C, SPI, UART, JTAG)
- Analog (ADC/DAC, RF, audio)
- Power distribution (input → regulators → loads)

### Constraints (each becomes a constraint task in Phase 2)
- Per-protocol SI constraints (impedance, timing, skew)
- Pin assignment flexibility (provides on MCU/FPGA)

## Step 2: Map Dependencies

```
Substrate ─────────────────────────────────────┐
Components (all independent of each other) ────┤
                                               ▼
              ┌─ Constraints (need routing structures from substrate)
              ├─ Pin Assignment wrappers (need component models)
              ├─ Circuits (need components + constraints)
              ▼
         Top-Level Assembly (needs all of the above)
              ▼
         Build + Verify
```

Key insight: **substrate and most components are independent** and can run in parallel. This is where the biggest parallelism win comes from. However, note that this independence is not absolute — a high-pin-count BGA may require a substrate with enough layers and microvia capability, and power supply complexity can be driven by the aggregate requirements of individual components. The orchestrator should identify these coupling points during Phase 0 and document them in ARCHITECTURE.md.

## Step 3: Assign to Phases

### Phase 0: Requirements + Architecture (orchestrator, not parallelized)
- Analyze requirements
- Create the dependency graph
- Write PLAN.md and ARCHITECTURE.md
- Identify datasheets and reference materials needed

### Phase 1: Substrate + Components (fully parallel)
One task per:
- Substrate
- Each component or component family

All of these are independent and spawn as parallel sub-agents.

### Phase 2: Constraints + Circuits + Pin Assignment (partially parallel)
Group into independent clusters that can run in parallel:
- Cluster A: Pin assignment wrappers (depend on central IC component — other clusters may need these)
- Cluster B: Power circuits (depend on power components only). For complex power trees (3+ regulators, mixed switching/linear, sequencing requirements), this cluster may need iterative design: regulator type selection (buck, boost, LDO, hybrid) depends on efficiency targets, noise budgets, and thermal constraints. Document the power plan in ARCHITECTURE.md including load current per rail, noise/ripple requirements, transient load handling, and sequencing order.
- Cluster C: Interface circuits + constraints (depend on central IC, connectors, substrate, and possibly Cluster A). Include clock distribution planning here — protocols like PCIe require shared reference clocks with jitter budgets.

Within each cluster, tasks may need to be sequential (e.g., constraints before circuits that use them). Between clusters, tasks can run in parallel.

### Phase 3: Top-Level Assembly (single agent, sequential)
- Instantiate all subcircuits
- Connect power and ground nets with `GroundSymbol` / `PowerSymbol` (these go HERE, not in subcircuits)
- Wire interfaces via require() from provides
- Apply ALL SI constraints here within `ReferencePlanes(GND)` (constraints go HERE, not in subcircuits — subcircuits only create `>>` topologies)
- Add ground pours on ground plane layers. For designs with multiple power domains, plan power planes and split planes as needed (e.g., analog/digital ground partitioning on mixed-signal boards)
- Define board geometry (shape, mounting holes). If mechanical constraints exist (DXF board outline, EMN placement data, keepout zones, height restrictions), incorporate them here. A dedicated mechanical interface skill may be used for importing DXF/EMN data.
- Verify power sequencing requirements are met by the physical power tree

### Phase 4: Build + Verify + Iterate (single agent, sequential)
- Full build
- DRC check
- SI constraint verification
- Iterate on failures

## Step 4: Write Task Definitions

Each task in PLAN.md needs these fields:

| Field | Description |
|-------|-------------|
| `id` | Unique identifier (e.g., `comp-fpga`, `cir-ddr5`, `sub-01`) |
| `phase` | Which phase (0, 1, 2, 3, 4) |
| `type` | `component`, `substrate`, `circuit`, `constraint`, `pin-assignment`, `assembly`, `verify` |
| `name` | Human-readable name |
| `description` | What to build — be specific about part numbers, interfaces, features |
| `skill` | Which sub-skill to invoke |
| `dependencies` | List of task IDs this depends on |
| `inputs` | Datasheets (path or URL), specs, or outputs from dependencies (labeled `Inputs` or `Datasheet` in template) |
| `checklist` | Which domain checklist(s) to apply |
| `verification` | Build command for testing |
| `status` | `pending` / `in-progress` / `review` / `accepted` / `rework` / `rejected` |

Be specific in descriptions. "Model the power regulator" is too vague. "Model TPS62933DRLR: 3.8-36V input, adjustable output buck, SOT-583 package, 6 pins + thermal pad" gives the sub-agent what they need.

### Engineering Questions (circuit tasks only)

For every circuit task, the orchestrator MUST write 3-5 specific engineering questions that force the sub-agent to think about the actual design. These are NOT generic checklist items — they are specific to this circuit's IC and application.

**Example for a USB PD sink circuit (HUSB238):**
```
- What voltage is VBUS after PD negotiation? (20V) — all pull-ups must go to 3.3V, NEVER to VBUS
- Does the HUSB238 need D+/D- connected? (Only for BC1.2 — if not needed, leave disconnected)
- Does the datasheet show an external PMOS on the GATE output? (Yes — include it)
- What I2C voltage domain does the HUSB238 use? (VIN-level — needs level shifter to 3.3V ESP32)
```

**Example for a buck converter circuit (TPS54202):**
```
- What is the input voltage range? (5-20V from PD) — does the converter handle this full range?
- Does the datasheet show a bootstrap capacitor on BOOT? (Yes — 100nF)
- Is a UVLO divider on EN needed for this input range? (Yes — prevents running at low VIN)
- Feedback reference voltage? (0.596V) — use voltage_divider_from_constraints, never manual values
```

**Example for an amplifier circuit (TAS5805M):**
```
- Is ADR_FAULT a dual-function pin? (Yes — address at boot, fault after) — use resistor, not hard tie
- Does the datasheet show external LDO or is DVDD the internal regulator output? (Internal output — decouple only)
- What external components are on PVDD? (Bulk caps + ferrite bead per datasheet)
- Does the FAULT output need a pull-up? (Yes — open-drain, 10k to 3.3V)
```

These questions go in the PLAN.md task definition. The sub-agent must answer each one (with datasheet evidence) before the circuit is accepted.

## CRITICAL: Bundle-First Interface Design

Circuits MUST expose bundle-typed ports (I2S, I2C, SPI, USB2, GPIO, DiffPair, Power) — not individual signal ports. This is what makes require() and the pin assignment solver work at top level.

**Wrong** (individual ports — defeats pin assignment):
```
Task description: "Expose I2S ports: SCLK, LRCLK, SDIN"
Result: circuit has self.SCLK = Port(), self.LRCLK = Port(), self.SDIN = Port()
Top-level: hardcodes self.net1 += esp32.GPIO4 + amp.SCLK  # BAD
```

**Right** (bundle port — enables require()):
```
Task description: "Expose I2S bundle port for upstream require()"
Result: circuit has self.i2s = I2S()  # bundle from jitxlib
Top-level: i2s = self.esp32.require(I2S)
           self += i2s.sck + self.amp.i2s.sck  # solver picks pins
```

When writing PLAN.md task descriptions for circuit tasks:
- Describe interfaces as bundles: "Expose I2S bundle port", not "Expose SCLK, LRCLK, SDIN"
- If the downstream circuit wraps a component with individual pins, the circuit must still expose a bundle port and wire the bundle sub-ports to the component pins internally
- The top-level assembly uses `require()` from the MCU/FPGA wrapper and wires to circuit bundle ports — never hardcode GPIO numbers

## Common Design Patterns

### Simple MCU Board (e.g., STM32 + sensors + USB)
```
Phase 1 (parallel, ~4 tasks):
  sub-01: 4-layer FR-4 substrate
  comp-01: STM32 MCU from datasheet
  comp-02: USB-C connector
  comp-03: Sensor IC

Phase 2 (partially parallel, ~4 tasks):
  pin-01: MCU provides (GPIO, SPI, I2C, USB) — depends on comp-01
  cir-01: Power circuit (LDO from USB VBUS) — depends on comp-02
  cir-02: Sensor interface (I2C + decoupling) — depends on comp-01, comp-03
  cir-03: USB interface (with ESD protection) — depends on comp-01, comp-02

Phase 3: Top-level assembly
Phase 4: Build + verify + iterate
```

### FPGA Eval Board (e.g., Agilex + DDR5 + SerDes)
```
Phase 1 (parallel, ~6 tasks):
  sub-01: 16-20 layer low-loss substrate
  comp-01: FPGA from pinout file
  comp-02: DDR5 memory from datasheet
  comp-03: Power module family (3-5 regulators)
  comp-04: QSFP/SFP connector
  comp-05: SMA connectors + JTAG header

Phase 2 (clustered parallel, ~7 tasks):
  Cluster A: cir-01 power tree — depends on comp-03
  Cluster B: cst-01 DDR5 constraints, cir-02 DDR5 interface — depends on comp-01, comp-02, sub-01
  Cluster C: cst-02 SerDes constraints, cir-03 SerDes interface — depends on comp-01, comp-04, sub-01
  pin-01: FPGA provides — depends on comp-01

Phase 3: Top-level assembly (complex — ReferencePlanes, pours, many constraints)
Phase 4: Build + verify + iterate
```

### Power Supply Board (e.g., multi-rail supply)
```
Phase 1 (parallel, ~4 tasks):
  sub-01: 4-layer FR-4 substrate
  comp-01: Input connector + protection
  comp-02: Primary regulators (buck converters)
  comp-03: Secondary regulators (LDOs)

Phase 2 (parallel per rail, ~4 tasks):
  cir-01: Input stage (TVS, fuse, bulk caps)
  cir-02: Primary rail circuits — depends on comp-02
  cir-03: Secondary rail circuits — depends on comp-02 output, comp-03
  cir-04: Power monitoring / sequencing

Phase 3: Top-level with power tree, status LEDs, test points
Phase 4: Build + verify + iterate
```

### Mixed-Signal Board (e.g., ADC/DAC + digital processing)
```
Phase 1 (parallel, ~5 tasks):
  sub-01: 6-layer substrate with analog/digital ground strategy
  comp-01: Digital IC (MCU or FPGA)
  comp-02: ADC
  comp-03: DAC
  comp-04: Analog front-end components (op-amps, filters)

Phase 2 (clustered, ~5 tasks):
  Cluster A (analog): cir-01 ADC interface, cir-02 DAC interface
  Cluster B (digital): cir-03 digital interfaces, pin-01 MCU provides
  cst-01: Mixed-signal constraints (guard rings, ground partitioning)

Phase 3: Top-level with careful ground plane partitioning
Phase 4: Build + verify + iterate
```

## De-Risk / Bundle Strategy

Strategy for managing risk and reducing task overhead:

**De-risk first**: Identify the technically hardest piece of the design and tackle it early. In hardware, this is usually:
- The highest-speed interface (DDR5, 25G+ SerDes)
- The most complex component (FPGA with 500+ pins)
- The tightest thermal constraint (high-current regulators in small area)
- The most unusual package (custom footprint, non-standard BGA)

If the hard part fails, you discover it before investing time in the routine parts.

**Bundle routine work**: Group simple, similar tasks. Multiple connectors in one task. Multiple simple LDOs in one power task. Multiple low-speed interfaces in one circuit task. This reduces task boundary overhead.
