# JITX Code Review — Pattern Checklist

The checklist the reviewer walks. Patterns are organized by category. Each pattern: name (the tag used in findings), what to look for, severity guidance, and the rule source to quote.

Pattern tags are **orthogonal to severity** — a single tag can produce CRITICAL, WARNING, or NOTE findings depending on the instance. Severity is set by how clearly the instance matches the rule.

## Architectural patterns (anti-string-hacking)

These are the dominant failure mode in AI-generated JITX code. Catch them at write time and at review time.

### `string-keyed-model`

**Look for:** `dict[str, ...]` indexed by hand-built strings (`f"TX_b{i}"`, `(row_letter, col)`, etc.) used as the design's data structure. Variables named like `_BALLOUT`, `_SIGNAL_ROW_MAP`, `records` (when populated by string-keyed dicts).

**Carve-out:** `@provide` methods return `list[dict[Port, Port]]` — dicts keyed by **Port objects** (not strings). This is the framework's pin-mapping contract, not a violation. The discriminator is key type: strings = bad, Port / structural object = fine.

**Severity:** CRITICAL when the dict drives design construction (the AI is using strings to walk the scene graph). WARNING when used as intermediate parameter-staging (might be benign). NOTE for typed metadata dicts that aren't load-bearing.

**Rule source:** `jitx/SKILL.md` Don'ts ("Don't key design state by hand-built strings…"); `jitx/references/architectural-patterns.md` § 1.

### `getattr-on-self`

**Look for:** `getattr(self, f"...")` or `getattr(self.<child>, "...")` with a string-formatted attribute name. Reflection-as-iteration over sibling attributes.

**Severity:** CRITICAL. Hard-fail grep gate already catches `getattr(self, ...)`; the broader `getattr(<other>, "...")` is review-required. Both are usually fixable by declaring the collection as a `list` / `dict` attribute up front.

**Rule source:** `jitx/SKILL.md` Don'ts ("Don't reflect on `self` by name…"); `jitx/references/architectural-patterns.md` § 2. Quoted PR-review verdict: "this is illegal" / "illegal — no getattr".

### `parallel-data-model`

**Look for:** `_build_X_records` or similar functions returning `list[dict]` / `list[<frozen-dataclass>]` that is then *re-interpreted* in a separate consumer to emit JITX objects. The intermediate model has no role once the JITX objects exist.

**Severity:** CRITICAL when the intermediate model is a `list[dict[str, Any]]` mirroring JITX-object shape one-to-one. WARNING when typed but still pointlessly indirect.

**Rule source:** `jitx/references/architectural-patterns.md` § 3 ("Build the scene graph directly"). Quoted PR-review verdict: "This is building a separate model and then constructing the object out of that model. Just build the scene graph directly."

### `substrate-pollution` / `substrate-shaped-table-in-design`

**Look for:** Design-level constants that mirror substrate properties — `_NUM_CONDUCTOR_LAYERS`, `_SIGNAL_LAYER_TO_VIA`, per-layer trace widths declared at module scope in a design file. The substrate is the authoritative source; the design should query, not duplicate.

**Severity:** WARNING by default (the AI may not know JITX's substrate-query API). CRITICAL when the design *contradicts* the substrate (e.g., wrong layer count, stale via map).

**Rule source:** `jitx/references/architectural-patterns.md` § 4. Quoted PR-review verdict: "out of place — the substrate has layers. Introspect from stackup."

### `untyped-records`

**Look for:** Bare `dict[str, Any]` or `list[dict]` (without explicit element type) used to batch intermediate state. No `@dataclass` / `NamedTuple` / `TypedDict` discipline.

**Severity:** WARNING. Always fixable by introducing a `@dataclass(frozen=True)`.

**Rule source:** `jitx/references/architectural-patterns.md` § 5. Quoted PR-review verdict: "There's no safety here — typechecker won't help against typos. Poor craftsmanship."

### `module-import-time-logic`

**Look for:** `for` loops or `if` blocks at column 0 (module scope) that populate global tables. Module-level `_BALLOUT = {}` followed by `for i in range(7): _BALLOUT[f"X{i}"] = ...`.

**Severity:** CRITICAL (hard-fail grep gate catches the `for` form). WARNING for comprehension form (`{f"X{i}": ... for i in range(7)}` at module scope).

**Rule source:** `jitx/SKILL.md` Don'ts; `jitx/references/architectural-patterns.md` § 6.

### `inline-subclass-as-instantiation`

**Look for:** `@inline class stackup(Generic_Stackup): pass` or any other class declaration whose body is `pass`, used where `stackup = Generic_Stackup()` would suffice.

**Severity:** WARNING. The behavior may be identical at runtime; the style is wrong.

**Rule source:** `jitx/references/architectural-patterns.md` § 7.

### `manual-jitx-assigned-value`

**Look for:** Code computing `refdes=`, net names, layer indices, or other values JITX assigns automatically. Strings like `f"U1_A1_solderball"` or `f"L{layer}_via"` constructed for the purpose of naming a JITX object.

**Severity:** WARNING (often driven by export-pipeline pressure — odb++/HFSS workflows). CRITICAL if it actively breaks JITX's naming/refdes assignment.

**Rule source:** `jitx/references/architectural-patterns.md` § 8.

## JITX-API patterns

Patterns where the substrate / routing-structure / framework API is being misused.

### `coplanar-feature-misplaced`

**Look for:** Reference planes, keepouts, or fence definitions bolted onto a routing structure via a tag-based `design_constraint(...)` rule when they belong inside the routing structure's layer entry (`DifferentialRoutingStructure.Layer(...).reference(...).fence(...)`).

**Severity:** WARNING. Functional code; structural code-smell.

**Rule source:** `jitx-substrate-modeler/SKILL.md` (the coplanar-features-in-routing-structure callout, post-update).

### `generic-substrate-design-leak`

**Look for:** A "generic" or reusable substrate file (`generic_<n>layer.py`) that imports / declares design-specific tags, trace widths, or geometric constants. `DESKEW_TRACE_WIDTH` in a generic substrate is the canonical example.

**Severity:** WARNING / CRITICAL depending on how invasive. The substrate is supposed to be reusable; design-specific concepts in it block reuse.

**Rule source:** `jitx-substrate-modeler/SKILL.md` (the anti-string-hacking callout, post-update).

### `symmetric-mirroring-confusion`

**Look for:** Layer names inside a `Symmetric` stackup that bake in a unique layer position (e.g., `L1_Ground1` — `Symmetric` auto-mirrors so the bottom conductor gets the same name). Or core dielectric that's *not* mirrored while everything else is.

**Severity:** WARNING.

**Rule source:** `jitx-substrate-modeler/SKILL.md` (Stackup section).

## Code-craft patterns

Hygiene patterns. Lower priority on their own but they accumulate.

### `unparameterized-factory`

**Look for:** Factory functions that take zero arguments and return a fully-baked construction object. `_make_drs_layer_85()` with constants inlined.

**Severity:** NOTE if the function is called from one site. WARNING if it's called from 4+ sites with all calls identical except for `.reference()` / `.fence()` post-construction chains — those varying inputs should be function arguments.

**Rule source:** Quoted PR-review verdict: "why have a function to make the construction instead of making the construction? doesn't make sense if not parameterized."

### `dead-named-constant`

**Look for:** Named constants used exactly once, with no unit / derivation information the bare number wouldn't carry. The bare number is clearer than the name.

**Severity:** NOTE. Inline-or-keep is a judgment call; reviewer flags for author decision.

**Rule source:** Quoted PR-review verdict: "This is a descriptive structure — put the number in it instead of having a variable."

### `vestigial-construct`

**Look for:** `from __future__ import annotations` on Python 3.10+ where forward refs are auto-deferred; `LEGACY` / `DORMANT` / `OLD` in names that haven't been cleaned up; commented-out code blocks.

**Severity:** NOTE.

**Rule source:** PR-review hygiene cluster.

### `name-vs-base-class-mismatch`

**Look for:** Subclass names that don't echo the base class. `HexBGA_Base extends BGADecorated` → should be `HexBGADecorated`. Tag names that describe geometry primitive rather than role (`DiffPairTag` when it's actually a transmission-line-class tag → `StriplineDiffPairTag`).

**Severity:** NOTE.

**Rule source:** PR-review hygiene cluster.

## Cross-cutting tags (selection from the jitx-skills-review taxonomy)

These are pattern tags from the `jitx-skills-review` skill's twelve-pattern taxonomy that translate cleanly to JITX-Python targets. Use them as a fallback when the named architectural / API / code-craft patterns above don't fit, or as a *secondary* tag alongside a named pattern when the same finding has two shapes.

The eight tags below are the ones that fire most often on user-written JITX code; the remaining four from the twelve-pattern taxonomy (`recommend-against-yourself`, `miscalibrated-heuristic`, `block-vs-warn`, `trigger-ambiguity`) are skill-doc-shaped and rarely apply to user code.

- `inaccurate` — code claims a mechanism that doesn't match how JITX actually works.
- `wrong-abstraction-level` — rule / construct placed at the wrong scope (component-level when it should be circuit-level, etc.).
- `quantitative-error` — magic numbers that don't check out against the cited datasheet / spec.
- `coverage-gap` — categorical handling that misses adjacent cases (USB-C without USB-A; USB 2.0 without USB 3.0).
- `internal-inconsistency` — the same concept named differently across files in this PR.
- `stale-reference` — code refers to a file / class that no longer exists.
- `example-shaped-rule` — a constant / function that's overfit to one specific instance (rather than parametric).
- `compliance-theater` — a claim made without backing evidence (e.g., "datasheet says X" with no page/figure reference; "tested clean" with no test file).
