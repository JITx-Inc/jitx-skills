# Verification: pre-port (3.x baseline) and 4.x export comparison

The porting workflow brackets every conversion with two builds:

- **Pre-port:** build the original 3.x Stanza design to confirm a working
  baseline. Port-specific procedure — covered in detail below.
- **Post-port:** build the new 4.x Python design. The order-sensitive
  bootstrap (symlink → sign-in → `jitx interactive` → socket → pip
  install → version check → headless build) is **canonical** in
  [`jitx-skills:jitx/references/bootstrap.md`](../../jitx/references/bootstrap.md);
  this file only adds the port-specific layer (artifact capture for
  comparison, alternating between 3.x and 4.x).

Both runs capture artifacts to known directories so a future automated
comparator can diff them.

The general parallel-install / `~/.jitx/current` symlink discipline
(applies to anyone running 4.x, not just porters) lives in
[`jitx-skills:jitx/SKILL.md`](../../jitx/SKILL.md) §"Parallel JITX
installs" and `jitx/references/bootstrap.md` §"Parallel installs". The
port-specific twist is that this workflow alternates between 3.x and
4.x, so the symlink is repointed between every build — the snippets
below include the `ln -sfn` step explicitly.

## Pre-port build (3.x baseline)

Identify the design's entry from its `nightly_design_tests`-style row
(or equivalent):

```yaml
- project_dir: "ethernet_io"
  stanza_file: "main.stanza"
  design_name: "ethernet-board"
```

Build with the 3.x install:

```bash
DESIGN=ethernet_io
PROJECT_DIR=/path/to/${DESIGN}
DESIGN_NAME=ethernet-board
JITX_3X=~/.jitx/3.36.1            # adjust
OUT=/tmp/jitx-port/${DESIGN}/baseline-3.x
mkdir -p "$OUT"

# CRITICAL: point ~/.jitx/current at the 3.x install before invoking it,
# otherwise runtime state from a different version leaks in and breaks the
# export pipeline.
ln -sfn "$(basename "$JITX_3X")" ~/.jitx/current

(
  cd "$PROJECT_DIR"

  # Resolve SLM dependencies declared in slm.toml (clones jsl etc.). Stanza
  # must be on PATH for SLM to invoke it, and SLM_ROOT must point at the
  # 3.x slm install or `slm fetch` exits with
  #   ValueError: No Environment Variable 'SLM_ROOT' found
  SLM_ROOT="$JITX_3X/slm" \
      PATH="$JITX_3X/stanza:$PATH" "$JITX_3X/slm/slm" fetch

  # Run via the `jitx` wrapper, which finds the install's .stanza config.
  # Calling jstanza directly fails with "Could not locate .stanza
  # configuration file".
  PATH="$JITX_3X/stanza:$PATH" "$JITX_3X/jitx" run main.stanza \
      > "$OUT/build.stdout" 2> "$OUT/build.stderr"
  echo $? > "$OUT/exit-code"
)
```

The exact invocation may differ per design (some designs ship a wrapper
script, some use `slm build`, some run `jitx run` against a specific
entrypoint). The design's own runner / Makefile / README is the source
of truth — read it and reuse its invocation, only substituting binary
paths with `"$JITX_3X/..."`.

**On nonzero `exit-code`, do not silently proceed.** Surface
`build.stderr` verbatim, tell the user the 3.x baseline did not build
cleanly, and ask whether to continue. The user is allowed to override
(some legacy 3.x designs no longer build but still need to be ported),
but they must explicitly acknowledge that:

- Pre-existing errors in the 3.x source may carry over into the 4.x
  port without being caught by post-port verification.
- The export comparison step is unreliable because there is no clean
  baseline to diff against.

When proceeding under override, record the failure mode in a
`BASELINE-FAILED.md` next to the port (or in PR notes) so reviewers can
see what was waived. The default is still to fix the baseline first.

Expected artifacts under `$OUT/` (varies by design): KiCad project + 3D
STEP under `kicad/`, schematic, BOM, internal `stable.design` /
`netlist.json`.

### Sibling path dependencies in `slm.toml`

`slm.toml` files commonly declare deps with `path = "../<name>"`,
expecting that sibling repo to be cloned next to the design under one
parent directory. A fresh-clone porting workflow rarely has that
already, so `slm fetch` fails with `Failed to Resolve Path
../<dep>/stanza.proj. Double check path dependencies and confirm
expected git repos in '.slm/deps'`.

Pre-clone every sibling path-dep before `slm fetch`. **Version pinning
matters** — some sibling deps have known-broken HEAD revisions that the
3.x compiler rejects. For `jsl`, pin to `v0.10.9` to avoid the
`pad-island.stanza:72 'minus' type error` introduced in 0.10.10/0.10.11.

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

When the 3.x build fails, run **at most one probe** before deciding to
revert and record `BASELINE-FAILED.md`. Acceptable probes:

1. Look for a commented-out `import` line in the failing file that
   looks related to the missing symbol (e.g. `; import ocdb/utils/bundles`
   when the error is `Could not resolve 'usb-2-data'`). Uncomment and
   re-build.
2. Try a different jsl tag pin (jsl-related errors specifically — e.g.
   `pad-island.stanza:72` → pin `v0.10.9`).

If the single probe doesn't expose a clean path to `exit 0`, **revert**
to the original source verbatim and record the failure in
`BASELINE-FAILED.md`. Multi-step debugging of the 3.x source is out of
scope for the porting workflow; the port can use `main.stanza` itself
as the source-of-truth even without a clean baseline. Real example from
the `pd_audio` port: three layered import / namespace conflicts at
commit `78b6709` — uncommenting one import exposed an
ambiguous-reference error, removing another import exposed a third
symbol that's jsl-only. The right call was to revert and document, not
to keep digging.

### Known baseline blockers — do not waste time debugging

Before treating a baseline failure as a real source-of-truth issue,
check whether it matches one of these known incompatibilities. Each is
a permanent upstream mismatch that re-running the build will not fix.

- **`pad-island.stanza:72 : 'minus' applied to incompatible types`** —
  jsl ≥ 0.10.10 against jitx 4.0.5 (the current stable). `minus`'s type
  signature changed in jsl 0.10.10 in a way the 4.0.5 Stanza front-end
  rejects. Confirm with
  `grep 'pad-island.stanza:72' "$OUT/build.stderr"`. Mitigation: do
  **not** try to patch jsl. Either (a) pin `slm.toml` back to
  `jsl = "0.10.9"` if the design tolerates the older API surface, or
  (b) document the failure in `BASELINE-FAILED.md` and proceed without
  a clean baseline. The `nightly_design_tests` repo already skips all
  designs hitting this — see its `config/designs.yaml` `skip:` flags
  for the canonical list.

When proceeding under a known baseline blocker, the Phase 7
export-comparison checklist cannot be run automatically. Run each check
manually against the **Stanza source** (not the failed build output):
net inventory by reading `pcb-net` statements, connector pin assignment
by reading the connector module, power topology by tracing `power` nets
in source. Mark the check column "unverifiable — no 3.x baseline"
rather than skipping it; an unverifiable check that is later proven
correct by a co-reviewer is still useful, a skipped one is invisible.

## Post-port build (4.x)

The order-sensitive 4.x startup recipe (symlink → sign-in → interactive
→ socket wait → pip install → version check → headless build) is the
**canonical bootstrap** for any 4.x design — see
[`jitx-skills:jitx/references/bootstrap.md`](../../jitx/references/bootstrap.md).
Follow that checklist verbatim. The port-specific additions to layer on
top:

1. **Set `~/.jitx/current` to the 4.x install** (not the 3.x that the
   pre-port build pointed at). The porting workflow alternates between
   the two; the `~/.jitx/current` symlink must match the binary you're
   about to invoke.
2. **Capture build artifacts to a known directory** so the export
   comparator (below) can find them:
   ```bash
   OUT=/tmp/jitx-port/<design>/ported-4.x
   mkdir -p "$OUT"
   ```
   Redirect `interactive.log`, `pip.log`, `jitx-version.txt`,
   `pyright.txt`, `build.stdout`, `build.stderr`, and `exit-code` into
   `$OUT` so the Compare-exports section below can diff them against
   the 3.x baseline.
3. **`pyright` must pass before the build is reviewable**:
   ```bash
   pyright . > "$OUT/pyright.txt" 2>&1 || { echo "pyright failed"; exit 1; }
   ```
   Treat any `pyright` error as blocking — type errors in JITX 4.x
   commonly mask wiring bugs.
4. **CI sign-in via env vars**: in headless / CI runs, set
   `JITX_USER_EMAIL` and `JITX_USER_PASS` and pipe the password into
   `jitx sign-in -email "$JITX_USER_EMAIL" <<<"$JITX_USER_PASS"`. See
   `jitx-test/scripts/jitx-build-design.bash` for the production
   pattern (which also sets `JITX_ENV` to `app` / `app-testing` /
   `app-dev`).
5. **Some projects use `uv sync --active --prerelease=allow`** instead
   of `pip install --pre .` for the venv install step.

## Compare exports — port-mode wrapper

`status: ok` is **not sufficient evidence that the port is correct**.
The general six-section export-verification checklist (net inventory,
power topology, component output pins, control-signal completeness,
etc.) lives at
[`jitx-skills:jitx/references/export-verification.md`](../../jitx/references/export-verification.md)
and applies to any 4.x design. Run it against the post-port
`ported-4.x/` artifacts.

The port-mode work adds **two extra checks** on top, both of which
require both `baseline-3.x/` and `ported-4.x/` artifacts on disk:

### Port-only check B′. Connector pin-index translation

1. Read every `inst <conn> : pin-header(N)` and `net (<conn>.p[i] <name>)`
   in the Stanza source.
2. Verify the Python connector uses matching assignments. **Stanza pin
   indices are 1-based; Python is 0-based** — `conn.p[1]` in Stanza is
   `conn.p[0]` in Python. A mechanical 1:1 transcription off-by-ones
   every connector pin and produces a build that passes every general
   check while the entire connector is shifted by one position.
3. Confirm every connector pin's net name matches (`VCC`, `GND`, `EN`,
   `SCL`, `SDA`, etc.).

### Port-only check E′. Passive-count delta

Compare approximate passive counts between Stanza and Python:

- Stanza: count `bypass-cap-strap`, `cap-strap`, `res-strap`, and
  direct `inst c : capacitor` / `resistor` calls per module.
- Python: count `Capacitor`, `Resistor`, `Inductor` instances per
  `Circuit`.

A discrepancy of more than ~2× per circuit is a strong signal that a
`pcb-module` wrapper was missed (see `workflow.md` Phase 3/4
boundary) — the bare component was ported but its application-circuit
wrapper (bypass caps, output filters, thermal vias) was not. The
general check D (Component output pins) catches the symptom; this
delta catches the cause.

### Phase 7 fallback — Stanza source as the reference

When the Phase 0 build failed and `BASELINE-FAILED.md` exists, there
is no `baseline-3.x/` artifact for the export diff to consume. Phase 7
must fall back to a **static source-to-source diff** with the Stanza
source as the only reference.

This is manual today and produces a `PORT-DIFF.md` artifact attached
to the PR. Six steps, in order:

1. **Module / Circuit count.** Number of `pcb-module` blocks in the
   Stanza source = number of `Circuit` subclasses in the Python port
   (including the top-level `TopCircuit` / `<Name>Top` and any
   parametric variants that became separate Python classes — see
   `side-by-side/02-circuit.md` §"Parametric modules"). Mismatch is a
   Phase 7 blocker.

2. **Per-module instance count.** For each `pcb-module`, count `inst`
   declarations on the Stanza side and `self.x = X()` lines in the
   matching Python `__init__`. 1:1 match required.

3. **Per-module net inventory.** For each `pcb-module`, list every
   `net (...)` declaration on the Stanza side; cross-reference each
   to a Python `Net(...)` or `+`-chain. Top-level rail names must
   survive (`VBUS` Stanza → `VBUS` Python, etc.); intra-circuit
   anonymous nets need a matching anonymous Net in Python.

4. **`supports` / `require` graph.** For each Stanza `supports`
   clause, locate the Python `@provide` (or document why it became
   fixed wiring; see `workflow.md` Phase 4 hardware-analysis gate).
   For each Stanza `require X : <bundle> from <inst>`, locate the
   matching `self.<inst>.require(<Bundle>)` in Python. See
   `references/side-by-side/04-pin-assignment.md` for the four
   shapes and their idiomatic Python forms.

5. **Constraints.** Apply the Phase 5 constraint-inventory gate from
   `workflow.md` §"Phase 5 exit criteria — Stanza-source constraint
   inventory" — grep `topology-segment`, `structure(...) =`,
   `timing-difference`, `property(... net-class)` in the Stanza
   source; locate the Python equivalent for each. This is the same
   four-pattern check; the difference here is that Phase 7 enforces
   it by **listing each hit in `PORT-DIFF.md`** with a Python
   citation, not just running it as a Phase 5 self-check.

6. **Parametric module formulas.** For each `pcb-module module (-- kw1
   = ..., ...)` parametric call site in the Stanza source, verify the
   Python equivalent **ports the formula**, not one example's snapped
   values. See `side-by-side/05-parametric-module.md` for the audit
   checklist.

This is a manual diff — not a substitute for the export-level diff —
but it catches the six structural-loss categories that an
unavailable-baseline port is most exposed to.

### Future automation

A future automated comparator at `scripts/compare-exports.py` (not yet
implemented) is expected to mechanize the general checks A, F, plus
port-only B′ and E′:

```bash
# FUTURE — not implemented yet
python scripts/compare-exports.py \
    --baseline /tmp/jitx-port/<design>/baseline-3.x \
    --ported   /tmp/jitx-port/<design>/ported-4.x \
    --report   /tmp/jitx-port/<design>/diff-report.html
```

Until then, every porting session should still produce both directories
under `/tmp/jitx-port/<design>/{baseline-3.x,ported-4.x}/` so the
future tool can be retrofit without re-running builds.

## Smoke test

For an end-to-end runnable example of this flow (a small two-resistor
design in both versions, with a real `slm.toml` for the 3.x side and a
real `pyproject.toml` for the 4.x side), see `runnable-example/` next
to this doc.

## Cross-shell hygiene

Don't put both versions on `PATH` in the same shell — both 3.x and 4.x
ship a binary named `jitx`. Either:

- **Always invoke by absolute path** (`"$JITX_3X/jitx"`,
  `"$JITX_4X/jitx"`), as the snippets above do, **or**
- Run each build in its own subshell with only that version's bin on
  `PATH`:

```bash
( PATH="$JITX_3X:$PATH"; jitx run ... )              # 3.x only
( PATH="$JITX_4X:$PATH"; jitx interactive ... )      # 4.x only
```

Subshells (`( ... )`) discard the env on exit, so the next build starts
clean. Don't forget the `~/.jitx/current` symlink update — that's
separate from `PATH` and applies process-globally.
