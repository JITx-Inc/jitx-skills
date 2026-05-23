# Architectural Patterns — Anti-String-Hacking

Worked counter-examples for the architectural don'ts in `jitx/SKILL.md`. The category name is "parallel-model / stringly-typed-indirection" — the shorthand "string-hacking" is from PR-review register.

These patterns are the dominant failure mode in AI-generated JITX code. They cluster around the same root cause: the AI built a parallel data model keyed by hand-built strings (or did reflection-as-iteration on `self`) instead of letting JITX's own class/list/dict structure *be* the model. Every pattern below: a real failure pattern observed in review, and the JITX-native counter-pattern that replaces it.

## Table of contents

1. [String-keyed dicts → structural objects](#1-string-keyed-dicts--structural-objects)
2. [Sibling attributes → array attributes](#2-sibling-attributes--array-attributes)
3. [Build the scene graph directly](#3-build-the-scene-graph-directly)
4. [Substrate-shaped tables live on the substrate](#4-substrate-shaped-tables-live-on-the-substrate)
5. [Typed records over `dict[str, Any]`](#5-typed-records-over-dictstr-any)
6. [No code at module-import time](#6-no-code-at-module-import-time)
7. [Instantiate, don't inline-subclass](#7-instantiate-dont-inline-subclass)
8. [Don't assign what JITX assigns](#8-dont-assign-what-jitx-assigns)

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

**Why.** "Why isn't this an array of arrays?" (PR review). Sibling attributes are the failure mode when the underlying collection is homogeneous (same type, same role). Reach for `list` / `dict` / `PinGroup` directly. If you need a programmatic collection, `getattr(self, ...)` is the wrong answer; the right answer is to declare the collection.

If you genuinely need to introspect children (across heterogeneous types, e.g., "give me every pad on this Component"), use JITX's inspection API — never name-reconstruction with `getattr`.

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

**Why.** "This is building a separate model and then constructing the object out of that model. Just build the scene graph directly. Use constructors, objects, composites, containers" (PR review). The intermediate `list[dict]` is scaffolding — it has no role once the JITX objects exist. Cut it out; construct the objects directly inside a `@dataclass` or a composite container.

The exception is *intentional parameter staging* — e.g., gathering input parameters for a generator function. That's not a "spec model"; that's just function arguments. The smell is when the dict mirrors the JITX-object shape one-to-one.

---

## 4. Substrate-shaped tables live on the substrate

**Failure pattern.** The design file maintains its own `_SIGNAL_LAYER_TO_VIA` dict, hardcodes `_NUM_CONDUCTOR_LAYERS = 20`, or computes `_SIGNAL_VIA_KEEPOUT_RADIUS` from substrate parameters — all duplicating data the substrate already owns.

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
    a, b = self._signal_layer_pair(i)
    return self.substrate.via[(a, b)]

# substrate file — owns the mapping
class Generic_Substrate(Substrate):
    # ... vias declared as class attributes ...
    @property
    def via(self) -> dict[tuple[int, int], Via]:
        return {
            (0, 1): self.uVia_L1_L2,
            (0, 3): self.uVia_L1_L4,
            (0, 5): self.uVia_L1_L6,
            (0, 7): self.uVia_L1_L8,
        }

    @property
    def n_conductors(self) -> int:
        return len(self.stackup.conductors)
```

**Why.** "Out of place — the substrate has layers. Introspect from stackup" (PR review). When a constant is naturally indexed by `(from_layer, to_layer)`, it belongs in the substrate as `via[(0,1)]`-style mapping. Designs should not maintain a parallel "L1→uVia_L1_L2" table. If JITX doesn't expose the right API, that's a gap to file — not a license to copy.

This also applies to: trace widths (per-routing-structure, not as design-level globals), keepout radii (per-routing-structure layer entry, not bolted via tag rules), fence-via spacing (in the routing structure's fence definition, not as a design constant).

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

**Why.** "There's no safety here — typechecker won't help against typos. Poor craftsmanship. There are dataclasses for this, named tuples, etc." (PR review). The Python tooling (pyright, mypy) catches dataclass-attribute typos at write-time; it can't catch dict-key typos. If batching into records is necessary (after rules 1–3 have been honored), use a frozen dataclass or NamedTuple — never bare `dict[str, Any]`.

---

## 6. No code at module-import time

**Failure pattern.** Module-level `for` loops that populate global `_BALLOUT` / `_SIGNAL_ROW_MAP` dicts at import time, building names by string-formatting (`f"TX{lane}_{pol}"`).

**Bad:**
```python
# module top level
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

Or — if the data really is static and you want it precomputed — keep the *computation* import-time-free by writing a literal:

```python
# explicit literal data — no module-import-time computation, no string keys
BALLOUT: list[BallPosition] = [
    BallPosition(lane=0, polarity="P", position=(0, 0)),
    BallPosition(lane=0, polarity="N", position=(0, 1)),
    BallPosition(lane=1, polarity="P", position=(1, 0)),
    BallPosition(lane=1, polarity="N", position=(1, 1)),
    # ...
]
```

**Why.** "Code that runs on initialization is poor form. Again it's constructing names" (PR review). The rule has two senses: (1) avoid populating mutable globals at import time, and (2) avoid running computation at import time when a literal or a lazy function would do. Module-level loops/comprehensions that populate globals are a strong signal that themes 1 (string keys) and 2 (parallel models) are also present. Wrap in a function (called lazily) or write the data as a literal.

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

**Why.** "This is incorrect — should instantiate generic instead of inlining" (PR review). An empty-body `@inline class X(Base): pass` does nothing the base class doesn't already do — it's just a more expensive way to instantiate. The general principle: prefer instance composition over class-level mechanisms when both produce the same runtime structure. Inheritance is for *adding or changing* behavior; if you're not adding or changing anything, instantiate.

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

**Why.** "Would not assign reference designator here, because JITX assigns those. Lots in this design to handle hardships going through odb++ to hfss" (PR review). If you're computing a name that JITX should be giving you, you're bypassing the framework. The general principle: don't manually assign values that JITX assigns automatically — reference designators, net names from topology, layer indices from stackup, etc. Pressure from export-pipeline tools (e.g., `odb++` → HFSS) is a known temptation to do the wrong thing; resist it.

---

## Meta-rule: when in doubt, use what JITX already has

The thread running through every pattern above: when the framework already has a structural object for what you're modeling, use it. Don't build a parallel one keyed by strings. If JITX doesn't have what you need, the right answer is usually a typed Python primitive (`@dataclass`, `list[T]`, `dict[StructuralKey, T]`), never `dict[str, Any]` or sibling attributes plus `getattr`.

A useful one-line check: *if your only handle on a design object is a string you assembled at runtime, you're string-hacking — stop and find the structural object.*
