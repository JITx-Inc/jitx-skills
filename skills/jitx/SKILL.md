---
name: jitx
description: "Base skill for JITX Python hardware design projects, PCB design, circuit creation, board builds, and JITX CLI workflows. Use when the user asks to build a JITX design, set up the environment, create circuits, design a PCB from requirements, or create a full project. Route component modeling to jitx-component-modeler, substrate or stackup work to jitx-substrate-modeler, physical layout code to jitx-physical-layout, and mechanical CAD import/export work to jitx-mechanical."
---

# JITX Workflow Skill

Base skill for JITX hardware design automation. JITX is a Python framework for programmatic PCB design.

## Environment Setup

The `jitx` CLI owns project scaffolding, auth, runtime install/start, and design build for VSCode-free workflows. Drive everything through it.

> **Platform note (read once).** These commands run in **your** shell on **your** OS. macOS / Linux / WSL / Git Bash use **bash**; native Windows uses **PowerShell**. Commands identical in both (all `jitx ...`, `pip ...`, `pyright`, `ruff`, every `python scripts/...`) are shown once; where they diverge, a `bash` block and a `powershell` block are given — run the one for your shell.
>
> Conventions used throughout this bundle:
> - **Interpreter:** `python3` on macOS/Linux, `python` on Windows (the launcher there exposes `python`). Note `python scripts/...` runs the same script either way.
> - **venv activation:** macOS/Linux/WSL bash `source .venv/bin/activate`; Git Bash on Windows `source .venv/Scripts/activate`; PowerShell `.\.venv\Scripts\Activate.ps1` (if blocked by execution policy, run `Set-ExecutionPolicy -Scope Process Bypass` first).
> - **venv layout:** macOS/Linux `.venv/bin/`, `.venv/lib/python*/site-packages/`; native Windows `.venv\Scripts\`, `.venv\Lib\site-packages\`.
> - **Inline env vars** (`VAR=value cmd`) are bash-only and one-shot; PowerShell's `$env:VAR="value"; cmd` *persists for the session* — clear it with `Remove-Item Env:VAR` when it should apply to a single command (e.g. `TOP_LEVEL_PATH`).
> - **Library/source discovery:** prefer your own **Grep**/**Glob** tools (OS-agnostic) over shell `grep` — they handle `lib/`-vs-`Lib/` and path globs for you.

### Step 1 — Ensure the `jitx` CLI is available

```bash
# bash (macOS / Linux / WSL / Git Bash)
if ! command -v jitx >/dev/null 2>&1; then
  # Bootstrap venv + install jitx from PyPI + the internal index.
  # PIP_PRE / extra-index-url cover the 4.x pre-release line.
  # `click` is a runtime import of the `jitx` CLI but the 4.3.x wheel doesn't declare it — install it explicitly.
  [ -d .venv ] || python3 -m venv .venv 2>/dev/null || python -m venv .venv
  # venv layout: .venv/bin on macOS/Linux/WSL, .venv/Scripts under Git Bash (Windows Python).
  source .venv/bin/activate 2>/dev/null || source .venv/Scripts/activate
  PIP_PRE=1 pip install --extra-index-url https://pypi.jitx.com/jitx/main/+simple jitx ruff click --quiet 2>&1 | tail -1
else
  # `jitx` is on PATH — activate the project venv if one exists so build/runtime calls resolve consistently.
  [ -d .venv ] && { source .venv/bin/activate 2>/dev/null || source .venv/Scripts/activate; }
fi

jitx --version 2>/dev/null || jitx --help >/dev/null
```
```powershell
# PowerShell (Windows)
if (-not (Get-Command jitx -ErrorAction SilentlyContinue)) {
  # Bootstrap venv + install jitx from PyPI + the internal index.
  # PIP_PRE / extra-index-url cover the 4.x pre-release line.
  # `click` is a runtime import of the `jitx` CLI but the 4.3.x wheel doesn't declare it — install it explicitly.
  if (-not (Test-Path .venv)) { python -m venv .venv }
  .\.venv\Scripts\Activate.ps1
  $env:PIP_PRE=1; pip install --extra-index-url https://pypi.jitx.com/jitx/main/+simple jitx ruff click --quiet 2>&1 | Select-Object -Last 1; Remove-Item Env:PIP_PRE
} else {
  # `jitx` is on PATH — activate the project venv if one exists so build/runtime calls resolve consistently.
  if (Test-Path .venv) { .\.venv\Scripts\Activate.ps1 }
}

jitx --version 2>$null; if ($LASTEXITCODE -ne 0) { jitx --help | Out-Null }
```

If `jitx --version` raises `ModuleNotFoundError: No module named 'click'`, the wheel's missing-dep gap bit you — `pip install click` resolves it.

### Step 2 — Project layout (scaffold if missing)

```bash
# bash (macOS / Linux / WSL / Git Bash)
if [ ! -f pyproject.toml ] || ! grep -q "jitx" pyproject.toml; then
  # No JITX project here — scaffold the canonical layout.
  # CONFIRM WITH THE USER BEFORE RUNNING in a non-empty directory.
  jitx project layout init
  # Sync project deps. PIP_PRE + extra-index-url are required for `jitxlib-*` to resolve.
  # Note: pip's resolver may re-pin `jitx` to an older 4.x that satisfies the project's `<5` constraint.
  # This skills bundle documents the 4.2 API surface (RoutePoint/PairInsertion/PairPoint, runtime
  # auto-resolution, etc. do not exist below 4.2) — if the resolver lands below 4.2, pin it:
  #   PIP_PRE=1 pip install --extra-index-url https://pypi.jitx.com/jitx/main/+simple "jitx==4.2.*"
  PIP_PRE=1 pip install --extra-index-url https://pypi.jitx.com/jitx/main/+simple -e . --quiet 2>&1 | tail -1
fi
```
```powershell
# PowerShell (Windows)
if ((-not (Test-Path pyproject.toml)) -or (-not (Select-String -Quiet -Pattern "jitx" pyproject.toml))) {
  # No JITX project here — scaffold the canonical layout.
  # CONFIRM WITH THE USER BEFORE RUNNING in a non-empty directory.
  jitx project layout init
  # Sync project deps. PIP_PRE + extra-index-url are required for `jitxlib-*` to resolve.
  # Note: pip's resolver may re-pin `jitx` to an older 4.x that satisfies the project's `<5` constraint.
  # This skills bundle documents the 4.2 API surface (RoutePoint/PairInsertion/PairPoint, runtime
  # auto-resolution, etc. do not exist below 4.2) — if the resolver lands below 4.2, pin it:
  #   $env:PIP_PRE=1; pip install --extra-index-url https://pypi.jitx.com/jitx/main/+simple "jitx==4.2.*"; Remove-Item Env:PIP_PRE
  $env:PIP_PRE=1; pip install --extra-index-url https://pypi.jitx.com/jitx/main/+simple -e . --quiet 2>&1 | Select-Object -Last 1; Remove-Item Env:PIP_PRE
}
```

`jitx project layout init` writes the canonical project skeleton: `pyproject.toml`, a flat `<ns>/` package (NOT `src/<ns>/`) containing `__init__.py` + a `main.py` that already defines a working two-resistor `SampleDesign`, plus `.gitignore` and `.vscode/`. That seeded design is buildable as-is once auth and runtime are up — a useful smoke test before writing real design code. Subcommands `jitx project layout {pyproject,gitignore,settings,vscode}` refresh individual pieces of an existing project.

### Step 3 — Auth

```bash
# bash (macOS / Linux / WSL / Git Bash)
# Inspect first — `auth show` reads on-disk license state and reports authorization.
jitx auth show 2>&1 | head -20
```
```powershell
# PowerShell (Windows)
# Inspect first — `auth show` reads on-disk license state and reports authorization.
jitx auth show 2>&1 | Select-Object -First 20
```

The output has an `Authorized: yes | no` line. Three cases:

1. **`Authorized: yes`.** Done.
2. **`Authorized: no` (token present but expired/invalid).** Run `jitx auth refresh`. This exchanges the on-disk refresh token for a fresh license (and rewrites the refresh token when the server rotates it) — **fully headless**, no user action needed. Re-run `jitx auth show` to confirm.
3. **No state on disk, or `auth show` reports no account / no token.** STOP and ask the user to sign in. Initial sign-in is NOT headless — pick one path with the user:
   - VSCode JITX sidebar → interactive sign-in (recommended for desktop developers).
   - The bundled launcher binary: `~/.jitx/current/jitx sign-in -email <email>` (`$HOME\.jitx\current\jitx` on Windows) sends an email link the user must click.
   - `jitx auth login --email <email> --password-stdin` accepts a password on stdin (works for password-bound accounts; some accounts are email-link only).

**`LauncherError: ... did not produce valid JSON` from `auth show` / `auth refresh`** means the CLI is hitting a stale `launcher` binary that predates the `introspect` subcommand. Most common cause: a `JITX_ROOT` env var pointing at a dev build of `jitx-client`. Either `unset JITX_ROOT` (PowerShell: `Remove-Item Env:JITX_ROOT`) so the CLI uses `~/.jitx/current`, or install a fresh runtime (Step 4) and retry. Don't try to script around this — surface it to the user.

### Step 4 — Runtime install + start

The runtime is a daemon (an instance of the bundled `jitx` launcher binary, run with `interactive <project-root>`) that hosts the websocket server `jitx build` and `jitx ui open` talk to. When `jitx runtime start --background` succeeds, the daemon writes `.socket.jitx` into the project root — that's the file every subsequent CLI invocation in that project uses to find the running runtime.

```bash
# bash (macOS / Linux / WSL / Git Bash)
# If a runtime is already running, do nothing.
if jitx runtime status >/dev/null 2>&1; then
  :
elif jitx runtime introspect >/dev/null 2>&1; then
  # Installed but not running — start it.
  jitx runtime start --background
else
  # Not installed. `update` is the idempotent variant of `install`; safe in setup
  # scripts. Without --version it installs the runtime matching the installed
  # py-jitx version; pass --version only to honor an explicit pin.
  jitx runtime update
  jitx runtime start --background
fi
```
```powershell
# PowerShell (Windows)
# If a runtime is already running, do nothing.
jitx runtime status 2>$null | Out-Null
if ($LASTEXITCODE -eq 0) {
  # already running
} else {
  jitx runtime introspect 2>$null | Out-Null
  if ($LASTEXITCODE -eq 0) {
    # Installed but not running — start it.
    jitx runtime start --background
  } else {
    # Not installed. `update` is the idempotent variant of `install`; safe in setup
    # scripts. Without --version it installs the runtime matching the installed
    # py-jitx version; pass --version only to honor an explicit pin.
    jitx runtime update
    jitx runtime start --background
  }
}
```

**Runtime version.** Since 4.2, `jitx runtime install/update` with `--version`
omitted asks the backend for the runtime build **matching the installed py-jitx
version** — that's the right default. (`--progress` follows the download on
stderr.) Pass `--version` only when the project pins one explicitly:
1. `$JITX_RUNTIME_VERSION` env var, or a `jitx.version` file in the project root.
2. A `jitx` runtime version pinned in the project's `mise.toml` or equivalent.

Honor an existing pin; otherwise omit `--version` and let the backend resolve.
(Pre-4.2 CLIs require `--version` — if `jitx runtime update` errors asking for
one, resolve it from (1)–(2) or ask the user.)

**Channels:** development-channel runtime builds (versions like
`4.3.0-develop.N`) are served by the testing backend — install them with
`jitx runtime install --version <v> --testing` (the prod backend 404s on them).
The runtime is **per-project** (discovered by walking up from CWD); each project
you build or capture from needs its own `jitx runtime start --background`.

### Step 5 — Verify

```bash
jitx runtime status         # confirms the socket is up
jitx find                   # lists the designs the runtime sees in this project
```

Also probe the target substrate package if known (e.g., `python -c "import jitxlib.jlcpcb"` when the user has chosen JLCPCB). For complete-board tier, the Phase 0 → 1 gate requires this probe.

**Missing-dependency rule:** if `jitx runtime status` fails, `jitx find` errors, or a required import is missing, stop and surface it to the user as a blocker. Do NOT remove or substitute design requirements as a workaround (e.g. dropping controlled-impedance routing because `jitxlib` didn't import). See `references/project-builder-flow.md` Recovery Procedures → "Missing dependency escalation".

Skip steps 1–4 on subsequent runs once everything is in place — only step 5 (a status probe) needs to run every time. Don't ask the user to do manual setup.

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

**Verify:** Ask the agent to "check for type errors" or run manually:
```bash
pyright <ns>/
```

## JITX Python Code Conventions

Durable rules for JITX Python user code. The architectural rules below protect against the dominant failure mode in AI-generated JITX code (parallel string-keyed models instead of JITX-native structure). The runtime rules protect JITX's internal instantiation tracking. The rest are standard Python encapsulation discipline.

### Don'ts

**Architectural — anti-string-hacking + framework-boundary discipline (the failure modes that produced the worst AI-generated JITX code):**

- **Don't key design state by hand-built strings.** `dict[str, Whatever]` indexed by `f"TX_b{i}"` / `(row_letter, col)` / `f"L{n}_via"` is the failure mode. Use lists, dicts keyed by JITX Port / structural objects (like `@provide` mappings), `@dataclass(frozen=True)`, or `NamedTuple` instead. **If the only key you have is a string you assembled at runtime, the structural object you need is missing.** Exception: `@provide` mappings return `list[dict[Port, Port]]` keyed by Port objects — that's the framework's pin-mapping contract, not a parallel model. See `references/architectural-patterns.md` § "String-keyed dicts → structural objects".
- **Don't reflect on `self` by name to find your own children.** `getattr(self, f"TX_b{i}")` is illegal in JITX user code. If you need to iterate sibling objects, declare them as a `list` or `dict` attribute up front: `self.lanes: list[DiffPair] = [...]`. See `references/architectural-patterns.md` § "Sibling attributes → array attributes".
- **Don't build an intermediate `list[dict[str, Any]]` "spec" model and then iterate it to emit JITX calls.** Construct JITX objects directly in the Component / Circuit / Substrate. If you find yourself batching into records and then walking them, the right composite or container is missing. See `references/architectural-patterns.md` § "Build the scene graph directly".
- **Don't mutate a circuit from a free function.** `def add_x(circuit): circuit.xyz = <something>` creates a structural member by side effect, invisible at the class declaration. Compose instead: `class MyX(Container): xyz = <something>` (or build in its `__init__`), then `self.my_x = MyX()` on the circuit — `Container` members are traversed by the structural walk. Use a `Circuit` subclass when the group has its own ports/nets. See `references/architectural-patterns.md` § "Compose members — don't mutate a circuit from a free function".
- **Don't restate data or logic owned by a structural object.** Substrates own layer counts and via maps; landpatterns own pad numbering; routing structures own per-layer trace/keepout geometry; protocol bundles own pin role assignments. Query through the owning object (`self.substrate.signal_via[layer]`, `lp.get_pad(row, col)`, etc.); do not maintain a parallel table or copy the navigation logic into design code. See `references/architectural-patterns.md` § "Owner-shaped data lives on the owning structural object".
- **Don't reinvent framework code in design code.** If the framework uses a banned pattern (e.g., `getattr`, `type(...)`) inside a class that owns the relevant invariant, that's the framework's same-class exception. **The exception does not transfer to design code on the other side of the boundary.** Copying the framework's internal navigation logic into your design is the failure mode, not a license. The right move is to use the framework's public API; if only a protected method exists (`_get_pad`, etc.), add a public adapter on a subclass that delegates to it (allowed by the "method calling another method on the same class" carve-out). See `references/architectural-patterns.md` § "Framework boundary — internals don't transfer to design code".
- **Don't generate lookup tables or populate mutable globals at module-import time.** Module-level `_BALLOUT = {}; for i in range(N): _BALLOUT[f"X{i}"] = ...` is the failure mode. Class-body structural collections (`lanes: list[list[DiffPair]] = [...]`, `GND = [Port() for _ in range(N)]`) are fine — they're the actual object model. The discriminator is whether the loop is populating a parallel/mutable global or declaring class structure.
- **Don't manually assign values that JITX assigns automatically** in design code. Reference designators like `refdes="U1"`, net names from topology, and layer-derived names / labels are assigned by the framework when the design queries the right structural object. Substrate code legitimately defines layer indices (`start_layer = 0` on a Via class, etc.) — that's the structural definition, not a design-side duplication. The failure mode is *design* code computing names or indices the framework's owning object already exposes.

**JITX runtime — protect internal instantiation tracking:**

- **No `setattr` / `getattr`.** They exist for very narrow scenarios; JITX user code is not one of them. Use lists/dicts when you need to store a programmatic collection on `self`.
- **No dynamic types at runtime.** Do not call `type(...)` to construct a new class on the fly. This breaks JITX's internal instantiation tracking. Express the same intent with parameterized classes — instantiate, don't synthesize.
- **No subclassing JITX classes inside functions or methods.** Same instantiation-tracking failure mode. Declare jitx-class subclasses at module scope (nested at class-body scope is fine).

**Encapsulation — standard Python discipline:**

- **No `type()` for type checks.** Use `isinstance` so subclasses are handled correctly.
- **No access to double-underscore (private) members.** They are private for a reason.
- **No use of leading-underscore packages, modules, or functions from elsewhere.** The Python "protected" convention applies. The single exception is a method calling another method on the same class.

### Dos

- **Run pyright** for type checking and language-server diagnostics.
- **Run `ruff check`** for common-mistake analysis (the `ruff` package is already installed by the environment-setup step).
- **Run `ruff format`** for style consistency.
- **Run `jitx-code-review`** as a same-model self-critique pass before declaring a task complete. Mandatory for complete-board tier (folds into Phase 1+ Think Twice); user-invoked for single-task work. See the subskill description below.

## Running JITX Designs

Build commands talk to the running runtime over its websocket — `jitx runtime start --background` from the Environment Setup must have succeeded first.

```bash
# List the designs the runtime sees in this project
jitx find

# Build a specific design
jitx build <module.path.DesignClass>

# Build every design in the project
jitx build-all
```

**Parameterized designs:** discovery (`jitx find` / `build-all`) skips `Design`
subclasses whose `__init__` has required parameters, and building one directly
fails with `Design is parameterized but no parameters were provided`. To build a
parameterized design, add a thin module-scope subclass that fills in the
arguments with concrete values.

**Don't run parallel builds on the same design.** Concurrent JITX builds against the *same design* aren't reliable — cache state, build artifacts, and design-explorer output overlap. Sequence those. Parallel builds of *different designs* in the same project (different test designs, different module paths) share the WebSocket session but are generally safe — the JITX backend serializes internally, possibly with a wait. The skill orchestrator's Phase 1 runs sub-agents in parallel on different test designs; the parallelism is at the design-work level, and concurrent builds on distinct designs are an acceptable consequence.

**Success output:** `status: ok`
**Error output:** Python traceback or `status: error`

**Structured output:** pass `--format json` on any subcommand for machine-readable output (the JSON shape is part of the public contract — what VSCode reads).

**Non-interactive shells:** some rebuilds ask `[Y/n]` (stale-instance /
component-removal confirmation) and die with `EOF when reading a line` without a
TTY — pipe assent: `yes | jitx build <design>`.

**Output files** (in `designs/<design_name>/`):
- `cache/netlist.json` - JSON netlist for verification
- `cache/design-explorer.json` - Design hierarchy
- `design-info/stable.design` - Design snapshot

**`design-info/` is encoding-versioned state**, not a disposable cache: it holds
interactive placements AND is written in the current py-jitx/runtime encoding. A
build that fails with a cryptic `No field with key '$_...' under O.../C...` after
a py-jitx or runtime version change means the on-disk design-info is unreadable by
the new pairing — restore `design-info/` from git and restart the project runtime.
Never `rm -rf designs/<design>` casually (placements live there).

**`status: ok` does not mean code routes realized copper.** Route realization is
silent; verify it programmatically via the 4.3 reverse flow (submit + `capture()` +
assert `route.traces`) — see `jitx-physical-layout`
`references/geometry-verification.md`.

### Programmatic iteration & exports (4.3 reverse flow)

For geometry-heavy iteration, skip the build CLI entirely: `with jitx.runtime as
r: rd = r.submit(DesignClass); rd.capture()` gives python the *realized* design
(route copper, computed pours, placements, nets) for direct assertion — the loop
is ~10–15 s per design and needs no TTY. Details:
`jitx-physical-layout/references/geometry-verification.md`.

Exports are **plugins** (entry-point group `jitx-plugin`), invoked as:

```bash
jitx design export <plugin> <module.path.DesignClass> [plugin options]
# e.g. jitx design export hfss my.designs.Board --output out/board   (jitxlib-ansys)
#      jitx design export legacy-odb++ my.designs.Board
```

`legacy-kicad` / `legacy-altium` / `legacy-edx` / `legacy-odb++` / `legacy-step`
run through the runtime (useful as a runtime-side cross-check of realized copper);
new-style plugins (e.g. `hfss` from `jitxlib-ansys`) consume the captured
`RuntimeDesign` in python.

## Visualizers (Board / Schematic Popout)

VSCode is no longer required to view a built design. `jitx ui open` spawns the bundled `jitx-ui` Electron viewer pointed at the running runtime. Pick exactly one of `--board` / `--schematic`:

```bash
# Open the board (PCB layout) viewer for a specific design.
jitx ui open --board     --design <module.path.DesignClass>

# Open the schematic viewer for a specific design.
jitx ui open --schematic --design <module.path.DesignClass>

# --design is optional. With one discoverable design, the viewer auto-picks it
# and prints e.g. `(one design found; using <module.path.DesignClass>)`.
# With multiple designs, the CLI prompts you to pick.
jitx ui open --board
```

The viewer probes `.socket.jitx` in the project root to find the runtime; build it first with `jitx runtime start --background` (Step 4 above). If no runtime is reachable, `jitx ui open` exits with: `Error: no runtime reachable in this project. Start one with \`jitx runtime start --background\`.`

`jitx ui open` runs *foreground* until you close the window. The viewer is a separate child process (`jitx-ui` Electron app) — if you launch it from an agent shell, background it and remember to kill it when you're done, or it will keep running after the agent exits.

```bash
# bash (macOS / Linux / WSL / Git Bash)
jitx ui open --board &                       # background
pkill -f "jitx ui open"; pkill -f jitx-ui    # stop when done
```
```powershell
# PowerShell (Windows)
Start-Process jitx -ArgumentList 'ui','open','--board'             # background
Get-Process jitx-ui -ErrorAction SilentlyContinue | Stop-Process  # stop when done
```

Use the popout viewer for visual inspection (DRC review, placement sanity check, schematic walkthrough). It is read-only — live editing (route, place, schematic move) still requires the VSCode extension.

## Project Structure

Standard JITX project layout — what `jitx project layout init` seeds, plus the conventional subdirs for larger projects:
```
project/
├── pyproject.toml          # Project config with JITX deps
├── <namespace>/            # Flat package (NOT src/<namespace>/)
│   ├── __init__.py
│   ├── main.py             # Seeded Design class lives here
│   ├── components/         # Custom component definitions (add as needed)
│   │   ├── <category>/     # mcus, connectors, power, etc.
│   │   │   └── <mfr>_<mpn>.py
│   │   └── __init__.py
│   ├── circuits/           # Reusable circuit blocks (add as needed)
│   └── designs/            # Top-level designs (add as needed)
├── designs/                # Build output directory (created on first build)
├── .socket.jitx            # Written by `jitx runtime start --background`
├── .jitx/logs/             # Runtime logs (written by the daemon)
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

For ad-hoc work outside the project-builder flow: just don't run two `jitx build` calls against the same design at once.

### Grep Gate Enforcement

Copy `scripts/grep_gates.py` from this skill into the project's `scripts/` directory. Sub-agents (and the orchestrator at every phase exit gate) run it against the project's Python package (e.g. `<ns>/`) to enforce JITX code conventions and top-level-only rules:

```bash
python scripts/grep_gates.py <ns>/
```

The script reports hard-fail hits (which block task acceptance and gate transitions) and review-required hits (which need a disposition in the task acceptance block). Pattern set and disposition rules: `references/completion-blocks.md` "Grep Gate Patterns".

### Two-Tier Quality System

Sub-agent work goes through TWO quality checks before being accepted:

**1. Sub-Agent Self-Validation ("Think Twice")**

After initial implementation, sub-agents MUST stop and run the domain-specific checklist against the datasheet before returning. This forced second pass typically catches 3-5 missed details (floating enable pins, missing thermal pads, wrong output types, forgotten decoupling). Sub-agents return a **task acceptance block** documenting what they checked and fixed — the block is mandatory; "build clean" is not a substitute. See `references/completion-blocks.md` for the template.

**2. Orchestrator Acceptance Review**

The orchestrator does NOT blindly trust the self-validation block. For each returned task:
- Read the generated code for obvious issues
- Verify the build claim (re-run `jitx build` for critical tasks)
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

### Parts Data and Footprint Conversion

The agent selects parts based on engineering requirements first. Data for each component comes from the **user-approved data source plan** (see Phase 0 data audit).

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

**How to invoke:** Use the `jitx-component-modeler` skill

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
- Add basic top-level pours or simple net copper (custom/overlapping/shapely geometry, antennas, filters, pad features, code-placed vias/routes → jitx-physical-layout)

**How to invoke:** Use the `jitx-circuit-builder` skill

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

Import: `from jitxlib.jlcpcb import JLC04161H_1080`. These include stackup, fab rules, 9 via definitions, and routing structures.

**Invoke this subskill** to create a custom substrate (the default path unless user opts into a predefined one):
- User has not confirmed JLCPCB as fab house
- Non-FR-4 materials (Rogers, Megtron)
- Non-standard layer count or impedance targets
- Additional routing structures beyond predefined

**How to invoke:** Use the `jitx-substrate-modeler` skill

Covers:
- Stackup and Symmetric layer definitions
- Material properties (Dielectric, Conductor)
- All via types (through-hole, laser micro, stacked, blind, buried, backdrilled)
- RoutingStructure with NeckDown, via fencing, geometry, reference planes
- DifferentialRoutingStructure with pair spacing and uncoupled regions
- FabricationConstraints for manufacturing rules
- Design constraint rules with Tags

### Physical Layout (`jitx-physical-layout`)

**Invoke this subskill** when user asks to:
- Draw copper from code, or create antennas, filters, or net-ties (overlapping copper)
- Build custom shapes with shapely for any feature (copper, pours, keepouts, board outline, pads)
- Add pad features — soldermask/paste openings, thermal pads with vias
- Place vias or components from code — stitching/thermal vias join nets directly; `PortAttachment` binds signal vias / control points (signal topologies only)
- Apply layout-intent tags (fanout/escape, direct-connect / thermal-relief) to layout objects
- Author code-based routes or control points for escape routing / deskew (advanced)

**How to invoke:** Use the `jitx-physical-layout` skill

Covers:
- `Copper` vs `OverlappableCopper` vs `Pour` (net membership + overlap exemption)
- Shapely (`ShapelyGeometry`) custom shapes feeding any feature; built-in composites
- Pad features (`Soldermask`, `Paste`, `SMDPadConfig`, `.thermal_pad`)
- `PortAttachment` + explicit placement — `.at()` (default), `Circuit.place` (deferred/relative), local frames
- Keepouts that shape pours; local-vs-global pour placement
- Layout-intent tags for object selection (rule mechanics stay in jitx-substrate-modeler)
- `Route`, `RoutePoint`, `PairInsertion`, `PairPoint` (advanced; stable as of JITX 4.2)

This skill owns design-side geometry and placement; the substrate owns the via and
routing-structure *definitions* and the `design_constraint(...)` rules that act on it.

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

**How to invoke:** Use the `jitx-interconnect-constraints` skill

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

**How to invoke:** Use the `jitx-pin-assignment` skill

Covers:
- `@provide`, `@provide.one_of`, `@provide.subset_of` decorators
- Programmatic `Provide().one_of()`, `Provide().all_of()`, `Provide().subset_of()`
- Hierarchical provider composition with `self.require()` inside `@provide`
- Protocol-specific pin flexibility rules (DiffPair P/N, PCIe lanes, DDR4 byte/bit)
- Topology and constraint composition on pin-assigned ports
- `DiffPairConstraint` and `ConstrainReferenceDifference` with `require()`

### Code Review (`jitx-code-review`)

**Invoke this subskill** when:
- A sub-agent finishes a complete-board task — runs at Think Twice Step 4 before emitting the task acceptance block. **Mandatory for complete-board tier.**
- The user asks "review my JITX code", "self-critique", "check JITX conventions", or "find string-hacking" on single-task work — **user-invoked**.

**How to invoke:** Use the `jitx-code-review` skill

Covers:
- Same-model self-critique against `jitx/SKILL.md` Don'ts and `references/architectural-patterns.md`
- Recognition of the recurring architectural failure patterns (string-keyed models, sibling-attribute reflection, parallel data models, owner-shaped data misplaced, tag proliferation, etc.)
- Severity-tagged findings (CRITICAL / WARNING / NOTE) that fold into the task acceptance block's `JITX code review (self):` field

Skill is the *per-task* same-model pre-pass before codex outside-voice. Phase 3b uses a different same-model pre-pass (the four-pass design audit) — see `references/outside-voice-review.md`.

### Mechanical Interface (`jitx-mechanical`)

**Invoke this subskill** when user asks to:
- Inspect or import DXF/EMN/IDF/IDX/BDF mechanical data
- Set a board outline from a mechanical CAD file
- Export JITX board XML to DXF for mechanical review
- Attach a 3D STEP model to a component
- Export the full board assembly as a STEP file
- Work with mechanical CAD data (DXF, EMN/IDF, STEP)

**How to invoke:** Use the `jitx-mechanical` skill

Covers:
- Mechanical import, inspect, and DXF export via the single `jitx-mechanical` CLI
- Required user choice for circular/plated mounting-hole policy before import
- Board-focused generated Python modules, optional mechanical-hole companion
  modules, and import reports
- `Model3D` for attaching STEP files to component landpatterns
- Board-level STEP export via the JITX UI
- STEP file sourcing, alignment, and troubleshooting

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
| Scaffold new project | `jitx project layout init` |
| Auth check / login | `jitx auth show` / `jitx auth login` |
| Install runtime | `jitx runtime update` (auto-matches py-jitx; `--version <X.Y.Z>` to pin) |
| Start runtime | `jitx runtime start --background` |
| Runtime status | `jitx runtime status` |
| List designs | `jitx find` |
| Build design | `jitx build module.Design` (sequence calls — see "Build Safety") |
| Build all designs | `jitx build-all` |
| Open board viewer | `jitx ui open --board --design module.Design` |
| Open schematic viewer | `jitx ui open --schematic --design module.Design` |
| Submit support bundle | `jitx support request` |
| Format code | `ruff format path/to/file.py` |
