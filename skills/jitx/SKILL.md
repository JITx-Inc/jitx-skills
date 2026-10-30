---
name: jitx
description: "Base skill for JITX Python PCB design: install, the jitx CLI, auth and the runtime, building designs, the viewers, exports, code quality (ruff, pyright, type annotations, check.py and grep gates), and design introspection (jitx.inspect, jitx.query, runtime submit). Use to set up JITX, start the runtime, build or find a design, open the viewer, fix a build or environment error, run ruff, pyright or static checks, or find things in a design from Python. Route a whole board from requirements to jitx-project-builder, self-review of written code to jitx-code-review, component modeling to jitx-component-modeler, wiring and passives to jitx-circuit-builder, stackups to jitx-substrate-modeler, layout geometry and realized-geometry checks to jitx-physical-layout, design rules to jitx-layout-constraints, SI constraints to jitx-interconnect-constraints, pin flexibility to jitx-pin-assignment, and mechanical CAD to jitx-mechanical."
---

# JITX

Run this skill's setup before any sub-skill: they assume a working runtime.

> **Supported version line.** This bundle is written for **jitx 4.6.x** (`jitx >= 4.6, < 4.7`). Sibling skills do not restate the range; their "verified on 4.4.0" notes are evidence for those claims on that release. Where the installed package differs from these pages, follow the package and verify every import with `pyright`.

Commands are bash. In Windows PowerShell: use `python` for `python3`, activate with `.\.venv\Scripts\Activate.ps1`, write the `[ ... ] ||` guards as `if (-not (Test-Path ...))` and `grep -q` as `Select-String -Quiet`, and clear a `$env:VAR=` setting with `Remove-Item Env:VAR` when it should apply to one command. On Windows, in PowerShell or Git Bash, the `&`, `pkill` and `pgrep` steps have no verified form: ask the user to run long-lived commands in their own terminal and to close viewers themselves.

## Install

### Step 1: CLI and packages

In an existing project, activate its venv, read `jitx --version`, and ask before moving it to another line.

```bash
[ -d .venv ] || python3 -m venv .venv
source .venv/bin/activate          # Git Bash on Windows: .venv/Scripts/activate
python -c 'import sys; assert sys.version_info >= (3, 12), sys.version'
pip install "jitx>=4.6,<4.7" jitxlib-standard jitxlib-parts ruff pyright
jitx --version
```

`jitx` brings the framework and CLI but no `jitxlib`: `jitxlib-standard` gives `jitxlib.landpatterns`, `.symbols`, `.protocols`, `.bundles`, `.via_structures` and `.physics`; `jitxlib-parts` the `Resistor`/`Capacitor`/`Inductor` queries; `jitxlib-jlcpcb`, only for a confirmed JLCPCB fab, its substrates.

If the assertion fails, recreate `.venv` with Python 3.12 or newer.

### Step 2: Project

```bash
[ -f pyproject.toml ] && grep -q jitx pyproject.toml || jitx project layout init   # ask first if files other than .venv exist
pip install -e . "jitx>=4.6,<4.7" jitxlib-standard jitxlib-parts
python -c "import jitxlib.landpatterns, jitxlib.parts"
```

`jitx project layout init` writes a flat `<ns>/` package (not `src/<ns>/`) and `pyproject.toml`. Change its `jitx>=4.4.0,<5` to `jitx>=4.6,<4.7`; add `jitxlib-parts>=2,<3` (and `jitxlib-jlcpcb` when used) to `dependencies`. Without `pip install -e .`, `jitx find` exits 0 listing no designs (`import failed: ModuleNotFoundError`).

Passive queries need a provider chain in `pyproject.toml` (without one: `NoChainConfigured`). Commit `parts/approved-parts.csv` (user-approved parts only) and the build-written `parts.lock.json` (never hand-made). If the user has none, copy the example CSV `jitxexamples` ships there (`jitx-project-builder` Phase 0) and tell the user it is not an approval:

```toml
[tool.jitx.parts]
chain = ["csv:parts/approved-parts.csv", "ideal"]
```

`ideal`, last, synthesizes unorderable `IDEAL-...` parts so the design builds before approval, silently answering most queries the CSV cannot. Before calling it done, pass `jitx build <design>` and `jitx design export parts-check <design> --fail all`, and check that no MPN starts with `IDEAL-`: the parts check passes an ideal part. Take an `IDEAL-` part to the user; change a value or rating only with their sign-off. On the stand-in, the user approves the final build's MPNs or supplies a list. Read parts and `IDEAL-` MPNs from the design, never from the lock. Run [`prune_lock.py`](scripts/prune_lock.py), excluding test designs, after removing a component or running tests, and before committing or handing off the lock. Never delete the whole lock once parts are placed, routed or approved without the user's say-so. Cleanup, care, deliberate re-resolves: [`references/parts-lock.md`](references/parts-lock.md). CSV format, lockfile, the `IDEAL-` test, parts databases: https://docs.jitx.com/en/latest/essentials/design/parts.html

The scaffold skips `git init` (do it and say so). Its `.gitignore` keeps the built design directory tracked on purpose: do not broaden it.

### Step 3: Auth

`jitx auth show` prints `Authorized: yes | no`. On `no` with a token on disk, `jitx auth refresh` renews it headlessly. With no account on disk, stop and ask the user to sign in: `jitx auth login` (opens a browser), the VSCode JITX sidebar, `jitx auth login --email <email> --password-stdin` for password accounts, or `jitx auth install-token` for a token a team admin exported. `LauncherError: no JITX runtime found` means none is installed: do Step 4's install, then return. `LauncherError: ... did not produce valid JSON` usually means `JITX_ROOT` points at a dev build: unset it, retry, and tell the user.

### Step 4: Runtime

Each project runs its own runtime daemon (socket: `.socket.jitx`).

```bash
jitx runtime introspect | grep '"version"'; jitx --version     # major.minor must match
grep jitx_version .jitx/runtime.json 2>/dev/null               # the running daemon, if any
```

A mismatch fails like a code bug. If `introspect` fails or any major.minor differs, ask first: the switch applies to every project on the machine. Honor a pin in `$JITX_RUNTIME_VERSION`, a `jitx.version` file or `mise.toml` with `--version`, then run `jitx runtime install`. A pre-release `X.Y.ZrcN` needs `--version X.Y.Z-rc.N --testing`, or it can get a production runtime. Install does not touch a running daemon: `jitx runtime stop` here (other projects need it too: tell the user), then repeat the check. Start only once it passes; if it cannot, report a blocker:

```bash
jitx runtime status | grep -q reachable || jitx runtime start --background
```

`jitx runtime status` exits 0 either way: read its text (`reachable at ws://...` or `not running`).

### Step 5: Verify

`jitx runtime status` reads `reachable`, and `jitx find` lists the designs with no `import failed` line. On later runs, repeat Step 4's check and gated start, then this check.

**Missing-dependency rule.** If the runtime will not start, `jitx find` errors, or a required import is missing, stop and report it as a blocker. Never drop or substitute a design requirement to get past it.

## CLI

| Task | Command |
|---|---|
| List designs | `jitx find` |
| Build one / all | `jitx build <module.path.DesignClass>` / `jitx build-all` |
| Runtime | `jitx runtime start --background`, `status`, `stop`, `introspect`, `cleanup` (leaked runtimes; reports unless `--kill`) |
| Viewers | `jitx ui open --board` / `--schematic` `[--design <module.path.DesignClass>]` |
| Export | `jitx design export <plugin> <module.path.DesignClass>` |
| Script the open layout | `jitx design session <design> > .jitx/session.log 2>&1 &`, then `jitx design exec <design> script.py` (runs `main(design)`; paths start `root.`). Until the session is up, exec fails with `message could not be delivered`: retry every 5 s for up to a minute. Then, or on a traceback, report what `.jitx/session.log` says. End with `jitx design session --stop <design>` |
| Dependencies | `jitx project dependencies check` |
| Support | `jitx support bundle` / `jitx support request` (sends data to JITX: ask first) |

`jitx --format json <command>` gives JSON.

## Running designs

`jitx build` prints `status: ok` or a traceback and `status: error`. Results land in `designs/<module.path.DesignClass>/`: `cache/netlist.json`, `cache/design-explorer.json` (the hierarchy), and `design-info/` (interactive placements). Never delete `designs/<design>` casually. A cryptic `No field with key '$_...'` after a version change means `design-info/` is unreadable by the new pairing: restore it from git and restart the runtime.

- **`--dry` is not a build.** With no runtime, `jitx build` exits 1 and offers `--dry`, which then reports `status: ok`. It misses failures such as `Public name already in use`, and never satisfies a step that asks for a build.
- **Dependency check.** Do not run the `jitx project dependencies upgrade` a build suggests: it can leave the supported line.
- **Parameterized designs.** `jitx find` lists a `Design` whose `__init__` takes required arguments, but building it fails with `Design is parameterized but no parameters were provided`. Add a thin module-scope subclass with concrete values and build that.
- **Rebuild prompts.** Some rebuilds ask `[Y/n]` before deleting stale instances; headless, the build ends `EOF when reading a line`. The answer is the user's: end your build, tell them what it printed, and rebuild once they answer in the JITX UI or their own terminal. Pipe `yes |` only when the user says to; PowerShell has no verified equivalent.
- **Stalled build.** Run long builds with `PYTHONUNBUFFERED=1`. If a build shows no output and little CPU for a minute, check `jitx runtime status` in every other open JITX project, `pgrep -fl interactive-client` for accumulated clients, and what `jitx runtime cleanup` reports. Ask before stopping anything.
- **`status: ok` is not routed copper.** Realization is silent: verify geometry from Python (Introspection, `jitx-physical-layout`).
- **Exports.** The `legacy-*` plugins are fab and CAD handoffs, not verification. Other packages (such as `jitxlib-ansys`) add plugins.

### Build safety: don't parallelize same-design work

Concurrent builds of one design share cache and output: sequence them. Different designs in one project are generally safe: the runtime serializes them.

## Visualizers

`jitx ui open --board` or `--schematic` opens the `jitx-ui` viewer on the running runtime (no runtime: exit 1). Pass `--design` from a script, and background it: it runs until the window closes. Killing the backgrounded `jitx ui open` leaves the window up: close only the viewer you opened, matched by the runtime port (`jitx runtime status`) and design, `pkill -f "jitx-ui .* <port> design/<module.path.DesignClass>$"`. Never a bare `pkill -f jitx-ui`: another viewer is an interactive editor and may hold unsaved edits.

## Writing good code

These hold for every JITX skill.

- **Annotate every function's parameters and return type**, including test methods (`-> None`). No `# type: ignore` and no `# pyright:` comments: narrow, assert or annotate instead.
- **Run pyright inside the project's environment.** Against an interpreter without `jitx`, pyright reports `Import "jitx" could not be resolved`: that is the interpreter, not the code, so never "fix" the imports. A tool launched from outside the venv points at it with `[tool.pyright] venvPath`/`venv` or `pyright --pythonpath`.
- **Commit a ruff config and run ruff from the project root.** Config discovery walks up from the working directory. Set `line-length` explicitly if anything in the project emits Python. `RUF012` flags class-body port arrays (`GND = [Port() for _ in range(n)]`), which are the declaration model: silence it per file in `[tool.ruff.lint.per-file-ignores]` with a comment. Moving the ports into `__init__` breaks the component.
- **Copy `scripts/check.py` and `scripts/grep_gates.py` from this skill into the project's `scripts/`** and run `python scripts/check.py <ns>/` before calling work done. It runs ruff, ruff format, pyright, the grep gates and, with `--build`, a build. How to disposition a gate hit: `jitx-project-builder` [`references/completion-blocks.md`](../jitx-project-builder/references/completion-blocks.md).
- **Test with `jitx.test.TestCase`** and `python -m unittest discover -s tests`. Assert each value against its source (datasheet, fab report, standard, independent formula), never the tested code's constants or output: that catches no regression. Test designs set `parts_lock = Lock(mode=LockMode.OFF)` (`references/parts-lock.md`).
- **Run `jitx-code-review`** as a self-critique before declaring a task complete.

### Don'ts

Worked counter-examples for each: `references/architectural-patterns.md`.

- **Don't key design state by hand-built strings.** `dict[str, X]` indexed by `f"TX_b{i}"` means the structural object is missing. Use lists, `@dataclass(frozen=True)`, or dicts keyed by Ports and structural objects. `@provide` mappings keyed by Port are the framework's contract, not a parallel model.
- **Don't reflect on `self` by name to find your own children.** Declare a `list` or `dict` attribute up front: `self.lanes: list[DiffPair] = [...]`.
- **Don't build an intermediate `list[dict[str, Any]]` "spec" model and then iterate it to emit JITX calls.** Construct JITX objects directly.
- **Don't mutate a circuit from a free function.** Compose a `Container` or `Circuit` subclass and assign it as a member.
- **Don't restate data or logic owned by a structural object.** Query the owner: `self.substrate.signal_via[layer]`, `lp.get_pad(row, col)`.
- **Don't reinvent framework code in design code.** A banned pattern inside the framework class that owns the invariant does not license it on your side. Use the public API, or a public adapter on a subclass over a protected method.
- **Don't generate lookup tables or populate mutable globals at module-import time.** Class-body structural collections are fine.
- **Don't manually assign values that JITX assigns automatically**: reference designators, net names from topology, layer-derived names.
- **No `setattr` / `getattr`, no `type(...)` to build classes, no JITX subclass defined inside a function or method.** These break instantiation tracking.
- **No `type()` for type checks** (use `isinstance`), no double-underscore members, and no leading-underscore names from elsewhere; a method may call another method on its own class.

## Introspection

The design tree exists only inside an instantiation context: a `jitx.test.TestCase`, or a design submitted to the runtime. Outside one, `MyDesign()` is an `Instantiable` placeholder whose traversal yields nothing: an empty result there is not evidence.

```python
from jitx.copper import Copper
from jitx.inspect import decompose, extract, visit
from jitx.net import Port
from jitx.query import query
from jitx.test import TestCase


class Find(TestCase):
    def test_find(self) -> None:
        design = MyDesign()   # MyDesign, MyResistor: your own classes
        for trace, port in visit(design, Port):   # str(trace.path) == "circuit.r1.p1"
            ...
        ports = list(extract(design.circuit, Port))
        p1, p2 = decompose(MyResistor(), Port)
        top = [c for _, c in query(design, Copper, filter=lambda c: c.layer == 0)]
```

- **`visit(root, types, through=None, *, opaque=None, refs=False, filter=None)`** yields each structural match with its `Trace` (`path`, `transform`). `extract` is `visit` without the trace. `decompose` stops at direct children, traversing lists and dicts.
- **`jitx.query.query`** takes the same filters (`through` is keyword-only) and also converts objects through registered transformers, such as `Pad -> Copper`, `Via -> Copper`, `Via -> Cutout` and `Route -> Copper`; a `Pour` is already `Copper`. Results are in the source's local frame: compose `trace.transform` yourself.
- **What the runtime knows:** `with jitx.runtime as r: rd = r.submit(MyDesign)` gives `rd.root`, `rd.query(...)`, `rd.nets.find(element)` (the `Net` the runtime assigned, or `None`) and `rd.layers`. Realized routes and pours need `r.capture(...)`. Its semantics and the geometry-verification loop are in `jitx-physical-layout` `references/geometry-verification.md`.

## Sub-skills

Invoke it before writing that code.

| Work | Skill |
|---|---|
| A whole board from requirements: PLAN.md, phases, gates, sub-agents | `jitx-project-builder` |
| A component from a datasheet, part number, pin file or footprint | `jitx-component-modeler` |
| Wiring, nets, typed ports and bundles, hierarchy, placement, passives | `jitx-circuit-builder` |
| Stackup, materials, vias, routing structures, fab rules | `jitx-substrate-modeler` |
| Pours, copper, shapes, pad features, code-placed vias and routes, realized-geometry checks | `jitx-physical-layout` |
| Design rules, clearances, net classes, power widths, decoupling placement, fanout step-down | `jitx-layout-constraints` |
| Topology, SI constraints, diff pairs, protocol constraints | `jitx-interconnect-constraints` |
| provide/require, pin muxing, lane and polarity swapping | `jitx-pin-assignment` |
| Self-review of JITX code against the rules above | `jitx-code-review` |
| DXF/IDF/STEP import and export, board outlines, 3D models | `jitx-mechanical` |

A buildable board goes to `jitx-project-builder`.

## Documentation lookup

JITX docs live at `https://docs.jitx.com/en/latest/` (LLM index: `https://docs.jitx.com/llms.txt`). For anything unfamiliar, find its page in `references/docs-index.md`, fetch and apply it. If it does not resolve, say so rather than proceed from memory.
