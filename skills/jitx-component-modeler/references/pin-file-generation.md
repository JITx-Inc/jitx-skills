# Generating a component from a machine-readable vendor pin file

For parts where the pin map is published as data rather than as a drawing — FPGAs, large SoCs, and
most high-ball-count BGAs. Vendors ship these as an ASCII table: one row per ball, with the pin name,
the ball reference, the bank, and a type column. At four figures' worth of balls, transcribing that
table is not a job anyone should do by hand or by eye, and "spot-checked a sample" is not verification.

The rule that makes this tractable: **parse, don't transcribe.** Write a small generator that reads
the vendor file and *emits* the component module as Python. Commit the generator and the emitted
module; do not commit the vendor file.

## When this path applies

**The trigger is the data, not the pin count:** the vendor publishes a machine-readable pin map, and
you have confirmed it is authoritative for names, balls and banks. Parse it whenever it exists —
parsing is not more work than transcribing at any size, and it is the only version that can be
re-run when the vendor revises the file.

What scale changes is the *rigor*, not the decision. A few dozen pins need the parse and the
round-trip check; a few thousand additionally justify the committed generator, the `--check` gate and
the human inventory gate described below, because at that size no reviewer can eyeball the result.

Geometry still comes from the packaging document, and the two are separate authorities. The pin file
knows nothing about body size, pitch or land diameter; the packaging manual knows nothing about which
ball carries which signal. Do not let one stand in for the other.

When the vendor publishes no machine-readable map, the ordinary datasheet path applies — see the main
skill's Step 1 and `package-examples.md`.

**The file's schema is per-source.** Vendors publish these as whitespace-aligned columns, CSV, or
tab-separated, with different column sets and different header and footer conventions. Write the
parse against the schema of the file in front of you, and state which columns you relied on. Nothing
below assumes a particular layout.

## Reconcile before you emit

**No component code is written until the parse reconciles.** The generator's first stage parses and
counts; nothing emits until the counts agree. Reconcile at least four ways:

1. parsed row count == the file's own total-pins footer, where it has one,
2. every ball reference unique,
3. the decoded grid is complete (or its gaps are ones the vendor documents),
4. the inventory sums to the total.

A ball-reference decoder needs a **round-trip self-check** — decode to `(row, col)` and re-encode
back to the reference for every row. Get the row alphabet from the **BGA-Specific Notes** in
`package-examples.md` rather than assuming base-26; it is mixed-radix, and an off-by-one past the
first rollover is silent and systematic. Confirm the vendor uses that alphabet rather than assuming
it — this is a per-source fact, and the round-trip check is what catches a source that differs.

**The inventory must partition, not merely sum.** Ask for "a table of group → count that sums to
N" and you will get one that double-counts: a rail that is also a member of a bank appears under
both, and the arithmetic still lands if something absorbs the difference. State the property you
actually want — **every pin in exactly one group** — and assert it. It is the same property the
symbol-coverage requirement asks for, and it is just as cheap to check.

If it does not reconcile, show the gap. Do not adjust a count to reach the expected total.

## The generator's shape

Standard-library only, no project imports. It must run before the component exists, and it should
not break because the design's dependencies moved.

- **A pure-function core** — `parse`, `decode_ball_reference`, `classify`, `emit_module`. Pure
  functions are the part you can test against a small synthetic fixture without the real vendor file,
  which matters because you cannot commit the real one.
- **`--report`** prints the inventory and the reconciliation line. This is what a human reviews at
  the gate, before any code is emitted.
- **`--check`** regenerates and diffs against the committed module, exiting non-zero on any
  difference. State its guarantee precisely: it proves the committed module is what *this* generator
  produces from *this* input, right now. It does **not** prove the module was never hand-edited — an
  edit made to both the generator and the module still passes — and it says nothing about whether the
  input is the file the vendor currently publishes. Those are separate checks: review the generator
  as code, and re-verify the recorded source hash against a fresh download.

**The emitted module is generated output. Never hand-edit it.** If it is wrong, the generator is
wrong. Editing the output makes `--check` fail on a file nobody can now regenerate, which is worse
than the original defect because it is silent.

## Deterministic and formatter-stable output

`--check` only means something if the generator is deterministic: sort anything set-derived, never
emit a hash seed or a timestamp, and iterate in a defined order.

Determinism is the easy half. **Formatter stability is the half that bites.** If the emitter and the
formatter disagree by one line, the formatter rewrites the file, `--check` then reports the
*committed* module as stale, and the gate fails on a file nobody touched.

Mirror the formatter's own decision:

- emit a collection **inline** when it fits the configured line length;
- otherwise **explode it one element per line with a trailing comma**, which pins it open.

Two sub-cases account for most of the churn:

- a tuple of several long names overflows the line length and must be pre-exploded;
- a **single-element tuple fits and must not be exploded** — its comma is required syntax, so the
  formatter does not read it as a magic trailing comma.

This makes the project's configured line length load-bearing on a file that does not obviously depend
on it. Say so in the generator's docstring.

## Provenance

The emitted module's header records what it was generated from:

- the source file name,
- its **sha256**,
- the vendor URL it came from,
- the packaging document's edition, for the geometry that did not come from this file.

That header is the durable record, and it is worth having whether or not the file is committed.

**Whether to commit the file is a licensing question, so answer it from the license.** Vendor pinout
files carry varying terms; some permit redistribution, many do not, and a customer's repository may
be public. Where the terms permit, committing the input is the stronger choice — it makes the build
reproducible without a network fetch. Where they don't, keep it in the project's gitignored scratch
directory and rely on the recorded hash. If you cannot determine the terms, ask rather than assume
either way.

Record the hash of the **raw bytes**, and say so. These files often ship CRLF, so a hash of
newline-normalized text will not match what a fresh download hashes to, and a provenance record
nobody can reproduce is not one.

## Ball references exist only at generation time

The emitted code carries **zero-indexed `(row, col)` coordinates**. Strings like `"AB34"` appear only
in the generator's input and in trailing comments for human readers.

This is the difference between a structural model and a string-keyed one. A downstream consumer that
has to parse `"AB34"` to find a neighbour has inherited the vendor's serialization format as its
data model. See the main skill's "Anti-string-hacking" rule, which this is a special case of.

## What the emitted module holds

- One `Port` per pin. Unique names become scalar attributes; repeated names (rails, grounds,
  no-connects) become **indexed lists**, `GND = [Port() for _ in range(N)]`. The classification rule
  is mechanical — repeated name → list, unique name → scalar — and that is what makes it trustworthy.

  **Vendor names are not always Python identifiers.** Real pin names carry `/`, `#`, `+`, `-`,
  parentheses, and sometimes a leading digit; a few collide with Python keywords. So the attribute
  name is a *derived* value, and deriving it needs three properties: a documented, deterministic
  transformation; **collision rejection** — if two distinct vendor names sanitize to the same
  identifier, fail loudly rather than silently dropping a pin; and the **exact vendor name preserved**
  in a comment or a lookup so the mapping back to the datasheet survives. Do not quietly rewrite a
  name you could not use.

  Note the consequence for supplies: a rail the vendor gives exactly one pin lands as a *scalar*,
  not a one-element list. The base skill's **MCU / FPGA Components** checklist owns what follows
  from that.

- Coordinate tables under a formatter-off guard, so the grid stays readable.
- An iterator yielding every (port, coordinate) pair.
- **Structural groupings as methods returning fresh records** — never as stored attributes. See the
  main skill's "A `Port` has exactly one home".
- No-connects declared per the **BGA-Specific Notes** in `package-examples.md`.

## The human gates

Two places to stop, and they are before the expensive work, not after. Each names the operation that
**must not run** until the user has answered — a gate whose next step proceeds anyway is decoration.

1. **After the inventory, before emitting.** Run the generator in `--report` mode only and present
   the partitioned table and the reconciliation line. **Do not run the emitting mode, and do not
   write any component file, until the user approves the inventory.** This is the last point at which
   a misclassification is cheap; past it, every downstream artifact is built on it.
2. **After the land pattern, before the circuit.** Present a hand-checked sample spanning the grid
   extremes and one pin per group type, each traced ball → coordinate → port → pad, plus a geometry
   cross-check against the packaging drawing's overall array dimension. **Do not start the circuit
   wrapper until the user approves the sample** — the wrapper's rail roster and bundles are derived
   from this mapping, so a bad mapping propagates into work that is expensive to redo.

If the user has not answered, the correct state is stopped, not "proceeded with a note."

## Testing a generated component

Everything in "Verifying a component with tests" applies. Additionally:

- **Counts as literals** — total pins, and per-group counts taken from the inventory report. A
  generated module will happily produce a self-consistent wrong answer; the literal is what makes the
  count an assertion rather than a tautology.
- **Hand-read spot checks** spanning the grid extremes, a two-letter row, and one pin per group type,
  asserted ball → coordinate → port → pad. Read these off the vendor file by eye; that is the point.
- **Mapping bijectivity** — every port maps to exactly one pad and back.
- **Symbol coverage** — every port in exactly one partition, no partition over the box ceiling.
- **The generator's pure functions** against a small synthetic fixture committed alongside the tests.
- **A regeneration-idempotency test** that runs `--check`, skipped when the vendor file is absent so
  the suite still passes on a fresh clone. Make sure it is *not* skipping when you are relying on it.

Share one cached design instantiation across the suite — a part this size costs seconds per build,
and a per-test instantiation turns a fast suite into a slow one for no added coverage.
