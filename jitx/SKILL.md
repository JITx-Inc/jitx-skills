---
name: jitx
description: Base skill for JITX hardware design workflow. Use when working with JITX Python projects for PCB design, circuit creation, or component modeling. Provides environment setup verification, build commands, project structure guidance, and navigation to specialized subskills (component-modeler, etc.). Triggers on any JITX-related task or when user mentions JITX, circuits, PCB design, or hardware.
---

# JITX Workflow Skill

Base skill for JITX hardware design automation. JITX is a Python framework for programmatic PCB design.

## Environment Verification

Before any JITX work, verify the environment:

```bash
# Check Python version (requires 3.12+)
python --version

# Check if in a JITX project (has pyproject.toml with jitx dependency)
grep -q "jitx" pyproject.toml 2>/dev/null && echo "JITX project detected"

# Check virtual environment
which python | grep -q ".venv" && echo "venv active" || echo "WARNING: activate venv first"

# Verify JITX is installed
python -c "import jitx; print(f'JITX version: {jitx.__version__}')" 2>/dev/null || echo "JITX not installed"
```

If environment issues exist, guide user to:
1. Activate venv: `source .venv/bin/activate`
2. Install dependencies: `pip install -e .`

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
Generate JITX component code from datasheets. Use for:
- Creating new component definitions from datasheets
- BGA, QFN, SOIC, SON, SOT packages
- Multi-unit symbols
- Complex pin mappings

### Coming Soon
- Circuit templates
- Design patterns
- Signal integrity constraints

## Documentation

- Docs: https://docs-testing.jitx.com/en/latest/
- Key areas: JITX Manual, Reference, Standard Library

## Quick Reference

| Task | Command/Pattern |
|------|-----------------|
| Build design | `python -m jitx build module.Design` |
| Check netlist | Read `designs/<name>/cache/netlist.json` |
| Verify ports | `from jitx.inspect import extract; extract(comp, Port)` |
| Verify pads | `extract(comp.landpattern, Pad)` |
