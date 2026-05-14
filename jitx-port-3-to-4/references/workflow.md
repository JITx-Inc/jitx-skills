# Porting Workflow (Stanza 3.x → Python 4.x)

A phased recipe. Verification phases (0 and 6) bracket the port and are mandatory; the build smoke test is what makes a port reviewable.

## Phase 0 — Pre-verify the 3.x design

**Goal:** prove the Stanza source builds *before* you change anything.

1. Confirm an active sign-in: `~/.jitx/<3.x>/jitx sign-in -email <email>`. Without sign-in the build fails at the OCDB part-database query.
2. Point `~/.jitx/current` at the 3.x install you're about to use (`ln -sfn <3.x version> ~/.jitx/current`). JITX reads runtime state via this symlink — a stale 4.x target silently breaks the export pipeline (see `verification.md`).
3. Read the 3.x entry point. For nightly-test style designs, find the row in `nightly_design_tests/config/designs.yaml` to identify `project_dir`, `stanza_file`, and `design_name`.
4. Run `slm fetch` to resolve dependencies declared in `slm.toml`, then run the 3.x build using the installed 3.x release at `~/.jitx/<3.x version>/`. See `verification.md` for the exact invocation.
5. Capture the baseline export (BOM, schematic, board) to `/tmp/jitx-port/<design>/baseline-3.x/`.
6. If the build fails, **do not silently proceed**. Surface the error verbatim, tell the user "the 3.x baseline did not build cleanly," and ask whether to continue. Continuing is allowed — the user may be porting a legacy design that no longer builds. The user must acknowledge:
   - Pre-existing errors in the 3.x source may carry over into the 4.x port without being detected by the post-port verification.
   - The export comparison step (Phase 7) will be unreliable because there's no clean 3.x baseline to compare against.

   Record the user's acknowledgement in the porting notes (e.g. add a `BASELINE-FAILED.md` to the project root listing the 3.x error) so reviewers know the comparison was waived.

### Sibling path dependencies in `slm.toml`

`slm.toml` files commonly declare deps with `path = "../<name>"`, expecting
that sibling repo to be cloned next to the design under one parent directory.
A fresh-clone porting workflow rarely has that already, so `slm fetch` fails
with `Failed to Resolve Path ../<dep>/stanza.proj. Double check path
dependencies and confirm expected git repos in '.slm/deps'`.

Pre-clone every sibling path-dep before `slm fetch`. **Version pinning
matters** — some sibling deps have known-broken HEAD revisions that the
3.x compiler rejects. For `jsl`, pin to `v0.10.9` to avoid the
`pad-island.stanza:72 'minus' type error` introduced in 0.10.10/0.10.11
(documented in `nightly_design_tests/CLAUDE.md`).

```bash
WORK=$HOME/tmp/<design-name>_port
cd "$WORK"
git clone git@github.com:JITx-Inc/PD-audio.git && (cd PD-audio && git checkout <commit>)
git clone git@github.com:JITx-Inc/jsl.git      && (cd jsl && git checkout v0.10.9)
# now slm fetch resolves cleanly:
cd PD-audio
SLM_ROOT=~/.jitx/<3.x>/slm PATH=~/.jitx/<3.x>/stanza:$PATH ~/.jitx/<3.x>/slm/slm fetch
```

### Triage protocol when the 3.x build fails

When step 4 fails, run **at most one probe** before deciding to revert and
record `BASELINE-FAILED.md`. Acceptable probes:

1. Look for a commented-out `import` line in the failing file that looks
   related to the missing symbol (e.g. `; import ocdb/utils/bundles` when
   the error is `Could not resolve 'usb-2-data'`). Uncomment and re-build.
2. Try a different jsl tag pin (jsl-related errors specifically — e.g.
   `pad-island.stanza:72` → pin `v0.10.9`).

If the single probe doesn't expose a clean path to `exit 0`, **revert** to
the original source verbatim and record the failure in
`BASELINE-FAILED.md`. Multi-step debugging of the 3.x source is out of
scope for the porting workflow; the port can use `main.stanza` itself as
the source-of-truth even without a clean baseline. Real example from the
`pd_audio` port: three layered import / namespace conflicts at commit
`78b6709` — uncommenting one import exposed an ambiguous-reference error,
removing another import exposed a third symbol that's jsl-only. The
right call was to revert and document, not to keep digging.

## Phase 1 — Inventory the Stanza design

Read the source tree and list:

- Entry point (`main.stanza`) and any `set-board` / `set-current-design` / `view` / `run` calls.
- Top-level `pcb-module` (the design root).
- All child `pcb-module` definitions (the hierarchy).
- All `pcb-component` definitions (leaves).
- Any `pcb-stackup`, `pcb-via`, `pcb-material`, `pcb-bundle` declarations.
- `supports` / `require` clauses (provide/require — these become Python decorators).
- Topology declarations and signal constraints.
- The `stanza.proj` and `defpackage` graph (informs Python module layout).

This inventory drives the rest of the port. Save it to a scratch file so it can be checked off as work progresses.

### Finding hidden Stanza stdlib symbols

Some bundle / helper symbols are not present in any text-grep-able
`.stanza` file — they live in compiled stdlib packages at
`~/.jitx/<3.x>/pkgs/*.pkg`. The shim files
(e.g. `ocdb/utils/bundles.stanza`) only do `forward
jitx/parts/legacy-ocdb-misc`, with no `pcb-bundle` declarations to grep.

If `grep -rn <symbol> ~/.jitx/<3.x>/slm/` finds nothing, search the
compiled packages with `strings(1)`:

```bash
strings ~/.jitx/<3.x>/pkgs/jitx\$parts\$legacy-ocdb-misc.pkg | grep <symbol>
```

Common offenders that cause "where is this defined?" rabbit-holes during
inventory: `usb-2-data`, `I2S-MCK`, `I2S-SDMI`, `SPI-DQS`, `octal-spi`,
the legacy `power` bundle. Knowing where these live also tells you which
import combination is required in the porting target (vs which can be
satisfied by jsl or another sibling lib).

## Phase 2 — Bootstrap the Python project

Use the `jitx` skill for the canonical layout. Minimum:

```
<project>/
├── pyproject.toml
├── main.py             # imports + Design subclass
└── <package>/          # mirrors the Stanza package layout where useful
    ├── __init__.py
    ├── components/
    └── circuits/
```

Stub the top-level `class <Design>(Design)` so `python -m jitx build` can find a target before the implementation lands. Use the `jitx-component-modeler` and `jitx-circuit-builder` skills for boilerplate templates.

> ⚠️ Before the first build smoke, you must run `~/.jitx/<4.x>/jitx interactive
> "$PWD" &` and wait for `.socket.jitx` to appear. The `interactive` subcommand
> is **not** listed in `jitx --help` (known quirk) — do not assume it's missing
> because `--help` doesn't show it. Without it, builds fail with
> `Unable to determine socket URI`. See the canonical bootstrap recipe at
> [`jitx-skills:jitx/references/bootstrap.md`](../../jitx/references/bootstrap.md)
> for the full ordered checklist.

## Phase 3 — Port components (leaves first)

One Python file per `pcb-component`. For each:

1. Look up the construct mapping in `references/construct-map.md`.
2. Translate pin tables, package, landpattern, symbol mapping.
3. Defer API depth to `jitx-component-modeler` — especially for symbol generation, multi-unit symbols, thermal pads, and complex pin mappings.
4. If the Stanza component used parametric helpers (e.g. a generator that produced a family of components), port the generator as a Python function or factory rather than transcribing every emitted instance.

### Read `components/*/module.stanza` before closing Phase 3

In Stanza, a `pcb-component` is the bare IC. A companion `pcb-module` in
`components/<part>/module.stanza` (or similar wrapper) is a parametric
**application circuit** that adds bypass caps, output filter networks,
bootstrap caps, thermal vias, and exposes higher-level ports. Skipping
these wrappers is the most common silent-failure mode — the bare component
ports cleanly, the design builds `status: ok`, and entire output sections
are missing from the netlist (see SKILL_GAPS GAP-18).

For each component used by the design:

- [ ] Does `components/<part>/` contain both `component.stanza` and
      `module.stanza` (or `<part>-module.stanza`, etc.)?
- [ ] If yes: read `module.stanza` fully. List its ports, passives,
      output networks, and any `add-thermal-vias` calls.
- [ ] Map each element of `module.stanza` into the **Python `Circuit`**
      that instantiates the component. The bare component goes in Phase 3;
      the module wrapper's contents go in Phase 4 inside the appropriate
      Circuit.

## Phase 4 — Port circuits / modules

Bottom-up: leaf circuits before parents. For each:

1. Translate `pcb-module` to `class X(Circuit)`.
2. Map `inst` declarations to attribute assignments inside `__init__`.
3. Translate every `net (a, b)` / `connect ...` to a Python `+` chain on `Port`s.
4. Use `jitx-circuit-builder` for nets, passives, power, pours, copper geometry.
5. For any `supports` / `require` clause, first run the **hardware-analysis
   gate** below before delegating to `jitx-pin-assignment` — most `require`
   constructs in real designs are bundle-typed fixed wiring, not pin-mux.

### Hardware-analysis gate for `require` / `supports`

Stanza syntax alone does not tell you whether a `require` reflects real
layout-engine flexibility. The decision tree (real mux flexibility →
`@provide`/`require()`; fixed hardware path → plain `Net`; unknown →
TODO + read the datasheet) is general to JITX 4.x and lives in
[`jitx-skills:jitx-pin-assignment`](../../jitx-pin-assignment/SKILL.md)
§"Hardware-analysis gate — pin-assignment vs fixed wiring". Apply it
verbatim during the port.

Porter twist: a Stanza `require` clause does **not** imply the Python
translation needs pin-assignment. Most Stanza `require`s in real designs
are fixed wiring — reaching for `@provide` by default is the most
common over-translation.

### Phase 4 exit criteria (do not skip)

`status: ok` from `python -m jitx build` is **not** sufficient to close
Phase 4. A design with stub `Port()` connections and "module port(s) have
no internal connections" warnings can build cleanly while half the wiring
is missing.

Before advancing to Phase 5, grep the ported circuits for `# TODO` and
unconnected `Port()` declarations that correspond to Stanza `require` /
`supports` / `provide` constructs. Every one must reach one of these
three states:

| State | How to reach it |
|---|---|
| **Implemented as fixed wiring** | Hardware analysis (above) shows no layout flexibility; wired as plain `Net` |
| **Implemented via `@provide` / `require()`** | Invoke `jitx-pin-assignment` inline before closing Phase 4 — do not defer |
| **Explicitly deferred** | Named follow-up task created; reason documented in a `PORT-DEFERRED.md` or PR notes; not just a `# TODO` comment |

> ⚠️ The `jitx-circuit-builder` skill **cannot invoke other skills**. Its
> delegation notes for `require` / `provide` describe what a human (or the
> calling agent) should do — they do not happen automatically. If you see
> a stubbed provide/require after `jitx-circuit-builder` finishes, **you
> must explicitly invoke `jitx-pin-assignment` yourself** as part of Phase 4.

> ⚠️ Build warnings of the form `module port(s) <foo> have no internal
> connections` are a **signal that Phase 4 is incomplete**, not a cosmetic
> artifact. Treat them as Phase 4 errors and resolve before Phase 5.

### Power topology check (mandatory)

Stanza power-net names invert easily during porting. Before naming any net
in Python, read **every** Stanza net definition that touches the input
connector (`net (conn.p[N] ...)`) and the regulator (`net (reg.vout ...)`)
and write down which Python name maps to which physical rail. See
`pitfalls.md` §"Power topology / net naming" for the explicit mapping
table and rationale.

### Context budget

Phase 4 is the most context-intensive step in the port. The general
guidance on managing context for ≥3-circuit designs (checkpoint per
circuit, keep both source files open, use a long-context model) lives in
[`jitx-skills:jitx/SKILL.md`](../../jitx/SKILL.md) §"Working on large
designs — context budget". The porter-specific consequence: keep the
Stanza source for the in-progress circuit and the corresponding Python
file open simultaneously, since each circuit's port involves both ends.

## Phase 5 — Substrate, constraints, topology, pin assignment

These are the domain-heavy parts of the port. They typically arrive intact in the design but must be reformulated for the Python API:

- **Stackup:** translate `pcb-stackup` to `Stackup` / `Symmetric` (uses `jitx-substrate-modeler`). **If the design targets JLCPCB**, do not hand-roll the stackup — use one of `JLC04161H_1080`, `JLC04161H_7628`, `JLC06161H_7628` from `jitxlib.jlcpcb` (the closest analog to Stanza `jlcpcb-jlc2313` is `JLC04161H_1080`). There is no 2-layer JLCPCB class; build a custom `Substrate` for that case.
- **Vias and routing structures:** `pcb-via` → `Via`; new in 4.x, formalize via `RoutingStructure`, `DifferentialRoutingStructure`, `NeckDown` (all in `jitx.si`; construct with the `symmetric_routing_layers({...})` helper) where appropriate. Stanza-side `structure ... = SingleEnded(...)` / `Differential(...)` declarations have **no class with those names** in 4.x — rename to `RoutingStructure` / `DifferentialRoutingStructure`.
- **Signal constraints:** Stanza topology constraints → `Constrain`, `ConstrainDiffPair`, `TimingConstraint`, `InsertionLossConstraint`, `ReferencePlanes` (uses `jitx-interconnect-constraints`).
- **Topology graph:** `>>` operator builds the routed graph; bridging/terminating pin models attach to nodes.

## Phase 6 — Post-verify the 4.x design

**Goal:** prove the Python target builds, types-check, and produces an export.

1. Confirm an active sign-in (same as Phase 0). The 4.x build connects to the part database too — without sign-in it fails with `You are not authenticated`.
2. Repoint `~/.jitx/current` to the 4.x install (`ln -sfn <4.x version> ~/.jitx/current`). The same symlink rule applies — a stale 3.x target will break the 4.x pipeline.
3. Set up a project venv: `python -m venv .venv && source .venv/bin/activate && pip install --pre .` (or `uv sync --active --prerelease=allow`). The `jitx` Python package lives on the JITX internal index, not public PyPI.
4. `pyright` must be clean (the `jitx` skill covers the venv + pyright config). Treat any `pyright` error as blocking — type errors in JITX 4.x commonly mask wiring bugs.
5. Start `~/.jitx/<4.x>/jitx interactive "$PWD" &` in the background — it writes `.socket.jitx`, which `python -m jitx build` discovers automatically by walking up from cwd.
6. Run `python -m jitx build <package>.<module>.<DesignClass>` from the project root (with `PYTHONPATH=$PWD` if the project isn't installed). See `verification.md` for the exact invocation.
7. Capture the export to `/tmp/jitx-port/<design>/ported-4.x/`.

## Phase 7 — Compare exports

Manual today, automatable later. Two layers of checks:

1. **General six-section export verification** (applies to any 4.x
   design, not just ports) — see
   [`jitx-skills:jitx/references/export-verification.md`](../../jitx/references/export-verification.md):
   A. Net inventory, B. Connector pin assignment, C. Power topology,
   D. Component output pins, E. Passive count sanity, F. Control-signal
   completeness.
2. **Port-only checks** — see `verification.md` §"Compare exports —
   port-mode wrapper": B′ connector pin-index translation (Stanza
   1-based ↔ Python 0-based), E′ passive-count delta between Stanza
   and Python (catches missing application-circuit wrappers).

`status: ok` is not evidence of correctness — the TEC-example pilot
built cleanly with four categories of silent netlist errors. Treat
Phase 7 as mandatory, not optional. Until the planned
`scripts/compare-exports.py` automation lands, attach the two export
directories (`baseline-3.x/` and `ported-4.x/`) to the PR / report and
complete the checklist by hand.

## Heuristic: what to port first when stuck

If the design is large, port a **vertical slice** end-to-end before going wide:

1. Top-level `Design` class with a Board + Substrate (placeholder) + a single trivial Circuit (one component).
2. Confirm pre/post build smoke works.
3. Add components and circuits incrementally, re-running `python -m jitx build` after each addition.

This catches build / packaging / pyright issues early, when the diff is small enough to debug.
