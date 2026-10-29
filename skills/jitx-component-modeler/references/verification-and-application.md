# Verification

The agent opens this file when a test constructs a component directly or build discovery fails. The universal completion gate remains in `SKILL.md`; this file carries the detailed harnesses and test gotchas.

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

A build proves the component translates. It does not prove the pin count matches the datasheet, or that the value the BOM prints is the value the user asked for. Those need tests.

**Tests that construct a component must subclass `jitx.test.TestCase`, never plain `unittest.TestCase`**. It activates the JITX instantiation context, and needs no runtime — instantiating a component works offline. Outside that context a constructor does not run: `MyPart()` returns a deferred `Instantiable` proxy and **`__init__` is never called**, so every fail-fast check in the class silently passes. A negative test written on a plain `unittest.TestCase` then fails for the wrong reason — not because the validation is missing but because nothing ran — and a demo script that constructs a deliberately invalid part raises nothing at all.

This is about *construction*, not about the base class on its own: a plain `unittest.TestCase` exercising a pure function — a table cross-check, a classmethod that validates arguments without instantiating — is fine, and is a good reason to put validation in such a classmethod in the first place.

**To build a component directly — outside a `SampleDesign` class body — open a substrate context as well:**

```python
from jitx.sample import SampleSubstrate
from jitx.substrate import SubstrateContext

with SubstrateContext(SampleSubstrate()):
    part = MyPart()
```

**Declare every JITX class at module scope, never inside a test method.** Defining one while an
instantiation context is active raises:

```
TypeError: Creating new JITX classes dynamically during instantiation is not supported,
please create new classes separately.
```

So a `SampleDesign`, a `Circuit` harness, or a throwaway component built to exercise one case all
belong at module scope, even when only one test uses them. This is the same instantiation-tracking
rule as the base skill's "no JITX subclass defined inside a function"; it bites here
because a test method is the natural place to reach for a one-off fixture.

Direct construction is what `@pytest.mark.parametrize` forces, since a parametrized case cannot drive a class-body `SampleDesign`. The jitxlib land-pattern generators read fabrication values off the active substrate — silkscreen-to-soldermask spacing, via `jitx.current.substrate.constraints` — so with no substrate active they raise instead of building. **Never rely on a context an earlier test left set**: that passes in suite order and fails when the test runs alone, which is the order a bisect or a `-k` filter uses.

**What a component test asserts,** beyond `status: ok` from the build:

- **It builds in a `SampleDesign`** and its metadata reads back — manufacturer, reference-designator prefix, ratings.
- **Pad count equals pin count**, once per package variant, so every land pattern is exercised at least once. Count with the framework's structural traversal, which does not depend on the numbering scheme:

  ```python
  from jitx.inspect import visit
  from jitx.landpattern import Pad

  pad_count = sum(1 for _ in visit(lp, Pad))  # every pad the landpattern owns, thermal pads included
  ```

  Inside a `SubstrateContext` it gives 8 for a generated SOIC-8, equal to `len(lp.p)`, and 441 for a generated 21 by 21 BGA, where `lp.p` does not exist. Do not count by enumerating attributes: `lp.p` exists only on the linearly numbered generators, a BGA's `AlphaDictNumbering` keeps its row dictionaries outside the instance namespace, and an attribute walk over one-letter row names returned 0 for that BGA. `lp.pads` is not an accessor either. Compare `pad_count` with the datasheet's pin count plus its thermal pads. If the count cannot be established for the package at hand, the pad-count check stays open and verification stops rather than recording an unchecked number.
- **The value field left unset**, as the SKILL.md `Value / BOM` row requires.
- **Library defaults against the datasheet**, wherever the land pattern took them — dimensions *and* density level. Pin a known-bad entry as still-wrong, so the override is removed when the table is fixed.

**For a generated component**, add the assertions in [pin-file-generation.md](pin-file-generation.md#testing-a-generated-component). Note that a spot-check expression indexing a `PadMapping` needs the narrowing in [component-code-patterns.md](component-code-patterns.md#padmapping-requirements); written literally it does not type-check, and a suite gated on "pyright clean" will contradict itself.

Where a test is skipped unless a source file is present — the idempotency check usually is, since the vendor file cannot be committed — **confirm it actually ran** when you are relying on it. A skipped test is green.

**"The environment can't run this" is a claim to test, not to assert.** Before recording a check as unavailable, try it. The completion block's hard-fail is on an *undeclared* unavailable environment, which makes declaring feel like the safe move — but a declaration that turns out to be wrong is worse than a failing check, because it reads as diligence while hiding the result.

The specific trap: a missing `pyproject.toml` looks like "no project, so no build," and it is four lines away from being a project. Add a minimal `pyproject.toml` and run `jitx build --dry`. Cheap to check, and `--dry` needs no runtime. If the check then fails for a reason you already know and accepted (geometry deliberately absent, say), record the actual message; "cannot be placed on a board" and "cannot be translated into any design" are different claims, and the second is the one the reader needs.

### Build Command

Always use the available virtual environment. If one is not present, stop and ask.
```bash
jitx build <module>.TestDesign
```

Don't run parallel JITX builds against the same project — sequence them. See [Build safety: don't parallelize same-design work](../../jitx/SKILL.md#build-safety-dont-parallelize-same-design-work).

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

Emit the **task acceptance block** from `jitx-project-builder/references/completion-blocks.md` "Task Acceptance Block", with the [Component completeness check — run before calling it done](../SKILL.md#component-completeness-check--run-before-calling-it-done) filled in under its `Checks run` field. For a component task, the block's `Primary source` field cites the datasheet pages with the pinout and mechanical drawing; the `Footprint source` field names the JITX generator used (or KiCad import with reason); the `Checks run` field includes the Component checklist from `jitx-project-builder/references/domains/component-modeling.md` with N/N items and any issues fixed (pin count vs datasheet, pad count vs landpattern, dimensions vs datasheet mechanical drawing). The acceptance block is the report; do not invent a parallel format.

The checklist and the completeness check are complementary, not interchangeable. The **domain checklist is the per-pin / per-pad enumeration you walk while writing** the component; the **completeness check is the evidence you present when claiming it is done**, one row per way a component fails quietly. Report each build, type check and test run **once** — the completeness check's `Checks` row is where they live, and it satisfies the checklist's Build Test items.
