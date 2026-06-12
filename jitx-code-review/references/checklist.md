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

### `reflection-as-iteration` (formerly `getattr-on-self`)

**Look for:** `getattr(self, f"...")`, `getattr(self.<child>, "...")`, OR `getattr(<framework-object>, <runtime-string>)` with a string-formatted attribute name. The failure isn't about `self` — it's about navigating structural state by an assembled string.

The name `getattr-on-self` was too narrow: it let agents rationalize `getattr(lp, row_letter)` as fine because "it's not on self." That rationalization is the framework-boundary-bypass failure — see Pattern `framework-boundary-bypass` below.

**Severity:** CRITICAL when the call navigates JITX/framework-owned structural state by an assembled string, regardless of whether the receiver is `self` or another object. Hard-fail grep gate catches `getattr(self, ...)`; broader `getattr(...)` is review-required and demands per-hit ownership analysis (not just disposition prose).

**Rule source:** `jitx/SKILL.md` Don'ts ("Don't reflect on `self` by name…"); `jitx/references/architectural-patterns.md` § 2.

### `parallel-data-model`

**Look for:** `_build_X_records` or similar functions returning `list[dict]` / `list[<frozen-dataclass>]` that is then *re-interpreted* in a separate consumer to emit JITX objects. The intermediate model has no role once the JITX objects exist.

**Severity:** CRITICAL when the intermediate model is a `list[dict[str, Any]]` mirroring JITX-object shape one-to-one. WARNING when typed but still pointlessly indirect.

**Rule source:** `jitx/references/architectural-patterns.md` § 3 ("Build the scene graph directly").

### `owner-shaped-data-misplaced` (formerly `substrate-pollution`)

**Look for:** Design-level constants or tables that mirror data owned by *any* structural object — substrate (layer counts, via maps), landpattern (pad numbering), routing structure (per-layer trace widths, references, keepouts), protocol bundle (pin roles). The owning object is authoritative; the design should query, not duplicate.

**Severity:** WARNING by default. CRITICAL when the design *contradicts* the owning object (wrong layer count, stale via map) or when the data is design-state-critical (pad numbering for placement).

**Rule source:** `jitx/references/architectural-patterns.md` § 4. Sub-example 4a covers substrates; sub-example 4b covers routing-structure per-layer geometry.

### `framework-boundary-bypass`

**Look for:** Design code that *replicates the navigation logic* of a framework class, rather than calling the framework class's public API. The smell can be:
- An import of a framework helper that touches an invariant the framework class owns (`from jitxlib.landpatterns.grid_layout import to_bga_row_ref`).
- A thin wrapper in design code that hides a `getattr(<framework-object>, ...)` call (`_pad_at(lp, r, c)` wrapping `getattr(lp, row_letter)[c]`).
- A design-side comment rationalizing one `getattr` / one `type(...)` / one `_protected_method` call as "the boundary call" or "the framework does this."

The failure mode is the AI seeing framework code use a banned pattern (because the framework class has same-class access to its own internals) and concluding that the pattern is allowed in design code too. The wrapper is the rationalization, not the fix.

**Recognition shape (ownership test):** for every banned-pattern hit or proposed exception:
1. What object owns the invariant?
2. Is this code inside that object's class or subclass?
3. Is the caller using a public method?
4. If no public method exists, can a subclass adapter expose one (delegate to the protected method from a same-class context)?

If the answer is "outside the owner, copying internals," the finding is `framework-boundary-bypass`.

**Severity:** CRITICAL. The right fix is to add a public adapter method on a framework subclass that delegates to the protected method (allowed by the "method calling another method on the same class" carve-out of the no-leading-underscore-from-elsewhere rule), and route all design-side calls through the adapter.

**Rule source:** `jitx/SKILL.md` Don'ts ("Don't reinvent framework code in design code…"); `jitx/references/architectural-patterns.md` § 9 ("Framework boundary — internals don't transfer to design code").

### `untyped-records`

**Look for:** Bare `dict[str, Any]` or `list[dict]` (without explicit element type) used to batch intermediate state. No `@dataclass` / `NamedTuple` / `TypedDict` discipline.

**Severity:** WARNING. Always fixable by introducing a `@dataclass(frozen=True)`.

**Rule source:** `jitx/references/architectural-patterns.md` § 5.

### `module-import-time-parallel-model`

**Look for:** Module-level `for` loops, `if` blocks, or comprehensions at column 0 that populate a mutable global parallel design model — `_BALLOUT = {}; for i in range(7): _BALLOUT[f"X{i}"] = ...`. The smell almost always co-occurs with `string-keyed-model` (Pattern 1) and `parallel-data-model` (Pattern 3).

**Class-body comprehensions are not this pattern.** `lanes: list[list[DiffPair]] = [[DiffPair() for _ in cols] for cols in pair_cols]` inside a class body is the *actual* object model, not a parallel one. This pattern targets module-level globals only.

**Severity:** WARNING (grep gate now review-required after later codex findings). CRITICAL when the global drives string-keyed downstream dispatch.

**Rule source:** `jitx/SKILL.md` Don'ts; `jitx/references/architectural-patterns.md` § 6.

### `inline-subclass-as-instantiation`

**Look for:** `@inline class stackup(Generic_Stackup): pass` or any other class declaration whose body is `pass`, used where `stackup = Generic_Stackup()` would suffice.

**Severity:** WARNING. The behavior may be identical at runtime; the style is wrong.

**Rule source:** `jitx/references/architectural-patterns.md` § 7.

### `manual-jitx-assigned-value`

**Look for:** Code computing `refdes=`, net names, layer indices, or other values JITX assigns automatically. Strings like `f"U1_A1_solderball"` or `f"L{layer}_via"` constructed for the purpose of naming a JITX object. Carve-out: *owner-side* structural definitions legitimately set layer indices — `start_layer = 0` on a substrate's Via class is the definition, not a duplication (see `jitx/SKILL.md` Don'ts); the smell is *design-side* code computing what the owning object already exposes.

**Severity:** WARNING (often driven by export-pipeline pressure — odb++/HFSS workflows). CRITICAL if it actively breaks JITX's naming/refdes assignment.

**Rule source:** `jitx/references/architectural-patterns.md` § 8.

## JITX-API patterns

Patterns where the substrate / routing-structure / framework API is being misused.

### `coplanar-feature-misplaced`

**Look for:** Reference planes, keepouts, or fence definitions bolted onto a routing structure via a tag-based `design_constraint(...)` rule when they belong inside the routing structure's layer entry (`DifferentialRoutingStructure.Layer(...).reference(...).fence(...)`).

**Severity:** WARNING. Functional code; structural code-smell.

**Rule source:** `jitx-substrate-modeler/SKILL.md` (the coplanar-features-in-routing-structure callout).

### `generic-substrate-design-leak`

**Look for:** A "generic" or reusable substrate file (`generic_<n>layer.py`) that imports / declares design-specific tags, trace widths, or geometric constants. `DESKEW_TRACE_WIDTH` in a generic substrate is the canonical example.

**The leak surface includes prose, not just code.** A comment or docstring in a generic file that names a specific downstream tool (`jitx-ansys` / HFSS, `odb++`) or asserts the substrate is suitable for some specific flow is the same leak — it couples the reusable artifact to one consumer and often asserts a fact the code doesn't back. Don't flag every mention of a downstream tool; flag tool-specific claims in a file that's supposed to be tool-agnostic, and prose suitability claims with no evidence (pair with `compliance-theater`).

**Severity:** WARNING / CRITICAL depending on how invasive. The substrate is supposed to be reusable; design-specific concepts in it block reuse.

**Rule source:** `jitx-substrate-modeler/SKILL.md` (the anti-string-hacking callout).

### `symmetric-mirroring-confusion`

**Look for:** Layer names inside a `Symmetric` stackup that bake in a unique layer position (e.g., `L1_Ground1` — `Symmetric` auto-mirrors so the bottom conductor gets the same name). Or core dielectric that's *not* mirrored while everything else is.

**Severity:** WARNING.

**Rule source:** `jitx-substrate-modeler/SKILL.md` (Stackup section).

### `tag-proliferation`

**Look for:** A flat set of near-identical sibling tags that all inherit straight from `Tag` and differ only by name (`AntipadFenceTag`, `DeskewAntipadFenceTag`, `BGAFanoutFenceTag`, …), each wired to its own `design_constraint(...)` rule that mostly restates the others. The smell is N parallel tags + N parallel rules where a tag *hierarchy* (a base tag whose rule applies to all subtags) or a single combined rule (`&` / `|` / `~`) would express the same intent.

**Carve-out:** Distinct tags for genuinely distinct rule sets are fine. The smell is specifically *near-duplication* — many tags whose rules share most of their body — or a comment like "we need a tag per lane" where one base-tag rule (plus a higher-priority rule on the one subtype that differs) would do. (`priority=` is set on the `design_constraint(...)` rule, not on individual tagged objects.)

**Severity:** WARNING (architecture smell; functional code). NOTE when it's only two tags.

**Rule source:** `jitx-substrate-modeler/SKILL.md` ("Tag inheritance & proliferation").

## Code-craft patterns

Hygiene patterns. Lower priority on their own but they accumulate.

### `unparameterized-factory`

**Look for:** Factory functions that take zero arguments and return a fully-baked construction object. `_make_drs_layer_85()` with constants inlined.

**Severity:** NOTE if the function is called from one site. WARNING if it's called from 4+ sites with all calls identical except for `.reference()` / `.fence()` post-construction chains — those varying inputs should be function arguments.

**Rule source:** code-craft hygiene — an unparameterized factory is just a costlier constructor call; parameterize it or inline it.

### `dead-named-constant`

**Look for:** Named constants used exactly once, with no unit / derivation information the bare number wouldn't carry. The bare number is clearer than the name.

**Severity:** NOTE. Inline-or-keep is a judgment call; reviewer flags for author decision.

**Rule source:** code-craft hygiene — a single-use named constant that adds no unit or derivation; the literal is clearer.

### `vestigial-construct`

**Look for:** `from __future__ import annotations` on projects pinned to Python 3.14+ (where PEP 649 defers annotations by default — on 3.12/3.13 the import still changes annotation semantics, so don't flag it there); `LEGACY` / `DORMANT` / `OLD` in names that haven't been cleaned up; commented-out code blocks.

**Severity:** NOTE.

**Rule source:** Naming-hygiene cluster.

### `name-vs-base-class-mismatch`

**Look for:** Subclass names that don't echo the base class. `HexBGA_Base extends BGADecorated` → should be `HexBGADecorated`. Tag names that describe geometry primitive rather than role (`DiffPairTag` when it's actually a transmission-line-class tag → `StriplineDiffPairTag`).

**Severity:** NOTE.

**Rule source:** Naming-hygiene cluster.

### `convenience-alias`

**Look for:** Aliases (extra accessor names, shorthand attributes, hand-typing-friendly pad names) whose only justification is being easy for a human to type. With editor tooling (autocomplete, go-to-definition) the ergonomic argument is weak, and each alias is a second naming surface to keep in sync with the real one.

**Carve-out:** Aliases that are part of a published / public API contract, or that a downstream consumer depends on, are legitimate — this is a *soft* preference, not a banned pattern. Flag for author decision; never block on it.

**Severity:** NOTE only. Do not escalate; do not add to `jitx/SKILL.md` Don'ts.

**Rule source:** code-craft hygiene (soft) — editor tooling removes the need for hand-typing aliases; a published-API alias is the exception.

## Cross-cutting tags

These are general cross-cutting tags that translate cleanly to JITX-Python targets. Use them as a fallback when the named architectural / API / code-craft patterns above don't fit, or as a *secondary* tag alongside a named pattern when the same finding has two shapes.

- `inaccurate` — code claims a mechanism that doesn't match how JITX actually works.
- `wrong-abstraction-level` — rule / construct placed at the wrong scope (component-level when it should be circuit-level, etc.).
- `quantitative-error` — magic numbers that don't check out against the cited datasheet / spec.
- `coverage-gap` — categorical handling that misses adjacent cases (USB-C without USB-A; USB 2.0 without USB 3.0).
- `internal-inconsistency` — the same concept named differently across files in the design.
- `stale-reference` — code refers to a file / class that no longer exists.
- `example-shaped-rule` — a constant / function that's overfit to one specific instance (rather than parametric).
- `compliance-theater` — a claim made without backing evidence (e.g., "datasheet says X" with no page/figure reference; "tested clean" with no test file). Includes a code comment or docstring asserting a fact the code doesn't support ("optimized for HFSS extraction", "matches the reference stackup") — facts not in evidence.
