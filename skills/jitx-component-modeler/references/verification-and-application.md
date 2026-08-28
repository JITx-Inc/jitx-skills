# Verification and Application Handoff

The agent opens this file when a test constructs a component directly, build discovery fails, or a datasheet application circuit needs capture. The universal completion gate remains in `SKILL.md`; this file carries the detailed harnesses, test gotchas, and handoff workflow.

## Verification Process

### Step 4: Test Harness

```python
import jitx
from jitx.container import inline
from jitx.sample import SampleDesign

from .component import Device


class TestDesign(SampleDesign):
    @inline
    class circuit(jitx.Circuit):
        dut = Device()
```

**Put the harness where `jitx find` can see it.** The CLI's project scanner imports candidate modules by their top-level name, so a design that only exists inside a `tests/` package — or in any directory the project doesn't make importable — is not discovered, and `jitx find` reports `designs: []` with a `ModuleNotFoundError` per file rather than saying the design is missing. Confirm with `jitx find` before `jitx build`, and **take the build target verbatim from what `jitx find` prints** rather than composing it from the module path yourself. A `jitx.test.TestCase` suite is the offline check; it does not substitute for the build, and a design the CLI cannot find has not been built.

### Verifying a component with tests

A build proves the component translates. It does not prove the pin count matches the datasheet, that the part number the class computes is one the manufacturer sells, or that the value the BOM prints is the value the user asked for. Those need tests.

**Tests that construct a component must subclass `jitx.test.TestCase`, never plain `unittest.TestCase`** (verified on jitx 4.4.0). It activates the JITX instantiation context, and needs no runtime — instantiating a component works offline. Outside that context a constructor does not run: `MyPart(size="0505")` returns a deferred `Instantiable` proxy and **`__init__` is never called**, so every fail-fast check in the class silently passes. A negative test written on a plain `unittest.TestCase` then fails for the wrong reason — not because the validation is missing but because nothing ran — and a demo script that constructs a deliberately invalid part raises nothing at all.

This is about *construction*, not about the base class on its own: a plain `unittest.TestCase` exercising a pure function — a value-code encoder, a table cross-check, a classmethod that validates arguments without instantiating — is fine, and is a good reason to put validation in such a classmethod in the first place.

**To build a component directly — outside a `SampleDesign` class body — open a substrate context as well:**

```python
from jitx.sample import SampleSubstrate
from jitx.substrate import SubstrateContext

with SubstrateContext(SampleSubstrate()):
    part = MyPart(size="0402", ...)
```

**Declare every JITX class at module scope, never inside a test method.** Defining one while an
instantiation context is active raises (verified on 4.4.0):

```
TypeError: Creating new JITX classes dynamically during instantiation is not supported,
please create new classes separately.
```

So a `SampleDesign`, a `Circuit` harness, or a throwaway component built to exercise one case all
belong at module scope, even when only one test uses them. This is the same instantiation-tracking
rule as the base skill's "no subclassing JITX classes inside functions or methods"; it bites here
because a test method is the natural place to reach for a one-off fixture.

Direct construction is what `@pytest.mark.parametrize` forces, since a parametrized case cannot drive a class-body `SampleDesign`. The chip land-pattern generator reads fabrication values off the active substrate — silkscreen-to-soldermask spacing, via `jitx.current.substrate.constraints` — so with no substrate active it raises instead of building. **Never rely on a context an earlier test left set**: that passes in suite order and fails when the test runs alone, which is the order a bisect or a `-k` filter uses.

**What a component test asserts,** beyond `status: ok` from the build:

- **It builds in a `SampleDesign`** and its metadata reads back — manufacturer, reference-designator prefix, ratings.
- **Pad count equals pin count**, once per package variant, and for a family once per case size, so every land pattern is exercised at least once. The accessor depends on the numbering scheme: linearly numbered generators keep pads in `lp.p`, while a BGA mixes in `AlphaDictNumbering` and keeps one `dict[int, Pad]` per row letter with no `lp.p` at all. Both forms, and the `hasattr` guard `thermal_pads` needs because it is absent rather than empty, are in the base skill's verification step. `lp.pads` is not an accessor on either scheme. The pad-count check stays open, and verification stops, until this count runs.
- **The generated part number against the datasheet's own ordering example** — the worked example in the ordering-information section, or a real catalog part. This is the one assertion that proves the numbering scheme was read rather than inferred; one per scheme is enough.
- **The human-readable value label**, not just the part number — see below.
- **The value encoder as a unit test, with decade-carry cases** alongside the ordinary ones.
- **That validation raises** on each invalid axis *and* on the invalid cross-axis combinations.
- **Library defaults against the datasheet, per size**, wherever the land pattern took them — dimensions *and* density level. Pin a known-bad entry as still-wrong, so the override is removed when the table is fixed.

**For a generated component**, add the assertions in [pin-file-generation.md](pin-file-generation.md#testing-a-generated-component). Note that a spot-check expression indexing a `PadMapping` needs the narrowing in [component-code-patterns.md](component-code-patterns.md#padmapping-requirements); written literally it does not type-check, and a suite gated on "pyright clean" will contradict itself.

Where a test is skipped unless a source file is present — the idempotency check usually is, since the vendor file cannot be committed — **confirm it actually ran** when you are relying on it. A skipped test is green.

**"The environment can't run this" is a claim to test, not to assert.** Before recording a check as unavailable, try it. The completion block's hard-fail is on an *undeclared* unavailable environment, which makes declaring feel like the safe move — but a declaration that turns out to be wrong is worse than a failing check, because it reads as diligence while hiding the result.

The specific trap: a missing `pyproject.toml` looks like "no project, so no build," and it is four lines away from being a project. An agent that declares `jitx build` unrunnable for that reason skips the check entirely. Adding a minimal `pyproject.toml` lets `jitx build --dry` run, and it can report something like `translation failed: <Component> does not have a landpattern`, a fact about the delivered artifact that a completion block would otherwise never state. Cheap to check, and `--dry` needs no runtime. If the check then fails for a reason you already know and accepted (geometry deliberately absent, say), record the actual message; "cannot be placed on a board" and "cannot be translated into any design" are different claims, and the second is the one the reader needs.

**Assert the value label — scaling to an SI prefix reintroduces float noise on exactly the values a passive library uses most.** `PlainQuantity.to_compact()` divides by a power of ten, so an exactly specified `100e-9 F` comes back as `99.99999999999999 nanofarad`, and `2.2e6 Ω` as `2.1999999999999997 megaohm` (verified on jitx 4.4.0). Nothing else catches it: `pyright` sees a well-typed quantity, `pytest` never touches `.value` unless you tell it to, `jitx build` reports `status: ok` — and the string goes to the BOM. Round the scaled magnitude back to significant figures before assigning `.value`, and assert the rendered string. Assert it the way the translator renders it (`f"{value:g~P}"`), not through a bespoke format spec — a spec of your own can hide the noise it is supposed to catch.

### Build Command

Always use the available virtual environment. If one is not present, stop and ask.
```bash
jitx build <module>.TestDesign
```

Don't run parallel JITX builds against the same project — sequence them. See `jitx/SKILL.md` "Build Safety".

**Success:** `status: ok`
**Failure:** Python traceback or `status: error`

**Output files** (in `designs/<design_name>/`):
- `cache/netlist.json` - Verify net connections
- `design-info/stable.design` - Design snapshot

### Common Build Errors

| Error | Fix |
|-------|-----|
| `port X not mapped to symbol pin` | Add port to BoxSymbol |
| `port X not mapped to pad` | Check port count = pad count |
| `No pad configuration specified` | BGA needs `.pad_config(SMDPadConfig())` |

### Verification Report

Emit the **task acceptance block** from `jitx/references/completion-blocks.md` "Task Acceptance Block", with the **Component completeness check** in `SKILL.md` filled in under its `Checks run` field. For a component task, the block's `Primary source` field cites the datasheet pages with the pinout and mechanical drawing; the `Footprint source` field names the JITX generator used (or KiCad import with reason); the `Checks run` field includes the Component checklist from `jitx/references/domains/component-modeling.md` with N/N items and any issues fixed (pin count vs datasheet, pad count vs landpattern, dimensions vs datasheet mechanical drawing). The acceptance block is the report; do not invent a parallel format.

The checklist and the completeness check are complementary, not interchangeable. The **domain checklist is the per-pin / per-pad enumeration you walk while writing** the component; the **completeness check is the evidence you present when claiming it is done**, one row per way a component fails quietly. Report each build, type check and test run **once** — the completeness check's `Checks` row is where they live, and it satisfies the checklist's Build Test items.

## Step 5: Capture Application Circuit

**In the project-builder (complete-board) workflow, this step is MANDATORY — not optional.** The application circuit from the datasheet is the foundation for the downstream circuit task; capture it now while the datasheet is open.

In single-task tier (user invoked component-modeler standalone), this step is optional — ask the user.

After generating component code, check the datasheet for "Typical Application", "Reference Design", or "Application Circuit" sections. These provide valuable circuit templates.

**Process (complete-board):**

1. Capture the application circuit without asking. Extract the relevant datasheet figure (use `extract_pages.py`) and invoke `jitx-circuit-builder` to generate the circuit code.

**Process (single-task):**

1. **Ask user** whether to capture the application circuit:
   ```
   "The datasheet includes a Typical Application circuit (Figure X).
   Would you like me to also generate the application circuit code?"
   ```

2. **If yes**, invoke the `jitx-circuit-builder` skill to generate circuit code

3. **Pass context** to circuit-builder:
   - Component class name and import path
   - Datasheet figure reference
   - Component values from schematic (cap values, resistor values, inductor specs)
   - Pin connections shown in the schematic

**Example application circuit output:**

```python
"""
Texas Instruments TPS62933DRLR Application Circuit
From datasheet Figure 23 - Typical Application

3.8-V to 30-V input, 3.3V 3A output buck converter.
"""

from jitx import Circuit, Net
from jitx.toleranced import Toleranced
from jitx.common import Power
from jitxlib.parts import Capacitor, CapacitorQuery, Resistor, Inductor, ResistorQuery
# jitxlib.voltage_divider is absent from some installs (including jitxlib
# shipped with jitx 4.4.0rc5) — import it and check before relying on it.
from jitxlib.voltage_divider import VoltageDividerConstraints, voltage_divider_from_constraints

from .texas_instruments_TPS62933DRLR import TPS62933DRLR


class TPS62933DRLRCircuit(Circuit):
    """Buck converter application circuit per datasheet Figure 23."""

    vin = Power()   # Input power (3.8V-30V)
    vout = Power()  # Output power (3.3V)

    def __init__(self, output_voltage=3.3):
        self.GND = Net(name="GND")
        self.VOUT = Net(name="VOUT")
        self.VIN = Net(name="VIN")

        # Main IC
        self.buck = TPS62933DRLR()

        # Power connections
        self.VIN += self.vin.Vp + self.buck.VIN
        self.GND += self.buck.GND + self.vin.Vn + self.vout.Vn

        # Input capacitors (C1, C2 - 10µF each per schematic)
        with CapacitorQuery.refine(type="ceramic", case="0805"):
            self.c_in1 = Capacitor(capacitance=10e-6, rated_voltage=50.0)
            self.c_in1.insert(self.buck.VIN, self.GND, short_trace=True)

            self.c_in2 = Capacitor(capacitance=10e-6, rated_voltage=50.0)
            self.c_in2.insert(self.buck.VIN, self.GND, short_trace=True)

        # Feedback voltage divider
        vdiv_cons = VoltageDividerConstraints(
            v_in=Toleranced.exact(output_voltage),
            v_out=Toleranced.percent(0.8, 3.0),  # MUST have tolerance window
            current=0.8 / 10e3,
            prec_series=[1.00, 0.10],             # REQUIRED
            base_query=ResistorQuery(case=["0402"]),
        )
        self.fb_div = voltage_divider_from_constraints(vdiv_cons, name="feedback")
        self.VOUT += self.fb_div.hi + self.vout.Vp
        self.GND += self.fb_div.lo
        self.nets = [self.fb_div.out + self.buck.FB]

        # Output inductor and capacitors
        self.L = Inductor(inductance=4.7e-6, current_rating=3.9)
        # ... complete circuit per datasheet
```

**File location:** Save application circuits alongside the component:
```
components/
├── power_switchmode/
│   ├── texas_instruments_TPS62933DRLR.py      # Component
│   └── texas_instruments_TPS62933DRLR_circuit.py  # Application circuit
```
