# Port-mode pitfalls

Things that bite specifically during a Stanza-3.x → Python-4.x port. The
general JITX 4.x landmines (GC trap, port immutability, `Net()` varargs,
`Pour` import path, named nets at the top level only, power-rail naming,
provide-stub-returning-`[]` danger, `Constrain` vs `ConstrainDiffPair`,
polymer cap crash, thermal-via constraint pattern, build invocation
gotchas, invented-API gallery) live in the domain skills — see the
cross-reference table in `construct-map.md` §11–15 and
`jitx-skills:jitx/SKILL.md` §"Common API mistakes". This file is the
**porter-only** pitfall list.

## Object construction model

- **Stanza modules return values** (a `pcb-module` body produces the
  module). **Python `Circuit` subclasses build via attribute assignment
  in `__init__`** — there is no "return" of the circuit. Don't try to
  write `return self` or paraphrase the Stanza expression-style body as
  a Python expression.
- **Instance declarations** in Stanza (`inst foo : my-component`) become
  `self.foo = MyComponent()` in Python `__init__`. Order in `__init__`
  matters when later code references earlier instances.
- A natural translation of `net (a, b)` as `self.a += b` fails — Port
  immutability — see `jitx-skills:jitx-circuit-builder` §"Port
  immutability".
- ❌ **Don't bind a `Net` to a Python local.** A `+` chain between
  `Port`s returns a `Net`; assigning the result to a local instead of
  `self.<name>` causes the `Net` to be GC'd after `__init__` returns
  and the build logs:

  ```
  WARNING:jitx._structural:Reference to structural object Net() at
  <file>:<line> lost during instantiation, it likely needs to be
  assigned to an object.
  ```

  Connectivity may still appear in the netlist, but the warning is
  the only signal that the `Net`'s symbol / metadata is lost. Fix:
  assign every `+`-chain result to `self.<name>`.

## Naming — don't reuse a base class name

- ❌ **Do not name the ported design class `SampleDesign`** when
  subclassing `jitx.sample.SampleDesign`. Python rebinding makes
  `class SampleDesign(SampleDesign): ...` technically legal but confuses
  readers and static analysis tools. Pick something distinctive
  (`TecDesign`, `MyBoard`, `EthernetIODesign`).

## Power topology / net naming (mandatory Phase 4 check)

Stanza power-net naming is conventional: `VCC` is typically the **raw
external supply** (from the connector or input header), and `VDD` is
typically the **regulated output** (from a buck/LDO). The natural Python
instinct is to use `VCC` for the most prominent rail in the design —
which is often the regulated 3.3 V, not the raw input. **This inversion
produces a clean build with the wrong voltage on PVDD / I²C pullups /
copper pours.** The build will not catch it; only Phase 7's
power-topology check will.

Before naming any net in the Python port, read every Stanza `net`
definition that touches the input connector AND the regulator, and write
down the mapping explicitly:

```stanza
net VCC (conn.p[1])                     ; VCC = external input from connector
net VDD (vreg.vout)                     ; VDD = regulated output
net (VCC amps.pvdd.vdd)                 ; speaker supply = raw external
net (VDD amps.dvdd.vdd mcu.mcu-power.vdd)  ; digital supply = regulated
```

| Stanza net | Voltage | Python name |
|---|---|---|
| Connected to input connector AND regulator VIN | raw input | `VCC` |
| Connected to regulator VOUT | regulated | `VDD` |

If any amp PVDD / high-voltage speaker supply / motor-driver VBAT port
connects to the raw supply in Stanza, it **must** connect to the same
net as the regulator input in Python — not to a separate connector pin
and not to the regulated rail.

See `jitx-skills:jitx-circuit-builder` §"Power-rail naming" for the
general invariant; this section adds the porter-side translation
discipline.

## Stanza language idioms that trip up porters

- **`defmulti` dispatch** in Stanza often becomes a plain Python method,
  not `functools.singledispatch`. Python's `Circuit`/`Component` class
  hierarchy is rich enough that you rarely need open multimethod
  dispatch.
- **Stanza generators / `Seq` pipelines** map to Python list/generator
  comprehensions, not to a port of the Stanza sequence library.
- **`with-syntax` / parametric helpers** in Stanza often emitted
  families of designs at compile time. The Python equivalent is a plain
  factory function or a parameterized `Circuit` subclass; resist
  transcribing the macro structure.
- **3.x stdlib bundle-symbol drift.** A pre-verify failure of the form
  `Could not resolve '<SYMBOL>'` on a parametric bundle augmentation
  symbol (e.g. `SPI-DQS`, `usb-2-data`, `I2S-MCK`) during Phase 0 is
  almost always 3.x stdlib drift between point releases — not a
  port-side issue. Confirm with
  `strings ~/.jitx/<ver>/pkgs/*.pkg | grep -c '^<SYMBOL>$'`. If the
  count is zero the symbol was dropped from that release; either pin
  to the older release that defines the symbol, or accept the static
  Stanza source as the Phase 8 reference. See
  `jitx-port-3-to-4/references/workflow.md` §"Triage protocol when
  the 3.x build fails".
- **E-series snap on computed parts values.** Translating Stanza
  `cap-strap` / `res-strap` calls with a *computed* value (e.g. soft-
  start cap value from a formula) requires an E-series snap on the
  Python side before passing the value to `Capacitor` / `Resistor` /
  `Inductor`. The Stanza `closest-std-val(...)` call is the hint —
  without an equivalent Python snap, the parts DB rejects the
  awkward computed value with "No components meeting requirements".
  See `jitx-skills:jitx-circuit-builder` §"Snap computed values to a
  standard E-series".
- **Class-body comprehensions can't see sibling class attributes.**
  Inside a `Component` class body, a list / dict / set comprehension
  gets its own scope and cannot see other class attributes — `p`
  defined two lines above is invisible inside the comprehension and
  class definition fails with `NameError: name 'p' is not defined`.
  Workaround: write explicit `{port: pad, …}` literals in
  `PadMapping`, not comprehensions:

  ```python
  # ❌ class-body NameError at class definition
  class PinHeader5(Component):
      p = [Port() for _ in range(5)]
      landpattern = _PinHeader5Landpattern()
      cmappings = [PadMapping({p[i]: landpattern.p[i] for i in range(5)})]

  # ✅ explicit literal
  class PinHeader5(Component):
      p = [Port() for _ in range(5)]
      landpattern = _PinHeader5Landpattern()
      cmappings = [PadMapping({
          p[0]: landpattern.p[0],
          p[1]: landpattern.p[1],
          p[2]: landpattern.p[2],
          p[3]: landpattern.p[3],
          p[4]: landpattern.p[4],
      })]
  ```

## Package layout — Stanza paths are not Python paths

- **Stanza `defpackage` paths are not Python module paths.** A file at
  `src/foo/bar.stanza` with `defpackage foo/bar` is unrelated to where
  Python will put `foo/bar.py`. Python module layout follows
  `pyproject.toml` conventions; design from the Python side.
- **Stanza `import` is package-granular.** Python
  `from jitx import Circuit, Component, Port` is symbol-granular.
  Listing the imports in the Python file is more verbose but more
  navigable.

## "Fewer warnings" is not "more correct"

- A 3.x design that builds with warnings may produce a 4.x port that
  builds clean — the warnings often map to issues the 4.x type system
  catches at construction time. Don't treat "fewer warnings" as proof of
  correctness.
- Conversely, a 3.x design that builds *cleanly* and a 4.x port that
  builds *cleanly* still need export comparison — equivalent component
  placement and routing isn't guaranteed by passing builds alone. Phase
  7 of `workflow.md` covers the structured comparison.

## Stanza-pin-number trap on QFN thermal pads

Stanza `pin-properties` tables often list the thermal pad as one past
the last lead (e.g. pin 33 on a 32-lead QFN, pin 57 on a 56-lead QFN —
the ESP32-S3 FN8 source uses `[GND | 57 | Left | Power]`). In 4.x there
is no `lp.p[N+1]` — that pin **is** `lp.thermal_pads[0]`. Map the port
to `thermal_pads[0]` only; a literal Stanza-style `lp.p[57]` raises
`KeyError: 57`.

See `jitx-skills:jitx-component-modeler` §"PadMapping Requirements" for
the general thermal-pad mapping pattern. The trap above is the
port-specific naming gotcha when transcribing a Stanza pin-properties
table verbatim.

## Plan-mode omission of Phase 0

When an AI agent is asked to *plan* a port (rather than execute one),
the skill description's execution-verb triggers may not match. The
agent then writes a plan from memory of similar tasks and silently
skips Phase 0 (the 3.x pre-verify). The plan looks complete; execution
begins; only when the 4.x build fails does the question "is this the
port, or was the 3.x source already broken at this commit?" surface —
at which point there's no clean baseline to compare against and the
answer is unknowable.

**Symptom:** A port plan whose first execution step is "clone the
design, create the port branch, port the components..." with no
explicit Phase 0 that builds the 3.x source first.

**Fix:** Treat the five-item port plan checklist at the top of
`SKILL.md` as a gating reviewer test. Run through it before declaring
a plan done.

**Real example:** a planning session for the `pd_audio` design
(May 2026) wrote a plan that jumped directly from "clone + checkout
commit + create branch" to "inventory the Stanza source" to "initialize
Python skeleton", skipping Phase 0 entirely. The user caught it with a
Socratic-style question; the plan was patched, but if the user hadn't
noticed, the v4 port would have proceeded against an unverified v3
baseline.

## Don't (port-specific)

- ❌ Describe Stanza as JVM-compiled — it is natively compiled via C.
- ❌ Mass-rename Stanza identifiers to Python style without re-running
  the build at each step. Identifier-rename mistakes cascade through
  the wiring.
- ❌ Carry over Stanza package paths verbatim. Python uses standard
  module paths from `pyproject.toml`.

(General "do not invent APIs" / "do not skip pyright" rules live in
`jitx-skills:jitx/SKILL.md`.)
