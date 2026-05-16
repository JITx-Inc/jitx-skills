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

Pre-clone every sibling path-dep before `slm fetch`. **Preserve each
source repo's pinned deps** — every design committed against 3.x is
already pinned to a sibling revision that worked at the time, and that
revision is the right starting point for the port. Use the design's
`slm.toml` versions verbatim unless one of the known baseline blockers
fires (see `verification.md` §"Known baseline blockers — do not waste
time debugging"). The catalogued `pad-island.stanza:72 'minus' type
error` from `jsl ≥ 0.10.10` against `jitx 4.0.5` is one such case —
pinning `jsl` back to `v0.10.9` is the documented mitigation for that
specific blocker, not a general rule.

```bash
WORK=$HOME/tmp/<design-name>_port
cd "$WORK"
git clone git@github.com:JITx-Inc/<design>.git && (cd <design> && git checkout <commit>)
git clone git@github.com:JITx-Inc/jsl.git      && (cd jsl && git checkout <version-from-design-slm.toml>)
# now slm fetch resolves cleanly:
cd <design>
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

**3.x stdlib bundle-symbol drift.** Symbols can drop out of the
3.x stdlib between point releases (real example: `SPI-DQS` is absent
from `~/.jitx/3.36.1/pkgs/*.pkg` even though it was a documented
bundle augmentation symbol in earlier releases). When pre-verify
fails with `Could not resolve '<SYMBOL>'` for a bundle augmentation
symbol — `SPI-DQS`, `usb-2-data`, `I2S-MCK`, etc. — confirm with:

```bash
strings ~/.jitx/<3.x-version>/pkgs/*.pkg | grep -c '^<SYMBOL>$'
```

A zero count means the symbol was dropped from that release. This is
not a port-side issue: a commit that built cleanly on `3.x.<old>` may
legitimately fail on `3.x.<new>`. In that case either pin to the older
release where the symbol exists, or accept the static Stanza source
as the only Phase 7 fallback comparison reference (see
`references/verification.md` §"Phase 7 fallback — Stanza source as the
reference") and document the failure in `BASELINE-FAILED.md`.

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
are missing from the netlist.

For each component used by the design:

- [ ] Does `components/<part>/` contain both `component.stanza` and
      `module.stanza` (or `<part>-module.stanza`, etc.)?
- [ ] If yes: read `module.stanza` fully. List its ports, passives,
      output networks, and any `add-thermal-vias` calls.
- [ ] Map each element of `module.stanza` into the **Python `Circuit`**
      that instantiates the component. The bare component goes in Phase 3;
      the module wrapper's contents go in Phase 4 inside the appropriate
      Circuit.

#### When the Stanza module computes values from kwargs (parametric formula)

A Stanza module signature like

```stanza
public pcb-module module (-- output-voltage:Double = 3.3
                             input-voltage:Double = 25.0
                             output-current:Double = 3.0
                             ripple:Double = 30.0e-3
                             placed:True|False = false) :
```

is **parametric**: the body computes inductor value, feedback divider
ratio, output-cap count, soft-start cap, etc. from those kwargs. The
worked example is in
[`references/side-by-side/05-parametric-module.md`](side-by-side/05-parametric-module.md).

The Python port must **port the formula**, not pick the value the
formula produces at one example call site. Concrete signals to look
for in the Stanza body:

- `closest-std-val(...)` — value computed and snapped to a standard
  E-series. Port using `jitx-skills:jitx-circuit-builder` §"Snap
  computed values to a standard E-series".
- `for i in 0 to <computed-int> seq : bypass-cap-strap(...)` —
  output-cap count derived from a derating formula. Port the count
  computation as well as the per-cap parameters.
- `inst feedback : ocdb/modules/passive-circuits/voltage-divider(...)` —
  the generator solves for two resistor values from a target
  ratio + divider current. Port the divider math; do **not** hardcode
  the two resistor MPNs picked at one example call.
- `val css = soft-start * 5.5e-6 / 0.8` — closed-form RC sizing.

Branching on a specific kwarg value (`if abs(output_voltage - 3.3) <
0.01: r_hi = 31.6e3 else ...`) on the Python side is a code smell
that flags this trap: it's the symptom of picking values from one
example instantiation instead of porting the formula.

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

### Phase 4 leakage check — top-level-only constructs in subcircuits

A subtle Phase 4 failure mode: a faithful structural port of a Stanza
module places its symbols / pull-ups / pours where the Stanza module
had them — which on the Stanza side was the consumer subcircuit, and
on the Python side should be the top-level `Design`. The build still
passes, but the schematic shows duplicate ground symbols, I²C pull-ups
attach to the wrong rail copy, and copper pours land in the wrong
frame. See
[`jitx-skills:jitx-circuit-builder`](../../jitx-circuit-builder/SKILL.md)
§"Top-level-only constructs" for the full list and rationale.

Before advancing to Phase 5, grep the **ported circuits** (everything
not in `designs/` or the top-level `Design` class) for these tokens:

```bash
grep -rn "GroundSymbol\|PowerSymbol"            <python-pkg>/circuits/
grep -rn "Pour("                                <python-pkg>/circuits/
grep -rn "ReferencePlanes"                      <python-pkg>/circuits/
grep -rn "Constrain\|ConstrainDiffPair"         <python-pkg>/circuits/
# Shared-bus pull-ups — grep for the consumer-side rail attach pattern
grep -rEn "Resistor\(.*\)\.insert.*VDD3V3|3V3"  <python-pkg>/circuits/
```

Each hit needs to be either moved to the top-level `Design` / `designs/`
module, or justified inline (e.g. a chip-local rail like CH224K's
internal VDD legitimately stays inside the cir-01 subcircuit because
the rail itself does not leave the subcircuit). I²C / FAULT / PG
pull-ups to a board-wide rail (`+3V3`) always move up.

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

- **Stackup:** translate `pcb-stackup` to `Stackup` / `Symmetric` (uses `jitx-substrate-modeler`). **If the design targets JLCPCB**, prefer the predefined substrates from `jitxlib.jlcpcb` — `JLC04161H_1080` (closest analog to Stanza `jlcpcb-jlc2313`), `JLC04161H_7628`, or `JLC06161H_7628`. **If `jitxlib.jlcpcb` is not importable** in the installed version, fall back to the `four_layer_fr4.py` template under `jitx-substrate-modeler/references/templates/` rather than hand-rolling from scratch. There is no 2-layer JLCPCB class; build a custom `Substrate` for that case regardless.
- **Vias and routing structures:** `pcb-via` → `Via`; new in 4.x, formalize via `RoutingStructure`, `DifferentialRoutingStructure`, `NeckDown` (all in `jitx.si`; construct with the `symmetric_routing_layers({...})` helper) where appropriate. Stanza-side `structure ... = SingleEnded(...)` / `Differential(...)` declarations have **no class with those names** in 4.x — rename to `RoutingStructure` / `DifferentialRoutingStructure`.
- **Signal constraints:** Stanza topology constraints → `Constrain`, `ConstrainDiffPair`, `TimingConstraint`, `InsertionLossConstraint`, `ReferencePlanes` (uses `jitx-interconnect-constraints`).
- **Topology graph:** `>>` operator builds the routed graph; bridging/terminating pin models attach to nodes.

### Phase 5 exit criteria — Stanza-source constraint inventory

Before advancing to Phase 6, grep the **entire Stanza source tree** for
the four constraint patterns below and locate the Python equivalent for
each hit. Missing any one is a Phase 5 blocker, not a Phase 6 follow-up
or a `# TODO` comment.

```bash
grep -rn "topology-segment"        <stanza-root>   # → a >> b
grep -rn "structure(.*)\s*="       <stanza-root>   # → Constrain(...).structure(...) OR Tag + design_constraint(...).routing_structure(...)
grep -rn "timing-difference"       <stanza-root>   # → .timing_difference(lo, hi) on ConstrainDiffPair / ConstrainReferenceDifference
grep -rn "property(.*\.net-class)" <stanza-root>   # → Tag + design_constraint(tag).routing_structure(...)
```

For each hit, locate the corresponding Python construct. Reusable Stanza
helpers like `defn differential-constraint (in1, out1, in2, out2) :`
that bundle several constraints should be ported as **Python functions
returning `ConstrainDiffPair`** rather than inline-transcribed at every
call site — see
[`references/side-by-side/04-pin-assignment.md`](side-by-side/04-pin-assignment.md)
§"The `differential-constraint` helper recipe".

Common loss modes from real ports (these are the bugs this gate is
designed to catch):

- USB diff pair has resistors and named D+/D- nets but no `>>` topology,
  no `ConstrainDiffPair`, no routing structure — diff-pair routing
  rule never attaches.
- RF / antenna nets have a `property(... net-class)` clause on the
  Stanza side but no `Tag` + `design_constraint(...).routing_structure(...)`
  on the Python side — CBCPW / 50 Ω structure never attaches.
- `timing-difference(...) = TimingDifferenceConstraint(-1ps, 1ps)` on
  the Stanza side has no `.timing_difference(...)` call on the
  Python side — skew budget is silently relaxed to "unconstrained".

## Phase 6 — Post-verify the 4.x design

**Goal:** prove the Python target builds, types-check, and produces an export.

1. Confirm an active sign-in (same as Phase 0). The 4.x build connects to the part database too — without sign-in it fails with `You are not authenticated`.
2. Repoint `~/.jitx/current` to the 4.x install (`ln -sfn <4.x version> ~/.jitx/current`). The same symlink rule applies — a stale 3.x target will break the 4.x pipeline.
3. Set up a project venv: `python -m venv .venv && source .venv/bin/activate && pip install --pre -e .` (or `uv sync --active --prerelease=allow`). The `jitx` Python package lives on the JITX internal index, not public PyPI. **Use `-e` (editable)** during the port — non-editable installs silently break VSCode and any environment that doesn't set `PYTHONPATH` once you add new files. See [`jitx-skills:jitx/references/bootstrap.md`](../../jitx/references/bootstrap.md) step (5) for the rationale.
4. `pyright` must be clean (the `jitx` skill covers the venv + pyright config). Treat any `pyright` error as blocking — type errors in JITX 4.x commonly mask wiring bugs. **Exception**: errors of the form `Cannot access attribute "<NAME>" for class "Part"` on `Part(mpn=…).<port>` accesses are unavoidable — port names come from the parts DB at runtime, so pyright cannot know them. See `jitx-skills:jitx-component-modeler` §"pyright caveat on `Part(mpn=…).<port>`" for the recommended pyright filter and the wrap-in-Component alternative.
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
