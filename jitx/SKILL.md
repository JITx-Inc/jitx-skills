---
name: jitx
description: Base skill for JITX hardware design workflow. Use for JITX Python projects, PCB design, circuit creation, and build commands. Use when the user asks to "build my JITX design", "set up JITX environment", "create a circuit", "build a complete board", "design a PCB from requirements", or "create a full JITX project". For multi-component designs (3+ components, substrate, circuits), invoke the Project Builder workflow for orchestrated parallel agent execution with quality gates. CRITICAL - If user asks to create/model/generate a component or mentions a part number (NE555, LM1117, RP2040, etc.), immediately invoke jitx-component-modeler subskill. If user asks to create a substrate, stackup, via definitions, or routing structures, invoke jitx-substrate-modeler subskill.
---

# JITX Workflow Skill

Base skill for JITX hardware design automation. JITX is a Python framework for programmatic PCB design.

## Rule 0 — Verify every JITX API before using it

Do not guess at imports, class names, constructor kwargs, or chain methods.
Before writing any `from jitx…` / `from jitxlib…` line, verify the symbol
exists. Use this fallback chain, in order:

1. **Canonical source repos on GitHub** (most authoritative — clone or
   browse via `gh`):
   - `github.com/JITx-Inc/py-jitx` — core `jitx` package (`Component`,
     `Landpattern`, `PadMapping`, `Design`, `Board`, shapes,
     `NonPopulatedComponent`)
   - `github.com/JITx-Inc/py-jitx-stdlib` — `jitxlib` stdlib (landpattern
     generators under `jitxlib.landpatterns`, protocols under
     `jitxlib.protocols`, geometry)
   - `github.com/JITx-Inc/py-jitx-parts` — passive part dataclasses
     (`jitxlib.parts.Capacitor` / `Resistor` / `Inductor`)
   - Examples to cross-reference:
     `github.com/JITx-Inc/py-essentials-examples`,
     `github.com/JITx-Inc/py-components`
2. **Official API documentation**: `https://docs.jitx.com/llms.txt` (fetch
   with WebFetch) when source repos aren't checked out.
3. **Installed artifacts on the local machine**: site-packages of an
   installed venv, or the official install layout under `~/.jitx/`.
   Acceptable as a last resort but may lag the canonical repos.

If none of the above resolves the symbol, **document it as unknown** rather
than inventing an import. Falling back to a custom landpattern, a local
`jitx.Bundle` subclass, or an open gap is correct; inventing an import path
"by analogy" with another package is not.

Subskill "Rule 0" sections point back here for the canonical chain — domain
skills (`jitx-circuit-builder`, `jitx-component-modeler`, etc.) list only
the domain-specific landmines.

### Common API mistakes (recurring failure mode)

These are real wrong guesses observed during actual JITX 4.x work. Every
one of them follows the same anti-pattern: invent an import "by analogy"
with another package, write a plausible-looking constructor, and don't
verify against the source. Verify before writing, not after.

| ❌ Wrong guess | ✅ Actual API | Source |
|---|---|---|
| `from jitxlib.landpatterns.core import Landpattern` | `from jitx.landpattern import Landpattern, PadMapping` | `py-jitx/src/jitx/landpattern.py` |
| `BGADepop([(0,0)])` kwarg on `BGA(...)` | `.grid_planner(<GridPlanner subclass>)` | `py-jitx-stdlib/src/jitxlib/landpatterns/grid_planner.py` |
| `BGA(rows=5, cols=5, ...)` | `BGA(num_rows=5, num_cols=5, ball_diameter=..., pitch=...)` | `py-jitx-stdlib/src/jitxlib/landpatterns/generators/bga.py` |
| `QFN_DEFAULT_LEAD_PROFILE` exported symbol | Build a `LeadProfile(span=..., pitch=..., type=QFNLead(...))` explicitly | `py-jitx-stdlib/src/jitxlib/landpatterns/generators/qfn.py` |
| `LeadProfile(..., SMDLead(length, width))` for QFN | `LeadProfile(..., QFNLead(length, width))` — base `SMDLead` requires `lead_type` | same |
| `from jitx.feature import Pour` | `from jitx import Pour` or `from jitx.copper import Pour` — **not** in `jitx.feature` | `py-jitx/src/jitx/copper.py:45` |
| `Net(self.a, self.b, self.c, name="VDD")` (varargs) | `Net([self.a, self.b, self.c], name="VDD")` — single iterable | `py-jitx/src/jitx/net.py:662-668` |
| `from jitx import NonPopulatedComponent` | `from jitx.component import NonPopulatedComponent` — not re-exported from `jitx/__init__.py` in 4.0.5 | `py-jitx/src/jitx/component.py:150` |
| `Pad.at(x, y, theta)` (positional rotation) | `Pad.at(x, y, rotate=theta)` — keyword-only | `py-jitx/src/jitx/placement.py:104-106` |
| `Rectangle` as a class import | `Rectangle` is not a class — use the function `rectangle(w, h, *, radius=None)` from `jitx.shapes.composites`. `Circle` *is* a class. | `py-jitx/src/jitx/shapes/composites.py` |
| `RoundedRectangle(W, H, r)` for board outline | `rectangle(W, H, radius=r)` from `jitx.shapes.composites`, assigned to `design.board.shape` | `py-jitx/src/jitx/board.py`, `shapes/composites.py` |
| `PadMapping({"PVDD": [3, 4], ...})` (string keys) | `PadMapping({self.PVDD: [lp.p[3], lp.p[4]], ...})` — keys are `Port` objects, values are `Pad` or `Sequence[Pad]` | `py-jitx/src/jitx/landpattern.py:99-198` |
| `Capacitor(min_rated_voltage=35.0)` | `Capacitor(rated_voltage=35.0)` | `py-jitx-parts/src/jitxlib/parts/query_api.py` |
| `Capacitor(temperature_coefficient="C0G")` | `Capacitor(temperature_coefficient_code="C0G")` — kwarg is `_code` | same |
| `SOT89_3()`, `SOT223_3()`, `SOT583_8()` generators | Only `SOT23_3`, `SOT23_5`, `SOT23_6` exist. Build a custom `Landpattern` for the others. | `py-jitx-stdlib/src/jitxlib/landpatterns/generators/sot.py` |
| `from jitxlib.protocols.serial import I2SMCK` / bare `OctalSPI` | Not in jitxlib — define locally as a `jitx.Bundle` subclass | n/a |
| `Power.vdd` / `Power.gnd` / `DiffPair.P` / `DiffPair.N` | `Power.Vp` / `Power.Vn` / `DiffPair.p` / `DiffPair.n` — case-sensitive | `py-jitx/src/jitx/common.py`, `net.py` |
| `landpattern.add_pad(SMDPad(index=1, ...))` | Declare `p1 = SMDPad(...).at(x, y)` as a class attribute on the `Landpattern` subclass | `py-jitx-stdlib/src/jitxlib/landpatterns/pads.py` |

### Stanza helpers without a 4.x equivalent

Some convenience helpers from the Stanza-era JITX library have no direct
Python analog. Most fail **silently** — the build succeeds without the
helper, and the missing feature surfaces only at fab time. If you find
yourself looking for one of these in 4.x, the table below tells you what to
do instead.

| Stanza helper | Python 4.x | Workaround |
|---|---|---|
| `add-mounting-holes(board-shape, "M3")` | No `jitxlib.mechanical`, no helper | Define a PTH mounting-hole `Component` manually (e.g. 3.2 mm drill + 5.5 mm annular ring for M3 clearance), instantiate 4× at explicit coordinates. |
| `add-open-drain-pullups(net_or_port, rail)` | No helper | Expand inline — one explicit `Resistor` per pin. For an `i2c` bundle: `self.r_sda = Resistor(resistance=4.7e3); self.r_sda.insert(i2c.sda, vdd); …` |
| `add-xtal-caps(xtal, gnd)` | No helper | Two `Capacitor` instances per crystal, both `self.*`-assigned; size from the crystal's load-capacitance datasheet figure. |
| `setup-design(name, board, rules=..., vendors=..., quantity=...)` | Decomposed into `Design` class attributes | `class MyDesign(Design): board = MyBoard(); substrate = MySubstrate()`. Vendor / quantity / BOM metadata is not generally surfaced at `Design` level today. |
| `set-paper(ANSI-A)` | Class attribute | `class MyDesign(Design): paper = Paper.ANSI_A` from `jitx.paper`. Default is ANSI A. |
| `set-export-backend(`kicad)` | No-op | KiCad is the only export today; `python -m jitx build` emits KiCad artefacts implicitly. Drop the call. |
| `view-board()` / `view-schematic()` / `view-bom()` | No-op in headless build | Viewers live in the `jitx interactive` server / IDE plugin, not as top-level design entries. Drop the calls. |

Silent omission is the failure mode — a missing `add-mounting-holes`
equivalent produces a clean build and a fabbed board with no mounting
points, with no warning anywhere in the pipeline.

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

# Verify core imports (don't check __version__ — not present in all JITX versions).
# Fail loud if any import is missing; do not work around with substitutions.
python - <<'PY'
import sys
required = [
    "jitx",
    "jitxlib",
    "jitxlib.parts",
    "jitxlib.symbols.box",
    "jitxlib.voltage_divider",
]
missing = []
for mod in required:
    try:
        __import__(mod)
    except Exception as e:
        missing.append(f"{mod}: {e}")
if missing:
    print("ERROR: missing required JITX modules:")
    for m in missing:
        print(f"  - {m}")
    sys.exit(1)
print("JITX core ready")
PY
```

Also probe the target substrate package if known (e.g., `python -c "import jitxlib.jlcpcb"` when the user has chosen JLCPCB). For complete-board tier, the Phase 0 → 1 gate requires this probe.

**Missing-dependency rule:** if any required import fails, stop and surface it to the user as a blocker. Do NOT remove or substitute design requirements as a workaround (e.g. dropping controlled-impedance routing because `jitxlib` didn't import). See `references/project-builder-flow.md` Recovery Procedures → "Missing dependency escalation".

Only install deps on first run (venv creation). Skip `pip install` on subsequent runs — it's slow and noisy. Don't ask user to do manual setup.

### Parallel JITX installs and the `~/.jitx/current` symlink

JITX releases install per-version under `~/.jitx/<version>/` (e.g.
`~/.jitx/3.36.1/`, `~/.jitx/4.0.5/`, `~/.jitx/4.1.0/`) and multiple versions
can coexist. The active version is selected by the `~/.jitx/current`
symlink — JITX reads runtime, config, and plugin state via
`~/.jitx/current/...` regardless of which versioned binary you launched.

Symlink mismatch silently corrupts builds. The classic symptom is

```
FATAL PLUGIN ERROR: No appropriate branch for arguments of type (False)
```

in `StableBoardSerializer/write-stable-id`. Update the symlink before
invoking a different version:

```bash
ln -sfn 4.1.0 ~/.jitx/current
```

Note: the 3.x line is Stanza-only; only 4.x is the Python-Python target.
Both lines share the binary name `jitx`, so when both are installed,
invoke each by absolute path or use isolated subshells.

The order-sensitive bootstrap recipe (symlink → sign-in → `jitx interactive`
→ `.socket.jitx` wait → `pip install` → version check → build) is the
**canonical bootstrap** for any 4.x design and lives in
[`references/bootstrap.md`](references/bootstrap.md).

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
  **Symptom of violation:** at build time, `python -m jitx build` fails at the translation stage with `jitx.error.InstantiationException: Failed to instantiate <Circuit> at <file>:<line> — Unable to map local reference N, parent <Circuit> is not an ancestor of child <Port>`, and a misleading "child" file pointer to `jitx/__init__.py:32` (the canonical `Circuit` import site, NOT the actual offender). The actual line is the `setattr(self, …, x)` in your code. Replace with explicit `self.name1 = x1; self.name2 = x2; …` declarations; for repeated patterns prefer a helper `Circuit` subclass over a stamping loop. The most common trigger is auto-numbered bypass-cap loops — see `jitx-circuit-builder` §"Passives" for the canonical form.
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

A `python -m jitx build` invocation cannot succeed in isolation — it
requires a `~/.jitx/current` symlink, an active sign-in, a running
`jitx interactive` backend server, and `JITX_SKIP_STABILIZE_CONFIRMATION=1`
for headless runs. The setup is **order-sensitive**.

**Full ordered checklist, worked snippet, and failure-mode table:**
[`references/bootstrap.md`](references/bootstrap.md) — this is the
**canonical source** for the bootstrap sequence; other skills and
per-design `CLAUDE.md` files link here.

### Quick reference

```bash
JITX_VER=4.1.0                                       # adjust
ln -sfn "$JITX_VER" ~/.jitx/current                  # (1) symlink
~/.jitx/$JITX_VER/jitx sign-in -email "$EMAIL"       # (2) sign in
~/.jitx/$JITX_VER/jitx interactive $(pwd) &          # (3) server
until [ -e .socket.jitx ]; do sleep 1; done          # (4) wait
pip install --pre -e .                               # (5) editable install (in venv)
python -c 'import jitx; print(jitx.__version__)'     # (6) version check
JITX_SKIP_STABILIZE_CONFIRMATION=1 \
    python -m jitx build <module.path.DesignClass>   # (7) build
# Or build every Design subclass in the project:
JITX_SKIP_STABILIZE_CONFIRMATION=1 python -m jitx build-all
```

**Don't run parallel builds on the same design.** Concurrent JITX builds against the *same design* aren't reliable — cache state, build artifacts, and design-explorer output overlap. Sequence those. Parallel builds of *different designs* in the same project (different test designs, different module paths) share the WebSocket session but are generally safe — the JITX backend serializes internally, possibly with a wait. The skill orchestrator's Phase 1 runs sub-agents in parallel on different test designs; the parallelism is at the design-work level, and concurrent builds on distinct designs are an acceptable consequence.

**Success output:** `status: ok` &nbsp;&nbsp;**Error output:** Python traceback or `status: error`

`status: ok` is **necessary but not sufficient** — it catches type errors,
missing pin mappings, and unconnected `require()` providers, but it does
not catch wiring errors where every port is in *some* net but the wrong
net. After every build, walk the export-verification checklist at
[`references/export-verification.md`](references/export-verification.md)
to audit for silent wiring errors (net inventory, connector pins, power
topology, component output pins, passive counts, control signals).

**Build invocation gotchas:**

- `--port <PORT>` on `python -m jitx build` is the **TCP UI port for the
  `jitx interactive` server**, not a PCB port. Easy to confuse mid-design.
- The build target is `<module.path>.<DesignClass>`, not a file path. A
  mismatch fails with `no design found`, not a Python `ImportError`.
- Two installs (3.x + 4.x) in the same shell cross-contaminate `PATH` and
  Conan envs because both ship a binary named `jitx`. Use absolute paths
  or subshells; see the Parallel JITX installs section under Environment
  Setup.

**Output files** (in `designs/<design_name>/`):
- `cache/netlist.json` — JSON netlist for verification
- `cache/design-explorer.json` — design hierarchy
- `design-info/stable.design` — design snapshot

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

## First: Pick the Workflow Tier

> **STOP. Classify first. Before any architecture proposal, parts research, design prose, code, or `Skill(...)` invocation other than environment probes, your first observable action must be a chat line of the form:**
>
> > **Workflow tier: `single-task` | `complete-board` — because `<one-sentence reason>`**
>
> **For `complete-board`, the *next* observable action must be writing `PLAN.md` (and `ARCHITECTURE.md`).** Verbal architecture proposals, parts-list bullets, "here's what I'll build" prose, or `Write(...)` of code before `PLAN.md` exists are explicitly invalid work for a complete-board project — they must be backed out before the workflow can continue.
>
> If you find yourself already typing "Big design — here's my proposed architecture..." or "I'll set up the skeleton and start filling in components", you have skipped Phase 0. Stop, classify, and create `PLAN.md` first.
>
> This callout exists because the prior failure mode was exactly this: the agent jumped from request to architecture prose to component files without classifying, never entered Phase 0, and bypassed every Pass 1–5 enforcement.

After environment setup, classify the work into one of two tiers. The tier names which output blocks are required and whether the formal Phase 0 → Phase 4 chain applies. Every tier requires a **task acceptance block** for each unit of work — no exceptions.

| Tier | When | Required output | Path |
|------|------|-----------------|------|
| **single-task** | One subskill against one artifact: a component, a circuit, a substrate, a constraint set, a pin-assignment wrapper. No top-level assembly. | Task acceptance block in chat | Invoke the subskill directly |
| **complete-board** | Anything beyond a single isolated artifact — anything that produces a buildable board, no matter how few components. | Task acceptance block per task + phase exit gate blocks + Phase 3b audit + Phase 4 verification | Full Project Builder Workflow below |

If you're tempted to call something "small" or "trivial" to avoid the workflow, classify it as complete-board. The Phase 0–4 ceremony is cheap on a small board (a few extra block emissions); the cost of skipping it on a real board is shipping with required features missing. The original failure mode of this skill was exactly the "looks small, skip the workflow" escape hatch.

For tier definitions, the task acceptance block, phase exit gate blocks, the Phase 3b design audit block, and the Phase 4 verification block: read `references/completion-blocks.md`.

Do NOT skip the planning phase for complete-board designs. Do not start exploring libraries or writing code until PLAN.md exists.

## Core Concepts

**Circuit**: Python class inheriting from `jitx.Circuit`. Contains components and connections.

**Component**: Python class inheriting from `jitx.Component`. Defines ports, landpattern, symbol.

**Design**: Python class inheriting from design base (e.g., `SampleDesign`). Top-level entry point.

For net wiring, passives, and circuit patterns, invoke the `jitx-circuit-builder` subskill.

### Sanity-checking a new Circuit / Component

`MyCircuit()` or `MyComponent()` at the REPL **does not give you a
fully-realized object** — JITX uses lazy instantiation. Instances are
fully realized only when wrapped in a `Design` and exercised through
`python -m jitx build`. Until then, attribute access returns
`InstantiableAttribute` proxies:

```python
>>> c = MyCircuit()
>>> len(c.providers)
TypeError: object of type 'InstantiableAttribute' has no len()
>>> isinstance(c.items, list)
False
```

Use direct instantiation only to catch import / syntax / missing-attribute
errors that pyright should have caught. For runtime validation of wiring,
pin maps, or `@provide` options, write a `SampleDesign` test harness
(`jitx-component-modeler/SKILL.md` §"Test Harness" or
`jitx-circuit-builder/SKILL.md` §"Build Test"):

```python
from jitx.container import inline
from jitx.sample import SampleDesign

class TestDesign(SampleDesign):
    @inline
    class circuit(MyCircuit):
        pass
```

Then `python -m jitx build my_module.TestDesign`. That's the only way to
exercise `__init__` end-to-end on a Circuit / Component.

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

### Build Safety — Don't Parallelize Same-Design Work

Concurrent builds of the *same JITX design* share cache state, build artifacts, and design-explorer output. Sequence them. Concurrent builds of *different designs* in the same project — for example, parallel sub-agents each building their own component test design — share the WebSocket session but are generally safe: the JITX backend serializes the work internally, possibly with a wait.

For the project-builder workflow: Phase 1 sub-agents can run in parallel, each working on its own component file and its own test design. They are not running concurrent builds of the *same* design. Phase 2/3/4 builds are inherently sequential.

For ad-hoc work outside the project-builder flow: just don't run two `python -m jitx build` calls against the same design at once.

### Grep Gate Enforcement

Copy `scripts/grep_gates.sh` from this skill into the project's `scripts/` directory. Sub-agents (and the orchestrator at every phase exit gate) run it against `src/<ns>/` to enforce JITX code conventions and top-level-only rules:

```bash
bash scripts/grep_gates.sh src/<ns>/
```

The script reports hard-fail hits (which block task acceptance and gate transitions) and review-required hits (which need a disposition in the task acceptance block). Pattern set and disposition rules: `references/completion-blocks.md` "Grep Gate Patterns".

### Two-Tier Quality System

Sub-agent work goes through TWO quality checks before being accepted:

**1. Sub-Agent Self-Validation ("Think Twice")**

After initial implementation, sub-agents MUST stop and run the domain-specific checklist against the datasheet before returning. This forced second pass typically catches 3-5 missed details (floating enable pins, missing thermal pads, wrong output types, forgotten decoupling). Sub-agents return a **task acceptance block** documenting what they checked and fixed — the block is mandatory; "build clean" is not a substitute. See `references/completion-blocks.md` for the template.

**2. Orchestrator Acceptance Review**

The orchestrator does NOT blindly trust the self-validation block. For each returned task:
- Read the generated code for obvious issues
- Verify the build claim (re-run `python -m jitx build` for critical tasks)
- Spot-check high-risk checklist items independently
- Verify interface compatibility with downstream tasks
- Append the acceptance verdict to the same block: **accept** / **rework** (send back with specific issues) / **reject** (replan)

A task without an acceptance block is `in-progress`, not done. Phase gates only open when ALL tasks in the phase have `Verdict (acceptance): accept` blocks.

For the full protocol: read `references/task-execution.md`
For block templates: read `references/completion-blocks.md`
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

### Working on large designs — context budget

Designs with **≥3 interconnected circuits** routinely exhaust a single
session's context window. The risks are re-synthesis of skill content from
summaries, drift across circuits that should be consistent, and silent
forgetting of design-level invariants (rail naming, bundle conventions).
Mitigations:

- **Checkpoint one circuit per session**; commit a green build before
  starting the next. Make `python -m jitx build` part of the
  checkpoint — `pyright` clean is not enough.
- **Keep the relevant source files open simultaneously** when wiring a
  circuit that references another circuit's ports — don't rely on memory
  of the other class's port names or bundle fields.
- **For 3+ circuit designs, prefer a long-context model** (e.g. Claude
  Opus 4.5 / 4.7 in 1M-context mode). The cost difference is small
  compared to a re-synthesis pass.

### Parts Data and Footprint Conversion

Claude selects parts based on engineering requirements first. Data for each component comes from the **user-approved data source plan** (see Phase 0 data audit).

**Data sources (in priority order):**
1. **User-provided** — datasheets, KiCad footprints, or specs the user supplies directly
2. **JITX generators** — standard packages (QFN, SOIC, BGA, SOT, SON, QFP) with dimensions from datasheets
3. **LCSC / JLCPCB via `parts2jitx`** — split consent. **Lookup / evidence** (`parts2jitx-lcsc <C-number>`, `--pinout`) is implied when the user names LCSC/JLCPCB as the channel; the orchestrator may `pip install parts2jitx` automatically. **Footprint data ingestion** (`parts2jitx-lcsc --footprint`, `parts2jitx-kicad`) is a separate path that requires explicit per-project user approval because EasyEDA component data has its own terms of use.
   ```bash
   pip install parts2jitx
   parts2jitx-lcsc <C-number>            # lookup / evidence (auto-OK with named channel)
   parts2jitx-lcsc <C-number> --pinout   # lookup / evidence
   parts2jitx-lcsc <C-number> --footprint -o ...   # footprint data — explicit approval required
   parts2jitx-kicad <file.kicad_mod>     # footprint data — explicit approval required
   ```
   See `references/parts-sourcing.md` "LCSC / JLCPCB via parts2jitx" for the full split-consent table.

For non-standard packages (connectors, RF modules): convert from a `.kicad_mod` file (user-provided or downloaded). **NEVER hand-craft pad positions** — use the converter. Standard packages use built-in JITX generators. All symbols use `BoxSymbol`. Exception: mechanical / vendor-defined footprints (Tag-Connect, pogo-pin fixtures, castellations, fiducials) where no purchasable component exists — see `references/parts-sourcing.md` "Mechanical / Vendor-Defined Footprints".

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
| Build design | `python -m jitx build module.Design` (sequence calls — see "Build Safety") |
| Format code | `ruff format path/to/file.py` |