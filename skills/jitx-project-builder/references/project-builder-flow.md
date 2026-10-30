# Project Builder Orchestration Flow

Five-phase workflow for building complete JITX hardware designs from requirements. The orchestrator drives the flow, spawns parallel sub-agents, and enforces exit gates with acceptance reviews.

**This file applies to the complete-board tier only.** Tier classification happens before Phase 0 — see this skill's SKILL.md "First: Pick the Workflow Tier" and `references/completion-blocks.md`. Single-task tier does not enter the formal phase chain. If a single-task grows beyond a single artifact mid-work, upgrade to complete-board and apply Phase 0 retroactively (write PLAN.md + ARCHITECTURE.md, run the data audit) before continuing.

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
   ↑                      │
blocked: OQ-n             ├→ rework → review → accepted (max 2 cycles)
                          │
                          └→ rejected (replan or escalate to user)
```

- `pending`: not started, and startable
- `blocked: OQ-n`: not startable while an open question affects it. Blocking is transitive: a task whose dependency is blocked is blocked, not pending. Status alone records the task-to-question relationship; reconcile it against unresolved questions and task inputs and dependencies before starting work, per `plan-template.md`.
- `in-progress`: sub-agent working
- `review`: sub-agent returned task acceptance block, awaiting orchestrator review
- `accepted`: orchestrator verified, ready for downstream tasks
- `rework`: orchestrator found issues, sent back with specific feedback
- `rejected`: fundamental problem, task needs replanning

Every transition above runs through `python scripts/plan_status.py <task-id> <status> [--note "<short note>"]`. (`plan-template.md` owns the status rule.)

---

## Phase 0: Requirements + Architecture

**Who**: orchestrator (no sub-agents)

### Phase 0 Process

1. **Analyze requirements**: parse the user's request, spec documents, or reference designs into structured form.

2. **Identify all components**: propose ideal parts based on electrical requirements and engineering tradeoffs (voltage/current, thermal, peripheral set, package, reliability). Note the part number, package, and datasheet for each.

3. **Map interfaces**: document which components connect to which, via what protocol, and whether SI constraints are needed.

4. **Plan the power tree**: trace power from input through regulators to every load. Note voltage, current, and sequencing requirements.

5. **Assess substrate needs**: based on interface speeds, routing density, and component package complexity (e.g., high-pin-count BGAs require more layers), determine layer count, material class, and via technology. **Ask the user which fab house they are targeting.** If they confirm JLCPCB and need standard 4-layer or 6-layer FR-4 with 50/90/100 ohm impedance, predefined substrates from `jitxlib.jlcpcb` (JLC04161H_1080, JLC04161H_7628, JLC06161H_7628) are available — no substrate *modeling* is needed, and sub-01 narrows to selection and verification rather than disappearing. Otherwise, create a custom substrate (the default path).

6. **Data source audit**: for every component, identify where its data will come from, and ask for the user's approved-parts list for passives. Present a table to the user for approval **before proceeding**. See the Data Source Audit section below.

7. **Decompose into tasks**: follow `references/decomposition-guide.md` to create the task graph.

8. **Write PLAN.md**: use `references/plan-template.md` as the starting point. Lock the requirements, include the approved data sources, and define the task graph and initial statuses. Keep design facts in ARCHITECTURE.md.

9. **Write ARCHITECTURE.md**: use `references/architecture-template.md` as the starting point. Fill `Power Tree`, `Interface Map`, and `Board`; add `Object-Hierarchy Decisions` only for parametric subsystems and `Design Notes` only for non-derivable constraints. This gives sub-agents the design context without duplicating PLAN.md.

### Data Source Audit

Before decomposing into tasks, present the user with a data source plan for each component. This ensures the user controls where data comes from and can provide their own files.

**Present this table and wait for approval:**

```
## Data Source Plan

| Component | Package | Data Source | Footprint Method | Status |
|-----------|---------|-------------|------------------|--------|
| MCU (STM32H753) | QFP-100 | User datasheet (provided) | JITX QFP generator | Ready |
| USB-C connector | Non-std | Need footprint | User to provide .kicad_mod, or manufacturer KiCad library | Needs input |
| LDO (LM1117) | SOT-223 | Datasheet from manufacturer | JITX SOT generator | Will fetch |
| Buck (TPS62933) | SOT-23-6 | User datasheet (provided) | JITX SOT23_6 generator | Ready |
| WiFi module | Non-std | Need footprint + datasheet | User to provide, or manufacturer KiCad library | Needs input |

**Data sources:**
- "User datasheet (provided)" — user has already supplied the PDF
- "Datasheet from manufacturer" — will download from manufacturer site (ti.com, st.com, etc.)
- "JITX [generator] generator" — standard package, dimensions from datasheet
- "User to provide .kicad_mod" — non-standard package, user has KiCad footprint
- "Manufacturer KiCad library": non-standard package, the vendor publishes a `.kicad_mod`; jitx-component-modeler imports it entry by entry

Please confirm data sources or provide alternatives (datasheets, footprints, specs).
```

**Channel evidence is required.** If the user has named a sourcing channel (LCSC/JLCPCB, Digi-Key/Mouser, internal PLM), the audit table must include channel-specific evidence for every named IC and connector before code is written. For LCSC/JLCPCB, that means the part's channel record (stock, lifecycle, datasheet URL, pin labels) saved to the project. See [Required-Sourcing Rule (named channel → channel-specific evidence)](parts-sourcing.md#required-sourcing-rule-named-channel--channel-specific-evidence) for the full ladder including non-LCSC channels.

**Rules:**
- Always prefer user-provided data over automated lookups
- Standard packages (QFN, SOIC, SON, SOT, QFP, BGA) use JITX generators — no footprint download needed
- For non-standard packages, ask the user if they have a `.kicad_mod` before looking for the manufacturer's KiCad library
- Do NOT proceed past the data audit until the user approves the data source plan

### Approved passives

Passives resolve from the project's parts chain, and its first member reads `parts/approved-parts.csv` (base `jitx` skill, Step 2). Ask the user for their approved-parts list at the audit: a CSV whose header names `category`, `mpn`, `manufacturer`, then one column per attribute a query filters on (`capacitance`, `case`, `rated_voltage_dc`, ...), or an internal parts database a `jitxlib.parts.Provider` can serve. Save a CSV to `parts/approved-parts.csv`; a database goes into the chain in place of the `csv:` entry. Format and the provider route: https://docs.jitx.com/en/latest/essentials/design/parts.html

With no list from the user, copy the example CSV that ships in `jitxexamples` as a stand-in. Install it into the project venv once with `--no-deps`, so its own pins cannot replace the project's `jitx` or `jitxlib-parts`; it is not added to the project's dependencies:

```bash
pip install --no-deps --upgrade jitxexamples
mkdir -p parts
python -c "import importlib.resources as r, shutil; shutil.copy(r.files('jitxexamples') / 'parts' / 'example-passives.csv', 'parts/approved-parts.csv')"
```

If the copy raises `FileNotFoundError`, the installed `jitxexamples` predates the packaged example CSV: ask the user for a parts list instead.

Tell the user the list is a stand-in and record it in PLAN.md `Data Sources`. A stand-in is not an approval: the Phase 4 parts gate lists every MPN the final build resolved, each with the user's approval quoted, or the user's list replaces the stand-in. Read that list from the final build. Not from `parts.lock.json`: the lock never prunes, so it still holds stale entries, `IDEAL-` parts included. Not from `parts-check` either: it prints counts, not MPNs. Start `jitx design session <design>` in the background (it prints nothing until stopped), then:

```bash
jitx design exec <design> -c '
from jitx.inspect import extract
from jitxlib.parts import DeferredPart
def main(design):
    return sorted({part.mpn for part in extract(design.root, DeferredPart)})'
jitx design session --stop <design>
```

It prints the MPNs as a JSON list, the parts the chain resolved and no modeled components. If `exec` reports `message could not be delivered`, the session is not up yet: run it again. If the background session has exited, read its output, fix the error it reports, and start the session again.

When the user's list replaces the stand-in, tell the user every passive will be chosen again, delete `parts.lock.json` (the lock keys a CSV on its path, so a file overwritten in place re-resolves nothing), rebuild, and update the `Data Sources` row. That whole-lock delete is the re-resolve the user asked for; nothing else deletes the whole lock. After a row is added for a part that resolved `IDEAL-`, remove the lock's stale entries, then run `prune_lock.py` with `--unpin <IDEAL- MPN>` and rebuild: the lock keeps the ideal part it pinned until it is unpinned, and every other part stays pinned. Both procedures, and the stale-entry cleanup: base `jitx` skill [`references/parts-lock.md`](../../jitx/references/parts-lock.md).

### Exit Gate: Phase 0 → Phase 1

- [ ] PLAN.md exists with all tasks defined
- [ ] ARCHITECTURE.md exists with power tree and interface map
- [ ] No duplicated facts remain; task statuses reconcile with unresolved questions and task inputs and dependencies, including transitive blockers — either discrepancy blocks advancement per `completion-blocks.md`
- [ ] Data source audit completed and user approved
- [ ] `parts/approved-parts.csv` holds the user's approved-parts list, or the example stand-in recorded as such in PLAN.md (or the chain names the user's parts database)
- [ ] All datasheets and reference materials identified and accessible (or user committed to providing them)
- [ ] Dependencies are acyclic
- [ ] No ambiguous requirements remain (ask user if unclear)
- [ ] User has reviewed and approved the plan
- [ ] Planning document line counts are measured and within the template budgets, or the overage has a one-line justification

**Emit the `Gate: Phase 0 → Phase 1` block** from `references/completion-blocks.md` before advancing.

---

## Phase 1: Substrate + Components

**Who**: parallel sub-agents (one per task)

### Phase 1 Orchestrator Actions

1. For each Phase 1 task in PLAN.md:
   a. Run `python scripts/plan_status.py <task-id> in-progress`
   b. Prepare a spawn call with the task definition, relevant datasheet spec notes, and instruction to follow `references/task-execution.md`. For a component whose note does not exist, give that component-modeling sub-agent the PDF path and require it to write the note before modeling.
2. Dispatch every startable Phase 1 spawn batch in a single message carrying multiple spawn calls, not one message per task. Record `N`, `B`, and `C` for the Phase 1 exit gate.
3. As sub-agents return, perform acceptance review (Part B of task-execution.md).
4. Issue verdicts: accept, rework, or reject.

### Parallel Safety

Phase 1 tasks are independent at the *design* level. Each sub-agent writes its own component file with its own test design. Parallel sub-agents each build their own test design; because each agent's design is distinct (different module paths, different component class names), concurrent builds against the same project are acceptable. The JITX backend serializes internally on the WebSocket. What is NOT safe is two agents building the same design at the same time; the orchestrator should never spawn two tasks targeting the same test design class. The spawn-batch rule does not change this same-design build-safety rule. See [Build safety: don't parallelize same-design work](../../jitx/SKILL.md#build-safety-dont-parallelize-same-design-work).

### Exit Gate: Phase 1 → Phase 2

ALL of the following must be true:
- [ ] Dispatch record names `N` Phase 1 tasks, `B` spawn batches, and maximum concurrency `C`; for `N >= 3`, `B == N` or `C < 3` blocks unless each serialized task names the dependency that forced it
- [ ] Every Phase 1 task has status `accepted`
- [ ] Every component builds with `status: ok` in its test harness
- [ ] Substrate builds with all routing structures and via definitions
- [ ] Orchestrator has spot-checked high-risk items per task type (see task-execution.md Part B)
- [ ] `Interface notes` fields in task acceptance blocks are consistent (port names, power requirements match ARCHITECTURE.md)
- [ ] Orchestrator has run `python scripts/check.py <ns>/`; every summary line passes, hard-fail hits are 0, and review-required hits have dispositions

**Emit the `Gate: Phase 1 → Phase 2` block** from `references/completion-blocks.md` before advancing.

---

## Phase 2: Constraints + Circuits + Pin Assignment

**Who**: clustered parallel sub-agents

### Task Ordering

Phase 2 tasks have partial dependencies. Group into clusters:

- **Cluster A: Pin assignment wrappers** — depend on components from Phase 1. These define the provide/require flexibility for the central IC(s). Other Phase 2 tasks may depend on these.
- **Cluster B: Power circuits** — depend on power components. Often independent of other clusters.
- **Cluster C: Interface circuits + constraints** — depend on components, substrate routing structures, and possibly pin assignment wrappers.
- **SI verification tasks (`ver-`)**: one per constrained interface, each depending on every module task on the path (the modules at both ends and any module it passes through) and the constraint (`cst-`) task, so it starts once those are accepted. See [SI verification designs (CRITICAL)](#si-verification-designs-critical).

Run independent clusters in parallel. Within a cluster, respect dependencies.

### Phase 2 Orchestrator Actions

1. Identify which Phase 2 tasks can run immediately (dependencies all `accepted`).
2. Spawn those sub-agents.
3. As tasks complete and are accepted, check if new tasks are unblocked.
4. Continue until all Phase 2 tasks are accepted.

### Bundle wiring for constrained signals

Subcircuits that expose bundles (I2C, ULPI, USB2, etc.) wire the bundle sub-ports to component pins with `+`, including for signals that will receive an SI constraint at top level. On jitx 4.6 a constraint binds across plain nets; no `>>` is needed. What it does need is a `BridgingPinModel` on every part inside the subcircuit with a path through it (none on a flow-through package whose opposite pin is n.c.; its two lands are one net) and, before it measures, routes along the path. See [Plain nets carry SI constraints (CRITICAL)](#plain-nets-carry-si-constraints-critical).

Each constrained interface's verification design belongs to its own Phase 2 `ver-` task, not to the module tasks on its path; see [SI verification designs (CRITICAL)](#si-verification-designs-critical).

### Exit Gate: Phase 2 → Phase 3

- [ ] Every Phase 2 task has status `accepted`
- [ ] All circuits build individually with `status: ok`
- [ ] Constraint classes instantiate without error
- [ ] Provide/require interfaces are consistent across wrapper and consuming circuits
- [ ] **Interface circuits expose bundle-typed ports** (I2S, I2C, SPI, USB2, GPIO, Power) — not individual signal ports. If a circuit wraps individual-pin components, the bundle wiring happens inside the circuit.
- [ ] For any signal that will receive an SI constraint at top level, every part the signal passes through inside the subcircuit has a `BridgingPinModel` (a flow-through package whose opposite pin is n.c. gets none, and its two lands are one net), and the bundle wiring uses plain `+` nets with no `>>` added to make the constraint bind; see [Plain nets carry SI constraints (CRITICAL)](#plain-nets-carry-si-constraints-critical). The gate block records this in its `Constrained-path wiring and pin models` row
- [ ] **Every passive is an attribute on `self`, and no bare `+` expressions** in the subcircuit (see [Silent-drop patterns (CRITICAL)](#silent-drop-patterns-critical)). The `grep gates` line from `python scripts/check.py <ns>/` flags bare expressions as review-required.
- [ ] **Every power-rail capacitor is on a `ShortTrace`**: a decoupling, bypass, bulk or output filter capacitor is its own attribute on `self`, its supply-side pad joins the pin it serves through `ShortTrace(self.c_x.p1, <the IC power pin port>)` (`self.c_x.a` on a `PolarizedCapacitor`) and its other pad joins the return net (`jitx-circuit-builder`). AC coupling, RC timing, compensation and RF matching caps are dispositioned in the task acceptance block as not power-rail. A crystal's load caps take a `ShortTrace` to the crystal pin they serve, and a bootstrap cap takes a `ShortTrace` to its BOOT pin with its other pad on SW; neither is an exception. The `grep gates` line counts, per file, `Capacitor(` and `PolarizedCapacitor(` call sites against `ShortTrace(` call sites (comments and strings never count) and flags every capacitor call line in a file where capacitors outnumber short traces as review-required.
- [ ] Every constrained interface has an accepted `ver-` task whose verification design, `<ns>/designs/verify_<iface>.py`, passes per [SI verification designs (CRITICAL)](#si-verification-designs-critical), quoted in that task's `SI measurements` row. The gate block records this in its `SI verification designs` row
- [ ] Port names and bundle types match between providers and consumers
- [ ] Power circuit outputs match the voltage/current needs documented in ARCHITECTURE.md

**Emit the `Gate: Phase 2 → Phase 3` block** from `references/completion-blocks.md` before advancing.

---

## Phase 3: Top-Level Assembly

**Who**: single agent (not parallelizable)

### Phase 3 Process

A single sub-agent assembles the top-level design. The orchestrator reviews its code and acceptance block but does not author files under `<ns>/`.

**CRITICAL**: Net symbols (`GroundSymbol`, `PowerSymbol`) and SI constraints (`Constrain`, `ConstrainDiffPair`, `ReferencePlanes`) MUST be applied at the top-level design, not inside subcircuits. Subcircuits wire their signals with `+` nets; constraints are applied here, where the full signal path is visible.

1. Create the top-level Circuit class.
2. Instantiate all subcircuits from Phase 2.
3. Create global ground net with `GroundSymbol`, connect all ground ports, add pours on ground layers.
4. Create power nets with `PowerSymbol`, connect regulator outputs to load inputs.
5. Wire signal interfaces using `require()` from provides. Example:
   ```python
   i2s = self.mcu_wrapper.require(I2S)   # solver picks pins
   self.I2S_SCK = i2s.sck + self.amp.i2s.sck    # wire bundle sub-ports;
   self.I2S_WS = i2s.ws + self.amp.i2s.ws        # each field names its net
   self.I2S_SD = i2s.sd + self.amp.i2s.sd
   ```
   NEVER hardcode GPIO numbers. If a downstream circuit has individual ports instead of a bundle, wire the required bundle's sub-ports to them. SI-constrained signals use the same `+` wiring; see [Plain nets carry SI constraints (CRITICAL)](#plain-nets-carry-si-constraints-critical).
6. Add shared-bus components at the **bus-aggregation level** — the level where the bus is composed across multiple participants (master + slaves). Most of the time that's the top-level design here, because typical buses span subcircuits (MCU subcircuit talks to amp + sensor subcircuits). But if a single subcircuit aggregates an entire bus internally (e.g. a sensor-hub subcircuit containing master + 4 sensors all on one private I2C), the pull-ups belong inside that subcircuit. The rule is bus scope, not file location.
   - **Shared-bus (I2C, MDIO) pull-ups** — one set per bus, placed at the level that composes the bus, to the correct voltage rail (usually 3.3V)
   - **SPI pull-ups** on CS lines — same rule
   - **CAN termination** resistors — same rule
   - Any termination that spans multiple subcircuits goes at the top-level design that aggregates them
7. Apply ALL SI constraints at this level within `ReferencePlanes(GND)` context. Example:
   ```python
   with ReferencePlanes(self.GND):
       usb_topo = Topology(self.mcu.usb.data, self.usb_conn.usb)  # DiffPair ends
       self.cst_usb = ConstrainDiffPair(usb_topo) \
           .structure(substrate.DRS_90) \
           .timing_difference(0.1e-12)
   ```
   Every protocol with impedance or timing requirements needs constraints here. Read [Plain nets carry SI constraints (CRITICAL)](#plain-nets-carry-si-constraints-critical) below: a constraint measures only once routes close its path.
8. The assembly agent compares every SI constraint against its interface's
   accepted verification design: constraint class, parameters, routing
   structure, Topology ends and pin models, with the evidence listed under
   [SI verification designs (CRITICAL)](#si-verification-designs-critical). A
   missing comparison or mismatch sends the assembly task to `rework`; it does
   not reach its acceptance verdict.
9. Define board shape, mounting holes, and any keepout zones.
10. **Set passive query defaults on the Design class** to match the design's manufacturing path and circuit role (see [Passive query defaults — match manufacturing and circuit role](#passive-query-defaults--match-manufacturing-and-circuit-role)). Without them, each passive takes the first approved row that matches its value, whatever its case.
11. **Set default design rules on the Design class:** trace width, copper clearance, thermal relief, and wider traces for tagged power/ground rails. See [Default design rules (set on the Design class)](#default-design-rules-set-on-the-design-class). These are the production-friendly defaults every board should have; without them, the router uses the substrate's `FabricationConstraints` minimums, which are usually too narrow for power.
12. Build and verify `status: ok`.

### Passive query defaults — match manufacturing and circuit role

A query assigned in the Design class body is the default for every passive of its category built below it, and keywords on one part are added on top of it. Without one, a passive takes the first row of the approved-parts list that matches its value: on the example CSV, a 100 nF capacitor and a 10 kΩ resistor both resolve to 0201 parts. Filter only on keys the approved-parts list has a column for. A key with no column, or a bound no row meets, makes the CSV decline the query, and `ideal` then answers it without a warning (base `jitx` skill, Step 2). The example CSV's columns include `case`, `mounting`, `tolerance`, `rated_voltage_dc`, `type` and `temperature_coefficient_code`. The right values depend on the design:

| Design class | Typical defaults | Why |
|--------------|------------------|-----|
| **SMT production / economy** (JLCPCB, full-machine assembly) | SMD-only, ceramic for caps, every case the assembler accepts from its smallest up (0402 to 1210 in the example); a case left off is excluded | Through-hole picks are wrong; a short list sends a large-value or high-voltage part to `IDEAL-` |
| **Hand-build / prototype** (hand-soldered, mixed assembly) | SMD or mixed, larger case (0603–1206) for ease, allow common through-hole on large parts | Hand-rework needs accessible sizes |
| **Specialty** (high-voltage, RF-heavy, precision analog, high-current, automotive temp) | Per-circuit refinement of ratings and dielectric is the rule; design-level defaults stay broad | Circuit role dominates: bulk caps, film, RF passives and shunts each state their voltage, power or dielectric need |

```python
from jitxlib.parts import CapacitorQuery, ResistorQuery

class Design(...):
    substrate = ...
    board = ...

    # Example for an SMT-production design. Adjust per the design's class above.
    # The attribute name is free; the query's class picks the category it applies to.
    # `case` lists every package the assembler accepts; one left off is excluded.
    capacitor_defaults = CapacitorQuery(
        mounting="smd",
        type="ceramic",
        case=("0402", "0603", "0805", "1206", "1210"),
    )
    resistor_defaults = ResistorQuery(
        mounting="smd",
        case=("0402", "0603", "0805", "1206", "1210"),
    )

    circuit = TopCircuit()
```

**How to override.** A part that needs more than the default states its electrical need as keywords on itself, never a `case=`: the keywords are added to the design default, which keeps the case, mounting and type. A 22 µF bulk capacitor on a 3.3 V rail loses capacitance under DC bias, so it asks for voltage headroom and a dielectric:

```python
from jitx.units import V, uF
from jitxlib.parts import AtLeast, Capacitor

self.c_bulk = Capacitor(
    capacitance=22 * uF,
    rated_voltage_dc=AtLeast(10 * V),
    temperature_coefficient_code="X5R",
)
```

A `with CapacitorQuery(...)` block replaces the design default for every capacitor built inside it rather than adding to it, so restate the keys the default sets.

**The point:** every design has a default that matches its manufacturing path, plus per-circuit overrides where the role demands them. The Phase 3 exit gate confirms defaults exist and overrides are documented — not that any specific filter is set.

### Default design rules (set on the Design class)

Every Design declares four canonical rules on `self.rules` (default trace
width, copper-to-copper clearance, thermal relief on pads, wider power and
ground traces) so the router and DRC have production-friendly defaults above
the fab floor. The rule shapes, the priority ladder, calibration to the
substrate's floors, and the non-default net classes that go in the same list
at `priority >= 2` are owned by the `jitx-layout-constraints` skill
("Board-wide defaults" and "Net classes: tag, derive, express").
Invoke it for Phase 3 assembly; the Phase 3 gate checks that the four rules
are present.

### Plain nets carry SI constraints (CRITICAL)

On jitx 4.6, `Constrain`, `ConstrainDiffPair` and `ConstrainReferenceDifference` apply to `Topology(begin, end)` when the ports between the two ends are joined by ordinary `+` nets. A subcircuit wires its bundle sub-ports to component pins with `+`, the top level merges the bundles with `+`, and the constraint follows the signal across both. No `>>` is needed. On jitx 4.6.0rc10 with runtime 4.6.0-rc.16, a diff pair netted to a circuit-level `DiffPair` port with `+` in each of two subcircuits, joined with `+` at the top and code-routed, measured `Time: 104.529ps` and `Skew: 0s`, with no unresolved text in any group, whether the Topology named the component pins or the two circuit bundle ports. A circuit bundle port resolves to the first pad behind it, so with a series part inside the sub-circuit, name the chip pad instead, and on a single-ended net also put a structure-only constraint on the circuit ports: without it the segment joined through the ports reports `Missing routing structure` (with it the measured Time changes; not tried on a diff pair). `jitx-interconnect-constraints` "Choosing the ends" links the measured case.

```python
# Subcircuit: the bundle port and the component pin share a plain net.
class UsbPhyCircuit(Circuit):
    usb = DiffPair()

    def __init__(self) -> None:
        self.phy = UsbPhy()
        self.USB = self.usb + self.phy.usb_data


# Top level: join the bundles with +, constrain between component pins.
self.USB = self.phy_ckt.usb + self.conn_ckt.usb
with ReferencePlanes(self.GND):
    self.cst_usb = (
        ConstrainDiffPair(Topology(self.phy_ckt.phy.usb_data, self.conn_ckt.conn.usb))
        .timing_difference(USB.v2.skew)
        .structure(substrate.DRS_90)
    )
```

What a constraint does need, and what the design-issue report says when it is missing:

| Need | Report while it is missing |
|---|---|
| Routes along the path. The path is inferred from routes; code `Route`s close it without the board view. | `Unconnected Topology on Path: drv.o, cap.a`, `Signal path from drv.o to l1.o is not routed yet`, or `No path for signal constraint from X to Y` |
| A `BridgingPinModel` between the two ports of each part with a path through it (AC cap, series resistor, an ESD channel whose datasheet gives an in-to-out path); a flow-through package whose opposite pin is n.c. gets none, and its two lands are one net on board copper | `No path for signal constraint from drv.o to rcv.o: the ends are only connected through the part between cap.a and cap.b, which has no pin model.` |
| A routing structure on every segment: `.structure(...)` on the constraint, plus a structure-only constraint across the circuit ports when the ends are chip pads behind series parts in sub-circuits | `Missing routing structure on Path: drv.o, cap.a` |
| For pin-assigned ports, routes on the provider's physical pins (`jitx-pin-assignment`, "Constraints on Pin-Assigned Ports") | `Unassigned Pin on Path: ...` or `No path for signal constraint ...` |

A via on the path takes its delay and loss from its via class's `models = {(start, stop): PinModel(...)}`.

#### Quick checklist

For every signal that will have an SI constraint applied at the top level:
- [ ] Both Topology ends are the chip pads at the two ends of the path, except where a pin-assignment provider is itself an end: there the Topology begins on the `require()`d port (`jitx-pin-assignment`, "Constraints on Pin-Assigned Ports"). A circuit bundle port also works as an end, but it resolves to the first pad behind it, so a series part between that port and the chip is left out of the measurement
- [ ] Where the ends are chip pads behind series parts in sub-circuits joined through their ports, on a single-ended net, a structure-only constraint across those ports covers the segment between them (`jitx-interconnect-constraints` "Choosing the ends")
- [ ] Every part with a path through it between the ends has a `BridgingPinModel`; a flow-through package whose opposite pin is n.c. gets none, and its two lands are one net
- [ ] `>>` appears only for a daisy chain whose order is part of the design (a flyby clock), never to make a constraint bind
- [ ] The interface's verification design (code-routed) shows a Time, Loss or Skew measurement for the constraint (one with a timing, loss or skew target) in its SI check; see [SI verification designs (CRITICAL)](#si-verification-designs-critical). Without `satisfied=True`, satisfied constraints are left out. A measurement means the constraint applied; whether it is met is `group.satisfied`.

### SI verification designs (CRITICAL)

Binding is proven on a code-routed verification design, not on the shipping assembly. Proof routes fix one path and, on a pin-assigned port, one mapping. In the shipping assembly they would take away the routing and pin-assignment freedom the board is built to keep, so the assembly carries none.

A constrained interface is the constrained paths between the same modules, with every constraint on them: for example, every data, strobe, address, command and clock path between an FPGA and its DDR5 device, with each path's own constraint and each byte lane's `ConstrainReferenceDifference`. A path under two constraints belongs to that one interface, not to one interface per constraint. Each constrained interface gets its own Phase 2 `ver-` task (`ver-01`, `ver-02`, ...), which writes the verification design at `<ns>/designs/verify_<iface>.py`. Its PLAN entry depends on every module task on the path (the modules at both ends and any module the path passes through) and the constraint (`cst-`) task. The module tasks verify on their own `TestDesign` and do not depend on each other for SI, so two modules that share a path never wait on each other. The Phase 3 assembly checks its constraints against the verification design for parity. For routing and placement, follow the verification designs in `jitxexamples.patterns.pin_series_array` (`jitx-pin-assignment`, "Constraints on Pin-Assigned Ports"), but keep the constraint out of the product module: that pattern applies its constraints inside its circuit, which grep gate Pattern 1 hard-fails under `<ns>/circuits/`. Here the constraint goes in `verify_<iface>.py` and in the assembly.

A verification design:
- instantiates every module on the interface's paths with the parts between them, and places every part with `.at(...)`;
- applies the SI constraints the assembly will apply, with the same Topology ends and pin models;
- code-routes every path of the interface between physical pads; for a pin-assigned port, the routes land on the provider's physical pins and fix one legal mapping;
- is checked with its SI check script, `<ns>/designs/check_si_<iface>.py`, run as `python -m <ns>.designs.check_si_<iface>`: the Python check in `jitx-interconnect-constraints` "Verification" (`issues(satisfied=True, wait=30)`, a `report.complete` check, then each group's `satisfied` and text, all in `main()` behind the `__name__` guard) with the verification design imported. The assembly's script, `<ns>/designs/check_si_main.py`, belongs to the assembly task (`asm-01`).

It passes when every constraint with a timing, loss or skew target shows a Time, Loss or Skew measurement from its intended begin pad to its intended end pad, and no group for it holds unresolved text. Unplaced parts give `Missing Connection on Path` and `Unable to find path for requested route` instead of a measurement.

A constraint that carries only `.structure(...)`, with no timing, loss or skew target, never appears in the report, satisfied or not. It is exempt from the measured-line rule and from the absent-from-report rule; its evidence is the constraint in code (class, Topology ends, structure), recorded in the parity row.

On the shipping assembly, run `python -m <ns>.designs.check_si_main` and sort each SI group by whether its constraint's path has copper yet:

- No route on the path: `Unconnected Topology`, `not routed yet`, `No path for signal constraint` with no part named, and `Unassigned Pin` on a pin-assigned end are expected and recorded.
- Any route on the path: the constraint is held to the verification-design bar, a measurement between its intended ends with no unresolved text, `Missing routing structure` and a placeholder via model (`... Using placeholder model`) included. Those two appear only beside a measurement, so they are checked on the verification design and on routed paths.
- Blocking wherever it appears: `No path for signal constraint ... which has no pin model`, `Virtual connection without a pin model`, and a constraint with a timing, loss or skew target that is absent from the report.

Compliance is read from the routed assembly's own groups (`group.satisfied`); the printed text reads the same met or unmet. A verification design's values are proof-route numbers, not the board's.

Parity compares constraint class, parameters, routing structure, Topology ends and pin models between the verification design and the assembly. The verification side's evidence is its measurements (for a structure-only constraint, its code). The assembly side's is its constraint code, plus the `Unconnected Topology on Path:` segment list where the report gives one; a pin-assigned end reports `Unassigned Pin`, and an unrouted plain chain may report `not routed yet` or a bare `No path`, and then the code comparison stands alone. A missing comparison or a mismatch returns the assembly task to `rework`.

Where the evidence goes: the `ver-` task's `SI measurements` row in its task acceptance block quotes the verification design's check command and its printed groups. The `Gate: Phase 3 → Phase 3b` block's `SI design issues dispositioned` row quotes the assembly's sorted groups. The Phase 4 Verification Block's `SI constraint binding` row quotes each verification design's measurements and the assembly's sorted groups.

### Silent-drop patterns (CRITICAL)

A bare net or topology expression builds with `status: ok` and passes every JITX-side check but produces a **wrong netlist**, because the Python expression evaluates and is then immediately discarded. The design looks correct from the build but isn't.

JITX warns for *some* lost objects (you'll see `WARNING:jitx._structural:Reference to structural object <Class> at <file>:<line> lost during instantiation, it likely needs to be assigned to an object` for unassigned constraint objects and similar structural classes), but **the warning does not cover bare net expressions** (`+` between ports), which is exactly where this trap is easiest to fall into. Treat all such warnings as errors, and code review for the pattern below regardless.

A passive held only in a local variable, or constructed inline inside a net, is not silent: once its ports join a net, `jitx build` fails with `Unable to map local reference ..., parent <Circuit> is not an ancestor of child <Port>`, which a `TestCase` that only instantiates the design misses. Assign it to an attribute on `self` (`self.r_nrst = Resistor(resistance=10e3 * ohm)`). A passive whose ports join nothing builds with the `lost during instantiation` warning above.

#### Bare net expressions

```python
# WRONG — the Net object is built and discarded; no connection in the netlist.
self.usb.A6 + self.usb.B6                          # bare `+`

# RIGHT: assign to a `self.<name>` attribute named for the signal; the field
# name becomes the net name (jitx-circuit-builder, Nets). `self += a + b` also
# connects, but exports under an internal name.
self.USB_DP = self.usb.A6 + self.usb.B6            # named net
```

The trap is that the *expression evaluates without error* — Python sees `port_a + port_b` as `Net.__add__`, which returns a `Net` object, which Python then drops because nothing held a reference to it. No exception, no warning at parse time, and JITX has no way to recover the Net once it's been garbage-collected.

### Editor-side coverage

Configure the editor's Python language server to surface unused-expression warnings — this catches bare `+` / `>>` expressions before any build runs. Recommended:

- **Ruff** (works in any editor): enable rule `B018` ("Found useless expression") which flags top-level expressions whose return value is discarded. Add to `pyproject.toml`:
  ```toml
  [tool.ruff.lint]
  extend-select = ["B018"]
  ```
- **Pyright / Pylance**: enable `reportUnusedExpression = "warning"` (or `"error"`) in `pyrightconfig.json` (also picked up by the VS Code Python extension when present).
- **Pyflakes**: emits `Statement seems to have no effect` by default, which also catches bare `+` expressions.

These checks are cheap, and any extra signal during code review is worth turning on.

### Exit Gate: Phase 3 → Phase 3b

- [ ] `python scripts/check.py <ns>/ --build <ns>.main.Design` reports `PASS` for every check
- [ ] All nets connected (no floating ports on instantiated circuits)
- [ ] Power tree complete (every load rail connected to a regulator output)
- [ ] All require() calls have matching provides
- [ ] `GroundSymbol` on GND net, `PowerSymbol` on every power rail
- [ ] SI constraints applied **at this level** (not inside subcircuits) for every protocol with impedance/timing requirements
- [ ] Every SI constraint matches its interface's accepted verification design in
      constraint class, parameters, routing structure, Topology ends and pin
      models; the assembly acceptance block cites the parity evidence per
      [SI verification designs (CRITICAL)](#si-verification-designs-critical)
- [ ] `python -m <ns>.designs.check_si_main` run on the assembly and every SI group sorted per [SI verification designs (CRITICAL)](#si-verification-designs-critical): unrouted texts recorded only on constraints whose path has no copper, routed constraints held to the verification-design bar, and no text that blocks wherever it appears. The gate block records this in its `SI design issues dispositioned` row
- [ ] **No `Reference to structural object … lost during instantiation` warnings in the build output**: every structural object stored on `self`; no bare `+` expressions (see [Silent-drop patterns (CRITICAL)](#silent-drop-patterns-critical))
- [ ] `ReferencePlanes(...)` context wraps all constraint applications
- [ ] Board geometry defined (shape, mounting holes, pours)
- [ ] Passive query defaults (`CapacitorQuery`, `ResistorQuery`, `InductorQuery`) set in the Design class body to match the design's manufacturing path and circuit role, filtering only on columns the approved-parts list has, with per-circuit overrides documented for any specialty parts (HV, RF, bulk, precision, hand-build). The gate is the resolved parts, not the source: check the resolved package of each passive against the declared assembly capability, because a design with no query at all also builds clean.
- [ ] **Default design rules set on Design class**: the four canonical rules are present on `self.rules`, values calibrated to the substrate's fab floors (see [Default design rules (set on the Design class)](#default-design-rules-set-on-the-design-class) and the `jitx-layout-constraints` skill)
- [ ] The `grep gates` summary line reports 0 hard-fail hits; review-required hits are dispositioned

**Emit the `Gate: Phase 3 → Phase 3b` block** from `references/completion-blocks.md` before advancing.

---

## Phase 3b: Design Review and Loopback

**Who**: orchestrator spawns a **read-only audit agent** (critic only, editing nothing at all, including the datasheet spec notes), then separately spawns fix agents for issues found.

Each subcircuit was designed in isolation. Now review the assembled design as a system. **Do not proceed to Phase 4 with known electrical errors.**

### Audit Structure

Spawn a sub-agent to perform the design-level audit. The audit agent reads code and the datasheet PDFs and **edits nothing**. It reads the PDFs and not the spec notes (CD-1). Where a note and the datasheet disagree, the note is the defect. It runs in its own context, so the pages cost the orchestrator nothing. It produces a **Phase 3b Audit Block** with issues classified as CRITICAL / WARNING / NOTE; see the template in [Phase 3b Design Audit Block (complete-board only)](completion-blocks.md#phase-3b-design-audit-block-complete-board-only).

**After the same-model audit, attempt the bounded outside-voice fan-out (codex by default)
defined in `references/outside-voice-review.md`.** The attempt is mandatory for
complete-board tier. It runs one narrow pass per accepted trigger-list task plus
one cross-cutting power/arithmetic pass, with separate outputs. A pass that
produces no output is recorded as `skipped: <reason>`; it carries no findings, and the Phase 3b → 4 gate blocks until the user explicitly approves proceeding without it. Any
CRITICAL/WARNING finding from a completed pass makes the combined verdict
`issues-pending` even if the same-model audit said `clean`.

Before the audit runs, the orchestrator must have already dispatched and accepted fixes for the build-time silent-drop patterns documented in [Silent-drop patterns (CRITICAL)](#silent-drop-patterns-critical). Those bugs build with `status: ok` but produce a wrong design, and the audit agent's datasheet-comparison passes assume the netlist matches the source. JITX emits a `Reference to structural object … lost during instantiation` warning for some of these cases (constraint and similar structural classes), but not for bare net expressions. Handle both manually.

The audit runs four passes:

#### Pass 1: Circuit vs Datasheet Application Schematic

For each major IC circuit, open the datasheet's typical application schematic and compare component-by-component. Count from the datasheet, not from the spec note; a count taken from the note cannot catch a component the note itself omitted.
- Count external components in the datasheet. Count components in the code. Flag any missing.
- Check passive values match datasheet recommendations (cap values, resistor values, inductor values).
- Check component types match (e.g., datasheet says 0.22uF bootstrap but code has 0.1uF).
- Where the datasheet and `datasheets/<MPN>.spec.md` disagree, raise it as a finding against the note.
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

### Loopback

After the audit report, the orchestrator (not the audit agent) decides what to fix:

- **CRITICAL issues**: must fix before Phase 4. Spawn a separate sub-agent for each fix with the specific issue and datasheet reference.
- **WARNING issues**: should fix. Spawn fix agents.
- **NOTE issues**: document for the user; spawn a fix sub-agent if a fix is straightforward.

After fixes, **re-run the audit** to verify the fixes didn't introduce new issues and the original issues are resolved. Do not skip the re-audit.

For major redirections (bus contention needing new ICs, missing power rails, architecture changes), update ARCHITECTURE.md and PLAN.md, add new tasks, and go back to the appropriate phase.

Do not accept "noted for future refactoring" — if it's broken, fix it now.

### Exit Gate: Phase 3b → Phase 4

- [ ] Audit found no CRITICAL or WARNING issues (or all were fixed and re-audited)
- [ ] Outside-voice attempts record completed and skipped counts; every skipped
      pass has a reason and the user's explicit approval to proceed quoted (else the
      verdict is block), and every completed-pass finding has a disposition
- [ ] Every high-speed interface has SI constraints applied and functional: applied in the assembly, each constraint meeting the bar for its routing state, and functional because its interface's verification design passes (see [SI verification designs (CRITICAL)](#si-verification-designs-critical))
- [ ] PLAN.md updated with all rework tasks completed

**Emit the `Gate: Phase 3b → Phase 4` block** from `references/completion-blocks.md` before advancing. The gate references the Phase 3b audit block (in the same file), which the read-only audit agent emits during Phase 3b.

---

## Phase 4: Build + Verify + Iterate

**Who**: orchestrator or single agent

### Phase 4 Process

1. Run the parts gate first (base `jitx` skill, Step 2; https://docs.jitx.com/en/latest/essentials/design/parts.html): `jitx build <design>` and `jitx design export parts-check <design> --fail all` must pass, and no MPN the final build resolved (read as in Phase 0 "Approved passives") may start with `IDEAL-` (`ideal` stays in the chain, and the parts check passes an ideal part). When PLAN.md `Data Sources` records the example stand-in, the gate also lists each of those MPNs with the user's approval quoted, or the user's list has replaced the stand-in; otherwise it is a blocking item. Approved parts can change footprints, so every later check runs on the approved parts. An `IDEAL-` MPN or a `no part found` goes to the user, not to a fix sub-agent: ask for the approved part, and change a value or rating only with the user's sign-off and the affected circuit recomputed.
2. Run the full verification command: `python scripts/check.py <ns>/ --build <ns>.main.Design`
3. Check output for:
   - Every summary line reports `PASS`: proceed to verification
   - Any `FAIL` or `ERROR`: read the full tool output, dispatch a fix sub-agent, review its acceptance block, and re-run the command
4. Run each verification design's SI check (`python -m <ns>.designs.check_si_<iface>`) and the assembly's (`python -m <ns>.designs.check_si_main`), and apply [SI verification designs (CRITICAL)](#si-verification-designs-critical): each verification design passes, and each assembly constraint meets the bar for its routing state with no blocking line. Read compliance from the assembly's own `group.satisfied`. A constraint whose path has no route on the assembly has no compliance measurement: its `SI constraints` row reads `not measured: unrouted`, and the block lists the Deferred item `SI compliance pending routing: rerun python -m <ns>.designs.check_si_main after routing`, which goes to the user. Rerun after any change to routing, a pin model or an SI constraint.
5. Open the popout viewer (`jitx ui open --board --design <ns>.main.Design` and `jitx ui open --schematic --design <ns>.main.Design`) and verify:
   - Schematic: all connections present, symbols readable
   - Board: components placed (or floating), no overlaps
   - Issues List: SI constraints satisfied or flagged
   - DRC: clean or flagged
6. Iterate:
   - Build errors → dispatch a code fix, review, and re-run the verification command
   - DRC violations → dispatch a clearance or routing-structure fix
   - SI constraint failures → dispatch parameter and routing-structure review
   - A verification design that does not pass, or an assembly constraint below the bar for its routing state: dispatch a fix to the owning `ver-` task, module or assembly, then rerun step 4
   - Missing connections → trace back to Phase 2/3 and dispatch the fix

7. **Emit the Phase 4 Verification Block** from `references/completion-blocks.md`. The block requires the parts gate field and JITX UI / Issues List / DRC / SI / placement-overlap rows with explicit pass/fail status, or a `not run` reason for any row the environment can't run (e.g. headless CI). PLAN reconciliation, deferred items, and blocking items also belong in the block. **Blocking items must be empty for `Verdict: done`.**

### Completion Criteria

The Phase 4 Verification Block is the completion criterion. The block enforces:

- [ ] Parts gate passed: `parts-check --fail all` exit 0, no `IDEAL-` MPN (or a user-approved deferral), and, when the list is the example stand-in, every MPN the final build resolved (Phase 0 "Approved passives") listed with the user's approval quoted (or the user's list in its place)
- [ ] `status: ok` on final build
- [ ] JITX UI verification rows pass or are `not run` with reason
- [ ] Issues List, DRC, SI rows have status (or `not run` with reason)
- [ ] `SI constraint binding` row: every verification design passes and each assembly constraint meets the bar for its routing state, per [SI verification designs (CRITICAL)](#si-verification-designs-critical)
- [ ] Every assembly constraint read `not measured: unrouted` has the `SI compliance pending routing` Deferred item, shown to the user
- [ ] All PLAN.md tasks accepted; all gate blocks emitted; Phase 3b audit verdict `clean`
- [ ] No blocking items
- [ ] User-approved deferrals documented

A "builds clean" claim alone is not the criterion — the block is.

---

## Session Resumption

If the orchestrator session is interrupted, a new session can resume:

1. Read PLAN.md to see task statuses, gate outcomes, deferrals, blockers, and modification history.
2. Read ARCHITECTURE.md for the design context.
3. Identify the current phase based on task statuses.
4. Continue from where the previous session left off.

This is why PLAN.md must be kept up-to-date with every status change.

---

## Recovery Procedures

### Missing-Dependency Escalation

When a required dependency is missing — `jitxlib` doesn't import, the target substrate package isn't available, the datasheet PDF the user said they'd provide hasn't arrived — that is a **blocker**, not a license to drop the design requirement.

A failure seen in practice: `jitxlib` failed to import, so the agent silently dropped controlled-impedance routing from the design rather than fix the environment. **Do not do this.**

Concrete rule:

1. **Surface the missing dependency to the user immediately.** Name what's missing and what work it blocks.
2. **Do not substitute a lower-fidelity design as a workaround**: no removing SI constraints because the SI module didn't load, no swapping a custom substrate for a fallback because the predefined package didn't import.
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
4. Update both statuses with `python scripts/plan_status.py <task-id> <status>`.
