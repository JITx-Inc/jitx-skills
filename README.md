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

Codex uses `.codex-plugin/plugin.json` and the shared `skills/` directory. For local development, add a local Codex marketplace entry that points at this plugin root, then install `jitx-skills` from that marketplace.

Example marketplace entry:

```json
{
  "name": "jitx-skills",
  "source": {
    "source": "local",
    "path": "./plugins/jitx-skills"
  },
  "policy": {
    "installation": "AVAILABLE",
    "authentication": "ON_INSTALL"
  },
  "category": "Developer Tools"
}
```

Codex skills can be invoked explicitly with `$jitx`, `$jitx-component-modeler`, and the other skill names, or selected implicitly from the user request.

## Updating

Claude Code:

```text
/plugin marketplace update jitx
claude plugin update jitx-skills@jitx
```

Restart Claude Code or run `/reload-plugins` after local plugin edits.

Codex/GPT: update the plugin source, refresh or reinstall the local Codex plugin entry, and start a new thread so Codex reloads the skill list and manifest metadata.

## Skills

### jitx

Base workflow skill for JITX projects. Triggers on JITX-related tasks and provides environment setup, build commands, project structure guidance, and navigation to specialized skills.

Example triggers:

- "Build my JITX design"
- "Set up JITX environment"
- "Create a full JITX project"

### jitx-component-modeler

Generate JITX Python component code from datasheets, KiCad footprints, or user specifications.

Example triggers:

- "Create a JITX component from this datasheet"
- "Model the RP2040 for my project"
- "Add an LDO component from the TI datasheet"

### jitx-circuit-builder

Build JITX circuits with wiring, passives, power connections, application circuits, placement, and basic copper geometry.

Example triggers:

- "Wire up a buck converter circuit"
- "Connect the MCU to sensors over I2C"
- "Add decoupling caps to all power pins"

### jitx-substrate-modeler

Model JITX substrates: stackups, materials, vias, routing structures, fabrication constraints, and design rules.

Example triggers:

- "Create a 4-layer JLCPCB substrate"
- "Define a 14-layer RF stackup with via fencing"
- "Set up 100-ohm differential routing structure"

### jitx-physical-layout

Author PCB physical layout from code: copper, custom shapes, pad features, explicit placement, vias, code-based routes, and layout-intent tags.

Example triggers:

- "Draw an IFA antenna from code"
- "Create a net tie between AGND and DGND"
- "Route the BGA escape lanes from code"

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

Mechanical CAD interface for JITX designs: inspect/import DXF, EMN, IDF, IDX, and BDF data; export DXF; attach STEP models; export a full board STEP via the JITX UI (no CLI in py-jitx 4.2.x).

Example triggers:

- "Import this EMN as the board outline"
- "Export my board to DXF for the ME team"
- "Attach a STEP model to this connector"

## Project Structure

```text
jitx-skills/
├── .claude-plugin/
│   ├── plugin.json              # Claude Code plugin manifest
│   └── marketplace.json         # Claude marketplace listing
├── .codex-plugin/
│   └── plugin.json              # Codex plugin manifest
├── skills/
│   ├── jitx/
│   │   ├── SKILL.md
│   │   ├── agents/openai.yaml   # Codex UI metadata
│   │   ├── references/
│   │   └── scripts/
│   ├── jitx-component-modeler/
│   ├── jitx-circuit-builder/
│   ├── jitx-substrate-modeler/
│   ├── jitx-physical-layout/
│   ├── jitx-interconnect-constraints/
│   ├── jitx-pin-assignment/
│   ├── jitx-code-review/
│   └── jitx-mechanical/
├── scripts/
│   └── validate_dual_plugin.py
└── sample-project.md
```

## Requirements

- A JITX Python project with `pyproject.toml` containing a JITX dependency
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
- Codex/GPT: `.codex-plugin/plugin.json` and `skills/<skill-name>/agents/openai.yaml`
- Shared skill content: `skills/<skill-name>/SKILL.md`, `references/`, `scripts/`, and `assets/`
