# Component guide

Rules for a component built from a datasheet, drawing or KiCad footprint, in task order. A vendor pin file adds [pin-file-generation.md](pin-file-generation.md). API semantics are in the docstrings of the symbols named here.

## Sources

For every named part (an MPN, a distributor part number or a user-supplied datasheet), work down this ladder:

1. The manufacturer's current datasheet or package document, cited per dimension.
2. The manufacturer's machine-readable pin file: names, balls and banks only, never geometry, parsed per [pin-file-generation.md](pin-file-generation.md).
3. Records from a sourcing channel the user named, as a cross-check; the datasheet wins and the conflict is recorded.
4. The user, for the datasheet, a distributor part number or a `.kicad_mod`.

With none, the part is blocked unless the user explicitly authorizes a non-MPN generic placeholder, recorded under `Notes`. Writing "typical", "approximate" or "refine later" about a real part's geometry is the signal to stop: the reasoning that excuses one guessed part excuses a batch. Positional names (`p1`, `p2`) for terminals the source does not name are not invented labels. Before modeling a reusable family, search for an existing model per `jitx/references/parts-sourcing.md` "Reference Search Order for Component Modeling" and record `searched: found <path>` or `searched: no analog`.

### MPN identity

Nothing downstream checks `mpn`: pyright, tests and the build all pass a fabricated one. A pin file's device string or a manual's package name is not orderable; a real MPN usually also encodes speed grade and temperature range. Where no document states one, ask while the user confirms device and package, and set the agreed value with a comment saying what it identifies.

### Datasheets

Save the PDF to `datasheets/<mpn>.pdf` (or the project's gitignored scratch directory, uncommitted); the `datasheet` attribute carries the URL. Mirrors serve HTML under `.pdf` URLs, so check that `head -c 5` prints `%PDF-`. Run `python scripts/extract_pages.py <pdf> --find "pin description" "mechanical"`, then `--pages N ... -o extract.pdf`, and read only the extract. A manufacturer URL that times out is more likely your egress than a moved file: say which, and never silently substitute an aggregator's copy.

Cite by caption first: figure numbers move between editions, and a drifted number still resolves to a plausible wrong figure. Search for the caption, and record caption, edition and page beside the values.

## Package and generator choice

```
Two-terminal body -> jitxlib.landpatterns.twopin (SMT, MoldedTwoPin, AxialTwoPin;
                     Polarized* for a diode or LED, pads a and c)
Two-sided:  3 to 6 leads -> SOT23_3 / SOT23_5 / SOT23_6; more -> SOIC (gull-wing), SON (no-lead)
Four-sided: QFP (gull-wing), QFN (no-lead)
Ball array: BGA
Anything else (connectors, RF modules, irregular pads): KiCad import
Mechanical or vendor-defined (Tag-Connect, pogo pins, edge contacts):
  jitx/references/parts-sourcing.md "Mechanical / Vendor-Defined Footprints"
```

A standard package uses its generator, even when a KiCad footprint exists: generated code is auditable. Fall back to KiCad only after the generator fails to express the package (a split paddle, an irregular lead layout), with the reason under `Notes`.

Each generator has a worked `jitxexamples` component showing the call, ports, symbol and pad mapping. Its dimensions are that part's, and some modules take defaults or device-name MPNs this skill rejects. Read it in the docs (`jitx/references/docs-index.md` "Example Components") or, where installed, under `python -c "import jitxexamples; print(list(jitxexamples.__path__))"`.

| Generator | Module under `jitxexamples.` | Shows |
|---|---|---|
| `SOIC` | `components.flash.winbond_W25Q128JVSIQ` | explicit `LeadProfile`, `PadMapping` |
| `SOIC` | `components.timers.texas_instruments_NE555` | ports in pin order, no `PadMapping` |
| `SOT23_5` | `components.opamps.texas_instruments_TLV314IDBVR` | `SOTLeadProfile`, `RectanglePackage` |
| `QFN` | `components.mcus.raspberry_pi_RP2040` | port arrays, thermal pad in `PadMapping` |
| `SON` | `components.power_linear_regulators.texas_instruments_LM1117LD` | thermal pad in `PadMapping` |
| `BGA` | `jumpstart_kits.js1_stackup_components.versal_fpga.landpattern` (source only) | `BGA` subclass with a `get_pad` adapter |
| custom | `components.connectors.molex_2012670005` | hand-built `Landpattern`, `THPad` with a cutout |

QFP has no module; see the `QFP` docstring. Every dimension is a `Toleranced` from the drawing's min and max. The docstrings of `RectanglePackage`, `LeadProfile`, the lead classes and each generator's `thermal_pad` map the datasheet letters to arguments, including a leadless part's span and the thermal pad's X and Y, where misreads pass silently. Thermal-pad paste follows the datasheet's example stencil (`WindowSubdivide`); assert the window size in a test, and with no stencil record the coverage chosen.

## KiCad import

When no generator expresses the package and the vendor publishes a KiCad footprint, placing pads from the drawing is refused. Sources, in order: the user; the manufacturer's library; a third-party library (LCSC/EasyEDA, SnapEDA) only with the user's explicit approval, recorded under `Notes` and checked pad by pad against the manufacturer's drawing.

Write each pad, hole, soldermask and paste opening from the `.kicad_mod` entries, citing the file and URL. KiCad's y axis points down: negate every y, or the part builds mirrored. Check rotated pads and pin 1 against the drawing. With no footprint anywhere, place pads from the drawing's recommended land pattern, cited per dimension, and record "no vendor KiCad footprint found" under `Notes`.

## Writing the class and symbol

Start from the generator's module. Set `mpn`, `manufacturer`, `reference_designator_prefix` and `datasheet` as class attributes and end with `Device: type[MyPart] = MyPart` for the harness. Ports, land pattern and symbol go at class scope by bare name or in `__init__` through `self` (`jitx.Component` docstring). Every `components/` directory carries an `__init__.py`.

Pin names come from the datasheet's pin table (`OQSPIF_D0`, not `P0`), every pin enumerated, never sampled. Alternate functions share one port under the primary name; numbered names (GND1 to GND3) become an indexed list.

A port has one home: a grouping of the component's ports is a method returning fresh records, never a stored attribute. Storing one fails translation with "Child object ... encountered multiple times", naming both paths.

`PadMapping[port]` returns `Pad | Sequence[Pad]` and `Pad.transform` is `Placement | None`; narrow each with a check that raises, not a suppression comment. Pad coordinates compose through `jitx.inspect.visit`, per the `Pad.transform` docstring.

Split a part over about 40 pins into boxes, one per functional group the datasheet defines, after checking `jitxlib.symbols` for a standard symbol. Each amplifier of a multi-amplifier part is an `OpAmpUnitSymbol` and the supplies go on their own `BoxSymbol` (the `OpAmpUnitSymbol` docstring has the mapping); one amplifier takes `OpAmpSymbol`. A large part partitions along the source's own grouping (IO bank, power domain), every port in exactly one box, asserted in a test; the per-box cap and the rules are in the module docstring of `jitxexamples.jumpstart_kits.js1_stackup_components.versal_fpga.symbols` ("Partitioning rules", "Schematic groups"). A port listed twice in one `BoxSymbol` keeps only its last pin, so assert exactly once. Fixed-size slices suit only parts with no functional grouping. In the enclosing circuit, a `SchematicGroup` per box from `extract(part, Symbol)` gives the user a group to place on its own sheet, as `XCVP1002Circuit.symbol_groups` in that kit's `circuit` module does; rails cross boxes through net labels.

## BGAs

- `ball_diameter` is the copper land from the manual's PCB design-rule table, not the ball on the mechanical drawing; the ball builds a silently oversized pattern. The `BGA` docstring has the chain, pad access and row alphabet. Comment which document each number came from.
- A vendor-defined NC ball gets a port and symbol pin, marked `no_connect()` in the component's `__init__`, so unconnected-port checks can tell it from a forgotten wire. A depopulated position has no port; `GridPlanner.is_active` returns `False` for it.
- Off-grid balls (a second pitch, offset groups, a staggered grid) take an override of `_generate_layout`, per the `BGADecorated` docstring; `HexBGA` in `jitxexamples.demos.si_bga_optimization.generic_bga` is a worked one.
- Tests reach pads by position through a public adapter, as `VersalBGA.get_pad` does: zero-indexed `(row, column)`, stated in its docstring.

## Testing and build

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

`jitx find` imports modules by top-level name, so a harness only inside `tests/` is not found (`designs: []`, a `ModuleNotFoundError` per file). Take the build target verbatim from `jitx find`.

Tests constructing a component subclass `jitx.test.TestCase`; its docstring covers `SubstrateContext` and module-scope classes. A `SubstrateContext` stays active for the rest of the `TestCase` class, so a test leaning on an earlier test's context passes in suite order and fails alone. Count pads per package variant with `sum(1 for _ in visit(lp, Pad))`, never `lp.p` (a BGA has none), against pins plus thermal pads. Pin a known-bad library entry as still wrong, so the override goes when the table is fixed. A generated part adds [pin-file-generation.md](pin-file-generation.md#testing-a-generated-component). A skipped test is green: confirm the ones you rely on ran. "Can't run here" is a claim to test: `jitx build --dry` needs no runtime, and a missing `pyproject.toml` is four lines.

Build in the available virtual environment (none: stop and ask) with `jitx build <target>`, expecting `status: ok`, one build per design at a time ([Build Safety](../../jitx/SKILL.md#build-safety--dont-parallelize-same-design-work)).

Report with the task acceptance block (`jitx/references/completion-blocks.md`) carrying the SKILL.md component check under `Checks run`, plus the `jitx/references/domains/component-modeling.md` checklist as N/N. `Footprint source` names the generator, or the KiCad import and why. Each check appears once, in the `Checks` row.
