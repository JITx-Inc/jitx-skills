# Hardware Design Decomposition Guide

How to analyze requirements and break a hardware design into a parallelizable task graph for the project builder.

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

### Substrate (always one task)
- Layer count and material class (FR-4, low-loss, RF)
- Via types needed (through-hole, microvia, blind, buried, backdrilled)
- Impedance targets per signal class
- Routing structures (single-ended and differential)
- Fabrication constraints

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

Key insight: **substrate and all components have zero mutual dependencies** and can run fully in parallel. This is where the biggest parallelism win comes from.

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
- Cluster B: Power circuits (depend on power components only)
- Cluster C: Interface circuits + constraints (depend on central IC, connectors, substrate, and possibly Cluster A)

Within each cluster, tasks may need to be sequential (e.g., constraints before circuits that use them). Between clusters, tasks can run in parallel.

### Phase 3: Top-Level Assembly (single agent, sequential)
- Instantiate all subcircuits
- Connect power and ground nets
- Wire interfaces via require() from provides
- Apply board-level SI constraints
- Define board geometry

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

Adapted from the godogen decomposition pattern:

**De-risk first**: Identify the technically hardest piece of the design and tackle it early. In hardware, this is usually:
- The highest-speed interface (DDR5, 25G+ SerDes)
- The most complex component (FPGA with 500+ pins)
- The tightest thermal constraint (high-current regulators in small area)
- The most unusual package (custom footprint, non-standard BGA)

If the hard part fails, you discover it before investing time in the routine parts.

**Bundle routine work**: Group simple, similar tasks. Multiple connectors in one task. Multiple simple LDOs in one power task. Multiple low-speed interfaces in one circuit task. This reduces task boundary overhead.
