# Pitfalls & Non-Obvious Differences

Things that bite during a port and aren't covered by the construct map.

## Object construction model

- **Stanza modules return values** (a `pcb-module` body produces the module). **Python `Circuit` subclasses build via attribute assignment in `__init__`** — there is no "return" of the circuit. Don't try to write `return self` or paraphrase the Stanza expression-style body as a Python expression.
- **Instance declarations** in Stanza (`inst foo : my-component`) become `self.foo = MyComponent()` in Python `__init__`. Order in `__init__` matters when later code references earlier instances.

## Connectivity

- **Stanza connects by name (string-typed nets)** when you write `net pwr (a.vcc, b.vcc)`. **Python connects by Port object identity** with the `+` operator: `self.nets = [a.vcc + b.vcc]`. There is no global string namespace for nets in Python.
- **`+` is the net operator**, not topology. **`>>` is the topology (routed-graph) operator.** Mixing them produces type errors that pyright will catch — trust pyright here.
- **Named nets** (e.g., labeling `gnd` so it shows up in the schematic with that name) require explicit Python helpers; do not assume the Python form picks up names automatically.

## Pins, ports, and direction

- Stanza `pin.up` / `pin.down` (schematic placement direction) maps to **Python `Pin.up()` / `Pin.down()` / `Pin.right()` — these are method calls returning configured pin objects**, not enum values. Easy to mistype.
- Stanza `pin-properties` declarations cover pin number + name + direction in one block. The Python form splits this across `Pin` (logical), `Pad` (physical), and the symbol/landpattern mapping objects.

## Provide / require

- Stanza `supports` / `require` and Python `@provide` / `@require` are *similar* but **not identical** in hierarchical composition. Cases that "just worked" in Stanza via implicit propagation may need an explicit `Provide(...)` declaration in Python.
- `@provide.one_of`, `@provide.subset_of`, `@provide.all_of` are the Python idioms for the patterns Stanza expressed via free-form `supports` clauses with conditions. See `jitx-pin-assignment` for which to use.

## Topology and constraints

- 4.x has first-class `RoutingStructure`, `DifferentialRoutingStructure`, `NeckDown`, `ReferencePlanes`, `InsertionLossConstraint`, `TimingDifferenceConstraint` — many of these had no first-class Stanza equivalent in 3.x and were expressed ad-hoc. Don't search the Stanza source for an exact match; reformulate from the design intent.
- `BridgingPinModel` / `TerminatingPinModel` attach to topology nodes. In Stanza these were often modeled as parametric components; in Python they are pin-model objects on the topology graph itself.

## Build invocation gotchas

- **`python -m jitx build --port <PORT>`** — `--port` is the **TCP port for the JITX UI server**, not a PCB port. Easy to confuse mid-design.
- The Python build target is `<module>.<DesignClass>` (e.g., `mydesign.boards.MainBoard`), not a file path. Get this wrong and the build fails with "no design found", not a Python import error.
- Two installs in the same shell will cross-contaminate `PATH` and Conan envs. Use absolute paths or subshells. See `verification.md`.

## Stanza language idioms that trip up porters

- **`defmulti` dispatch** in Stanza often becomes a plain Python method, not `functools.singledispatch`. Python's `Circuit`/`Component` class hierarchy is rich enough that you rarely need open multimethod dispatch.
- **Stanza generators / `Seq` pipelines** map to Python list/generator comprehensions, not to a port of the Stanza sequence library.
- **`with-syntax` / parametric helpers** in Stanza often emitted families of designs at compile time. The Python equivalent is a plain factory function or a parameterized `Circuit` subclass; resist transcribing the macro structure.

## Package layout

- **Stanza `defpackage` paths are not Python module paths.** A file at `src/foo/bar.stanza` with `defpackage foo/bar` is unrelated to where Python will put `foo/bar.py`. Python module layout follows `pyproject.toml` conventions; design from the Python side.
- **Stanza `import` is package-granular.** Python `from jitx import Circuit, Component, Port` is symbol-granular. Listing the imports in the Python file is more verbose but more navigable.

## Verification gotchas

- A 3.x design that builds with warnings may produce a 4.x port that builds clean — the warnings often map to issues the 4.x type system catches at construction time. Don't treat "fewer warnings" as proof of correctness.
- Conversely, a 3.x design that builds *cleanly* and a 4.x port that builds *cleanly* still need export comparison — equivalent component placement and routing isn't guaranteed by passing builds alone.
- **`~/.jitx/current` symlink mismatch silently corrupts the build.** JITX reads runtime/config/plugin state via `~/.jitx/current/...` regardless of which versioned binary you launched. Repoint it to match the version you're invoking before each build (verified: a 4.x-pointing symlink while invoking a 3.x binary breaks Stanza export with `write-stable-id (False)` on every release tested 3.25.0 → 4.0.5).

## Don't

- ❌ Describe Stanza as JVM-compiled — it is natively compiled via C.
- ❌ Mass-rename Stanza identifiers to Python style without re-running the build at each step. Identifier-rename mistakes cascade through the wiring.
- ❌ Skip `pyright` because "the build worked." Type errors mask wiring bugs.
