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

## Data Sources (approved by user)

| Component | MPN | Package | Datasheet Source | Footprint Method |
|-----------|-----|---------|-----------------|------------------|
| MCU | STM32H753 | QFP-100 | User-provided PDF | JITX QFP generator |
| USB-C connector | TYPE-C-31-M-12 | Non-std | Manufacturer site | User-provided .kicad_mod |
| LDO | LM1117 | SOT-223 | ti.com download | JITX SOT generator |
| Buck converter | TPS62933 | SOT-23-6 | User-provided PDF | JITX SOT23_6 generator |

---

## Phase 1: Substrate + Components

### [sub-01] Substrate
- **Type:** substrate
- **Skill:** jitx-substrate-modeler (only if custom substrate needed)
- **Description:** [If user confirmed JLCPCB as fab house, predefined substrates from jitxlib.jlcpcb are available — JLC04161H_1080 (4L/1080), JLC04161H_7628 (4L/7628), JLC06161H_7628 (6L/7628) — with stackup, fab rules, vias, and routing structures (RS_50, DRS_90, DRS_100). Import directly: `from jitxlib.jlcpcb import JLC04161H_1080`. Otherwise (default), invoke `jitx-substrate-modeler` to create a custom substrate for the target fab house. Consider whether component packages (e.g., high-pin-count BGAs) require more layers than a simple 4-layer stackup.]
- **Inputs:** [reference design, spec document, or requirements section]
- **Checklist:** Substrate
- **Verification:** `jitx build <ns>.substrate.TestDesign` (skip if using predefined — no separate file to test)
- **Status:** pending

### [comp-01] [Component Name]
- **Type:** component
- **Skill:** jitx-component-modeler
- **Data source:** [from approved data source table — e.g., "User-provided datasheet + JITX QFP generator"]
- **Description:** Invoke `jitx-component-modeler` skill. [MPN, manufacturer, package, pin count, key features]. Use extract_pages.py for pinout and mechanical drawing. Capture application circuit (Step 5).
- **Inputs:** [datasheet path, footprint path if applicable]
- **Checklist:** Component + [MCU/FPGA if applicable]
- **Verification:** `jitx build <ns>.components.<name>.TestDesign`
- **Status:** pending

### [comp-02] [Component Name]
- **Type:** component
- **Skill:** jitx-component-modeler
- **Data source:** [from approved data source table]
- **Description:** [MPN, manufacturer, package, pin count, key features]
- **Inputs:** [datasheet path, footprint path if applicable]
- **Checklist:** Component
- **Verification:** `jitx build <ns>.components.<name>.TestDesign`
- **Status:** pending

---

## Phase 2: Constraints + Circuits + Pin Assignment

### [pin-01] [IC Name] Pin Assignment
- **Type:** pin-assignment
- **Skill:** jitx-pin-assignment
- **Dependencies:** [comp-01]
- **Description:** Invoke `jitx-pin-assignment` skill. [which provides to declare, what flexibility is needed]
- **Inputs:** [component model from comp-01, ARCHITECTURE.md interface map]
- **Checklist:** General Gotcha Scrub
- **Verification:** `jitx build <ns>.circuits.<wrapper>.TestDesign`
- **Status:** pending

### [cst-01] [Protocol] Constraints
- **Type:** constraint
- **Skill:** jitx-interconnect-constraints
- **Dependencies:** [sub-01]
- **Description:** Invoke `jitx-interconnect-constraints` skill. Define constraint classes for [protocol]. Use `ConstrainDiffPair` for differential pairs (USB, Ethernet, etc.) with the routing structure from the substrate. These constraints are applied at top-level assembly (Phase 3), but the constraint definitions must exist first.
- **Inputs:** [protocol spec, substrate routing structures from sub-01]
- **Checklist:** Substrate + General Gotcha Scrub
- **Verification:** `jitx build <ns>.constraints.<name>.TestDesign`
- **Status:** pending

### [cir-01] [Circuit Name]
- **Type:** circuit
- **Skill:** jitx-circuit-builder
- **Dependencies:** [comp-01, comp-02, cst-01]
- **Description:** Invoke `jitx-circuit-builder` skill. Also invoke `jitx-component-modeler` Step 5 to capture each IC's application circuit from the datasheet BEFORE writing code. [what it connects, passives needed, topology vs net, constraints to apply]. Expose bundle-typed ports (I2S, I2C, SPI, USB2, GPIO, Power) for upstream require(). Do NOT put I2C pull-ups or shared-bus termination here unless this circuit is the bus-aggregation level (encloses both master and slaves on a private bus). Pull-ups belong wherever the bus is composed across participants — usually the top-level design.
- **Inputs:** [datasheet PDF for every IC in this circuit — download English version from manufacturer site, use extract_pages.py, read the application circuit]
- **Checklist:** [Power Circuit / Interface Circuit] + Datasheet Compliance + General Gotcha Scrub
- **Engineering questions** (orchestrator writes these per-circuit):
  - [What voltage domains exist? Where do pull-ups go?]
  - [Are there external transistors in the datasheet app circuit?]
  - [Which pins are dual-function? How are they configured?]
  - [What happens during power sequencing / startup?]
- **Architectural questions** (required for *parametric / generator* tasks only — BGA ballout, deskew geometry, antipad fence, N-lane fanout, per-layer table, repeating-block scene graph. Skip for one-off circuits.):
  - [How are N parallel things structured? `list[T]` / `dict[StructuralKey, T]` / typed dataclass — *not* sibling attributes plus `getattr(self, f"X_{i}")`.]
  - [Where does substrate-shaped data live? On the substrate, queried by the design — *not* duplicated as a design-level constant table.]
  - [Are intermediate "spec" records needed, or can JITX objects be constructed directly? Default: direct construction. If a `@dataclass(frozen=True)` is needed, name its fields explicitly — *not* `dict[str, Any]`.]
  - [Does any iteration use `getattr(self, f"...")`? It must not — see `jitx/SKILL.md` Don'ts and `references/architectural-patterns.md`.]
- **Verification:** `jitx build <ns>.circuits.<name>.TestDesign`
- **Status:** pending

---

## Phase 3: Top-Level Assembly

### [asm-01] Top-Level Design
- **Type:** assembly
- **Skill:** jitx-circuit-builder
- **Dependencies:** [all Phase 2 task IDs]
- **Description:** Invoke `jitx-circuit-builder` skill. Also invoke `jitx-interconnect-constraints` skill for applying SI constraints. Instantiate all subcircuits, connect power/ground nets (GroundSymbol, PowerSymbol), tag power and ground nets with `PowerTag` / `GroundTag` for wider-trace rules, wire interfaces via require(), add I2C pull-ups and shared-bus termination at this level, apply ALL SI constraints from cst-* tasks within `ReferencePlanes(...)` context, define board geometry. **Set `capacitor_defaults` and `resistor_defaults` on the Design class** to match the design's manufacturing path and circuit role; per-circuit refinements documented for any specialty parts. **Set `self.rules` on the Design class** with the four default design constraints — `IsTrace` trace width, `IsCopper`/`IsCopper` clearance, `IsPad` thermal relief, and tagged power/ground wider traces — values calibrated to the substrate fab class. See `references/project-builder-flow.md` Phase 3 → "Passive query defaults" and "Default design rules".
- **Checklist:** General Gotcha Scrub
- **Verification:** `jitx build <ns>.main.Design`
- **Status:** pending

---

## Phase 4: Build + Verify + Iterate

### [ver-01] Final Verification
- **Type:** verify
- **Dependencies:** [asm-01]
- **Description:** Full build, check DRC, verify SI constraints in Issues List, iterate on failures
- **Verification:** `jitx build <ns>.main.Design`
- **Status:** pending
```
