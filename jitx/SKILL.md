---
name: jitx
description: Base skill for JITX hardware design workflow. Use for JITX Python projects, PCB design, circuit creation, and build commands. CRITICAL - If user asks to create/model/generate a component or mentions a part number (NE555, LM1117, RP2040, etc.), immediately invoke jitx-component-modeler subskill.
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

# Verify
python -c "import jitx; print(f'JITX ready: {jitx.__version__}')"
```

Run this automatically when starting JITX work. Don't ask user to do manual setup.

## IDE Setup (Recommended)

Install the Pyright LSP plugin for Python type checking:

```bash
claude plugin install pyright-lsp@claude-plugins-official
```

The plugin provides:
- Real-time type errors before running builds
- Autocomplete for JITX APIs (jitx, jitxlib, jitxstd)
- Import resolution and hover documentation

**Requires:** `pyright` or `pyright-langserver` installed:
```bash
pip install pyright
# or
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

**Net operators**:
- `+` : Unordered connection (add to net set)
- `>>` : Topology operator for ordered routing
- `self +=` : Add connections to circuit

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

### Coming Soon
- Circuit templates
- Design patterns
- Signal integrity constraints

## Documentation Lookup

JITX docs: `https://docs.jitx.com/en/latest/`

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
| Component class | `api/jitx.component.html` |
| Circuit class | `api/jitx.circuit.html` |
| QFN landpattern | `jitxlib-standard/jitxlib.landpatterns.generators.qfn.html` |
| BGA landpattern | `jitxlib-standard/jitxlib.landpatterns.generators.bga.html` |
| USB protocol | `jitxlib-standard/jitxlib.protocols.usb.html` |
| Box symbol | `jitxlib-standard/jitxlib.symbols.box.html` |

For complete index with all pages, see `references/docs-index.md`.

## Quick Reference

| Task | Command/Pattern |
|------|-----------------|
| Build design | `python -m jitx build module.Design` |