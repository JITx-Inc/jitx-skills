---
name: jitx
description: Base skill for JITX hardware design workflow. Use for JITX Python projects, PCB design, circuit creation, and build commands. Use when the user asks to "build my JITX design", "set up JITX environment", "create a circuit", "build a complete board", "design a PCB from requirements", or "create a full JITX project". For multi-component designs (3+ components, substrate, circuits), invoke the Project Builder workflow for orchestrated parallel agent execution with quality gates. CRITICAL - If user asks to create/model/generate a component or mentions a part number (NE555, LM1117, RP2040, etc.), immediately invoke jitx-component-modeler subskill. If user asks to create a substrate, stackup, via definitions, or routing structures, invoke jitx-substrate-modeler subskill.
---

# JITX Workflow Skill

Base skill for JITX hardware design automation. JITX is a Python framework for programmatic PCB design.

## Environment Setup

Before any JITX work, check and fix the environment automatically:

```bash
# Check for JITX project
if [ ! -f pyproject.toml ] || ! grep -q "jitx" pyproject.toml; then
  echo "ERROR: Not a JITX project (no pyproject.toml with jitx dependency)"
  exit 1
fi

# Create venv if missing, install deps
if [ ! -d .venv ]; then
  python3 -m venv .venv
  source .venv/bin/activate
  pip install -e . --quiet 2>&1 | tail -1
  pip install ruff --quiet 2>&1 | tail -1
else
  source .venv/bin/activate
fi

# Verify (don't check __version__ — not present in all JITX versions)
python -c "import jitx; print('JITX ready')"
```

Only install deps on first run (venv creation). Skip `pip install` on subsequent runs — it's slow and noisy. Don't ask user to do manual setup.

## Python Linting Setup (Recommended)

Pyright is available for Python type checking:

Install:
```bash
pip install pyright
```
or
```bash
npm install -g pyright
```

**Verify:** Ask Claude to "check for type errors" or run manually:
```bash
pyright src/
```

## JITX Python Code Conventions

Durable rules for JITX Python user code. The first three don'ts protect JITX's internal instantiation tracking; the rest are standard Python encapsulation discipline.

### Don'ts

- **No `setattr` / `getattr`.** They exist for very narrow scenarios; JITX user code is not one of them. Use lists/dicts when you need to store a programmatic collection on `self`.
- **No dynamic types at runtime.** Do not call `type(...)` to construct a new class on the fly. This breaks JITX's internal instantiation tracking. Express the same intent with parameterized classes — instantiate, don't synthesize.
- **No subclassing JITX classes inside functions or methods.** Same instantiation-tracking failure mode. Declare jitx-class subclasses at module scope (nested at class-body scope is fine).
- **No `type()` for type checks.** Use `isinstance` so subclasses are handled correctly.
- **No access to double-underscore (private) members.** They are private for a reason.
- **No use of leading-underscore packages, modules, or functions from elsewhere.** The Python "protected" convention applies. The single exception is a method calling another method on the same class.

### Dos

- **Run pyright** for type checking and language-server diagnostics.
- **Run `ruff check`** for common-mistake analysis (the `ruff` package is already installed by the environment-setup step).
- **Run `ruff format`** for style consistency.

## Running JITX Designs

```bash
# Build a specific design
python -m jitx build <module.path.DesignClass>

# Build all designs in project
python -m jitx build-all
```

**Success output:** `status: ok`
**Error output:** Python traceback or `status: error`

**Output files** (in `designs/<design_name>/`):
- `cache/netlist.json` - JSON netlist for verification
- `cache/design-explorer.json` - Design hierarchy
- `design-info/stable.design` - Design snapshot

## Project Structure

Standard JITX project layout:
```
project/
├── pyproject.toml          # Project config with JITX deps
├── src/<namespace>/
│   ├── components/         # Custom component definitions
│   │   ├── <category>/     # mcus, connectors, power, etc.
│   │   │   └── <mfr>_<mpn>.py
│   │   └── __init__.py
│   ├── circuits/           # Reusable circuit blocks
│   └── designs/            # Top-level designs
├── designs/                # Build output directory
└── .venv/                  # Virtual environment
```

## First: Decide the Workflow

After environment setup, decide which workflow to use:

- **Building a complete board** (multiple components, circuits, substrate) → Use the **Project Builder Workflow** below. Start with Phase 0: create PLAN.md and ARCHITECTURE.md before writing any code.
- **Single task** (one component, one circuit, one substrate) → Invoke the appropriate subskill directly.

Do NOT skip the planning phase for complete board designs. Do not start exploring libraries or writing code until PLAN.md exists.

## Core Concepts

**Circuit**: Python class inheriting from `jitx.Circuit`. Contains components and connections.

**Component**: Python class inheriting from `jitx.Component`. Defines ports, landpattern, symbol.

**Design**: Python class inheriting from design base (e.g., `SampleDesign`). Top-level entry point.

For net wiring, passives, and circuit patterns, invoke the `jitx-circuit-builder` subskill.

## Project Builder Workflow

For building complete JITX designs from requirements — multiple components, substrate, circuits, and constraints assembled into a working board. Use this when the design involves 3+ components with a substrate and interconnected circuits.

### Phases

| Phase | What | Parallelism |
|-------|------|-------------|
| 0 | Requirements analysis, decompose into tasks, create PLAN.md | Orchestrator only |
| 1 | Model substrate + all components | Fully parallel sub-agents |
| 2 | SI constraints, pin assignment, circuit wiring | Clustered parallel |
| 3 | Top-level assembly (instantiate, connect, constrain) | Single agent |
| 3b | **Design-level analysis + loopback** (voltage domains, bus contention, missing components, SI) | Orchestrator — loops back to fix upstream |
| 4 | Build, verify DRC + SI, iterate on failures | Single agent |

For full phase details and gate criteria: read `references/project-builder-flow.md`
For how to decompose requirements into tasks: read `references/decomposition-guide.md`
For PLAN.md format: read `references/plan-template.md`
For ARCHITECTURE.md format: read `references/architecture-template.md`

### Parallel Build Safety

JITX uses a single WebSocket backend — concurrent builds collide. When running parallel sub-agents, use the build lock wrapper:

```bash
python runner/build_lock.py <module.path.DesignClass>
```

Copy `scripts/build_lock.py` from this skill into the project's `runner/` directory. Sub-agents call this instead of `jitx build` directly. The lock serializes builds via `fcntl.flock`; parallel agents wait their turn.

### Two-Tier Quality System

Sub-agent work goes through TWO quality checks before being accepted:

**1. Sub-Agent Self-Validation ("Think Twice")**

After initial implementation, sub-agents MUST stop and run the domain-specific checklist against the datasheet before returning. This forced second pass typically catches 3-5 missed details (floating enable pins, missing thermal pads, wrong output types, forgotten decoupling). Sub-agents return a self-evaluation report documenting what they checked and fixed.

**2. Orchestrator Acceptance Review**

The orchestrator does NOT blindly trust self-evaluation. For each returned task:
- Read the generated code for obvious issues
- Spot-check high-risk checklist items independently
- Verify interface compatibility with downstream tasks
- Issue verdict: **accept** / **rework** (send back with specific issues) / **reject** (replan)

Phase gates only open when ALL tasks in the phase are `accepted` by the orchestrator.

For the full protocol: read `references/task-execution.md`
For domain checklists: read `references/domain-checklists.md`

### Exit Gates

| Gate | Key Criteria |
|------|-------------|
| 0 → 1 | PLAN.md created with all tasks, data source audit approved, user approved plan |
| 1 → 2 | All components + substrate build individually, acceptance reviews passed |
| 2 → 3 | All circuits build, constraint classes valid, provide/require interfaces consistent |
| 3 → 3b | Top-level assembles, all nets connected, power tree complete |
| 3b → 4 | **Design-level analysis passed**: voltage domains correct, no bus contention, no missing components, SI constraints functional. All blocking issues fixed via loopback. |

Do NOT proceed past a gate if any task has unresolved failures. Fix upstream before moving downstream.

### Parts Data and Footprint Conversion

Claude selects parts based on engineering requirements first. Data for each component comes from the **user-approved data source plan** (see Phase 0 data audit).

**Data sources (in priority order):**
1. **User-provided** — datasheets, KiCad footprints, or specs the user supplies directly
2. **JITX generators** — standard packages (QFN, SOIC, BGA, SOT, SON, QFP) with dimensions from datasheets
3. **LCSC/EasyEDA** (opt-in only — ask user before using) — if user explicitly approves, install `parts2jitx` into the project venv:
   ```bash
   pip install parts2jitx
   ```
   Then use:
   - **`parts2jitx-lcsc <LCSC_ID>`** — stock, pricing, datasheet URL, KiCad footprint download
   - **`parts2jitx-kicad <file.kicad_mod>`** — deterministic KiCad-to-JITX footprint conversion
   
   Do not use LCSC/EasyEDA data without user approval. Commercial users may have licensing concerns.

For non-standard packages (connectors, RF modules): convert from a `.kicad_mod` file (user-provided or downloaded). **NEVER hand-craft pad positions** — use the converter. Standard packages use built-in JITX generators. All symbols use `BoxSymbol`.

For details: read `references/parts-sourcing.md`

### Shared State Documents

The orchestrator creates and maintains these in the project root:

- **PLAN.md** — Task registry with status, dependencies, and acceptance verdicts. Single source of truth. Enables session resumption.
- **ARCHITECTURE.md** — Power tree, interface map, module hierarchy. Gives sub-agents the big picture.

## Subskills

### Component Modeler (`jitx-component-modeler`)

**ALWAYS invoke this subskill** when user:
- Provides a datasheet PDF (file path or URL)
- Asks to "create a component", "model a part", or "add a component"
- Mentions specific part numbers (e.g., "NE555", "RP2040", "LM1117")

**How to invoke:** Use the Skill tool with `skill: "jitx-skills:jitx-component-modeler"`

Supports:
- BGA, QFN, SOIC, SON, SOT packages
- Multi-unit symbols and thermal pads
- Complex pin mappings
- Batch component creation

**Do NOT attempt component generation without invoking this subskill** - it contains critical patterns, dimension mappings, and code templates.

### Circuit Builder (`jitx-circuit-builder`)

**Invoke this subskill** when user asks to:
- "Wire up" or "connect" components
- Build application circuits from datasheets
- Work with passives (resistors, capacitors, inductors)
- Set up power connections or decoupling
- Add copper pours or geometry

**How to invoke:** Use the Skill tool with `skill: "jitx-skills:jitx-circuit-builder"`

Covers:
- Circuit class structure and wiring
- Passives from jitxlib with query refinement
- Voltage divider solver
- Pours and copper geometry
- Component placement

For provide/require pin assignment patterns, use `jitx-pin-assignment` instead.

### Substrate Modeler (`jitx-substrate-modeler`)

**Ask the user which fab house they are targeting.** If they confirm JLCPCB, predefined substrates from `jitxlib.jlcpcb` are available:
- `JLC04161H_1080` — 4-layer, 1080 prepreg, RS_50/DRS_90/DRS_100
- `JLC04161H_7628` — 4-layer, 7628 prepreg, RS_50/DRS_90/DRS_100
- `JLC06161H_7628` — 6-layer, 7628 prepreg, RS_50/DRS_100

Import: `from jitxlib.jlcpcb import JLC04161H_1080`. These include stackup, fab rules, 11 via definitions, and routing structures.

**Invoke this subskill** to create a custom substrate (the default path unless user opts into a predefined one):
- User has not confirmed JLCPCB as fab house
- Non-FR-4 materials (Rogers, Megtron)
- Non-standard layer count or impedance targets
- Additional routing structures beyond predefined

**How to invoke:** Use the Skill tool with `skill: "jitx-skills:jitx-substrate-modeler"`

Covers:
- Stackup and Symmetric layer definitions
- Material properties (Dielectric, Conductor)
- All via types (through-hole, laser micro, stacked, blind, buried, backdrilled)
- RoutingStructure with NeckDown, via fencing, geometry, reference planes
- DifferentialRoutingStructure with pair spacing and uncoupled regions
- FabricationConstraints for manufacturing rules
- Design constraint rules with Tags

### Interconnect Constraints (`jitx-interconnect-constraints`)

**Invoke this subskill** when user asks to:
- Apply signal integrity constraints to signals
- Use the `>>` topology operator for ordered routing
- Constrain differential pairs (skew, loss, impedance)
- Match timing between bus signals (length matching)
- Define pin models (BridgingPinModel, TerminatingPinModel)
- Set up protocol-specific constraints (PCIe, USB, DisplayPort, RGMII, Ethernet, DDR)
- Use ReferencePlanes for routing structure constraints
- Build custom SignalConstraint subclasses

**How to invoke:** Use the Skill tool with `skill: "jitx-skills:jitx-interconnect-constraints"`

Covers:
- TopologyNet (`>>` operator) vs Net (`+` operator)
- Constrain, ConstrainDiffPair, ConstrainReferenceDifference
- DiffPairConstraint for reusable diff pair constraints
- SignalConstraint[T] protocol constraint pattern
- PinModel, BridgingPinModel, TerminatingPinModel
- ReferencePlanes context manager
- Built-in protocol constraints from jitxlib

### Pin Assignment (`jitx-pin-assignment`)

**Invoke this subskill** when user asks to:
- Model flexible pin assignment (provide/require beyond basics)
- Implement peripheral muxing on shared pins
- Allow DiffPair P/N polarity swapping
- Configure PCIe lane swapping or width variants
- Enable DDR byte lane or bit swapping
- Use `@provide.subset_of` or programmatic `Provide`
- Build hierarchical provider composition
- Apply topology (`>>`) and SI constraints on pin-assigned ports
- Combine pin assignment with `ConstrainDiffPair` or `ConstrainReferenceDifference` for high-speed protocols

**How to invoke:** Use the Skill tool with `skill: "jitx-skills:jitx-pin-assignment"`

Covers:
- `@provide`, `@provide.one_of`, `@provide.subset_of` decorators
- Programmatic `Provide().one_of()`, `Provide().all_of()`, `Provide().subset_of()`
- Hierarchical provider composition with `self.require()` inside `@provide`
- Protocol-specific pin flexibility rules (DiffPair P/N, PCIe lanes, DDR4 byte/bit)
- Topology and constraint composition on pin-assigned ports
- `DiffPairConstraint` and `ConstrainReferenceDifference` with `require()`

## Documentation Lookup

JITX docs: `https://docs.jitx.com/en/latest/`
or LLM-friendly access at `https://docs.jitx.com/llms.txt`

**When to fetch docs:**
- Unfamiliar API class or method → fetch API reference page
- Protocol wiring (USB, Ethernet, I2C) → fetch protocol docs
- Landpattern generator parameters → fetch generator docs
- UI commands or shortcuts → fetch UI command page
- Design patterns (pin assignment, SI constraints) → fetch essentials page

**How to look up:**
1. Read `references/docs-index.md` to find the right page URL
2. Use WebFetch to retrieve the page content
3. Apply the information to the task

**Common lookups:**

| Topic | Doc Path |
|-------|----------|
| Pin assignment | `essentials/design/pin_assignment.html` |
| Design hierarchy | `essentials/design/design-hierarchy.html` |
| Autorouter | `essentials/physical_design/autorouter.html` |
| SI constraints | `essentials/SI/constraints.html` |
| SI topology | `essentials/SI/topology.html` |
| SI API reference | `api/jitx.si.html` |
| Component class | `api/jitx.component.html` |
| Circuit class | `api/jitx.circuit.html` |
| QFN landpattern | `jitxlib-standard/jitxlib.landpatterns.generators.qfn.html` |
| BGA landpattern | `jitxlib-standard/jitxlib.landpatterns.generators.bga.html` |
| USB protocol | `jitxlib-standard/jitxlib.protocols.usb.html` |
| Box symbol | `jitxlib-standard/jitxlib.symbols.box.html` |

For complete index with all pages, see `references/docs-index.md`.

## Formatting

Run `ruff format` on generated code to keep it consistent:

```bash
ruff format path/to/file.py
```

## Quick Reference

| Task | Command/Pattern |
|------|-----------------|
| Build design | `python -m jitx build module.Design` |
| Format code | `ruff format path/to/file.py` |