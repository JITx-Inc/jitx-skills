# Project Builder Orchestration Flow

Five-phase workflow for building complete JITX hardware designs from requirements. The orchestrator drives the flow, spawns parallel sub-agents, and enforces exit gates with acceptance reviews.

**This file applies to the complete-board tier only.** Tier classification happens before Phase 0 — see `jitx/SKILL.md` "First: Pick the Workflow Tier" and `references/completion-blocks.md`. Single-task tier does not enter the formal phase chain. If a single-task grows beyond a single artifact mid-work, upgrade to complete-board and apply Phase 0 retroactively (write PLAN.md + ARCHITECTURE.md, run the data audit) before continuing.

Every task in every phase emits a **task acceptance block** (template in `references/completion-blocks.md`) and the orchestrator appends the acceptance verdict to it. A task without an accepted block does not count toward an exit gate.

## Overview

```
Phase 0: Requirements + Architecture
    │  Create PLAN.md + ARCHITECTURE.md
    ▼
Phase 1: Substrate + Components ──── parallel sub-agents
    │  Acceptance review each task
    ▼
Phase 2: Constraints + Circuits + Pins ──── clustered parallel
    │  Acceptance review each task
    ▼
Phase 3: Top-Level Assembly ──── single agent
    │  Acceptance review
    ▼
Phase 3b: Design Review and Loopback ──── read-only audit + fix loopback
    │  Audit block: CRITICAL / WARNING / NOTE; fixes re-audited
    ▼
Phase 4: Build + Verify + Iterate
    Phase 4 verification block: JITX UI / Issues / DRC / SI
```

## Task Status Flow

```
pending → in-progress → review → accepted
                          │
                          ├→ rework → review → accepted (max 2 cycles)
                          │
                          └→ rejected (replan or escalate to user)
```

- `pending`: not started
- `in-progress`: sub-agent working
- `review`: sub-agent returned task acceptance block, awaiting orchestrator review
- `accepted`: orchestrator verified, ready for downstream tasks
- `rework`: orchestrator found issues, sent back with specific feedback
- `rejected`: fundamental problem, task needs replanning

---

## Phase 0: Requirements + Architecture

**Who**: orchestrator (no sub-agents)

### Process

1. **Analyze requirements**: parse the user's request, spec documents, or reference designs into structured form.

2. **Identify all components**: propose ideal parts based on electrical requirements and engineering tradeoffs (voltage/current, thermal, peripheral set, package, reliability). Note the part number, package, and datasheet for each.

3. **Map interfaces**: document which components connect to which, via what protocol, and whether SI constraints are needed.

4. **Plan the power tree**: trace power from input through regulators to every load. Note voltage, current, and sequencing requirements.

5. **Assess substrate needs**: based on interface speeds, routing density, and component package complexity (e.g., high-pin-count BGAs require more layers), determine layer count, material class, and via technology. **Ask the user which fab house they are targeting.** If they confirm JLCPCB and need standard 4-layer or 6-layer FR-4 with 50/90/100 ohm impedance, predefined substrates from `jitxlib.jlcpcb` (JLC04161H_1080, JLC04161H_7628, JLC06161H_7628) are available — no substrate modeling task needed. Otherwise, create a custom substrate (the default path).

6. **Data source audit**: for every component, identify where its data will come from. Present a table to the user for approval **before proceeding**. See the Data Source Audit section below.

7. **Decompose into tasks**: follow `references/decomposition-guide.md` to create the task graph.

8. **Write PLAN.md**: use `references/plan-template.md` as the starting point. Fill in every task with specific details. Include the approved data sources.

9. **Write ARCHITECTURE.md**: use `references/architecture-template.md` as the starting point. Include module hierarchy, power tree (with noise/ripple requirements and sequencing), interface map (with clock distribution), voltage domains, and mechanical constraints. This gives sub-agents the big picture.

### Data Source Audit

Before decomposing into tasks, present the user with a data source plan for each component. This ensures the user controls where data comes from and can provide their own files.

**Present this table and wait for approval:**

```
## Data Source Plan

| Component | Package | Data Source | Footprint Method | Status |
|-----------|---------|-------------|------------------|--------|
| MCU (STM32H753) | QFP-100 | User datasheet (provided) | JITX QFP generator | Ready |
| USB-C connector | Non-std | Need footprint | User to provide .kicad_mod, or LCSC lookup | Needs input |
| LDO (LM1117) | SOT-223 | Datasheet from manufacturer | JITX SOT generator | Will fetch |
| Buck (TPS62933) | SOT-23-6 | User datasheet (provided) | JITX SOT23_6 generator | Ready |
| WiFi module | Non-std | Need footprint + datasheet | User to provide, or LCSC lookup | Needs input |

**Data sources:**
- "User datasheet (provided)" — user has already supplied the PDF
- "Datasheet from manufacturer" — will download from manufacturer site (ti.com, st.com, etc.)
- "JITX [generator] generator" — standard package, dimensions from datasheet
- "User to provide .kicad_mod" — non-standard package, user has KiCad footprint
- "LCSC lookup" — non-standard package, user named LCSC/JLCPCB as the channel; *lookup/evidence* via parts2jitx is implied. *Footprint data ingestion* (EasyEDA `.kicad_mod` as landpattern source) is a separate opt-in.

Please confirm data sources or provide alternatives (datasheets, footprints, specs).
**Note:** *Lookup/evidence* via parts2jitx is implied when LCSC/JLCPCB is the named channel. *Footprint data ingestion* (using EasyEDA-sourced `.kicad_mod` as the landpattern) requires explicit per-project approval — some users (especially commercial) may not want EasyEDA-sourced data in their project. See `references/parts-sourcing.md` "LCSC / JLCPCB via parts2jitx".
```

**Channel evidence is required.** If the user has named a sourcing channel (LCSC/JLCPCB, Digi-Key/Mouser, internal PLM), the audit table must include channel-specific evidence for every named IC and connector before code is written. For LCSC/JLCPCB, that means `parts2jitx-lcsc <C-number>` output (stock, lifecycle, datasheet URL) plus `parts2jitx-lcsc <C-number> --pinout` saved to the project. The orchestrator may `pip install parts2jitx` automatically when LCSC/JLCPCB is the named channel. See `references/parts-sourcing.md` "Required-Sourcing Rule" for the full ladder including non-LCSC channels.

**Rules:**
- Always prefer user-provided data over automated lookups
- Standard packages (QFN, SOIC, SON, SOT, QFP, BGA) use JITX generators — no footprint download needed
- For non-standard packages, ask the user if they have a `.kicad_mod` before suggesting LCSC
- LCSC/JLCPCB *lookup/evidence* (parts2jitx CLI) is implied when the user named that channel. LCSC/EasyEDA *footprint data ingestion* (using `.kicad_mod` as the landpattern source) requires explicit per-project approval — do not assume it is acceptable. Ask.
- Do NOT proceed past the data audit until the user approves the data source plan

### Exit Gate: Phase 0 → Phase 1

- [ ] PLAN.md exists with all tasks defined
- [ ] ARCHITECTURE.md exists with power tree and interface map
- [ ] Data source audit completed and user approved
- [ ] All datasheets and reference materials identified and accessible (or user committed to providing them)
- [ ] Dependencies are acyclic
- [ ] No ambiguous requirements remain (ask user if unclear)
- [ ] User has reviewed and approved the plan

**Emit the `Gate: Phase 0 → Phase 1` block** from `references/completion-blocks.md` before advancing.

---

## Phase 1: Substrate + Components

**Who**: parallel sub-agents (one per task)

### Orchestrator Actions

1. For each Phase 1 task in PLAN.md:
   a. Update status to `in-progress`
   b. Spawn a sub-agent with the task definition, relevant datasheets, and instruction to follow `references/task-execution.md`
2. As sub-agents return, perform acceptance review (Part B of task-execution.md).
3. Issue verdicts: accept, rework, or reject.

### Parallel Safety

Phase 1 tasks are independent at the *design* level — each sub-agent writes its own component file with its own test design. Parallel sub-agents each build their own test design; because each agent's design is distinct (different module paths, different component class names), concurrent builds against the same project are acceptable — the JITX backend serializes internally on the WebSocket. What is NOT safe is two agents building the same design at the same time; the orchestrator should never spawn two tasks targeting the same test design class. See `jitx/SKILL.md` "Build Safety".

### Exit Gate: Phase 1 → Phase 2

ALL of the following must be true:
- [ ] Every Phase 1 task has status `accepted`
- [ ] Every component builds with `status: ok` in its test harness
- [ ] Substrate builds with all routing structures and via definitions
- [ ] Orchestrator has spot-checked high-risk items per task type (see task-execution.md Part B)
- [ ] `Interface notes` fields in task acceptance blocks are consistent (port names, power requirements match ARCHITECTURE.md)

**Emit the `Gate: Phase 1 → Phase 2` block** from `references/completion-blocks.md` before advancing.

---

## Phase 2: Constraints + Circuits + Pin Assignment

**Who**: clustered parallel sub-agents

### Task Ordering

Phase 2 tasks have partial dependencies. Group into clusters:

- **Cluster A: Pin assignment wrappers** — depend on components from Phase 1. These define the provide/require flexibility for the central IC(s). Other Phase 2 tasks may depend on these.
- **Cluster B: Power circuits** — depend on power components. Often independent of other clusters.
- **Cluster C: Interface circuits + constraints** — depend on components, substrate routing structures, and possibly pin assignment wrappers.

Run independent clusters in parallel. Within a cluster, respect dependencies.

### Orchestrator Actions

1. Identify which Phase 2 tasks can run immediately (dependencies all `accepted`).
2. Spawn those sub-agents.
3. As tasks complete and are accepted, check if new tasks are unblocked.
4. Continue until all Phase 2 tasks are accepted.

### Topology-friendly bundle wiring

Subcircuits that expose bundles (I2C, ULPI, USB2, etc.) for any signal that will receive an SI constraint at top level **must** wire the bundle sub-ports with `>>`, not `+`. The constraint solver only walks `>>` chains; ports reached only via `+` are invisible to it. This is a common silent failure — the netlist is correct, the build passes, but the JITX UI reports "No path for signal constraint" once constraints are applied. See the Phase 3 "Topology vs net membership" section for the failure modes and patterns.

### Exit Gate: Phase 2 → Phase 3

- [ ] Every Phase 2 task has status `accepted`
- [ ] All circuits build individually with `status: ok`
- [ ] Constraint classes instantiate without error
- [ ] Provide/require interfaces are consistent across wrapper and consuming circuits
- [ ] **Interface circuits expose bundle-typed ports** (I2S, I2C, SPI, USB2, GPIO, Power) — not individual signal ports. If a circuit wraps individual-pin components, the bundle wiring happens inside the circuit.
- [ ] **For any signal that will receive an SI constraint at top level, the subcircuit's bundle wiring uses `>>` (not `+`)** between component pins and bundle sub-ports — see Phase 3 "Topology vs net membership"
- [ ] **No anonymous `Resistor` / `Capacitor` / `Inductor` `.insert(...)` calls and no bare `+` / `>>` expressions** in the subcircuit — every structural object stored on `self` (see Phase 3 "Silent-drop patterns"). Enforced via `bash scripts/grep_gates.sh <ns>/` — hard-fail hits block this gate.
- [ ] **Every power-rail capacitor `.insert(...)` call uses `short_trace=True`** — decoupling, bypass, bulk, output filter. Non-power-rail caps (AC coupling, RC time constants, RF matching, compensation, crystal load) and non-cap inserts (resistors, inductors) are dispositioned in the task acceptance block as exceptions or N/A. See `jitx-circuit-builder/SKILL.md` "short_trace=True is the default for power-rail capacitors". The grep gate `bash scripts/grep_gates.sh <ns>/` flags every `.insert(...)` missing `short_trace=` as review-required.
- [ ] Port names and bundle types match between providers and consumers
- [ ] Power circuit outputs match the voltage/current needs documented in ARCHITECTURE.md

**Emit the `Gate: Phase 2 → Phase 3` block** from `references/completion-blocks.md` before advancing.

---

## Phase 3: Top-Level Assembly

**Who**: single agent (not parallelizable)

### Process

The orchestrator (or a single sub-agent) assembles the top-level design.

**CRITICAL**: Net symbols (`GroundSymbol`, `PowerSymbol`) and SI constraints (`Constrain`, `ConstrainDiffPair`, `ReferencePlanes`) MUST be applied at the top-level design — not inside subcircuits. Subcircuits create topologies with `>>` but constraints are applied here where the full signal path is visible.

1. Create the top-level Circuit class.
2. Instantiate all subcircuits from Phase 2.
3. Create global ground net with `GroundSymbol`, connect all ground ports, add pours on ground layers.
4. Create power nets with `PowerSymbol`, connect regulator outputs to load inputs.
5. Wire signal interfaces using `require()` from provides. Example:
   ```python
   i2s = self.mcu_wrapper.require(I2S)   # solver picks pins
   self += i2s.sck + self.amp.i2s.sck    # wire bundle sub-ports
   self += i2s.ws + self.amp.i2s.ws
   self += i2s.sd + self.amp.i2s.sd
   ```
   NEVER hardcode GPIO numbers. If a downstream circuit has individual ports instead of a bundle, wire the required bundle's sub-ports to them. Use `>>` topology for SI-constrained signals.
6. Add shared-bus components at the **bus-aggregation level** — the level where the bus is composed across multiple participants (master + slaves). Most of the time that's the top-level design here, because typical buses span subcircuits (MCU subcircuit talks to amp + sensor subcircuits). But if a single subcircuit aggregates an entire bus internally (e.g. a sensor-hub subcircuit containing master + 4 sensors all on one private I2C), the pull-ups belong inside that subcircuit. The rule is bus scope, not file location.
   - **I2C pull-ups** — one set per bus, placed at the level that composes the bus, to the correct voltage rail (usually 3.3V)
   - **SPI pull-ups** on CS lines — same rule
   - **CAN termination** resistors — same rule
   - Any termination that spans multiple subcircuits goes at the top-level design that aggregates them
7. Apply ALL SI constraints at this level within `ReferencePlanes(GND)` context. Example:
   ```python
   with ReferencePlanes(self.GND):
       usb_topo = Topology(self.mcu.usb.data.p, self.usb_conn.DP)
       self.cst_usb = ConstrainDiffPair(usb_topo) \
           .structure(substrate.DRS_90) \
           .timing_difference(0.1e-12)
   ```
   Every protocol with impedance or timing requirements needs constraints here. **Read "Topology vs net membership" below before designing the chains.**
8. Define board shape, mounting holes, and any keepout zones.
9. **Set passive query defaults on the Design class** to match the design's manufacturing path and circuit role (see "Passive query defaults" below). Without explicit defaults, the unfiltered `jitxlib.parts` search may return parts unsuitable for the design (e.g. through-hole leaded electrolytics ahead of SMD ceramics on an SMT design).
10. **Set default design rules on the Design class** — trace width, copper clearance, thermal relief, and wider traces for tagged power/ground rails. See "Default design rules" below. These are the production-friendly defaults every board should have; without them, the router uses the substrate's `FabricationConstraints` minimums, which are usually too narrow for power.
11. Build and verify `status: ok`.

### Passive query defaults — match manufacturing and circuit role

The top-level Design class should set `capacitor_defaults` and `resistor_defaults` so auto-selected passives match the design's manufacturing path and circuit role. The right defaults depend on the design:

| Design class | Typical defaults | Why |
|--------------|------------------|-----|
| **SMT production / economy** (JLCPCB, full-machine assembly) | SMD-only, ceramic for caps, small case (0402–0805) | Through-hole picks are wrong; small case fits typical decoupling |
| **Hand-build / prototype** (hand-soldered, mixed assembly) | SMD or mixed, larger case (0603–1206) for ease, allow common through-hole on large parts | Hand-rework needs accessible sizes |
| **Specialty** (high-voltage, RF-heavy, precision analog, high-current, automotive temp) | Per-circuit refinement is the rule; design-level defaults stay broad | Circuit role dominates — bulk caps, film, RF passives, shunts, etc. need local choice |

```python
from jitxlib.parts import CapacitorQuery, ResistorQuery

class Design(...):
    substrate = ...
    board = ...

    # Example for an SMT-production design. Adjust per the design's class above.
    # Per-circuit refinement via `with CapacitorQuery.refine(...)` for bulk caps,
    # RF parts, thermal-limited regulators, etc.
    capacitor_defaults = CapacitorQuery(
        mounting="smd",
        type="ceramic",
        case=["0402", "0603", "0805"],
    )
    resistor_defaults = ResistorQuery(
        mounting="smd",
        case=["0402", "0603", "0805"],
    )

    circuit = TopCircuit()
```

**How to override.** These are *defaults* — circuit-level `Capacitor(...)` or `Resistor(...)` calls take query refinements via `CapacitorQuery.refine(...)` context managers, and explicit `query=...` arguments override the design-level defaults entirely. If a circuit needs a 22 µF tantalum bulk cap on a power rail, scope a refinement around just that capacitor:

```python
with CapacitorQuery.refine(type="tantalum", case="1210"):
    self.c_bulk = Capacitor(capacitance=22e-6, rated_voltage=10.0)
```

**The point:** every design has a default that matches its manufacturing path, plus per-circuit overrides where the role demands them. The Phase 3 exit gate confirms defaults exist and overrides are documented — not that any specific filter is set.

### Default design rules — set on Design class

Every Design should declare four canonical rules so the router and DRC have production-friendly defaults. Without them, the router uses the substrate's `FabricationConstraints` minimums, which are typically too narrow for power and don't apply thermal relief to pads.

Tag power and ground nets in the top-level Circuit so the wider-trace override can target them by tag, not by name. Tag classes live at module scope (subclassing `Tag` inside a function breaks JITX instantiation tracking).

```python
from jitx.constraints import (
    BinaryDesignConstraint,
    IsCopper,
    IsPad,
    IsTrace,
    Tag,
    UnaryDesignConstraint,
)


class PowerTag(Tag):
    """Marks power rails for wider trace rules."""


class GroundTag(Tag):
    """Marks ground nets for wider trace rules."""


class TopCircuit(Circuit):
    def __init__(self):
        self.GND = Net(name="GND", symbol=GroundSymbol())
        self.VBUS = Net(name="VBUS", symbol=PowerSymbol())
        self.V3V3 = Net(name="V3V3", symbol=PowerSymbol())

        # Tag the rails so the design rule below can match them.
        GroundTag().assign(self.GND)
        PowerTag().assign(self.VBUS)
        PowerTag().assign(self.V3V3)
        # ...


class Design(...):
    substrate = ...
    board = ...
    # passive defaults above
    circuit = TopCircuit()

    def __init__(self):
        self.rules = [
            # Default trace width for any trace not otherwise tagged.
            UnaryDesignConstraint(IsTrace).trace_width(0.125),
            # Default copper-to-copper clearance (applies to traces, pours, pads).
            BinaryDesignConstraint(IsCopper, IsCopper).clearance(0.125),
            # Thermal relief on through-hole and SMD pads — gap, spoke width, spoke count.
            UnaryDesignConstraint(IsPad).thermal_relief(0.125, 0.2, 4),
            # Power and ground rails get wider traces. priority=1 wins over IsTrace above.
            UnaryDesignConstraint(
                PowerTag() | GroundTag(), priority=1
            ).trace_width(0.4),
        ]
```

**How the rules compose.** Rules are predicate → action. The router applies the highest-priority matching rule for each net/segment; ties go to the more specific predicate. `priority=1` on the tagged power/ground rule overrides the `IsTrace` default (priority 0) when the trace belongs to a power or ground net. Adding a class-of-net rule for switch nodes, RF, sensitive analog, etc. is the same shape — declare a Tag, assign it to the relevant nets, add a constraint with higher priority.

**`IsTrace`, `IsCopper`, `IsPad`** are built-in predicates that match every trace / every copper / every pad in the design. Combined with `priority=0` defaults they give you board-wide defaults without tagging every net by hand.

**Tag-class scope rule:** Tag subclasses MUST be declared at module scope — never inside a function or method. JITX tracks structural classes by name and breaks when classes are synthesized at runtime. See `jitx/SKILL.md` "JITX Python Code Conventions".

**Calibrate to fab capability.** The 0.125 mm trace width / clearance and 0.4 mm power width above are typical JLC04161H-class defaults — adjust for the actual substrate's `FabricationConstraints` minimums. Heavier copper (2 oz, 3 oz) allows narrower traces at the same current; tighter fab classes allow narrower clearance.

**Non-default net classes (RF, switch node, sensitive analog, HV) get higher-priority rules.** See `references/net-classes.md` — those rules go in the same `self.rules` list with `priority >= 2`.

### Topology vs net membership (CRITICAL)

**`+` and `>>` are not interchangeable.** Both connect ports, but only `>>` creates a topology segment that the SI constraint solver can walk. Ports reached only via `+` are on the same *net* but invisible to `Constrain` / `ConstrainDiffPair` / `ConstrainReferenceDifference`.

When you call `Topology(src_endpoint, dst_endpoint)` and then `ConstrainDiffPair(topo)`, the engine searches for a chain of `>>` segments connecting the endpoints. If any physical port on the signal path is reached only by `+`, the search fails with one of:

- "Incomplete topology segments between X and Y"
- "No path for signal constraint from X to Y"

#### Common failure mode 1: virtual DiffPair endpoints aliased via `+`

A natural pattern is to declare a virtual `DiffPair` port at a circuit boundary so the top level can apply `ConstrainDiffPair`. The trap is wiring the alias with `+`:

```python
# WRONG — connector pads invisible to constraint solver
class USBFrontend(Circuit):
    usb_at_connector = DiffPair()                        # virtual endpoint

    def __init__(self):
        # `+` only — connector.A6 is on the net but not in any `>>` chain
        self.dp_alias = self.usb_at_connector.p + self.connector.A6
        self.dn_alias = self.usb_at_connector.n + self.connector.A7
        # Topology jumps straight from virtual port to ESD, skipping the connector pad
        self += self.usb_at_connector.p >> self.esd.usb.p >> self.phy.usb_data.p
        self += self.usb_at_connector.n >> self.esd.usb.n >> self.phy.usb_data.n
```

Result at top level: `Topology(usb.usb_at_connector, usb.phy.usb_data)` cannot find a path through `connector.A6` even though the net is correct. The router fails with "Incomplete topology segments".

```python
# RIGHT — chain through every physical port
self += (
    self.usb_at_connector.p
    >> self.connector.A6
    >> self.esd.usb.p
    >> self.phy.usb_data.p
)
self += (
    self.usb_at_connector.n
    >> self.connector.A7
    >> self.esd.usb.n
    >> self.phy.usb_data.n
)
```

#### Common failure mode 2: bundle wiring with `+` instead of `>>`

A subcircuit that exposes a bundle (I2C, ULPI, SPI, etc.) and wires the bundle sub-ports to component pins with `+` produces a constraint-invisible signal path:

```python
# WRONG — `+` only, no topology segments through the bundle
class USBFrontend(Circuit):
    ulpi = ULPI()
    def __init__(self):
        self.clk_net = self.ulpi.clk + self.phy.CLKOUT       # net merge only
        # ... 11 more `+` joins
class MCUWrapper(Circuit):
    ulpi = ULPI()
    def __init__(self):
        self.ulpi.clk + self.mcu.PA[5]                        # net merge only
```

Result: `Topology(usb.phy.CLKOUT, mcu.mcu.PA[5])` reports "No path for signal constraint" even though the netlist is fully connected.

```python
# RIGHT — `>>` from physical pin through bundle sub-port
# In USBFrontend (PHY-side):
self += self.phy.CLKOUT >> self.ulpi.clk
self += self.ulpi.stp   >> self.phy.STP        # MCU drives STP, hence reverse direction

# In MCUWrapper (MCU-side):
self += self.ulpi.clk   >> self.mcu.PA[5]
self += self.mcu.PC[0]  >> self.ulpi.stp
```

The two `>>` segments per signal stitch together when the top level merges the bundle sub-ports with `+` (`self.usb.ulpi.clk + self.mcu.ulpi.clk`). The engine walks `phy.CLKOUT >> ulpi.clk(usb) — joined to — ulpi.clk(mcu) >> mcu.PA[5]` end-to-end.

#### Quick checklist

For every signal that will have an SI constraint applied at the top level:
- [ ] Both Topology endpoints exist as actual ports (real component pins or virtual DiffPair / bundle ports declared on circuits)
- [ ] Every physical port between the endpoints is on a `>>` chain — not just on the same net via `+`
- [ ] Bundle sub-ports are `>>`-chained to the component pins they alias, in **both** subcircuits that touch the bundle
- [ ] Direction of `>>` follows signal flow at each end (driver → receiver). Bidirectional buses pick one direction by convention.

If a top-level constraint reports "no path" or "incomplete segments", trace each port name in the error backwards through the source — the missing segment is almost always a `+` where there should be a `>>`.

### Silent-drop patterns (CRITICAL)

Two source patterns build with `status: ok` and pass every JITX-side check but produce a **wrong netlist**, because the Python expression evaluates and is then immediately discarded. The design looks correct from the build but isn't.

JITX warns for *some* of these cases (you'll see `WARNING:jitx._structural:Reference to structural object <Class> at <file>:<line> lost during instantiation, it likely needs to be assigned to an object` for unassigned constraint objects and similar structural classes), but **the warning does not cover bare net or topology expressions** (`+` / `>>` between ports), which is exactly where this trap is easiest to fall into. Treat all such warnings as errors, and code review for the two patterns below regardless.

#### Pattern 1: anonymous `Resistor` / `Capacitor` / `Inductor` with `.insert(...)`

```python
# WRONG — Resistor object is garbage-collected after .insert returns;
# the design ends up without the resistor.
Resistor(resistance=10e3).insert(self.MCU.NRST, self.V3V3)

# RIGHT — store on self, then insert
self.r_nrst = Resistor(resistance=10e3)
self.r_nrst.insert(self.MCU.NRST, self.V3V3)
```

The same applies to `Capacitor`, `Inductor`, and any structural component constructor.

#### Pattern 2: bare net or topology expressions

```python
# WRONG — the Net object is built and discarded; no connection in the netlist.
self.usb.A6 + self.usb.B6                          # bare `+`
self.driver.OUT.p >> self.receiver.INP.p           # bare `>>`

# RIGHT — assign to a `self.<name>` attribute (any name is fine — JITX
# tracks structural objects by their attribute on the parent), or use the
# `+=` form which adds to the circuit's net list:
self.dp_mirror = self.usb.A6 + self.usb.B6         # named net
self += self.driver.OUT.p >> self.receiver.INP.p   # added to circuit
```

The trap is that the *expression evaluates without error* — Python sees `port_a + port_b` as `Net.__add__`, which returns a `Net` object, which Python then drops because nothing held a reference to it. No exception, no warning at parse time, and JITX has no way to recover the Net once it's been garbage-collected.

### Editor-side coverage

Configure the editor's Python language server to surface unused-expression warnings — this catches Pattern 2 before any build runs. Recommended:

- **Ruff** (works in any editor): enable rule `B018` ("Found useless expression") which flags top-level expressions whose return value is discarded. Add to `pyproject.toml`:
  ```toml
  [tool.ruff.lint]
  extend-select = ["B018"]
  ```
- **Pyright / Pylance**: enable `reportUnusedExpression = "warning"` (or `"error"`) in `pyrightconfig.json` (also picked up by the VS Code Python extension when present).
- **Pyflakes**: emits `Statement seems to have no effect` by default — also catches bare `+` / `>>` expressions.

These editor-side checks won't catch Pattern 1 (the `.insert(...)` call has a side effect, so it isn't a "useless expression" from the type checker's view), but they cover Pattern 2 cheaply, and any extra signal during code review is worth turning on.

### Exit Gate: Phase 3 → Phase 3b

- [ ] Top-level design builds with `status: ok`
- [ ] All nets connected (no floating ports on instantiated circuits)
- [ ] Power tree complete (every load rail connected to a regulator output)
- [ ] All require() calls have matching provides
- [ ] `GroundSymbol` on GND net, `PowerSymbol` on every power rail
- [ ] SI constraints applied **at this level** (not inside subcircuits) for every protocol with impedance/timing requirements
- [ ] **No "Invalid Topology Definitions" or "No path for signal constraint" errors in the JITX UI Issues list** — every constraint endpoint reachable via `>>` chains, not `+` (see "Topology vs net membership" above)
- [ ] **No `Reference to structural object … lost during instantiation` warnings in the build output** — every structural object stored on `self`; no bare `+` / `>>` expressions (see "Silent-drop patterns" above)
- [ ] `ReferencePlanes(...)` context wraps all constraint applications
- [ ] Board geometry defined (shape, mounting holes, pours)
- [ ] `capacitor_defaults` and `resistor_defaults` set on Design class to match the design's manufacturing path and circuit role — per-circuit refinements documented for any specialty parts (HV, RF, bulk, precision, hand-build)
- [ ] **Default design rules set on Design class** — `self.rules` contains a default trace width (`IsTrace`), copper clearance (`IsCopper`, `IsCopper`), thermal relief (`IsPad`), and wider trace rule for tagged power/ground nets (`PowerTag` / `GroundTag` with `priority=1`). Values calibrated to substrate fab class. See "Default design rules" above.
- [ ] `bash scripts/grep_gates.sh <ns>/` reports 0 hard-fail hits; review-required hits dispositioned

**Emit the `Gate: Phase 3 → Phase 3b` block** from `references/completion-blocks.md` before advancing.

---

## Phase 3b: Design Review and Loopback

**Who**: orchestrator spawns a **read-only audit agent** (critic only — no code edits), then separately spawns fix agents for issues found.

Each subcircuit was designed in isolation. Now review the assembled design as a system. **Do not proceed to Phase 4 with known electrical errors.**

### Audit Structure

Spawn a sub-agent to perform the design-level audit. The audit agent reads code and datasheets but **does not edit any files**. It produces a **Phase 3b Audit Block** with issues classified as CRITICAL / WARNING / NOTE — see the template in `references/completion-blocks.md` "Phase 3b Design Audit Block".

**After the same-model audit, run an outside-voice (codex) pass — mandatory for complete-board tier.** The two reviews are additive: the same-model audit uses skill knowledge, codex provides independent perspective from outside the conversation. See `references/outside-voice-review.md` for the trigger rules, prompt shape, invocation command, and combined-verdict rule (any CRITICAL/WARNING outside-voice finding makes the combined verdict `issues-pending` even if the same-model audit said `clean`).

Before the audit runs, the orchestrator must have already addressed the build-time silent-drop patterns documented in Phase 3 → "Silent-drop patterns" — those bugs build with `status: ok` but produce a wrong design, and the audit agent's datasheet-comparison passes assume the netlist matches the source. JITX emits a `Reference to structural object … lost during instantiation` warning for some of these cases (constraint and similar structural classes), but not for bare net or topology expressions — handle both manually.

The audit runs six passes (the full pass list and per-pass schema live in `references/completion-blocks.md` "Phase 3b Design Audit Block"):

#### Pass 1: Circuit vs Datasheet Application Schematic

For each major IC circuit, open the datasheet's typical application schematic and compare component-by-component:
- Count external components in the datasheet. Count components in the code. Flag any missing.
- Check passive values match datasheet recommendations (cap values, resistor values, inductor values).
- Check component types match (e.g., datasheet says 0.22uF bootstrap but code has 0.1uF).
- Note every assumption the circuit makes about its operating environment (input voltage, load current, enable timing, power sequencing).

#### Pass 2: Assumption Compatibility

Collect all assumptions from Pass 1 and check them at the system level:
- Does the actual input voltage match what each circuit assumes?
- Does the power sequencing match what each IC requires? (e.g., does the amp expect PDN held low during power-up, but the circuit pulls it high immediately?)
- Do the current draws add up within regulator ratings?
- Are voltage domains compatible across circuit boundaries?

#### Pass 3: Interface-by-Interface Trace

For every interface connecting two or more ICs, trace the complete signal path from source to destination through every component:
- **USB**: trace D+/D- from connector through every device on the bus. Are there bus conflicts? ESD protection? Series termination? **Are SI constraints applied?**
- **I2C**: trace SDA/SCL. Pull-up voltage and value correct? Address conflicts? Level compatible?
- **I2S**: trace BCLK/LRCLK/DIN/DOUT. Clock source correct? Format (I2S vs TDM vs LJ) compatible?
- **SPI**: trace MOSI/MISO/SCK/CS. Polarity? Speed? Pull-ups on CS?
- **Power**: trace each rail from source through regulation to every load. Decoupling at every IC?
- For every high-speed interface (USB, Ethernet, DDR, PCIe, HDMI): **verify SI constraints exist and are applied at the top level**. If constraints are missing, this is CRITICAL.

#### Pass 4: Power and Thermal

- Verify every regulator's output current rating exceeds the sum of its loads (with margin).
- Check thermal dissipation: P = (Vin - Vout) * I for linear regulators, efficiency loss for switchers. Flag any package that will exceed its thermal rating.
- Check hot-plug and transient scenarios: what happens when power appears suddenly? Does anything see voltage before its regulator stabilizes?
- Verify bulk capacitance meets datasheet recommendations (especially for power amplifiers).

#### Pass 5: Protection and Reliability

ESD, transient suppression, reverse polarity, environmental class. Walk the ESD-or-justification table from `references/domains/external-interfaces.md` for every external connector and user-touchable conductor. For aerospace / automotive / medical class designs, walk `references/domains/safety-critical.md`. Full per-row template in `references/completion-blocks.md` "Phase 3b Design Audit Block".

#### Pass 6: DFT / DFM

Test access and manufacturability. Walk `references/domains/dft.md` (test points, debug headers, named TPs) and `references/domains/dfm.md` (fab rules, edge clearance, BOM, footprint library). Full per-row template in `references/completion-blocks.md`.

### Loopback

After the audit report, the orchestrator (not the audit agent) decides what to fix:

- **CRITICAL issues**: must fix before Phase 4. Spawn a separate sub-agent for each fix with the specific issue and datasheet reference.
- **WARNING issues**: should fix. Spawn fix agents or fix directly.
- **NOTE issues**: document for the user, fix if straightforward.

After fixes, **re-run the audit** to verify the fixes didn't introduce new issues and the original issues are resolved. Do not skip the re-audit.

For major redirections (bus contention needing new ICs, missing power rails, architecture changes), update ARCHITECTURE.md and PLAN.md, add new tasks, and go back to the appropriate phase.

Do not accept "noted for future refactoring" — if it's broken, fix it now.

### Exit Gate: Phase 3b → Phase 4

- [ ] Audit found no CRITICAL or WARNING issues (or all were fixed and re-audited)
- [ ] Every high-speed interface has SI constraints applied and functional
- [ ] PLAN.md updated with all rework tasks completed

**Emit the `Gate: Phase 3b → Phase 4` block** from `references/completion-blocks.md` before advancing. The gate references the Phase 3b audit block (in the same file), which the read-only audit agent emits during Phase 3b.

---

## Phase 4: Build + Verify + Iterate

**Who**: orchestrator or single agent

### Process

1. Run full build: `jitx build <ns>.main.Design`
2. Check output for:
   - `status: ok` — proceed to verification
   - `status: error` — read traceback, fix, rebuild
3. Open the popout viewer (`jitx ui open --board --design <ns>.main.Design` and `jitx ui open --schematic --design <ns>.main.Design`) and verify:
   - Schematic: all connections present, symbols readable
   - Board: components placed (or floating), no overlaps
   - Issues List: SI constraints satisfied or flagged
   - DRC: clean or flagged
4. Iterate:
   - Build errors → fix code, rebuild
   - DRC violations → adjust clearances or routing structures
   - SI constraint failures → review parameters, check routing structure impedance
   - Missing connections → trace back to Phase 2/3 and fix

5. **Emit the Phase 4 Verification Block** from `references/completion-blocks.md`. The block requires JITX UI / Issues List / DRC / SI / placement-overlap rows with explicit pass/fail status, or a `not run` reason for any row the environment can't run (e.g. headless CI). PLAN reconciliation, deferred items, and blocking items also belong in the block. **Blocking items must be empty for `Verdict: done`.**

### Completion Criteria

The Phase 4 Verification Block is the completion criterion. The block enforces:

- [ ] `status: ok` on final build
- [ ] JITX UI verification rows pass or are `not run` with reason
- [ ] Issues List, DRC, SI rows have status (or `not run` with reason)
- [ ] All PLAN.md tasks accepted; all gate blocks emitted; Phase 3b audit verdict `clean`
- [ ] No blocking items
- [ ] User-approved deferrals documented

A "builds clean" claim alone is not the criterion — the block is.

---

## Session Resumption

If the orchestrator session is interrupted, a new session can resume:

1. Read PLAN.md to see the current state of all tasks.
2. Read ARCHITECTURE.md for the design context.
3. Identify the current phase based on task statuses.
4. Continue from where the previous session left off.

This is why PLAN.md must be kept up-to-date with every status change.

---

## Recovery Procedures

### Missing-Dependency Escalation

When a required dependency is missing — `jitxlib` doesn't import, the target substrate package isn't available, `parts2jitx` returns broken output that can't be patched in a smoke build, the datasheet PDF the user said they'd provide hasn't arrived — that is a **blocker**, not a license to drop the design requirement.

The Encore failure mode: `jitxlib` failed to import, so the agent silently dropped controlled-impedance routing from the design rather than fix the environment. **Do not do this.**

Concrete rule:

1. **Surface the missing dependency to the user immediately.** Name what's missing and what work it blocks.
2. **Do not substitute a lower-fidelity design as a workaround** — no removing SI constraints because the SI module didn't load, no skipping `voltage_divider_from_constraints()` because the solver isn't available, no swapping a custom substrate for a fallback because the predefined package didn't import.
3. **Wait for user confirmation** before making any design-scope change. If the user explicitly accepts a reduced scope ("ship without controlled impedance, we'll fix the env after"), record that as a deferred item with their approval in the relevant gate block.
4. **Environment fixes go before design fixes.** If the missing dependency is a setup issue (wrong venv, missing pip install, wrong Python version), fix the setup. If it's a real availability gap (`jitxexamples` not installed but referenced), confirm with the user before proceeding.

This rule applies through every phase, not just Phase 0. Mid-project missing-dependency discoveries follow the same protocol.

### Rework Loop

When a task is sent back for rework:
1. Orchestrator sends specific issues to the sub-agent (see task-execution.md rework protocol).
2. Sub-agent fixes only the identified issues, re-runs checklist, rebuilds.
3. Orchestrator reviews again.
4. Maximum 2 rework cycles. After that, escalate to reject.

### Replanning

When a task is rejected:
1. Orchestrator analyzes why the approach failed.
2. Options:
   a. Rewrite the task description with better guidance and reassign.
   b. Split the task into smaller, more focused tasks.
   c. Ask the user for clarification or additional data (e.g., missing datasheet pages).
3. Update PLAN.md with the new task definitions.
4. Resume from the affected phase.

### Upstream Cascade

If a Phase 2 task fails because of a Phase 1 output:
1. Identify the upstream task that produced the bad output.
2. Send the upstream task back to rework (with the downstream failure as evidence).
3. After upstream is fixed, re-run the downstream task.
4. Update PLAN.md statuses for both tasks.
