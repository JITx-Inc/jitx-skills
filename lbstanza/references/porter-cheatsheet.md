# Porter cheatsheet — Stanza surface for reading 3.x designs

The minimum LB Stanza surface a JITX 3.x → 4.x porter needs to *read* the source. Not a writing guide — for that, descend into `reference-manual.md` / `by-example.md`. Two sections:

1. **Stanza language surface** — the syntax porters encounter in real designs.
2. **JITX 3.x DSL surface** — the `pcb-*` forms layered on top of Stanza.

For each construct: the shape, a one-line gloss, and a pointer to where the **Python 4.x equivalent** lives.

---

## 1. Stanza language surface

### Files and packages

```stanza
#use-added-syntax(jitx)         ; pragma — enables `pcb-module` etc.
defpackage demo/foo :           ; package name (slash-separated)
  import core                   ; bring in symbols
  import collections
  import jitx
  import jitx/commands          ; sub-packages with `/`
```

→ **Python:** standard `from jitx import Circuit, Port` imports. The `#use-added-syntax(jitx)` line has no Python analogue — drop it. Package paths don't survive verbatim (see `jitx-port-3-to-4/references/pitfalls.md` §"Package layout").

### Bindings

```stanza
val x = 42                      ; immutable (prefer this)
var n = 0                       ; mutable
val r : Double = 1.0e3          ; with type annotation
val xs : Tuple<Int> = [1, 2, 3] ; parametric type
```

→ **Python:** ordinary `x = 42` / `xs: tuple[int, ...] = (1, 2, 3)`.

### Functions

```stanza
defn add (a:Int, b:Int) -> Int :
  a + b                         ; last expr is return value; no `return` keyword

public defn helper (xs:Seq<Int>) :   ; `public` = exported from package
  for x in xs do : println(x)
```

→ **Python:** `def add(a: int, b: int) -> int: return a + b`. `public` ≈ no leading underscore.

### Multimethods (open polymorphism)

```stanza
defmulti area (s) -> Double          ; declare the multi
defmethod area (c:Circle) : 3.14 * radius(c) * radius(c)
defmethod area (r:Rectangle) : width(r) * height(r)
```

→ **Python:** prefer regular class methods over multimethods. `defmulti`/`defmethod` rarely have a 1:1 Python translation; usually fold into a `Circuit`/`Component` method hierarchy. See `jitx-port-3-to-4/references/pitfalls.md` §"Stanza language idioms that trip up porters."

### Conditionals and matching

```stanza
if cond : a else : b
match (x) :
  (i:Int)    : println("int %_" % [i])
  (s:String) : println("str %_" % [s])
```

→ **Python:** `if/else`, `match/case` (3.10+), or `isinstance` chains. The Stanza `match` *on type* maps to `isinstance` (don't rewrite as a multimethod just because Stanza had a multi).

### Loops and sequences

```stanza
for x in xs do : println(x)          ; eager — for side effects
for x in xs seq : x * 2              ; lazy — returns a Seq<Int>
for x in xs seq? :                   ; lazy with optional skip
  if x > 0 : One(x) else : None()
val ys = to-list(map({_ * 2}, xs))   ; pipeline style
```

→ **Python:**
- `for x in xs do : f(x)` → `for x in xs: f(x)` (or `[f(x) for x in xs]` for list).
- `for x in xs seq : x * 2` → `[x * 2 for x in xs]` or `(x * 2 for x in xs)`.
- Anonymous fn `{_ * 2}` → `lambda x: x * 2`.

**Note on `for ... seq` in parametric pcb-modules:** when it loops over `0 to <computed-int>` to emit N caps, the count is **computed from kwargs**, not hardcoded — keep the count formula in the Python port. See `jitx-port-3-to-4/references/side-by-side/05-parametric-module.md`.

### Labels (non-local exit)

```stanza
defn find-first (xs:Seq<Int>) -> Int|False :
  label<Int|False> return :
    for x in xs do :
      if x > 0 : return(x)
    return(false)
```

→ **Python:** `return` from a function. Stanza `label` for non-local exit usually flattens to a normal Python `return`.

### Attempt / fail (parser-style backtracking)

```stanza
defn parse-or-default (s:String) -> Int :
  attempt :
    val n = to-int!(s)
    n
  else : 0
```

→ **Python:** `try/except` with the specific exception — but Stanza `attempt`/`fail` is for *control flow* whereas Python `try/except` is for genuine errors. Often a porter can rewrite as an explicit conditional check.

### Try / catch

```stanza
try :
  risky-io()
catch (e:IOError) :
  println("oops: %_" % [e])
```

→ **Python:** ordinary `try/except`. Direct mapping.

### Parametric types and capturing

```stanza
defn pair<T> (x:T, y:T) -> Tuple<T> : [x, y]
val ps = pair<Int>(1, 2)
val qs = pair(1.0, 2.0)              ; `T` inferred
```

→ **Python:** `def pair[T](x: T, y: T) -> tuple[T, T]: return (x, y)` (3.12+), or `TypeVar("T")` style on older Python.

### LoStanza (FFI)

```stanza
lostanza defn raw-add (a:long, b:long) -> long :
  return a + b
```

→ **Python:** rarely encountered in JITX designs. If you do hit it, it's almost always around vendor SDK glue and lives outside the design tree — flag as out-of-port-scope.

---

## 2. JITX 3.x DSL surface

These forms only exist with `#use-added-syntax(jitx)`. Every one has a **Python 4.x equivalent** that lives in `jitx-port-3-to-4/references/construct-map.md`. The rows below summarise; cite the construct-map for full mapping.

### Designs and modules

```stanza
pcb-module my-board :              ; Circuit / Design root
  port vin
  port gnd
  inst r1 : chip-resistor(1.0e3)   ; instance declaration
  inst c1 : chip-capacitor(10.0e-9)
  net VIN (vin, r1.p[1])           ; named net
  net OUT (r1.p[2], c1.p[1])
  net GND (gnd, c1.p[2])
```

→ **Python:** `class MyBoard(Circuit):` with `vin = Port()`, `self.r1 = Resistor(...)` in `__init__`, `self.VIN = self.vin + self.r1.p1`. See construct-map.md §3.

### Components

```stanza
pcb-component esp32 :
  pin-properties :
    [pin:Ref      | pads:Int ... | side:Dir]
    [GPIO[19]     | 25            | Right]
    ; ...
  symbol = make-symbol(...)
  landpattern = qfn-landpattern(...)
```

→ **Python:** `class ESP32(Component):` with `PadMapping(...)`, `Symbol`, `Landpattern`. See construct-map.md §4 + `jitx-skills:jitx-component-modeler`.

### Bundles, vias, stackups, materials

```stanza
pcb-bundle i2c : pin sda; pin scl
pcb-via std-th : ...
pcb-stackup std : stack(...) stack(...)
pcb-material soldermask : type = Dielectric; ...
```

→ **Python:** `class I2C(Port):` with sub-`Port()` attrs (no `jitx.Bundle` class — see `jitx-skills:jitx-pin-assignment` §"Bundles missing from jitxlib"). `Via`, `Stackup`, `Dielectric`/`Conductor`. See construct-map.md §4, §8.

### Provide / require (pin flexibility)

```stanza
supports i2c :                     ; offer this peripheral on these pins
  i2c.sda => self.GPIO[1]
  i2c.scl => self.GPIO[2]

require my-i2c : i2c from mcu      ; ask for one
```

→ **Python:** `@provide.one_of(I2C)` / `@provide(I2C)` decorators on a method that returns a mapping list; `self.require(I2C)` on the consumer side. **First run the hardware-analysis gate** (`jitx-skills:jitx-pin-assignment` §"Hardware-analysis gate") — most `require`s are fixed wiring, not pin-mux. See construct-map.md §7 + side-by-side/04-pin-assignment.md.

### Topology and constraints

```stanza
topology-segment(a.p[1], b.p[1])               ; ordered edge
structure(path-from-a-to-b) = differential-50  ; routing structure
property(net.net-class) = "RF"                 ; tag for design rule
timing-difference(p, n) = TimingDifferenceConstraint(-1ps, 1ps)
```

→ **Python:** `a.p[1] >> b.p[1]` returns `TopologyNet`; `Constrain(...).structure(...)`, `Tag` + `design_constraint(...).routing_structure(...)`, `ConstrainDiffPair(...).timing_difference(...)`. See construct-map.md §6, §9 + `jitx-skills:jitx-interconnect-constraints`.

### Copper, pours, geometry

```stanza
copper-pour(LayerIndex(0), isolate=0.1, rank=1) = shape
add-thermal-vias(net, shape)        ; helper for pad heat-sinking
```

→ **Python:** `Pour(shape, layer=0, isolate=0.1, rank=1)` from `jitx` or `jitx.copper` (**not** `jitx.feature`). Thermal vias use `design_constraint(net_tag).stitch_via(...)` — there is no `add-thermal-vias` Python helper. See construct-map.md §5, §9 + `jitx-skills:jitx-substrate-modeler`.

### Helpers that have no 4.x equivalent

These Stanza convenience helpers silently disappear in 4.x — porting them is *not* "delete the call." See `jitx-skills:jitx/SKILL.md` §"Stanza helpers without a 4.x equivalent" for the full table:

- `add-mounting-holes(...)`
- `add-open-drain-pullups(...)`
- `add-xtal-caps(...)`
- `setup-design(...)`
- `set-paper(...)`, `set-export-backend(...)`
- `view-board()` / `view-schematic()` / `view-bom()` (drop in headless builds)

---

## 3. When this cheatsheet is not enough

Symptoms that mean **descend into the full reference**:

- **The Stanza source uses a stdlib symbol you don't recognize and grep doesn't find in the design tree.** → `reference-manual.md` (grep first, narrow `Read` window).
- **A Stanza idiom feels load-bearing in the design and the cheatsheet doesn't explain why.** → `idioms.md`.
- **You need to author Stanza (e.g. patching a 3.x baseline so it builds before the port).** → `by-example.md` for tutorial content; `reference-manual.md` for syntax.
- **The Stanza source uses `lostanza` blocks or `defsyntax` macros.** → `by-example.md` final chapters; almost always means the construct is out of scope for a routine port.
- **The Stanza source uses `deftest` and you need to know what the tests assert.** → `test-framework.md`.
- **The `.proj` / `slm.toml` is non-trivial and you need to understand the build graph.** → `build-system.md`.

The general discipline (grep first, then read a narrow window — don't pull whole reference files into context) is in `lbstanza/SKILL.md` §"How to Use the References."
