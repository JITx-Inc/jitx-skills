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
- **Skill:** jitx-substrate-modeler (only if custom substrate needed)
- **Description:** [FIRST check predefined substrates from jitxlib.jlcpcb — JLC04161H_1080 (4L/1080), JLC04161H_7628 (4L/7628), JLC06161H_7628 (6L/7628). These include stackup, fab rules, vias, and routing structures (RS_50, DRS_90, DRS_100). Use predefined if fab house is JLCPCB and standard FR-4 with 50/90/100 ohm impedance targets. Import directly: `from jitxlib.jlcpcb import JLC04161H_1080`. Only invoke `jitx-skills:jitx-substrate-modeler` if custom substrate is needed (non-JLCPCB, unusual layers, non-FR-4 materials, non-standard impedance).]
- **Inputs:** [reference design, spec document, or requirements section]
- **Checklist:** Substrate
- **Verification:** `python runner/build_lock.py <ns>.substrate.TestDesign` (skip if using predefined — no separate file to test)
- **Status:** pending

### [comp-01] [Component Name]
- **Type:** component
- **Skill:** jitx-component-modeler
- **Description:** Invoke `jitx-skills:jitx-component-modeler` skill. Download English datasheet from manufacturer site. [MPN, manufacturer, package, pin count, key features]. Use extract_pages.py for pinout and mechanical drawing. Capture application circuit (Step 5).
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
- **Description:** Invoke `jitx-skills:jitx-pin-assignment` skill. [which provides to declare, what flexibility is needed]
- **Inputs:** [component model from comp-01, ARCHITECTURE.md interface map]
- **Checklist:** General Gotcha Scrub
- **Verification:** `python runner/build_lock.py <ns>.circuits.<wrapper>.TestDesign`
- **Status:** pending

### [cst-01] [Protocol] Constraints
- **Type:** constraint
- **Skill:** jitx-interconnect-constraints
- **Dependencies:** [sub-01]
- **Description:** Invoke `jitx-skills:jitx-interconnect-constraints` skill. Define constraint classes for [protocol]. Use `ConstrainDiffPair` for differential pairs (USB, Ethernet, etc.) with the routing structure from the substrate. These constraints are applied at top-level assembly (Phase 3), but the constraint definitions must exist first.
- **Inputs:** [protocol spec, substrate routing structures from sub-01]
- **Checklist:** Substrate + General Gotcha Scrub
- **Verification:** `python runner/build_lock.py <ns>.constraints.<name>.TestDesign`
- **Status:** pending

### [cir-01] [Circuit Name]
- **Type:** circuit
- **Skill:** jitx-circuit-builder
- **Dependencies:** [comp-01, comp-02, cst-01]
- **Description:** Invoke `jitx-skills:jitx-circuit-builder` skill. Also invoke `jitx-skills:jitx-component-modeler` Step 5 to capture each IC's application circuit from the datasheet BEFORE writing code. [what it connects, passives needed, topology vs net, constraints to apply]. Expose bundle-typed ports (I2S, I2C, SPI, USB2, GPIO, Power) for upstream require(). Do NOT put I2C pull-ups or shared-bus termination here — those go at top level.
- **Inputs:** [datasheet PDF for every IC in this circuit — download English version from manufacturer site, use extract_pages.py, read the application circuit]
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
- **Description:** Invoke `jitx-skills:jitx-circuit-builder` skill. Also invoke `jitx-skills:jitx-interconnect-constraints` skill for applying SI constraints. Instantiate all subcircuits, connect power/ground nets (GroundSymbol, PowerSymbol), wire interfaces via require(), add I2C pull-ups and shared-bus termination at this level, apply ALL SI constraints from cst-* tasks within ReferencePlanes(GND) context, define board geometry
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
