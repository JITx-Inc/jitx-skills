# PLAN.md Template

Copy this into the project root and fill in task details. The orchestrator maintains this file as the single source of truth for project state.

---

```markdown
# Project Plan: [Project Name]

## Architecture Summary

### Power Tree
| Rail | Voltage | Source | Regulator | Load | Current |
|------|---------|--------|-----------|------|---------|
| VCC_CORE | 0.8V | 12V_IN | TPS62933 | MCU core | 2A |
| VCC_IO | 3.3V | 12V_IN | LM1117 | MCU IO, peripherals | 500mA |

### Interface Map
| Interface | From | To | Protocol | SI Constrained | Impedance |
|-----------|------|----|----------|----------------|-----------|
| DDR5 | FPGA bank A | Memory U2 | DDR5-4800 | Yes | 40/80 ohm |
| USB | MCU USB_DP/DM | Connector J1 | USB 2.0 HS | Yes | 90 ohm diff |
| SPI | MCU SPI1 | Sensor U3 | SPI 10MHz | No | — |

### Board
- Dimensions: [width x height mm]
- Layers: [count]
- Material: [FR-4 / Megtron 6 / etc.]

---

## Phase 1: Substrate + Components

### [sub-01] Substrate
- **Type:** substrate
- **Skill:** jitx-substrate-modeler
- **Description:** [layer count, material, impedance targets, via types needed]
- **Inputs:** [reference design, spec document, or requirements section]
- **Checklist:** Substrate
- **Verification:** `python runner/build_lock.py <ns>.substrate.TestDesign`
- **Status:** pending

### [comp-01] [Component Name]
- **Type:** component
- **Skill:** jitx-component-modeler
- **Description:** [MPN, manufacturer, package, pin count, key features]
- **Inputs:** [datasheet path or URL]
- **Checklist:** Component + [MCU/FPGA if applicable]
- **Verification:** `python runner/build_lock.py <ns>.components.<name>.TestDesign`
- **Status:** pending

### [comp-02] [Component Name]
- **Type:** component
- **Skill:** jitx-component-modeler
- **Description:** [MPN, manufacturer, package, pin count, key features]
- **Inputs:** [datasheet path or URL]
- **Checklist:** Component
- **Verification:** `python runner/build_lock.py <ns>.components.<name>.TestDesign`
- **Status:** pending

---

## Phase 2: Constraints + Circuits + Pin Assignment

### [pin-01] [IC Name] Pin Assignment
- **Type:** pin-assignment
- **Skill:** jitx-pin-assignment
- **Dependencies:** [comp-01]
- **Description:** [which provides to declare, what flexibility is needed]
- **Inputs:** [component model from comp-01, ARCHITECTURE.md interface map]
- **Checklist:** General Gotcha Scrub
- **Verification:** `python runner/build_lock.py <ns>.circuits.<wrapper>.TestDesign`
- **Status:** pending

### [cst-01] [Protocol] Constraints
- **Type:** constraint
- **Skill:** jitx-interconnect-constraints
- **Dependencies:** [sub-01]
- **Description:** [protocol, impedance targets, timing/skew requirements]
- **Inputs:** [protocol spec, substrate routing structures from sub-01]
- **Checklist:** Substrate + General Gotcha Scrub
- **Verification:** `python runner/build_lock.py <ns>.constraints.<name>.TestDesign`
- **Status:** pending

### [cir-01] [Circuit Name]
- **Type:** circuit
- **Skill:** jitx-circuit-builder
- **Dependencies:** [comp-01, comp-02, cst-01]
- **Description:** [what it connects, passives needed, topology vs net, constraints to apply]. IMPORTANT: expose bundle-typed ports (I2S, I2C, SPI, USB2, GPIO, Power) for upstream require() — not individual signal ports. Do NOT put I2C pull-ups or shared-bus termination here — those go at top level.
- **Inputs:** [datasheet PDF for every IC in this circuit — download first, read the application circuit]
- **Checklist:** [Power Circuit / Interface Circuit] + Datasheet Compliance + General Gotcha Scrub
- **Engineering questions** (orchestrator writes these per-circuit):
  - [What voltage domains exist? Where do pull-ups go?]
  - [Are there external transistors in the datasheet app circuit?]
  - [Which pins are dual-function? How are they configured?]
  - [What happens during power sequencing / startup?]
- **Verification:** `python runner/build_lock.py <ns>.circuits.<name>.TestDesign`
- **Status:** pending

---

## Phase 3: Top-Level Assembly

### [asm-01] Top-Level Design
- **Type:** assembly
- **Skill:** jitx-circuit-builder
- **Dependencies:** [all Phase 2 task IDs]
- **Description:** Instantiate all subcircuits, connect power/ground nets, wire interfaces via require(), apply board-level SI constraints in ReferencePlanes context, define board geometry
- **Checklist:** General Gotcha Scrub
- **Verification:** `python runner/build_lock.py <ns>.main.Design`
- **Status:** pending

---

## Phase 4: Build + Verify + Iterate

### [ver-01] Final Verification
- **Type:** verify
- **Dependencies:** [asm-01]
- **Description:** Full build, check DRC, verify SI constraints in Issues List, iterate on failures
- **Verification:** `python runner/build_lock.py <ns>.main.Design`
- **Status:** pending
```
