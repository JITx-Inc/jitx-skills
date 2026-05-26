# Worked Patterns — PR #4 as the canonical evidence set

These are the failure patterns the reviewer should recognize on sight. Each pattern: a one-line description, a representative example from the PR-review evidence set (JITx-Inc/py-components#4), the rule that names it as wrong, and what good looks like.

Use this file as the *recognition* counterpart to `checklist.md` (which is the taxonomy). When the reviewer sees code that looks like one of the examples below, the finding writes itself.

---

## P1. String-keyed records become the design's data model

**Recognition shape:** A function `_build_X_records()` that returns `list[dict]`, populated by hand-built strings, then walked by a separate consumer.

**Evidence (PR #4, `src/jitxexamples/designs/si_bga_optimization/bga_escape.py`):**

```python
def _build_pair_records(self) -> list[dict]:
    records = []
    for i in range(7):
        records.append({
            "tx_pair": self._build_pair(i),
            "test_point": self._build_tp(i),
            "antipad": self._build_antipad(i),
            "deskew_antipad_keepout": self._build_dak(i),
        })
    return records

# Elsewhere — consumer walks records
for r in records:
    self += r["tx_pair"].P + r["test_point"].A
```

**Reviewer quote:** "This is building a separate model and then constructing the object out of that model. Just build the scene graph directly. Use constructors, objects, composites, containers." / "This whole file smells. From architecture perspective should be using a better scene graph so you're constructing names based on how design is constructed, not using the string dict hell."

**Finding severity:** CRITICAL. Pattern tags: `parallel-data-model`, `string-keyed-model`.

**Good:**

```python
@dataclass(frozen=True)
class EscapeLane:
    tx_pair: DiffPair
    test_point: TestPoint
    antipad: KeepOut
    deskew_antipad_keepout: KeepOut

self.lanes: list[EscapeLane] = [
    EscapeLane(
        tx_pair=self._build_pair(i),
        test_point=self._build_tp(i),
        antipad=self._build_antipad(i),
        deskew_antipad_keepout=self._build_dak(i),
    )
    for i in range(7)
]
```

---

## P2. Sibling-attribute storage + getattr iteration

**Recognition shape:** Several sibling attributes on a component, named with a numeric suffix; an iteration that reassembles them by `getattr(self, f"X_{i}")`.

**Evidence (`generic_bga.py`):**

```python
class HexBGA_Base(Component):
    def __init__(self):
        super().__init__()
        self.TX_b0 = DiffPair()
        self.TX_b1 = DiffPair()
        self.TX_b2 = DiffPair()
        self.TX_b3 = DiffPair()
        self.TX_b4 = DiffPair()
        self.TX_b5 = DiffPair()
        self.TX_b6 = DiffPair()

# Elsewhere
pairs = [getattr(self, f"TX_b{i}") for i in _NON_LEGACY_PAIR_INDICES]
```

**Reviewer quotes:** "this is illegal" / "illegal — no getattr" / "Why isn't this an array of arrays?" / "there has to be a better way to structure this."

**Finding severity:** CRITICAL. Pattern tags: `getattr-on-self`, `string-keyed-model`.

**Good:**

```python
class HexBGA(Component):
    def __init__(self):
        super().__init__()
        self.TX: list[DiffPair] = [DiffPair() for _ in range(7)]

# Elsewhere
for pair in self.TX:
    ...
```

---

## P3. Substrate-shaped tables duplicated in the design

**Recognition shape:** Module-level constants in a design file that describe substrate properties — layer counts, layer-to-via maps, layer-to-name maps.

**Evidence (`bga_escape.py:35`):**

```python
_NUM_CONDUCTOR_LAYERS = 20  # Generic_Stackup L1..L20

_SIGNAL_LAYER_TO_VIA = {
    1: Generic_Substrate.uVia_L1_L2,
    2: Generic_Substrate.uVia_L1_L4,
    3: Generic_Substrate.uVia_L1_L6,
    4: Generic_Substrate.uVia_L1_L8,
}
```

**Reviewer quotes:** "Out of place — the substrate has layers. Introspect from stackup." / "Encode as a mapping: from – to. L1-L2: 0-1. Can put this in the substrate. `via[(0,1)]`."

**Finding severity:** WARNING (default) or CRITICAL (if design contradicts substrate). Pattern tags: `substrate-pollution`, `substrate-shaped-table-in-design`.

**Good:** Design queries `self.substrate.via[(a, b)]` and `self.substrate.n_conductors`; substrate file owns the tables.

---

## P4. Generic substrate polluted with design-specific concepts

**Recognition shape:** A "generic" substrate file (`generic_<n>layer.py`) that imports / declares tags, trace widths, or fence definitions named after a specific design.

**Evidence (`generic_20layer.py`):**

```python
# In the file declaring a "generic" substrate
AntipadFenceTag = ...           # named after the BGA-escape design
DeskewAntipadFenceTag = ...     # ditto
DESKEW_TRACE_WIDTH = 0.115      # design-specific
DESKEW_PAIR_SPACING = 0.118     # design-specific
```

**Reviewer quotes:** "Tags and rules specific to a design should be in that design, not a generic substrate." / "Careful in this file of intermixing with BGA specific work. Should be isolable and reusable."

**Finding severity:** WARNING. Pattern tag: `generic-substrate-design-leak`.

**Good:** The generic substrate holds impedance-controlled geometry, fab rules, vias, and routing structures. Design-specific tags / trace widths / fence definitions live in the consuming design file.

---

## P5. Module-import-time loops constructing strings

**Recognition shape:** Module-level `for` loop or comprehension at column 0 that populates a global table by string-formatting names.

**Evidence (`generic_bga.py:113`):**

```python
# module top level
_BALLOUT: dict[str, tuple[int, int]] = {}
for lane in range(7):
    for pol in ("P", "N"):
        _BALLOUT[f"TX{lane}_{pol}"] = (lane, pol)
```

**Reviewer quote:** "Code that runs on initialization is poor form. Again it's constructing names."

**Finding severity:** CRITICAL (hard-fail grep gate catches the `for` form). Pattern tags: `module-import-time-logic`, `string-keyed-model`.

**Good:** Function called lazily, or restructure as a typed list / dict-keyed-by-structural-object. See `jitx/references/architectural-patterns.md` § 6.

---

## P6. Untyped intermediate records

**Recognition shape:** `list[dict]` (without explicit element type) or bare `dict[str, Any]` used to batch state, with no `@dataclass` discipline.

**Evidence (same `_build_pair_records` example as P1).**

**Reviewer quote:** "There's no safety here — typechecker won't help against typos. Poor craftsmanship. There are dataclasses for this, named tuples, etc."

**Finding severity:** WARNING. Pattern tag: `untyped-records`.

**Good:** `@dataclass(frozen=True)` or `NamedTuple`.

---

## P7. Coplanar feature applied via tag rule instead of routing-structure layer entry

**Recognition shape:** A `design_constraint(...)` rule with a tag (e.g., `BGAFanoutTag`) bolting a keepout or reference plane onto a routing structure, when the routing structure's `Layer(...)` already supports `.reference(...)` and the keepout can go there directly.

**Evidence (`generic_20layer.py:509`):**

```python
# tag-based keepout added far from the routing structure
design_constraint(BGAFanoutTag).fence_via(
    keepout=ShapelyGeometry(...0.25mm offset...),
    ...
)
```

**Reviewer quote:** "also the 0.25mm keepout should go on signal layer instead of being applied with a tag."

**Finding severity:** WARNING. Pattern tag: `coplanar-feature-misplaced`.

**Good:** Keepout / reference plane declared inline on the routing-structure layer entry:

```python
DRS_DiffPair_85 = DifferentialRoutingStructure([
    DifferentialRoutingStructure.Layer(layer=L_signal, ...)
        .reference(ref_plane)
        .keepout(0.25),
    ...
])
```

---

## P8. `Symmetric` stackup with name baked-in for a unique layer

**Recognition shape:** Names like `L1_Ground1` inside a `Symmetric` stackup. The mirror means the bottom conductor gets the same name, which loses information.

**Evidence (`generic_20layer.py:77`):**

```python
@inline
class stackup(Symmetric):
    L1_Ground1 = Conductor(...)  # this name is mirrored to the bottom
    L2_Signal1 = Conductor(...)
    ...
```

**Reviewer quote:** "With this symmetric setup, Bottom also gets called L1-Ground1."

**Finding severity:** WARNING. Pattern tag: `symmetric-mirroring-confusion`.

**Good:** Either name layers by role (`L_GroundOuter`, `L_SignalCoplanar1`, etc. — mirror-stable), or skip `Symmetric` and list all layers top-to-bottom.

---

## P9. Inline subclass when instantiation suffices

**Recognition shape:** `@inline class X(Base): pass` where `x = Base()` would do.

**Evidence (`generic_20layer.py:296`):**

```python
@inline
class stackup(Generic_Stackup):
    pass
```

**Reviewer quote:** "This is incorrect — should instantiate generic instead of inlining. `stackup = genericstackup()`."

**Finding severity:** WARNING. Pattern tag: `inline-subclass-as-instantiation`.

**Good:** `stackup = Generic_Stackup()`.

---

## P10. Manual JITX-assigned value

**Recognition shape:** `refdes=` set explicitly in user code; net names hard-coded by string-formatting; layer indices computed when the substrate could be queried.

**Evidence (`bga_geometry.py:121`):**

```python
def ball_spec(self, name: str, refdes: str = "U1") -> Ball:
    return Ball(name=f"{refdes}_{name}_solderball", ...)
```

**Reviewer quote:** "Would not assign reference designator here, because JITX assigns those. Lots in this design to handle hardships going through odb++ to hfss."

**Finding severity:** WARNING. Pattern tag: `manual-jitx-assigned-value`.

**Good:** Let JITX assign the refdes; downstream tools should see the right name without manual help.

---

## P11. Unparameterized factory function

**Recognition shape:** A function with zero arguments returning a fully-baked JITX construction object, with all parameters inlined as literals. Called from N sites, each adding `.reference(...)` / `.fence(...)` post-construction.

**Evidence (`generic_20layer.py:256`):**

```python
def _make_drs_layer_85() -> DifferentialRoutingStructure.Layer:
    return DifferentialRoutingStructure.Layer(
        width=0.115,
        spacing=0.118,
        ...all literals inlined...
    )

# Called from many sites, each adding suffix:
DRS_DiffPair_85_L1 = DRS_DiffPair_85.with_layer(_make_drs_layer_85().reference(L_top).fence(...))
DRS_DiffPair_85_L2 = DRS_DiffPair_85.with_layer(_make_drs_layer_85().reference(L_mid).fence(...))
```

**Reviewer quote:** "why have a function to make the construction instead of making the construction? doesn't make sense if not parameterized." / "would give reference layers as argument to the function though."

**Finding severity:** NOTE for single call; WARNING for many calls with varying post-construction chains. Pattern tag: `unparameterized-factory`.

**Good:** Either inline the construction, or push the varying inputs (reference layer, fence config) into the function signature.

---

## P11b. Framework-boundary-bypass (the "they did it, therefore so can I" trap)

**Recognition shape:** the AI follows the no-getattr / no-`type(...)` / no-leading-underscore rules literally but rationalizes one "boundary call" because "the framework does it." The smell is one of:
- An import of a framework helper that does internal navigation (`from jitxlib.landpatterns.grid_layout import to_bga_row_ref`).
- A thin design-side wrapper that hides a `getattr(<framework-object>, ...)` call (`_pad_at(lp, r, c)` wrapping `getattr(lp, row_letter)[c]`).
- A code comment rationalizing one banned-pattern call as "the boundary call" or "the framework does this."

**Evidence (PR #4 rearchitecture commit `ed95f1c`, before fix `be0be76`):**

```python
# generic_bga.py — design code copying framework navigation
from jitxlib.landpatterns.grid_layout import to_bga_row_ref

def _pad_at(lp, r: int, c: int):
    """Boundary call into AlphaDictNumbering's row-letter-keyed pad dict."""
    row_letter = to_bga_row_ref(r)
    return getattr(lp, row_letter)[c]

# Then in GenericHexGridBGA.__init__:
mapping[pair.p] = [_pad_at(lp, bottom_row, col)]
mapping[pair.n] = [_pad_at(lp, top_row, col)]
```

The AI's plan literally documented the rationalization: *"The only `getattr` is the single boundary call into `AlphaDictNumbering`'s row-letter-keyed pad dictionary; there is no design-side string-keyed model."*

**Reviewer quote:** *"rather amusing that this was indeed already called out, but missing the point/intent and ending up with the opposite conclusion ('they did it, therefore so can I! 🎉' — paraphrased). [...] This is bad architecture, and couples the landpattern to a numbering scheme. Since the numbering is a separate concern, [...] this code will fail instead of relying on the existing polymorphic behavior."*

**Finding severity:** CRITICAL. Pattern tag: `framework-boundary-bypass`.

**Good (PR #4 fix commit `be0be76`):**

```python
# generic_bga.py — public adapter on the framework subclass
class HexBGA(A1, AlphaDictNumbering, HexBGADecorated):
    """Hex-staggered BGA with A1-corner alpha/dict pad numbering."""

    def get_pad(self, r: int, c: int):
        """Public (row, col) -> Pad lookup.

        Polymorphic over the numbering mixin so design code stays
        decoupled from AlphaDictNumbering's row-letter attribute
        layout. Wraps the framework-internal _get_pad so callers can
        stay clear of leading-underscore access."""
        return self._get_pad(r, c)   # same-class call — allowed

# Then in design code:
mapping[pair.p] = [lp.get_pad(bottom_row, col)]
```

**Apply the ownership test (jitx-code-review/SKILL.md):**
1. Owner of the row-letter-numbering invariant? `AlphaDictNumbering` (the framework mixin).
2. Is `_pad_at(lp, r, c)` inside that class or a subclass? No — it's in design module scope.
3. Is the caller using a public method? No — it's calling `getattr(lp, ...)` directly.
4. Can a subclass adapter expose a public method? Yes — `HexBGA` is already a subclass; add `def get_pad(self, r, c): return self._get_pad(r, c)`.

→ Classify as `framework-boundary-bypass`; fix by adding the adapter.

**The meta-failure to watch for.** When the AI rationalizes a banned pattern as "OK because…" — especially "OK because the framework does it" — the reviewer must apply the ownership test, not accept the rationalization. The wrapper, the helper, and the comment naming it "the boundary call" are all rationalizations; only the ownership test determines whether the carve-out is real.

---

## P12. Naming hygiene

Single-comment items from PR #4 that don't repeat across themes:

- `LEGACY` / `DORMANT` in names — pattern tag `vestigial-construct`.
- Subclass not echoing base class name (`HexBGA_Base extends BGADecorated`) — pattern tag `name-vs-base-class-mismatch`.
- Tag named after geometry primitive instead of role (`DiffPairTag` when it's a transmission-line-class tag) — pattern tag `name-vs-base-class-mismatch`.

**Severity:** NOTE. Reviewer flags for author decision; not blocking.
