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

## Power Circuit

### Electrical Correctness
- [ ] Input voltage range of regulator covers the actual source voltage (with tolerance)
- [ ] Output voltage matches the load requirement
- [ ] Output current rating sufficient with margin (>20% headroom recommended)
- [ ] Efficiency acceptable at expected load (check datasheet curves)
- [ ] Output noise/ripple within load IC requirements (especially for analog, RF, PLL supplies)
- [ ] Transient load response adequate for the load profile (check datasheet load transient plots)

### Enable Pin — CRITICAL (commonly missed)
- [ ] Enable pin is NOT left floating
- [ ] If always-on: tied to input voltage through resistor or direct (check datasheet for max voltage)
- [ ] If controlled: connected to control signal at correct logic level
- [ ] If open-drain/open-collector: has pull-up to appropriate rail
- [ ] UVLO threshold appropriate for input source (EN pin voltage divider if needed)

### Feedback Network
- [ ] Fixed output: verify FB/VOUT pin wiring matches datasheet (some go to output, some to a divider)
- [ ] Adjustable output: voltage divider from output to FB pin to GND
- [ ] Voltage divider MUST use `voltage_divider_from_constraints()` — NEVER manual resistor values
- [ ] Reference voltage (Vref) matches datasheet exactly (0.6V, 0.8V, 1.0V, etc.)
- [ ] `v_out` uses `Toleranced.percent()` not `Toleranced.exact()`

### Soft-Start and Sequencing
- [ ] Soft-start capacitor included if pin is available (prevents inrush)
- [ ] Power sequencing requirements documented if multiple rails
- [ ] Sequencing order correct: core supplies before IO supplies, analog before digital where required
- [ ] Sequencing implementation identified: PGOOD chaining, enable sequencing, or dedicated sequencer IC

### Switching Regulator Specifics (skip for LDOs)
- [ ] Inductor selected: saturation current > peak current, DCR acceptable for efficiency, core material appropriate for frequency
- [ ] Bootstrap capacitor present if required (buck converters with high-side FET)
- [ ] Compensation network matches datasheet recommendation (Type II/III, values from datasheet or calculator)
- [ ] Input capacitance meets datasheet minimum (low-ESR ceramic + bulk), voltage rating exceeds max input
- [ ] Output capacitance meets datasheet minimum for stability AND transient response
- [ ] Boost capacitor present if required (e.g., charge pump pin on some converters)
- [ ] Frequency-setting resistor correct if oscillator frequency is configurable
- [ ] Current sense resistor value correct (if external current sensing)
- [ ] Layout-sensitive components identified (input cap, bootstrap cap, inductor — must be close to IC)

### Output Stage
- [ ] Output capacitance meets datasheet minimum
- [ ] Output capacitor ESR within stability range (check datasheet — some LDOs require minimum ESR)
- [ ] Output decoupling: at minimum 100nF ceramic + bulk cap per datasheet

### Input Stage
- [ ] Input decoupling per datasheet recommendations (value, type, ESR)
- [ ] Input capacitor voltage rating exceeds maximum input voltage

### Power-Good and Fault — CRITICAL (commonly missed)
- [ ] PGOOD pin type identified: open-drain or push-pull (check datasheet)
- [ ] If open-drain: pull-up resistor to appropriate voltage rail (1k-100k typical)
- [ ] If push-pull: direct connection, no pull-up needed
- [ ] PGOOD connected to monitoring input or indicator LED
- [ ] Fault pins (OVP, OCP, THERMAL_SHUTDOWN) handled if present

### Thermal
- [ ] Thermal/exposed pad connected to ground copper (not left floating)
- [ ] Power dissipation within component ratings for expected ambient temperature

---

## Interface Circuit

### Port Design
- [ ] Circuit exposes **bundle-typed ports** (I2S, I2C, SPI, USB2, GPIO, DiffPair, Power) — not individual signal ports
- [ ] If wrapping a component with individual pins, bundle wiring happens inside the circuit
- [ ] Bundle port types match what the MCU/FPGA wrapper provides via require()

### Signal Integrity
- [ ] Termination scheme matches the protocol standard:
      - Series termination at source for point-to-point
      - Parallel termination at receiver for transmission lines
      - AC coupling caps for DC-blocking (check value for frequency range)
- [ ] Impedance targets documented for constrained signals
- [ ] Routing structure assigned matches impedance target
- [ ] Topologies created with `>>` inside the circuit for constrained signal paths
- [ ] **SI constraints (Constrain, ConstrainDiffPair, ReferencePlanes) are NOT applied here** — they go at the top-level design where the full path is visible. The circuit only creates the topology segments.

### Level Translation
- [ ] Voltage domains of connected ICs compared — level shifter needed if they differ
- [ ] Level shifter direction correct (unidirectional vs bidirectional)
- [ ] Level shifter OE pin handled (not floating)
- [ ] Open-collector/open-drain outputs: pull-up voltage compatible with the receiving IC's input voltage range (e.g., a 5V-tolerant OC output pulled up to 5V must not drive a 3.3V-only input)

### Control Signal Handling
- [ ] I2C lines: open-drain with pull-ups to VDDIO (value per bus speed: 4.7k for 100kHz, 2.2k for 400kHz)
- [ ] SPI chip select: pull-up to deselect when inactive
- [ ] UART: TX-to-RX crossover verified (not TX-to-TX)
- [ ] Reset pins: RC filter for noise immunity, ESD protection if board edge
- [ ] Interrupt pins: pull-up or pull-down matching active polarity

### Unused Pin Handling
- [ ] Unused inputs on active devices terminated (not floating) — tie to VCC or GND per datasheet
- [ ] Unused outputs left unconnected or noted as NC
- [ ] Unused op-amp sections: non-inverting input to mid-rail, output left open

### Decoupling — CRITICAL (commonly missed)
- [ ] 100nF bypass cap on EVERY power pin of EVERY active IC in the circuit
- [ ] Bulk capacitor (10uF) per power domain
- [ ] **Every power-rail cap `.insert(...)` uses `short_trace=True`** — decoupling, bypass, bulk, output filter. Exceptions (AC coupling, RC time constants, RF, crystal load) are dispositioned in the task acceptance block. Gated at Phase 2 → 3.
- [ ] Ferrite bead or filter on analog supply pins if mixed-signal

### Protocol-Specific Checks
Apply the relevant protocol check:

**USB**: differential impedance 90 ohm, AC coupling caps if required by standard, VBUS decoupling, ESD on connector pins, ID pin handling (OTG)

**Ethernet (RGMII/SGMII)**: TX/RX clock routing, 50 ohm / 100 ohm impedance, magnetics/transformer, MDI termination

**DDR (DDR3/DDR4/DDR5)**: per-byte-lane DQ-to-DQS matching, CK differential, command/address timing, ODT values, VREF decoupling, ZQ calibration resistor

**LPDDR (LPDDR4/LPDDR5)**: differential read/write strobes per byte lane (different signaling than standard DDR), per-lane DQ-to-DQS matching, CK differential, CA bus timing, VREF decoupling, termination values differ from DDR — consult the specific LPDDR spec

**PCIe**: AC coupling on TX (required by spec for different ground references between endpoints — but verify for your specific link configuration), 100 ohm differential, REFCLK distribution to all endpoints on same clock domain, PERST# handling, WAKE# pull-up

**SPI**: clock polarity (CPOL) and phase (CPHA) mode verified, chip select unique per device

---

## External Connector / Hot-Plug Interface

Apply for any connector or interface that exposes the board to the outside world: USB (any flavor), Ethernet, audio jacks, power input (barrel, terminal, USB-PD, PoE), debug headers if user-accessible, expansion connectors, antenna connectors (U.FL, SMA, board-edge contacts). PCB antenna geometry itself belongs to the substrate / RF net-class rules — not this checklist.

### Per-Connector Decision

- [ ] **Connector orientation / pin mirroring**: USB-C is symmetric (CC1/CC2 mirror); standard USB-A/B is not. Verify pin map matches the chosen orientation.
- [ ] **Shield / chassis strategy**: connected to chassis ground via short trace, ferrite bead, capacitor, or hard-tied — picked deliberately, not by default.
- [ ] **Current rating**: connector ampacity exceeds the worst-case load with margin.
- [ ] **Polarity / hot-plug protection**: reverse-voltage, surge, inrush handled per the source class (USB-PD differs from barrel jack differs from PoE).
- [ ] **Mechanical retention**: through-hole tabs, screw mount, locking mechanism, or none — matched to expected use.

### ESD-or-Justification

For every external or user-accessible signal pin, the row must say one of:

- **TVS / ESD diode** specified, with capacitance compatible with the signaling speed (low-cap TVS for high-speed; standard for low-speed).
- **Internal-only**: connector is not user-accessible (board-to-board internal link, sealed enclosure, controlled environment).
- **Omitted by design**: explicit reason (e.g., RF impedance budget, cost-constrained prototype, EMC-controlled fixture). User confirms.

### Protocol-Specific Sub-Checklists (load only when applicable)

These are examples, not required coverage. Pick the ones that apply to the design.

**USB-C / USB-PD**: CC1/CC2 pull-down or PD configuration resistors per the role (sink/source/DRP); CC capacitance limits; VBUS protection rated for negotiated voltages (5V/9V/15V/20V); D+/D- ESD low-cap; configuration-trap pins per the controller datasheet.

**Ethernet (RJ45)**: magnetics/transformer or LAN module; MDI/MDIX termination; Bob Smith terminations; shield bond strategy; chassis-to-circuit-ground bond per EMC plan.

**Audio (3.5mm TRS / TRRS)**: switching contacts on TRS detect insertion; AC coupling on signal lines (or DC-coupled with explicit reason); ESD on tip/ring; ground-loop strategy for line-out.

**Antenna connector / feed (U.FL, SMA, board-edge contact)**: 50Ω routing structure to the connector; return-plane keepout under the feed (see Net Class Taxonomy → RF below); connector type matched to frequency and connector-mate strategy.

**Debug headers (if user-accessible)**: ESD on signals; protection if user can short pins; pin keying or marking to prevent reverse insertion. (Internal-only debug headers in sealed enclosures may justify omitting ESD — note explicitly.)

---

## Net Class Taxonomy (Per-Design Table)

Some nets need non-default physical rules — width, clearance, impedance, keepout, return path, shield. The class catalog isn't fixed; each design enumerates the net classes that apply. Generate this table during Phase 3 and apply rules via `design_constraint(<NetClassTag>(), priority=N).<rule>(...)`.

**Generate one row per applicable class. Skip rows that don't apply. If no nets in this design need non-default rules, record "no non-default net classes" with one-line rationale.**

| Net class | Why it matters | Width / clearance / keepout / impedance / return path | JITX expression |
|-----------|---------------|-------------------------------------------------------|-----------------|
| Switch node (buck/boost) | Hot loop EMI, dV/dt | Width sized for current; tight loop area; pour pulled back from node | `design_constraint(SwTag(), ...).clearance(...)` |
| RF / antenna feed | Impedance, return current, EMI | 50Ω routing structure; return-plane keepout under antenna | Routing structure + `design_constraint(RFTag(), ...)` |
| High-speed differential (USB, Ethernet, PCIe, etc.) | Impedance, skew, EMI | 90/100Ω diff; via stitching; reference-plane continuity | SI constraint + routing structure |
| DDR / LPDDR | Per-byte-lane timing | Per-class width/clearance; length matching | Diff and length-matching constraints |
| Sensitive analog | Coupling, ground loops | Guard rings, shield, separate return | Net class with clearance |
| High-voltage / mains | Creepage, isolation | Class-dependent clearance, no-pour zones | Clearance constraint, layer assignment |
| High-current | I²R, thermal, EMI | Wide trace or pour, multiple vias | Width and via-count constraint |
| Gate drive | dV/dt, ringing | Tight return loop, gate resistor placement | Net class + placement constraint |
| Kelvin sense | Accuracy | Separate trace from current path | Routing rule |
| Isolated domain | Galvanic isolation | Creepage / clearance / barrier | No-pour zone, clearance |

The list is not exhaustive — add new classes as a design demands them (e.g., low-leakage thermocouple inputs, guard rings, motor phase windings).

The Phase 3 → 3b transition confirms the table exists if the design has any non-default net classes; if not, it confirms the explicit "no non-default net classes" statement.

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
