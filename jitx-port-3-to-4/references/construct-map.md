# JITX 3.x (LB Stanza) -> JITX 4.x (Python) Construct Map

A lookup table for porting designs. Stanza-side citations are example
filenames where each construct appears (drawn from real JITX 3.x designs
and the `lbstanza` by-example reference); Python-side citations are line
ranges in the Python 4.x reference (`jitx-4-1-python-llms.txt`). For Stanza
syntax depth see the `lbstanza` skill; for Python API depth see the
`jitx-skills:jitx-*` skills (especially `jitx-component-modeler`,
`jitx-circuit-builder`, `jitx-substrate-modeler`,
`jitx-interconnect-constraints`, `jitx-pin-assignment`).

## 1. File / package layout

| Stanza 3.x | Python 4.x | Source citation |
|---|---|---|
| `#use-added-syntax(jitx)` pragma at top of file | (none — Python parser is standard) | Stanza: `tests/test-require.stanza:1`; LB Stanza preamble pragma documented in `lbstanza` reference-manual `Package Declarations` |
| `defpackage my-pkg : import jitx` | `from jitx import Component, Port, Circuit, ...` (standard Python imports) | Stanza: LB Stanza `reference-manual.md` lines 87-105 (`Package Declarations`); Python: [L492], [L517], [L530], [L771], [L789], [L847] |
| `import jitx/commands` (commands like `make-default-board`, `view-board`, `export-cad`, `assign-pins`) | replaced by `Design`/`Board`/`Substrate` class composition + `python -m jitx build` CLI | Stanza: `jitpcb-by-example/Examples/first-design/first-design.stanza:1-21`; Python: [L811-872], [L823-840] |
| `stanza.proj` build target ties `.stanza` files into a project | `pyproject.toml` `[project]` section; deps under `[project].dependencies = ["jitx>=4.0", ...]` (4.x ships the `jitx` package) | Stanza: LB Stanza `build-system.md`; Python: [L151-194] |
| Project layout: `src/<pkg>/*.stanza` + `stanza.proj` | Project layout: `<pkg>/main.py` + `<pkg>/pyproject.toml` (designs go in `designs/<design-name>/design-info`) | Python: [L151-179] |

## 2. Top-level design entry

| Stanza 3.x | Python 4.x | Source citation |
|---|---|---|
| `set-current-design("name")` then `make-default-board(my-module, 4, Rectangle(25.0,10.0))` then `view-board()` / `export-cad()` at top-level | `class MyDesign(Design):` with `board=`, `substrate=`, `circuit=` attributes; built from CLI rather than top-level statements | Stanza: `jitpcb-by-example/Examples/first-design/first-design.stanza:13-21`; Python: [L811-817], [L867-872] |
| `board-shape = RoundedRectangle(W, H, r)` on a Stanza board | `self.board.shape = rectangle(W, H, radius=r)` from `jitx.shapes.composites`. See `jitx-skills:jitx-circuit-builder` §"Board outline / shapes" for details (no `RoundedRectangle` class; `rectangle()` is a function). | Python: `py-jitx/src/jitx/board.py`, `py-jitx/src/jitx/shapes/composites.py` |
| `pcb-board ... outline = ArcPolygon([...])` (Stanza arbitrary curved outline) | `from jitx.shapes.primitive import ArcPolygon` — see `jitx-skills:jitx-circuit-builder` §"Board outline / shapes" for the decision tree (`ArcPolygon` only when `rectangle(...)` can't express the shape) and `side-by-side/03-design-entry.md` §"Board shapes beyond rectangles" for a worked recipe. | Python: `py-jitx/src/jitx/shapes/primitive.py:36-228` |
| `set-main-module(design)` (alternate form: marks the module as the design entry) | `Design` subclass discovered automatically by `python -m jitx find` | Stanza: `jitpcb-by-example/Examples/analyze/analyze.stanza:21`; Python: [L823-832] |
| `jstanza` build via `stanza.proj` target | `python -m jitx build --port <PORT> motor_controller.main.StepperMotorController` | Python: [L834-840] |
| `nightly_design_tests/config/designs.yaml` row: `targets: [{project_dir: "demo", stanza_file: "main.stanza", design_name: "DesignCon-demo"}]` | `jitx-test/.github/workflows/integration-testing.yml` runs `python -m jitx build-all` over a checked-out repo (entry resolved via `Design` subclass in `main.py`); a comparable matrix row is `{example-repo-name: essentials-examples, example-repo-url: "https://github.com/JITx-Inc/py-essentials-examples.git"}` | Stanza: `nightly_design_tests/config/designs.yaml:35-48`; Python: `jitx-test/.github/workflows/integration-testing.yml:100-119`, `jitx-test/scripts/jitx-build-design.bash:81` |

## 3. Modules / circuits

| Stanza 3.x | Python 4.x | Source citation |
|---|---|---|
| `pcb-module my-mod : ...` | `class MyMod(Circuit): ...` | Stanza: `tests/test-require.stanza:13`; Python: [L343-349], [L602-615], [L856-865] |
| `inst r : chip-resistor(1.0e3)` (instantiate inside module) | `r = ChipResistor(1.0e3)` declarative class attribute, or `self.r = ChipResistor(1.0e3)` in `__init__` | Stanza: `jitpcb-by-example/Examples/first-design/first-design.stanza:10`; Python: [L343-353], [L394-400] |
| `inst many-rs : chip-resistor(100.0e3)[30]` (instance array) | `timers = [NE555() for _ in range(30)]` (list/dict/tuple OK; generator/set NOT) | Stanza: `jitpcb-by-example/Examples/first-design/first-design.stanza:11`; Python: [L367-382] |
| `port p : pin[2]` (port array on module) | `p = [Port(), Port()]` or `PortArray(...)`. For non-contiguous indices (depopulated MCU GPIO), use `dict[int, Port]` — see `jitx-skills:jitx-pin-assignment` §"Port arrays at the circuit boundary" or `jitx-skills:jitx-circuit-builder` §"Port arrays" for the rule and rationale. | Stanza: `tests/test-require.stanza:14`; Python: [L1361-1372], [L10887] |
| Implicit module-as-schematic-sheet | implicit `SchematicGroup` per `Circuit` (dot-notation labels e.g. `audio.amp.preamp`) | Python: [L441-449] |
| Parametric `pcb-module my-mod (flag:True\|False) : if flag : ... else : ...` (one definition, two instantiations) | **No single direct mapping** — choose by what the parameter controls. See `side-by-side/02-circuit.md` "Parametric modules". Summary: (a) param affects wiring only → single `Circuit` with `__init__(*, variant=…)` and conditional body; (b) param changes port interface → two separate `Circuit` subclasses (Python class bodies cannot branch port declarations on instance kwargs); (c) variants share most wiring → `@classmethod` factory returning a configured instance. | (this skill, side-by-side/02-circuit.md) |

## 4. Components

| Stanza 3.x | Python 4.x | Source citation |
|---|---|---|
| `pcb-component cpu : ...` | `class CPU(Component): ...` | Stanza: `jitpcb/src/jitpcb/physical-design/pin-solver/tests/nested-no-restrict.stanza:59`; Python: [L329-333], [L494-498], [L8558] |
| `pcb-bundle dual : pin x; pin y` (logical signal grouping) | `class Dual(Port): x=Port(); y=Port()` (any `Port` subclass with sub-`Port` attrs is a bundle) | Stanza: `jitpcb/src/jitpcb/physical-design/pin-solver/tests/nested-no-restrict.stanza:51-53`; Python: [L503-509], [L1340-1348] |
| `pcb-pad my-pad : ...` (copper pad shape) | `class MyPad(Pad): shape = Circle(diameter=1.0)` | Stanza: `jitpcb/src/jitpcb/parts/legacy-ocdb-landpatterns.stanza:2563`, `jitpcb/src/jitpcb/esir/pose.stanza:116`; Python: [L529-538], [L10427] |
| `pcb-landpattern QFP-100 : ...` | `class MyLandpattern(Landpattern): p1 = MyPad().at(-1.27, 0); p2 = ...` | Stanza: `jitpcb/src/jitpcb/physical-design/pin-solver/tests/nested-no-restrict.stanza:20`; Python: [L530-538], [L10378] |
| Stanza pad placement `at loc(x, y, θ)` (rotation as third positional arg) | `.at(x, y, rotate=θ)` — see `jitx-skills:jitx-component-modeler` §"Pad rotation" (keyword-only). | Python: `py-jitx/src/jitx/placement.py:104-106` |
| Stanza SOT-23 footprint (3/5/6 lead) | `from jitxlib.landpatterns.generators.sot import SOT23_3, SOT23_5, SOT23_6` — see `jitx-skills:jitx-component-modeler` for the full chain (`lead_profile(...).package_body(...)`). | Python: `py-jitx-stdlib/src/jitxlib/landpatterns/generators/sot.py:162-225` |
| Stanza SOT-89-3 / SOT-89-5 / SOT-223 (asymmetric, wide thermal-tab middle pad) | **No `SOT89` / `SOT223` generator.** See `jitx-skills:jitx-component-modeler` §"Select Package Generator" for the custom-landpattern path. Do **not** substitute `SOT23_3` — pad 2 is a wide thermal tab. | Python: `py-jitx-stdlib/src/jitxlib/landpatterns/generators/sot.py` |
| Stanza body-dimension declarations on a `pcb-landpattern` (`body-width`, `body-length`, `body-height`) | `RectanglePackage(width=Toleranced.min_max(...), length=Toleranced.min_max(...), height=Toleranced.min_max(...))`. See `jitx-skills:jitx-component-modeler` Dimension Mapping for the datasheet-symbol → JITX-parameter mapping. `height` is required-keyword-only. | Python: `jitxlib.landpatterns.package.RectanglePackage` |
| `pcb-symbol single-shape : ...` | `class MySymbol(Symbol): vcc_pin = Pin.up((0,2), length=1)` | Stanza: `jitpcb/src/jitpcb/harnesses/schematic-symbol-shape-design-harness.stanza:49`; Python: [L519-523], [L12696] (`class Symbol`), [L12755] (`class Pin`) |
| `pin-properties : [pin:Ref \| pads:Ref \| side:Dir] [p[0] \| p[1] \| Left] ...` | `mapping = PadMapping({GND: [landpattern.p[9], landpattern.thermal_pad], VCC: landpattern.p[1]})`. **Multi-pad-per-port**: when a Stanza component shares one port across multiple physical pads (common on power-stage ICs), list every pad in the PadMapping value: `self.PVDD[0]: [lp.p[3], lp.p[4]]`, `self.PGND: [lp.p[25], lp.p[26], lp.p[31], lp.p[32]]`, `self.EP: [lp.thermal_pads[0]]`. Omitted pads stay unconnected at the landpattern level. | Stanza: `jitpcb/src/jitpcb/physical-design/pin-solver/tests/nested-no-restrict.stanza:85-90`; Python: [L732-743], [L10457] (`class PadMapping`) |
| (Stanza pin-properties also handles symbol-pin mapping per row) | `SymbolMapping(entries)` for explicit Port -> Symbol Pin mapping | Python: [L12865] (`class SymbolMapping`) |
| QFN / SON / DFN exposed (thermal) pad in `PadMapping` | `self.EP: [lp.thermal_pads[0]]` — see `jitx-skills:jitx-component-modeler` for the full pattern. **Stanza-pin-number trap (case A — thermal-pad-as-extra-pin)**: Stanza `pin-properties` tables often list the thermal pad as one past the last lead (e.g. pin 33 on a 32-lead QFN). In 4.x there is no `lp.p[N+1]` — that pin **is** `lp.thermal_pads[0]`. A literal `lp.p[57]` raises `KeyError: 57`. **Stanza-pin-number trap (case B — N+1 lead distinct from thermal pad)**: when Stanza pin-properties lists a `[NAME \| N+1 \| ...]` row separate from the thermal pad and N+1 is not exposed by the 4.x generator (which only exposes leads 1..N + `lp.thermal_pads[0]`), map the port to `lp.thermal_pads[0]` alone. The Stanza source is almost always referring to the same physical exposed pad — the duplicate row is a quirk of how Stanza-side pin-properties account for the EP pad. Confirm against the package mechanical drawing: a 56-lead QFN has 56 leads, not 57. Example: ESP32-S3 FN8 lists `[GND \| 57 \| Left \| Power]` plus a thermal pad declaration; map the `GND` Port to `lp.thermal_pads[0]` and **omit** the phantom pad-57 row. | Python: `py-jitx-stdlib/src/jitxlib/landpatterns/generators/qfn.py:78` |
| QFN landpattern lead profile (`make-qfn-landpattern` in Stanza) | `QFNLead(length, width)` from `jitxlib.landpatterns.generators.qfn`, **not** base `SMDLead` — see `jitx-skills:jitx-component-modeler` Landpattern Constructor Signatures. | Python: `py-jitx-stdlib/src/jitxlib/landpatterns/generators/qfn.py:102` |
| Stanza `make-bga-landpattern(rows, cols, pitch, ball_dia, body_w, body_l, depop)` | `BGA` from `jitxlib.landpatterns.generators.bga` — see `jitx-skills:jitx-component-modeler` Landpattern Constructor Signatures + `references/package-examples.md` for the full chain (`BGA(num_rows=..., num_cols=...).grid_planner(...).pad_config(SMDPadConfig()).package_body(...)`). Pad addressing is AlphaDict (`lp.A[1]`, `lp.B[2]`), maps almost 1:1 from a Stanza `B[2]` ref. | Python: `py-jitx-stdlib/src/jitxlib/landpatterns/generators/bga.py:16-74` |

## 5. Nets and connectivity

| Stanza 3.x | Python 4.x | Source citation |
|---|---|---|
| `net (vdd op-amp.v+ decoupling-cap.p[1])` | `self.vdd = self.op_amp.vp + self.decoupling_cap.p[1]` (the `+` operator returns a `Net`) | Stanza: `jitpcb-by-example/Examples/learn-jitx-main.stanza:185`; Python: [L348-353], [L629-633], [L11101] (`class Net`) |
| `net VDD (a, b, c)` (named net) | `self.VDD = Net([a, b, c], name="VDD")` — see `jitx-skills:jitx-circuit-builder` §"Net Definitions" for the rules (`Net()` takes a single iterable not varargs; name nets only at the top level of the hierarchy, leave nested rail nets anonymous). | Python: `py-jitx/src/jitx/net.py:635, 662-668` |
| Same-name `net` statements merge (implicit) | `+=` on a `Net` extends it: `GND += self.ssvia.COMMON`. Note that `Port += Port` is forbidden — see `jitx-skills:jitx-circuit-builder` §"Port immutability". Create a `Net` first, then `+=` into it. | Python: [L1230-1233] |
| `copper-pour(LayerIndex(i), isolate=0.1, rank=1) = shape` (Stanza copper-pour binding) | `self.GND += Pour(shape, layer=i, isolate=0.1, rank=1)`. Signature: `Pour(shape, layer: int, *, isolate=0.0, rank=0, orphans=True)`. **Import from `jitx` or `jitx.copper`** — see `jitx-skills:jitx-circuit-builder` §"Pour import path" (not in `jitx.feature`). `layer` is a plain `int` (no `LayerIndex` wrapper). | Python: `py-jitx/src/jitx/copper.py:45-79` |

## 6. Topology

| Stanza 3.x | Python 4.x | Source citation |
|---|---|---|
| `topology-segment(A.p[1], B.p[1])` (ordered topology edge) | `topo = self.A.p[1] >> self.B.p[1]` (the `>>` operator returns a `TopologyNet`) | Stanza: `jitpcb-by-example/src/essentials/examples/stubs_example.stanza:54`; Python: [L644-649], [L11187] (`class TopologyNet`) |
| `topo-net(...)` JSL helper that combines `net` + `topology-segment` | `>>` operator (single op produces both connectivity and ordering) | Stanza: `jitpcb-by-example/src/essentials/usage_patterns.md:9`; Python: [L644-649] |
| Pass-through component bridging two topo segments (resistor between TX and RX) | `BridgingPinModel(portA, portB, delay=..., loss=...)` collapses disjoint topologies | Python: [L3317-3343], [L11771] (`class BridgingPinModel`) |
| Endpoint package-level pin model on a `pcb-component` | `TerminatingPinModel(port, delay=..., loss=...)` declared on the `Component` subclass | Python: [L3351-3377], [L11800] (`class TerminatingPinModel`) |
| `Topology(begin, end)` endpoint pair object | `Topology(begin, end)` and `Constrain(Topology(...))` | Python: [L11201], [L11877] (`class Constrain`) |

## 7. Provide / require

| Stanza 3.x | Python 4.x | Source citation |
|---|---|---|
| `supports gpio : gpio.gpio => p[0]` (declares a provider mapping inside `pcb-module`/`pcb-component`) | `@provide(GPIO)` decorator on a method returning a list of `{bundle_port: pin}` mappings; or `@provide.all_of(...)` | Stanza: `tests/test-require.stanza:15-18`; Python: [L1395-1406], [L1482-1495] |
| `supports gpio : ...` repeated N times to expose N options | `@provide.all_of(GPIO)` returning a list comprehension of mappings (one offer per mapping) | Stanza: `tests/test-require.stanza:15-18`; Python: [L1424-1437] |
| (no direct equivalent — `supports` is "all of" by default) | `@provide.one_of(Bundle)` — exactly one option chosen from N | Python: [L1462-1466], [L1521], [L10910] |
| (no direct equivalent) | `@provide.subset_of(Bundle, M)` — pick M from N | Python: [L1462-1478], [L10972] |
| `require mygpio:gpio from self` | `gpio = self.require(GPIO)` (returns a port that gets pin-assigned by the solver) | Stanza: `tests/test-require.stanza:19`; Python: [L725-727], [L1547-1548], [L17744] |
| `require mygpio:gpio from m1` (require from a child instance) | `i2c = self.mcu.require(I2C)` | Stanza: `tests/test-require.stanza:27`; Python: [L725-727] |
| (programmatic provide construction not available in 3.x except via `for` loops over `supports`) | `Provide(Bundle, mapping=...)` constructed inside `__init__` | Python: [L10979] (`class Provide`), [L11020-11044] |

## 8. Stackup / substrate

| Stanza 3.x | Python 4.x | Source citation |
|---|---|---|
| `pcb-material soldermask : type = Dielectric; dielectric-coefficient = 3.2` | `class LPIMask(Dielectric): thickness = 0.1` (material properties live on the layer subclass) | Stanza: `jitpcb-by-example/src/reference/statements/stackupstmt/heading.md:34-45`; Python: [L951-958], [L12454] (`class Dielectric`), [L12486] (`class Conductor`) |
| `pcb-material copper : type = Conductor` | `class Cu1oz(Conductor): thickness = 0.035` | Stanza: same; Python: [L957-958] |
| `pcb-stackup std-stackup : stack(0.019, soldermask) stack(cu-1oz, copper, "GND1") ...` | `class Basic_Two_Layer(Stackup): top_solder_mask = LPIMask(); top_copper = Cu1oz(); core = FR4Core(); ...` (ordered class attrs = ordered layers) | Stanza: `jitpcb-by-example/src/reference/statements/stackupstmt/heading.md:47-67`; Python: [L949-967], [L12366] (`class Stackup`) |
| (manual symmetric stackup by repeating layers) | `class Symmetric_Four_Layer(Symmetric): solder_mask = ...; ext_copper = ...; pp = ...; inner_copper = ...; core = ...` (top-half declared, mirrored automatically) | Python: [L1011-1021] |
| `pcb-via default-th : ...` (top-level via definition) | `class THVia(Via): start_layer=0; stop_layer=3; type=ViaType.MechanicalDrill; ...` — see `jitx-skills:jitx-substrate-modeler` §"Via Types" for the rules (declared as a **nested class** inside the `Substrate`; attribute names are `start_layer`/`stop_layer`, not `start`/`stop`; integer layer indices preferred). | Stanza: `jitpcb-by-example/src/reference/statements/viastmt/heading.md:62`; Python: [L1031-1106] |
| (via referenced by name in routing/code) | `viaType = SampleSubstrate.THVia; self.via = viaType().at(2.0, 3.0)` | Python: [L1110-1121] |
| (3.x has no first-class substrate object — stackup + fab rules are loose top-level definitions) | `class SampleSubstrate(Substrate): stackup = SampleTwoLayerStackup(); constraints = SampleFabConstraints(); ...` ties stackup + constraints + via defs + routing structures together | Python: [L897-921], [L12512] (`class Substrate`), [L12608] (`class FabricationConstraints`) |

## 9. Constraints

| Stanza 3.x | Python 4.x | Source citation |
|---|---|---|
| `constrain-topology(...)` JSL helper plus routing-structure application (**single-ended**) | `Constrain(Topology(self.A.p, self.B.p)).structure(rs)` — see `jitx-skills:jitx-interconnect-constraints` for the full pattern. | Stanza: `jitpcb-by-example/src/essentials/usage_patterns.md:161`; Python: `py-jitx/src/jitx/si.py:325-357` |
| `structure(path, differential)` / `pcb-differential-routing-structure` applied to a pair of nets (**differential**) | `ConstrainDiffPair(Topology(dp_begin, dp_end)).structure(drs)` — see `jitx-skills:jitx-interconnect-constraints` §"Common Mistakes" (do **not** use two separate `Constrain` calls; that silently disables coupling). | Python: `py-jitx/src/jitx/si.py:433-471` |
| (Stanza topology timing constraint via JSL/`si` helpers) | `Constrain(Topology(elem[0], elem[1])).timing(phase_delay)` where `phase_delay = Toleranced(1e-9, 10e-12)` | Python: [L3833-3838], [L11969] (`class TimingConstraint`) |
| (Stanza diff-pair skew handled via JSL `diff-pair-constraint`) | `DiffPairConstraint(skew=Toleranced(0,1e-12), loss=12.0, structure=diff_100); cst.constrain(B1.MCU.LVDS, B2.MCU.LVDS)` | Python: [L3577-3585], [L11735] (`class DiffPairConstraint`), [L11948] (`class ConstrainDiffPair`) |
| (no first-class equivalent — reference plane assignment is implicit/manual) | `ReferencePlanes({0: GND, 1: GND})` declared as class attr, or `with ReferencePlanes(self.GND1):` context manager inside `__init__` | Python: [L12276-12306] |
| (3.x length matching) | `TimingDifferenceConstraint(min_delta, max_delta)` (skew between two topologies) | Python: [L12007-12024] |
| `TimingDifferenceConstraint(lo, hi)` on a diff pair (intra-pair P/N skew budget) | `.timing_difference(lo, hi)` chained on `ConstrainDiffPair`. Also accepts a `Toleranced` window: `.timing_difference(Toleranced.min_max(-1e-12, 1e-12))`. **Only available on `ConstrainDiffPair` and `ConstrainReferenceDifference`** (`BaseConstrainPairwise`), not on plain `Constrain`. | Python: `py-jitx/src/jitx/si.py:381-400` (`def timing_difference`), `py-jitx/src/jitx/si.py:503-513` (`class TimingDifferenceConstraint`) |
| `TimingDifferenceConstraint(lo, hi)` across a reference signal (bus length-matching) | `.timing_difference(lo, hi)` chained on `ConstrainReferenceDifference(guide, [topos...])`. The guide topology is the matched-to reference; each other topology is compared pairwise against it. | Python: `py-jitx/src/jitx/si.py:403-430` (`class ConstrainReferenceDifference`) |
| (3.x insertion-loss specified by routing structure layer attrs only) | `InsertionLossConstraint(min_loss, max_loss)` first-class | Python: [L11988-12005] |
| (3.x routing structures defined via JSL `pcb-routing-structure`) | `RoutingStructure(impedance=50*ohm, layers=symmetric_routing_layers({0: RoutingStructure.Layer(trace_width=0.12, clearance=0.2, velocity=vel, insertion_loss=0.018)}))` declared on `Substrate` | Python: [L907-916], [L3744-3766], [L12026-12056] |
| (3.x differential routing structure via JSL) | `DifferentialRoutingStructure(impedance=100*ohm, layers=..., uncoupled_region=...)` | Python: [L912-916], [L3779-3811] |
| (3.x neckdown by parameter) | `RoutingStructure.NeckDown(trace_width=0.09, clearance=0.075)` nested in a `Layer` | Python: [L3759-3765], [L3788-3793] |
| Stanza tags / `design-rule`-style fab constraints | `Tag` subclasses + `design_constraint(condition, effect)` returning `UnaryDesignConstraint` / `BinaryDesignConstraint` (e.g. `trace_width`, `clearance`, `thermal_relief`, `stitch_via`, `fence_via`) | Python: [L2561-2756], [L8970] (`class Tag`), [L9237] (`class DesignConstraint`) |
| `add-thermal-vias(net, shape)` (places via grid under a thermal pad) | **No direct function equivalent.** Use `design_constraint(net_tag).stitch_via(...)` — see `jitx-skills:jitx-substrate-modeler` §"Thermal vias via design_constraint" for the full pattern and prerequisites (tag the net, ensure a `Pour` exists). | Python: `jitx.constraints.design_constraint`, `SquareViaStitchGrid` |

## 10. Build invocation (CI matrix row shape)

A concrete row from each system (citations above already include path + line). Stanza side is keyed on `stanza_file` + `design_name`; Python side is keyed on a repo URL — the design module path comes from `python -m jitx find` discovering `Design` subclasses in `main.py`.

| Stanza 3.x (`nightly_design_tests/config/designs.yaml`) | Python 4.x (`jitx-test/.github/workflows/integration-testing.yml`) | Source citation |
|---|---|---|
| `- id: designcon2025` <br> `  repo: "git@github.com:JITx-Inc/designcon2025.git"` <br> `  targets:` <br> `    - project_dir: "demo"` <br> `      stanza_file: "main.stanza"` <br> `      design_name: "DesignCon-demo"` | `- example-repo-name: essentials-examples` <br> `  use-prerelease: true` <br> `  example-repo-url: "https://github.com/JITx-Inc/py-essentials-examples.git"` <br> `  jitx-env-var: JITX_ENV_PROD` <br> (build invoked via `python -m jitx build-all` against the cloned repo) | Stanza: `nightly_design_tests/config/designs.yaml:35-48`; Python: `jitx-test/.github/workflows/integration-testing.yml:100-105`, `jitx-test/scripts/jitx-build-design.bash:81` |

### Transitional shape — `nightly_design_tests` row for a Python-ported design

While the harness in `nightly_design_tests` still drives Stanza builds, Python-ported designs share the same YAML schema with a `python_module` field replacing `stanza_file` + `design_name`. The corresponding row for `pd_audio_py4` (the Python port of `pd_audio`) is:

```yaml
- id: pd_audio_py4
  repo: "git@github.com:JITx-Inc/PD-audio.git"
  branch: jitx4opus2
  skip: true                         # current Stanza-only harness can't build Python designs yet
  skip_reason: "JITX 4.x Python port — needs 4.x-capable harness"
  exportable: false
  timeout_build: 1200
  targets:
    - project_dir: "."
      python_module: "pd_audio.main.PdAudioDesign"
  checks:
    pcb: [pour_rank]
    bom: [bom_validity]
    odb: [upload_odb, check_layers]
```

The `python_module` value is a dotted path: `<pyproject [project].name>.<module>.<Design subclass>`. All three components must match — the package name in `pyproject.toml`, the actual `.py` file inside the package, and the `class XDesign(Design)` declaration that file exports. A mismatch produces `python -m jitx build` "no design found", not a Python import error.

## 11–15. Bundles, parts, substrate, helpers — see target skills

The catalog content that previously lived here (bundle field names, DNP
patterns, MPN-lookup replacement, dielectric codes, JLCPCB predefined
substrates, routing structures, missing Stanza helpers, strap-helper
expansion) is now owned by the domain skills. For a port, the relevant
cross-references are:

| Topic | Skill | Section |
|---|---|---|
| Bundle field names (`Power.Vp`/`Vn`, `DiffPair.p`/`n`, `I2S.sck`/`ws`/`sd`) | `jitx-skills:jitx-pin-assignment` | §"Built-in Bundles and Their Sub-Ports" |
| Missing-from-jitxlib bundles (`I2SMCK`, full-duplex `I2S`, bare `OctalSPI`) | `jitx-skills:jitx-pin-assignment` | §"Bundles missing from jitxlib — define locally" |
| Protocol bundles at hierarchy boundaries (use plain `Port()`) | `jitx-skills:jitx-pin-assignment` | §"Protocol bundles at hierarchy boundaries" |
| DNP patterns (`NonPopulatedComponent`, `in_bom = False; soldered = False`) | `jitx-skills:jitx-circuit-builder` | §"DNP / do-not-populate"; `jitx-skills:jitx-component-modeler` §"Marking a Component as Do-Not-Populate" |
| `database-part(...)` replacement — MPN kwargs on `Resistor`/`Capacitor`/`Inductor`; custom `Component` for non-passives; OCDB has no Python equivalent | `jitx-skills:jitx-component-modeler` | §"Querying a passive by MPN" |
| Dielectric temperature codes (`C0G`/`NP0`/`X7R`/`X5R`/`X8R`/`Y5V`) | `jitx-skills:jitx-component-modeler` | §"Capacitor dielectric temperature codes" |
| Closest E-series snap (no `closest-std-val(...)` helper) | `jitx-skills:jitx-circuit-builder` | §"Snap computed values to a standard E-series" |
| Strap-helper expansion (`bypass-cap-strap`/`cap-strap`/`res-strap` inline; project-local helper factory) | `jitx-skills:jitx-circuit-builder` | §"Strap-helper expansion" |
| Polymer/electrolytic cap crash (`C ≳ 100µF` + `V ≥ 25V`) | `jitx-skills:jitx-circuit-builder` | §"Relaxing query defaults" |
| Mounting holes — no `jitxlib.mechanical` | `jitx-skills:jitx-circuit-builder` | §"Mounting holes — no jitxlib helper" |
| JLCPCB predefined substrates (`JLC04161H_1080`, `_7628`, `JLC06161H_7628`); no 2-layer class | `jitx-skills:jitx-substrate-modeler` | §"Predefined Substrates" |
| Routing structures (`RoutingStructure`, `DifferentialRoutingStructure`, `symmetric_routing_layers`) — class names not `SingleEnded`/`Differential` | `jitx-skills:jitx-substrate-modeler` | §"Routing Structures" |
| Thermal vias via `design_constraint(...).stitch_via(...)` (no `add-thermal-vias`) | `jitx-skills:jitx-substrate-modeler` | §"Thermal vias via design_constraint" |
| Stanza helpers without a 4.x equivalent (`add-mounting-holes`, `add-open-drain-pullups`, `add-xtal-caps`, `setup-design`, `set-paper`, `set-export-backend`, `view-*`) | `jitx-skills:jitx/SKILL.md` | §"Stanza helpers without a 4.x equivalent" |
| Symbol pin direction methods (`Pin.up()`/`.down()`/`.right()`/`.left()`) | `jitx-skills:jitx-component-modeler` | §"Symbol pin direction" |

The construct map keeps only the **mapping shape** (Stanza side ↔ Python
side). For *how* to use the Python target, follow the cross-refs above.

### Port-access conventions on parts-DB-resolved components

Port-access depends on **how the part was sourced**, not on what it
is. Three conventions exist; mixing them in the same Circuit is
fine but you have to pick the right one per source:

| Component source | Port access | Example |
|---|---|---|
| `Resistor(resistance=…)` / `Capacitor(capacitance=…)` / `Inductor(inductance=…)` from `jitxlib.parts` | `.p1`, `.p2` | `self.c.p1 + self.ic.VCC` |
| `Part(mpn="…")` for a generic SMD package (speaker terminal, pushbutton, generic 2-pin) | `.p[1]`, `.p[2]`, … (port array, **1-indexed**) | `self.spk.p[1] + self.amp_out` |
| `Part(mpn="…")` whose pin-properties names pads (connectors, ICs, encoders, crystals) | flat attribute names — `.SDA`, `.VBUS0`, `.GND0`, etc. | `self.usbc.VBUS0 + self.usbc.VBUS1 + self.P5V0` |

Caveats:

- `Part(mpn="…").p1` raises `AttributeError: 'Part' object has no
  attribute 'p1'` — use `.p[1]`.
- The structural-bundle types (`USB_C_Connector`, `AudioJack`, etc.)
  are for **user-defined** `Component` classes that *choose* to expose
  a bundle interface. They are NOT what parts-DB lookups return.
- To bridge a parts-DB connector to a structural bundle, wire per-pad
  (e.g. for USB-2 data: `self.usbc.DN1 + self.usbc.DN2 + my_usb2.data.n`).

See `jitx-skills:jitx-component-modeler` §"Port access on parts-DB-
resolved components" for the full pattern.

## Notes / gaps

- The Stanza-side rows above point to real constructs from the JITX 3.x by-example reference and similar Stanza JITX example designs. Where the Stanza `lbstanza` reference covers only generic language syntax (not the JITX PCB DSL), citations target the JITX-specific example files (`tests/`, `jitpcb/src/`, `jitpcb-by-example/`) instead.
- Python-side line numbers refer to the JITX 4.x Python LLM reference (`jitx-4-1-python-llms.txt`); the `jitx` skill bundles this file for lookups. (The reference filename retains its original `4-1` tag from when it was extracted; the content covers the 4.x Python line.)
- For deeper Python API surfaces (Tag-based design constraints, BOM queries, schematic symbol generation, via structures with ground cages), see the corresponding `jitx-skills:jitx-*` skills rather than expanding these tables.
