# JITX Skills

Claude Code skills for JITX hardware design automation. These skills help Claude work effectively with JITX Python projects for PCB design, circuit creation, and component modeling.

## Installation

Inside Claude Code, run these slash commands:

```
/plugin marketplace add JITx-Inc/jitx-skills
/plugin install jitx-skills@JITx-Inc/jitx-skills
```

## Skills

### jitx (Base Skill)

Base workflow skill for JITX projects. Triggers on any JITX-related task and provides:

- Automatic environment setup (venv creation, dependency installation)
- Build commands for designs
- Project structure guidance
- Navigation to specialized subskills

**Example triggers:**
- "Build my JITX design"
- "Set up JITX environment"
- "Create a circuit for..."

### jitx-component-modeler

Generate JITX Python component code from datasheets. Supports:

- **Package types:** BGA, QFN, SOIC, SON, SOT
- **Features:** Multi-unit symbols, thermal pads, complex pin mappings
- **Batch creation:** Organized component folder structure

**Example triggers:**
- "Create a JITX component from this datasheet"
- "Model the RP2040 for my project"
- "Add an LDO component from the TI datasheet"

## Project Structure

```
jitx-skills/
├── jitx/                      # Base JITX workflow skill
│   └── SKILL.md
├── jitx-component-modeler/    # Component generation skill
│   ├── SKILL.md
│   └── scripts/
│       └── extract_pages.py   # PDF extraction utility
└── .claude-plugin/
    └── marketplace.json
```

## Requirements

- Follow `LLM_RULES.md` for tiered (Draft vs Production) LLM workflows.
- A JITX Python project (with `pyproject.toml` containing jitx dependency)
- Python 3.12+
- For datasheet processing: `pip install pymupdf`

## Usage Examples

### Generate a Component from Datasheet

```
User: Create a JITX component for the NE555 timer from this datasheet
Claude: [Uses jitx-component-modeler skill to generate component code]
```

### Build a Design

```
User: Build my power supply design
Claude: [Uses jitx skill to set up environment and run build]
```

### Extract Datasheet Pages

The `extract_pages.py` script helps extract relevant pages from large datasheets:

```bash
# Find pages with package info
python extract_pages.py datasheet.pdf --find "pinout" "dimension" "package"

# Extract specific pages
python extract_pages.py datasheet.pdf --pages 10 11 12 -o extract.pdf
```

## Supported Package Generators

| Package Type | Generator | Use Case |
|-------------|-----------|----------|
| SOT-23 | `SOT23_3`, `SOT23_5`, `SOT23_6` | Small transistors, simple ICs |
| SOIC | `SOIC` | Standard gull-wing ICs |
| SON | `SON` | No-lead 2-sided packages |
| QFN | `QFN` | 4-sided no-lead packages |
| QFP | `QFP` | 4-sided gull-wing packages |
| BGA | `BGA` | Ball grid arrays |

## Contributing

Skills follow the Claude Code skill format with:

- `SKILL.md` containing frontmatter (name, description) and instructions
- Optional `scripts/` for executable utilities
- Optional `references/` for documentation loaded on demand
- Optional `assets/` for templates and resources
