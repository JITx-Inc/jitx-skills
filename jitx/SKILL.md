---
name: jitx
description: This skill should be used when the user asks to "build my JITX design", "set up JITX environment", "create a circuit", or works with JITX Python projects for PCB design, circuit creation, and build commands. CRITICAL - If user asks to create/model/generate a component or mentions a part number (NE555, LM1117, RP2040, etc.), immediately invoke jitx-component-modeler subskill. If user asks to create a substrate, stackup, via definitions, or routing structures, invoke jitx-substrate-modeler subskill.
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

# Create venv if missing
if [ ! -d .venv ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi

# Activate venv and install deps
source .venv/bin/activate
pip install -e . --quiet

# Install ruff for code formatting
pip install ruff --quiet

# Verify
python -c "import jitx; print(f'JITX ready: {jitx.__version__}')"
```

Run this automatically when starting JITX work. Don't ask user to do manual setup.

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

## Core Concepts

**Circuit**: Python class inheriting from `jitx.Circuit`. Contains components and connections.

**Component**: Python class inheriting from `jitx.Component`. Defines ports, landpattern, symbol.

**Design**: Python class inheriting from design base (e.g., `SampleDesign`). Top-level entry point.

For net wiring, passives, and circuit patterns, invoke the `jitx-circuit-builder` subskill.

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

**Invoke this subskill** when user asks to:
- Create a substrate or define a stackup
- Add via definitions (laser, mechanical, backdrilled, blind, buried)
- Set up routing structures or impedance control
- Define differential pair routing
- Set fabrication rules or constraints
- Model a PCB layer structure

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