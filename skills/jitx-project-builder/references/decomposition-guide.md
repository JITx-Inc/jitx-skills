# Decomposition Guide

## Step 0: Requirements Lock

Before proposing subsystems or parts, ask the user for every item in the plan template's `Requirements Lock` and record each row as `plan-template.md` sets out.

With no fab named, never assume the fab house, assembly tier or parts channel. Ask once, in one Open Questions row owned by the user, for whichever of the three the user did not state. Until it is answered, the fab house and assembly tier rows read `open: OQ-n`, never an assumed or recommended value, and the tasks they gate read `blocked: OQ-n`: the substrate task, every task needing the stackup, and every part choice the assembly tier constrains (`parts-sourcing.md` "Part Selection"). The question may offer JLCPCB as one option, since it has predefined substrates and an export from parts to the order packet (`jitx-jlcpcb`), beside "a fab and assembler you already use"; never choose it for the user, list it first or call it the default. With a fab named, the assembly tier and parts channel may follow from it as `assuming: X`, the channel written in the assembly tier row; a channel the user stated goes there as `user-stated`.

The default trace width and clearance are the user's figures or come from a named row of the fab's sheet, and sit above the fab's minimum unless the user asks for the minimum: unruled copper routes at the minimum, which is for the pads that need it (an escape rule), not for the board. Unstated, the row reads `not specified — assuming: X`, X naming the sheet's standard-capability row where it has one, else 1.5 times its minimum, written as that factor (this workflow's margin, not a fab figure); show the user the assumption. With no fab named it reads `open: OQ-n` on the fab question and blocks no task of its own.

## Step 1: Subsystems to tasks

- Components: one task per IC; a regulator family from one manufacturer, or similar connectors, may share one. Passives come from the approved-parts list at circuit build time, with no component task.
- Substrate: always one task, blocked on the fab question while no fab is named. It selects a predefined class (JLCPCB's: `jitx-jlcpcb`), or models one with `jitx-substrate-modeler` for a fab without predefined substrates, a non-FR-4 material, an unusual layer count or impedance target, or a routing structure no predefined class has. SI constraints need routing structures; the densest package sets layers and via technology.
- Interfaces: a circuit task each, describing its ports as bundles in `Specifics` ("expose an I2S bundle port", never a signal list): individual ports defeat `require()` at the top level.
- SI constraints: a `cst-` task per protocol; pin flexibility on an MCU or FPGA: a `pin-` task; each constrained interface: a `ver-` task (`project-builder-flow.md` "SI verification designs").

## Step 2: Dependencies

Substrate and components depend on nothing and run in parallel. Constraints need the substrate's routing structures, pin-assignment wrappers their component, circuits their components and constraints, the assembly everything.

### Check the data flow, not just the declared edges

A task whose `Data` or `Specifics` names a decision another task makes ("the variant cir-04 picks") has an edge to it. Declare it, move the decision earlier, or make it an Open Question that blocks both; otherwise two sub-agents wait on each other.

## Step 3: Parametric tasks

A parametric or generator task (BGA ballout, deskew geometry, antipad fence, N-lane fanout, per-layer table, repeating block) gets its architectural questions in its PLAN.md task, and the answers once in ARCHITECTURE.md `Object-Hierarchy Decisions`, before code exists:

- How are N parallel things structured: `list[T]`, `dict[StructuralKey, T]` or a typed dataclass, not sibling attributes reached by `getattr(self, f"X_{i}")`?
- Where does substrate-shaped data live: on the substrate, not a design-level table?
- Are spec records needed, or are the JITX objects built directly? Default: directly; a frozen dataclass names its fields, never `dict[str, Any]`.

### Engineering Questions (circuit tasks only)

A question belongs on a circuit task only if the datasheet's application circuit does not answer it and no checklist the task names asks it. Write at most three, and none for a part whose application circuit settles everything. Each turns on a value or conflict the application circuit alone leaves open, for a USB PD sink (HUSB238):

```
- Does the HUSB238 need D+/D- connected? (Only for BC1.2; otherwise leave them open)
- Does the datasheet show an external PMOS on GATE? (Yes: include it)
- What I2C voltage domain does it use? (VIN level: it needs a level shifter to the 3.3 V MCU)
```

## Support circuitry

Every powered IC needs a task that owns its support circuitry: every external part its application circuit shows that no other task owns. Decoupling per supply pin, reset, boot straps, the clock source and unused-pin tie-offs recur; so do enable networks, reference filters, termination, compensation, sense and feedback dividers, and crystal load caps. Run the test against the datasheet, not this list. A power task does not cover it.

At the end of decomposition, walk the component list, not the task list: each part that takes a supply gets a named owning task, or "none needed, per <datasheet section>". The Phase 0 gate's `Support circuitry owned` criterion records that walk.

## Example: MCU board (STM32, sensor, USB)

```
Phase 1 (parallel):
  sub-01: 4-layer FR-4 substrate
  comp-01: STM32 MCU
  comp-02: USB-C connector
  comp-03: sensor IC

Phase 2:
  pin-01: MCU provides (GPIO, SPI, I2C, USB), depends on comp-01
  cir-01: LDO from VBUS, depends on comp-02
  cir-02: MCU support (per-VDD decoupling, NRST, boot straps, clock source), depends on comp-01
  cir-03: sensor interface (I2C, decoupling), depends on comp-01, comp-03
  cir-04: USB interface with ESD protection, depends on comp-01, comp-02

Phase 3: top-level assembly
Phase 4: build, verify, iterate
```
