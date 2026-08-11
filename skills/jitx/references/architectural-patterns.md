# Architectural Patterns — Anti-String-Hacking

Worked counter-examples for the architectural don'ts in `jitx/SKILL.md`. The category name is "parallel-model / stringly-typed-indirection" — "string-hacking" is the shorthand.

These patterns are the dominant failure mode in AI-generated JITX code. They cluster around the same root cause: the AI built a parallel data model keyed by hand-built strings (or did reflection-as-iteration on `self`) instead of letting JITX's own class/list/dict structure *be* the model. Every pattern below: a real failure pattern observed in review, and the JITX-native counter-pattern that replaces it.

## Table of contents

1. [String-keyed dicts → structural objects](#1-string-keyed-dicts--structural-objects)
2. [Sibling attributes → array attributes](#2-sibling-attributes--array-attributes)
3. [Build the scene graph directly](#3-build-the-scene-graph-directly) — includes the dataclass / Container / Composite / Circuit triage
4. [Owner-shaped data lives on the owning structural object](#4-owner-shaped-data-lives-on-the-owning-structural-object) — substrate is one sub-example
5. [Typed records over `dict[str, Any]`](#5-typed-records-over-dictstr-any)
6. [No module-import-time generation of mutable globals or parallel design models](#6-no-module-import-time-generation-of-mutable-globals-or-parallel-design-models)
7. [Don't pass-through inline-subclass — instantiate](#7-dont-pass-through-inline-subclass--instantiate)
8. [Don't assign what JITX assigns](#8-dont-assign-what-jitx-assigns)
9. [Framework boundary — internals don't transfer to design code](#9-framework-boundary--internals-dont-transfer-to-design-code) — the meta-rule the others build to
10. [Compose members — don't mutate a circuit from a free function](#10-compose-members--dont-mutate-a-circuit-from-a-free-function)

---

## 1. String-keyed dicts → structural objects

**Failure pattern.** Constructing a parallel data model out of `dict[str, ...]` keyed by hand-built strings like `f"TX_b{i}"`, `f"TX{lane}_{P|N}"`, or `(row_letter, col)` tuples, then walking that dict to build the design. Records like `record["tx_pair"]`, `record["test_point"]`, `record["antipad"]` get re-indexed all the way down the pipeline.

**Bad:**
```python
# 7 differential lanes laid out by hand-built string keys
records: list[dict[str, Any]] = []
for i in range(7):
    records.append({
        "name": f"TX_b{i}",
        "tx_pair": self._build_pair(i),
        "test_point": self._build_tp(i),
        "antipad": self._build_antipad(i),
    })
# Now everything downstream walks `records` and re-indexes by string
for r in records:
    self += r["tx_pair"].P + r["test_point"].A
```

**Good:**
```python
# Lanes are first-class objects — JITX-native structure
@dataclass(frozen=True)
class EscapeLane:
    tx_pair: DiffPair
    test_point: TestPoint
    antipad: KeepOut

self.lanes: list[EscapeLane] = [
    EscapeLane(
        tx_pair=self._build_pair(i),
        test_point=self._build_tp(i),
        antipad=self._build_antipad(i),
    )
    for i in range(7)
]

# Downstream uses object attributes — typechecker catches typos
for lane in self.lanes:
    self += lane.tx_pair.P + lane.test_point.A
```

**Why.** String keys are reflection by another name. A typo in `r["tx_pair"]` is a silent runtime error; `lane.tx_pair` is a typecheck error. Dataclasses + typed lists give you the same data structure with no string-indirection cost.

**Exception.** `@provide` methods in `jitx-pin-assignment` return `list[dict[Port, Port]]`. Those dicts are keyed by **Port objects**, not strings — that's the framework's pin-mapping contract, not a parallel-model. The discriminator is "what's the key type": strings = bad, Port / structural object = fine.

---

## 2. Sibling attributes → array attributes

**Failure pattern.** Declaring N parallel objects as N sibling attributes (`self.TX_b0 = ...`, `self.TX_b1 = ...`, ...), then iterating them with `getattr(self, f"TX_b{i}")`. Reflection-as-iteration.

**Bad:**
```python
class HexBGA(Component):
    def __init__(self):
        super().__init__()
        self.TX_b0 = DiffPair()
        self.TX_b1 = DiffPair()
        self.TX_b2 = DiffPair()
        self.TX_b3 = DiffPair()
        self.TX_b4 = DiffPair()
        self.TX_b5 = DiffPair()
        self.TX_b6 = DiffPair()

# Elsewhere — illegal reflection
for i in range(7):
    pair = getattr(self.bga, f"TX_b{i}")  # NO
    self += pair.P + ...
```

**Good:**
```python
class HexBGA(Component):
    def __init__(self):
        super().__init__()
        self.TX: list[DiffPair] = [DiffPair() for _ in range(7)]

# Elsewhere — typed iteration, no reflection
for pair in self.bga.TX:
    self += pair.P + ...
```

**Why.** "Why isn't this an array of arrays?". Sibling attributes are the failure mode when the underlying collection is homogeneous (same type, same role). Reach for `list` / `dict` / `PinGroup` directly. If you need a programmatic collection, `getattr(self, ...)` is the wrong answer; the right answer is to declare the collection.

If you genuinely need to introspect children (across heterogeneous types, e.g., "give me every pad on this Component"), use JITX's inspection API — never name-reconstruction with `getattr`. When you want *positions* out of that walk, compose `trace.transform * element.transform`; an element's own `transform` is local to its immediate container and is not a coordinate on its own (see `jitx-physical-layout/references/geometry-verification.md` § "Coordinate frames").

---

## 3. Build the scene graph directly

**Failure pattern.** Writing a `_build_X_records` function that constructs a list of dicts describing what *should* be built, then a separate consumer that walks those records and emits the actual JITX objects. The intermediate model exists only as scaffolding around the AI's inability to use JITX constructors directly.

**Bad:**
```python
def _build_pair_records(self) -> list[dict]:
    records = []
    for i in range(self.n_pairs):
        records.append({
            "via_layer": self._signal_layer_for_pair(i),
            "via_offset": self._offset_for_pair(i),
            "antipad_shape": self._antipad_shape_for(i),
            "fence_radius": self._fence_radius_for(i),
        })
    return records

# Consumer walks the records
for rec in self._build_pair_records():
    via = Via(layer=rec["via_layer"], offset=rec["via_offset"])
    antipad = KeepOut(shape=rec["antipad_shape"])
    fence = Pour(radius=rec["fence_radius"])
    self.insert(via)
    self.insert(antipad)
    self.insert(fence)
```

**Good:**
```python
@dataclass(frozen=True)
class EscapeLane:
    via: Via
    antipad: KeepOut
    fence: Pour

def _make_lane(self, i: int) -> EscapeLane:
    return EscapeLane(
        via=Via(layer=self._signal_layer_for_pair(i), offset=self._offset_for_pair(i)),
        antipad=KeepOut(shape=self._antipad_shape_for(i)),
        fence=Pour(radius=self._fence_radius_for(i)),
    )

self.lanes: list[EscapeLane] = [self._make_lane(i) for i in range(self.n_pairs)]
```

**Why.** "This is building a separate model and then constructing the object out of that model. Just build the scene graph directly. Use constructors, objects, composites, containers". The intermediate `list[dict]` is scaffolding — it has no role once the JITX objects exist. Cut it out; construct the objects directly inside the right JITX-native grouping (see triage below).

The exception is *intentional parameter staging* — e.g., gathering input parameters for a generator function. That's not a "spec model"; that's just function arguments. The smell is when the dict mirrors the JITX-object shape one-to-one.

### Triage — pick the right grouping primitive

Once you've decided the intermediate `list[dict]` has to go, the next question is *what to replace it with*. The choice depends on what the grouped values are:

| Grouped values | Right primitive |
|----------------|------------------|
| Pure metadata / parameters / coordinates (not JITX structural children) | `@dataclass(frozen=True)` or `NamedTuple` |
| Repeated JITX structural children with no transform (DiffPairs, Ports, Components) | `jitx.container.Container` — or simply assign as `self.<collection>: list[T]` on the parent so the framework traverses through introspection |
| Geometric grouping with local transform (rotation, translation) | `Composite` (`jitx.feature.Custom` / equivalent geometric composite) |
| Electrical reusable block with ports | A new `Circuit` or `Component` subclass |

Reaching for `@dataclass` when the grouped values are JITX structural children is risky: the dataclass owns them by reference but doesn't surface them for framework traversal. If downstream code relies on JITX seeing those children, the dataclass becomes a parallel model in disguise — Pattern 1 / Pattern 2 surfacing under a different name. Prefer the framework primitive when the framework needs to *see* the children.

---

## 4. Owner-shaped data lives on the owning structural object

**Failure pattern.** The design file maintains its own table of values that some structural object already owns — substrate properties, landpattern pad numbering, routing-structure per-layer geometry, protocol-bundle pin roles. The design duplicates the table (or copies the navigation logic) instead of querying through the owning object.

The owning object isn't always "the substrate." It's whatever JITX class owns the *invariant* the data describes. Substrates own layer counts and via maps. Landpattern subclasses (`AlphaDictNumbering` etc.) own pad numbering. Routing structures own per-layer trace widths, references, and keepouts. Protocol bundles own pin roles. User-defined framework subclasses can also own invariants.

### Sub-example 4a: Substrate-shaped tables

**Bad:**
```python
# design file
_NUM_CONDUCTOR_LAYERS = 20  # Generic_Stackup L1..L20

_SIGNAL_LAYER_TO_VIA = {
    1: Generic_Substrate.uVia_L1_L2,
    2: Generic_Substrate.uVia_L1_L4,
    3: Generic_Substrate.uVia_L1_L6,
    4: Generic_Substrate.uVia_L1_L8,
}

def via_for_lane(i: int) -> Via:
    layer = (i % 4) + 1
    return _SIGNAL_LAYER_TO_VIA[layer]
```

**Good:**
```python
# design file — query the substrate
def via_for_lane(self, i: int) -> Via:
    return self.substrate.signal_via[self._signal_layer_for_lane(i)]

# substrate file — owns the mapping
class Generic_Substrate(Substrate):
    # ... vias declared as class attributes ...
    @property
    def signal_via(self) -> dict[int, type[Via]]:
        return {1: self.uVia_L1_L2, 2: self.uVia_L1_L4, 3: self.uVia_L1_L6, 4: self.uVia_L1_L8}

    @property
    def n_conductors(self) -> int:
        return len(self.stackup.conductors)
```

### Sub-example 4b: Routing-structure per-layer geometry

Trace widths, reference-plane assignments, fence-via patterns, and keepout radii belong inside the routing structure's per-layer entry (`DifferentialRoutingStructure.Layer(...).reference(...).fence(...)`). The design should not maintain a parallel constant table or apply these via tag-based `design_constraint(...)` rules when the routing structure already supports them.

**Why.** "Out of place — the substrate has layers. Introspect from stackup". When a value is naturally indexed by an invariant a structural object owns, the table lives on that object. Designs should not maintain a parallel "L1→uVia_L1_L2" table. If JITX doesn't expose the right API, that's a gap to file — not a license to copy.

Closely related: see Pattern 9 ("Framework boundary — internals don't transfer to design code"). Copying the *navigation logic* (not just the data) is the same failure with a different surface.

---

## 5. Typed records over `dict[str, Any]`

**Failure pattern.** Even when the records are short-lived (intermediate-parameter staging, e.g.), using bare `dict[str, Any]` means typos are silent runtime errors.

**Bad:**
```python
records: list[dict] = []
for i in range(n):
    records.append({
        "tx_pair": ...,
        "test_point": ...,
        "antipad": ...,
    })

# elsewhere — typo silently returns None
r = records[0]
self.use(r["tx_piar"])  # typo, AttributeError at runtime
```

**Good:**
```python
@dataclass(frozen=True)
class LaneInputs:
    tx_pair: DiffPair
    test_point: TestPoint
    antipad: KeepOut

records: list[LaneInputs] = [
    LaneInputs(tx_pair=..., test_point=..., antipad=...)
    for i in range(n)
]

# elsewhere — typo is a typecheck error
r = records[0]
self.use(r.tx_pair)  # typecheck OK
```

**Why.** "There's no safety here — typechecker won't help against typos. Poor craftsmanship. There are dataclasses for this, named tuples, etc.". The Python tooling (pyright, mypy) catches dataclass-attribute typos at write-time; it can't catch dict-key typos. If batching into records is necessary (after rules 1–3 have been honored), use a frozen dataclass or NamedTuple — never bare `dict[str, Any]`.

---

## 6. No module-import-time generation of mutable globals or parallel design models

**Failure pattern.** Module-level `for` loops that populate global `_BALLOUT` / `_SIGNAL_ROW_MAP` dicts at import time, building names by string-formatting (`f"TX{lane}_{pol}"`). This rule targets *parallel design models constructed at import time*, not all module-level computation.

**Bad:**
```python
# module top level — parallel design model populated at import
_BALLOUT: dict[str, tuple[int, int]] = {}
for lane in range(7):
    for pol in ("P", "N"):
        _BALLOUT[f"TX{lane}_{pol}"] = (lane, pol)
```

**Good:**
```python
# function called when needed — no side effects at import
def _ballout_position(lane: int, pol: Literal["P", "N"]) -> tuple[int, int]:
    return (lane, 0 if pol == "P" else 1)
```

### What this rule does NOT ban

**Class-body structural collections are fine** — they're the *actual* object model, not a parallel one:

```python
class GenericHexGridBGA(jitx.Component):
    # class-body: this IS the model, not a parallel one
    lanes: list[list[DiffPair]] = [
        [DiffPair() for _ in bga.signal_cols_for_pair(pair_index)]
        for pair_index in range(len(bga.SIGNAL_ROW_PAIRS))
    ]
    GND = [Port() for _ in range(_num_gnd_balls())]
```

The discriminator:
- **Module-level mutable globals + string-keyed names** = bad (themes 1, 2, 9 are also present).
- **Class-body declaring JITX structural children** = fine.
- **Module-level literal data without computed string keys** (e.g., `BALLOUT: list[BallPosition] = [BallPosition(lane=0, polarity="P", ...), ...]`) = fine if literals only; once you have a loop or comprehension building names, see the bad pattern.

**Why.** "Code that runs on initialization is poor form. Again it's constructing names". The specific failure is *generating a parallel data model from scratch at import time*. Class-body structural declarations don't generate a parallel model — they ARE the model. The grep gate `^for\s+\w+\s+in\s+` (column-0 only) catches the module-level form without firing on class-body comprehensions.

---

## 7. Don't pass-through inline-subclass — instantiate

**Failure pattern.** Using `@inline class stackup(Generic_Stackup): pass` (empty body) inside a `Substrate` instead of `stackup = Generic_Stackup()`. The AI reaches for class-level mechanisms (subclassing, `@inline`) instead of instance composition, then leaves the body empty so the subclass adds nothing.

**Bad — empty inline subclass:**
```python
class MySubstrate(Substrate):
    @inline
    class stackup(Generic_Stackup):
        pass    # the body is empty — pass-through inline subclass
```

**Good:**
```python
class MySubstrate(Substrate):
    stackup = Generic_Stackup()
```

**Note — legitimate inline-subclass case:** `@inline class stackup(Symmetric):` with a *non-empty body* that declares layers (see `jitx-substrate-modeler/SKILL.md` "Inline Stackup") is the canonical pattern for defining a stackup. This rule applies only to **pass-through inline subclasses** where the body adds no fields, no overrides, no methods. The discriminator is body content: empty body = bad (instantiate instead); non-empty body = legitimate inline-stackup pattern.

**Why.** "This is incorrect — should instantiate generic instead of inlining". An empty-body `@inline class X(Base): pass` does nothing the base class doesn't already do — it's just a more expensive way to instantiate. The general principle: prefer instance composition over class-level mechanisms when both produce the same runtime structure. Inheritance is for *adding or changing* behavior; if you're not adding or changing anything, instantiate.

---

## 8. Don't assign what JITX assigns

**Failure pattern.** Setting `refdes="U1"` as a default arg in `ball_spec()`, then generating object names like `U1_A1_solderball`. JITX assigns reference designators itself.

**Bad:**
```python
def ball_spec(self, name: str, refdes: str = "U1") -> Ball:
    return Ball(name=f"{refdes}_{name}_solderball", ...)
```

**Good:**
```python
def ball_spec(self, name: str) -> Ball:
    return Ball(name=name, ...)
# JITX assigns the refdes; downstream tools see the right name
```

**Why.** "Would not assign reference designator here, because JITX assigns those. Lots in this design to handle hardships going through odb++ to hfss". If you're computing a name that JITX should be giving you, you're bypassing the framework. The general principle: don't manually assign values that JITX assigns automatically — reference designators, net names from topology, layer indices from stackup, etc. Pressure from export-pipeline tools (e.g., `odb++` → HFSS) is a known temptation to do the wrong thing; resist it.

---

## 9. Framework boundary — internals don't transfer to design code

**Failure pattern.** The AI sees framework code using a pattern the skill bans in user code (e.g., `getattr` for navigation, `type(...)` for dispatch) and reasons: "the framework does it, so I can do it." It then copies the framework's navigation logic into design code — often wrapped in a thin helper to make it look like a single "boundary call." The wrapper is the rationalization, not the fix.

This is the meta-failure of the previous patterns. Even when the AI has correctly applied Patterns 1–8, it can still cross a framework boundary by replicating internal logic that the framework has factored out for separation of concerns.

**Bad:**
```python
# design module
from jitxlib.landpatterns.grid_layout import to_bga_row_ref   # WRONG — copying framework navigation

def _pad_at(lp, r: int, c: int):
    row_letter = to_bga_row_ref(r)   # the framework's own row-numbering logic
    return getattr(lp, row_letter)[c]   # the framework's own getattr pattern

# Then in __init__:
mapping[pair.p] = [_pad_at(lp, bottom_row, col)]
```

The AI rationalized: "the only `getattr` is the single boundary call into `AlphaDictNumbering`'s row-letter-keyed pad dictionary; there is no design-side string-keyed model." The skill's rule against `getattr` was followed *literally*, but the rule's *intent* — don't replicate framework navigation in design code — was violated. The design is now coupled to a specific row-numbering scheme; if the framework's numbering changes, the design breaks.

**Good:**
```python
# framework subclass (in this design's component file)
class HexBGA(A1, AlphaDictNumbering, HexBGADecorated):
    def get_pad(self, r: int, c: int):
        """Public (row, col) -> Pad lookup. Polymorphic over the numbering mixin
        so design code stays decoupled from AlphaDictNumbering's row-letter
        attribute layout. Wraps the framework-internal _get_pad so callers
        can stay clear of leading-underscore access."""
        return self._get_pad(r, c)   # same-class call into framework's protected method — allowed

# design code
mapping[pair.p] = [lp.get_pad(bottom_row, col)]   # polymorphic, decoupled
```

**Why.** "[Y]ou're not going with the grain" / "this code will fail instead of relying on the existing polymorphic behavior" (reviewer, paraphrased). Framework code factored out for separation of concerns is a **boundary**, not a license. When framework code uses `getattr` inside the class that owns the row-letter numbering invariant, that's the framework's same-class exception inside its own implementation. Design code on the *outside* of that boundary does not inherit the exception — replicating the navigation logic out there is the failure mode.

The reviewer's framing: *"rather amusing that this was indeed already called out, but missing the point/intent and ending up with the opposite conclusion ('they did it, therefore so can I! 🎉' — paraphrased)."*

### Ownership test (apply to every banned-pattern hit or proposed exception)

Before accepting any rationalization of a banned pattern, answer:

1. **What object owns the invariant?** (The numbering scheme, the layer-via map, the protocol pin roles, etc.)
2. **Is this code inside that object's class or a subclass of it?** If yes, you have the same-class exception (carve-out is real). If no, see step 3.
3. **Is there a public method on the owning object that returns what you need?** If yes, use it.
4. **If no public method exists, can a subclass adapter expose one?** If yes, that's the fix — add a public method on the subclass that delegates to the framework's protected method (the "method calling another method on the same class" carve-out of the no-leading-underscore-from-elsewhere rule).
5. **If you reach for `getattr` / `type(...)` / `_protected_method()` in design code and none of steps 2–4 apply,** you're committing framework-boundary-bypass. Stop. Add the adapter or escalate.

Wrapping the banned pattern in a helper does not make it allowed. The helper is the rationalization — the boundary is the real test.

---

## 10. Compose members — don't mutate a circuit from a free function

**Failure pattern.** A free function that takes the circuit (or design) and assigns attributes onto it — `def add_thermal_vias(circuit, ...): circuit.thermal_vias = [...]`. The member is created by a side effect at a call site instead of being declared on the class, so neither a reader nor the type checker sees it where the circuit is defined, and helpers grow order-dependence between calls.

**Bad — builder function mutating the passed-in circuit:**
```python
def add_thermal_vias(circuit: Circuit, positions: list[tuple[float, float]]) -> None:
    circuit.thermal_vias = [ThermalStitchVia().at(x, y) for (x, y) in positions]

class AmpCircuit(Circuit):
    def __init__(self):
        ...
        add_thermal_vias(self, positions)   # member appears by side effect elsewhere
```

**Good — a `Container` subclass owns the group; the circuit composes it as a member:**
```python
from jitx import Container

class ThermalViaField(Container):
    def __init__(self, positions: list[tuple[float, float]]):
        self.vias = [ThermalStitchVia().at(x, y) for (x, y) in positions]

class AmpCircuit(Circuit):
    def __init__(self):
        ...
        self.thermal_vias = ThermalViaField(positions)   # composed, visible, traversed
        for via in self.thermal_vias.vias:
            self.GND += via
```

The class-attribute form is fine when the contents are static (`class MyX(Container): xyz = <something>`); build in `__init__` when construction is parameterized. Use a `Circuit` subclass instead of `Container` when the group has ports/nets of its own — § 3's dataclass / Container / Composite / Circuit triage picks the right base.

**Why.** Every structural member of a circuit belongs *on the circuit* — class body or `self.` in `__init__` — the single place the structural walk and a human reader both look. A mutating helper is an imperative side door around that declaration point. Compose objects; don't bolt them on. (Build-verified on 4.2.1: `Container` members are traversed and the composed-vias form builds clean.)

---

## Meta-rule: when in doubt, use what JITX already has

Three layers, in order:

1. **Use what JITX already exposes** — public API on the structural object that owns the invariant (Pattern 4, Pattern 9). This includes public *constructors and overloads* on primitives, not only methods on structural objects: before hand-rolling a helper that assembles a geometry/value the framework already builds, check for an existing overload. (E.g. a hand-written arc-builder that duplicates one of `Arc`'s overloaded constructors — three-point, start/end/radius, and center/radius/start/sweep all exist — could be reduced to just using the existing overload. Reinventing a *public* primitive is a code-craft / simplification miss, distinct from `framework-boundary-bypass`, which is copying framework *internals*.)
2. **If no public API exists, add one as a subclass adapter** — Pattern 9's exit hatch. This keeps the boundary intact while giving design code a clean call site.
3. **If JITX has no structural object for what you're modeling,** the right answer is a typed Python primitive (`@dataclass(frozen=True)`, `list[T]`, `dict[StructuralKey, T]`), never `dict[str, Any]` or sibling attributes plus `getattr` (Patterns 1, 2, 5). Note: prefer `jitx.container.Container` or assigning structural collections directly on `self` when the grouped values are JITX structural children that need traversal — `@dataclass` is for pure metadata or parameter records.

A useful one-line check: *if your only handle on a design object is a string you assembled at runtime, OR you're replicating framework internals in design code, stop — find the structural object or add a public adapter.*

### One trap to watch for

"The framework does X, so I can do X." This is the operational form of framework-boundary-bypass. Even one `getattr` in design code that mimics a framework's internal pattern is the failure mode — the wrapper or the comment explaining "this is the boundary call" is the rationalization, not the fix. Apply the ownership test in Pattern 9 before accepting any such carve-out.
