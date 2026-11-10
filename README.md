# JITX Skills

JITX hardware design automation skills for both Claude Code and Codex/GPT. The repo uses one shared `skills/` tree and platform-specific plugin manifests for each agent runtime.

## Installation

### Claude Code

Install from the Claude marketplace:

```text
/plugin marketplace add JITx-Inc/jitx-skills
/plugin install jitx-skills@jitx
```

For local development without installing from a marketplace:

```bash
claude --plugin-dir /absolute/path/to/jitx-skills
```

Claude plugin skills are namespaced. For example, invoke the base workflow with `/jitx-skills:jitx`.

### Codex / GPT

Codex uses `.codex-plugin/plugin.json` and the shared `skills/` directory. The repo ships its Codex marketplace at `.agents/plugins/marketplace.json`, so the repo itself is a marketplace named `jitx`.

This GitHub marketplace layout requires Codex CLI 0.142.0 or newer.

Install from GitHub:

```bash
codex plugin marketplace add JITx-Inc/jitx-skills
codex plugin add jitx-skills@jitx
```

For local development, point the marketplace at a checkout instead:

```bash
codex plugin marketplace add /absolute/path/to/jitx-skills
codex plugin add jitx-skills@jitx
```

Codex skills can be invoked explicitly with `$jitx`, `$jitx-component-modeler`, and the other skill names, or selected implicitly from the user request.

## Updating

From 1.8.x to 2.0.0: `jitx-physical-layout` is now `jitx-code-layout`, so invoke it by the new name in Claude Code and Codex. 2.0.0 also adds `jitx-interactive-layout` and `jitx-jlcpcb`. Projects that install `jitxexamples` move to 2.1.x (see Requirements).

Claude Code:

```text
/plugin marketplace update jitx
claude plugin update jitx-skills@jitx
```

Restart Claude Code or run `/reload-plugins` after local plugin edits. If you previously added this marketplace under the old `jitx-skills` name, migrate it with:

```text
/plugin marketplace remove jitx-skills
/plugin marketplace add JITx-Inc/jitx-skills
/plugin install jitx-skills@jitx
```

Codex/GPT:

```bash
codex plugin marketplace upgrade jitx
codex plugin add jitx-skills@jitx
```

For local-path marketplaces, update the checkout instead of running `marketplace upgrade` (it only refreshes Git snapshots). Then start a new thread so Codex reloads the skill list and manifest metadata.

## Skills

### jitx

Base workflow skill for JITX projects: install, the jitx CLI and runtime, building designs, the board and schematic viewers, code quality checks, design introspection, and navigation to specialized skills.

Example triggers:

- "Build my JITX design"
- "Set up JITX environment"
- "List every port in my design from Python"

### jitx-project-builder

Turn board requirements into a complete, verified JITX design: tier classification, PLAN.md and ARCHITECTURE.md, phased sub-agent work with exit gates, and the Phase 3b design audit.

Example triggers:

- "Create a full JITX project"
- "Design a PCB from these requirements"
- "Resume the board project, what's left in the task graph?"

### jitx-component-modeler

Generate JITX Python component code from datasheets, KiCad footprints, or user specifications.

Example triggers:

- "Create a JITX component from this datasheet"
- "Model the RP2040 for my project"
- "Add an LDO component from the TI datasheet"

### jitx-circuit-builder

Build JITX circuits with wiring, typed ports, hierarchy, passives, power connections, application circuits, and placement.

Example triggers:

- "Wire up a buck converter circuit"
- "Connect the MCU to sensors over I2C"
- "Add decoupling caps to all power pins"

### jitx-substrate-modeler

Model JITX substrates: stackups, materials, vias, routing structures, and fabrication constraints.

Example triggers:

- "Model a substrate from our fab's stackup report"
- "Define a 14-layer RF stackup"
- "Set up 100-ohm differential routing structure"

### jitx-code-layout

Write a fixed layout in code: relative placement, code-placed vias, code routes through control points, narrowing a route, length matching, pours, keepouts, copper and overlappable copper, and reading the realized layout back from the capture. Also sorts which control points stay in code and which a designer moves interactively.

Example triggers:

- "Draw an IFA antenna from code"
- "Create a net tie between AGND and DGND"
- "Route the BGA escape lanes from code"

### jitx-interactive-layout

Place and route in the open board layout from scripts run through `jitx design session` and `jitx design exec`. Placements, routes, vias, pair insertions and hull pours made this way stay editable in the board editor. Reads the result back through route status, design issues and skew margins.

Example triggers:

- "Place and route the buck converter in the open layout"
- "Fan out the BGA and route the DDR byte lanes interactively"
- "How much skew margin is left on the DQS pairs?"

### jitx-layout-constraints

Design rules for the layout: board defaults, classes of nets by tag with their own width and clearance, pour rules (relief, sliver removal, heavy copper), via stitching and fencing, routing structures applied by tag, fanout step-down into package pads, and after-build checks that each rule applied.

Example triggers:

- "Keep the 12 V copper 0.3 mm from ground on the inner layer"
- "The 0.5 mm power trace won't fit the QFN pad"
- "Why isn't my clearance rule applying?"

### jitx-interconnect-constraints

Apply signal-integrity constraints to JITX designs: topologies, insertion loss, timing, differential pairs, bus matching, pin models, and protocol constraints.

Example triggers:

- "Constrain this differential pair with 5ps skew"
- "Add insertion loss limits to the data bus"
- "Set up PCIe Gen4 constraints"

### jitx-pin-assignment

Model flexible pin mapping with provide/require patterns, pin muxing, P/N swap, lane ordering, byte/bit swapping, and topology constraints on assigned ports.

Example triggers:

- "Let the tool pick which UART maps to these pins"
- "Allow P/N swap on the LVDS pairs"
- "Set up DDR4 byte swapping"

### jitx-code-review

Same-model self-critique pass on JITX Python code just written in the current workspace. Catches architectural failure modes that grep gates and static linters miss.

Example triggers:

- "Review my JITX code"
- "Check this for string-hacking"
- "Audit before merge"

### jitx-mechanical

Mechanical CAD interface for JITX designs: use `jitxlib-mechanical` to inspect/import DXF and IDF text (.emn/.idf/.idx/.bdf), and export captured designs with `jitx design export dxf`. Attach STEP models and export a full board STEP with `jitx design export legacy-step` or the JITX application UI.

Example triggers:

- "Import this EMN as the board outline"
- "Export my board to DXF for the ME team"
- "Attach a STEP model to this connector"

### jitx-jlcpcb

The JLCPCB option, opt-in for a user who has chosen JLCPCB as fab and assembler: its predefined substrates, parts resolved to LCSC C-numbers with the basic, preferred and extended tiers, catalogue footprints, the `lcsc.lock.json` file, and the order packet (gerbers, BOM, pick-and-place, order sheet), all through `jitxlib-jlcpcb`. JITX names no default fab; a board with no fab named goes to jitx-project-builder, which asks.

Example triggers:

- "Create a 4-layer JLCPCB substrate"
- "Use only JLCPCB basic parts for the passives"
- "Make the JLCPCB order packet for this board"

## Project Structure

```text
jitx-skills/
├── .agents/
│   └── plugins/
│       └── marketplace.json     # Codex marketplace listing
├── .claude-plugin/
│   ├── plugin.json              # Claude Code plugin manifest
│   └── marketplace.json         # Claude marketplace listing
├── .codex-plugin/
│   └── plugin.json              # Codex plugin manifest
├── skills/
│   ├── jitx/
│   │   ├── SKILL.md
│   │   ├── references/
│   │   └── scripts/                  # check.py, grep_gates.py, prune_lock.py
│   ├── jitx-project-builder/
│   │   ├── SKILL.md
│   │   ├── references/
│   │   │   ├── domain-checklists.md  # Checklist index
│   │   │   ├── domains/              # Focused checklist files
│   │   │   └── net-classes.md        # Cross-domain net taxonomy
│   │   └── scripts/                  # plan_status.py
│   ├── jitx-component-modeler/
│   ├── jitx-circuit-builder/
│   ├── jitx-substrate-modeler/
│   ├── jitx-code-layout/
│   ├── jitx-interactive-layout/
│   ├── jitx-layout-constraints/
│   ├── jitx-interconnect-constraints/
│   ├── jitx-pin-assignment/
│   ├── jitx-code-review/
│   ├── jitx-mechanical/
│   └── jitx-jlcpcb/
├── scripts/
│   └── validate_dual_plugin.py
└── sample-project.md
```

## Requirements

- A JITX Python project with `pyproject.toml` containing a JITX dependency
- JITX 4.6 (`jitx>=4.6,<4.7`) and the JITX 4.6 runtime, with `jitxlib-standard` 4.6, `jitxlib-parts` 2.x, `jitxexamples` 2.1.x and, for JLCPCB boards, `jitxlib-jlcpcb` 4.x. This release targets JITX 4.6 only, as 1.8.1 did. Release 1.7.0 documents the JITX 4.2 API, and no release targets 4.4, so move a 4.4 project to 4.6 before using these skills. The released versions the skills were checked against are in the Supported versions table in `skills/jitx/SKILL.md`.
- Python 3.12+
- For datasheet processing: `pip install pymupdf`

## Usage Examples

### Generate a Component from Datasheet

```text
User: Create a JITX component for the NE555 timer from this datasheet
Agent: uses the jitx-component-modeler skill to generate component code
```

### Build a Design

```text
User: Build my power supply design
Agent: uses the jitx skill to set up the environment and run the build
```

### Extract Datasheet Pages

The `extract_pages.py` script helps extract relevant pages from large datasheets:

```bash
python skills/jitx-component-modeler/scripts/extract_pages.py datasheet.pdf --find "pinout" "dimension" "package"
python skills/jitx-component-modeler/scripts/extract_pages.py datasheet.pdf --pages 10 11 12 -o extract.pdf
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

## Validation

Run the repo-local dual validation:

```bash
python scripts/validate_dual_plugin.py .
```

Check that every cross-reference between skill pages still resolves, and that no section is
cited by a truncated name instead of a link:

```bash
python scripts/check_doc_links.py .
```

Run the unit tests. The project tests in `skills/jitx/scripts/test_prune_lock.py` build a
scratch JITX project, so they need `JITX_PYTHON` set to a Python with jitx 4.6 and
jitxlib-parts 2; without it they are skipped, and with one that cannot import jitx they fail:

```bash
JITX_PYTHON=/path/to/venv/bin/python python3 -m pytest -q
```

Run Codex manifest validation with the Codex plugin-creator validator:

```bash
python /path/to/plugin-creator/scripts/validate_plugin.py .
```

Run Claude validation when Claude Code is installed:

```bash
claude plugin validate .
```

## Contributing

Keep the shared instructions in `skills/<skill-name>/SKILL.md`. Use platform-specific metadata only where each runtime expects it:

- Claude Code: `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`
- Codex/GPT: `.codex-plugin/plugin.json` and `.agents/plugins/marketplace.json`
- Shared skill content: `skills/<skill-name>/SKILL.md`, `references/`, `scripts/`, and `assets/`
