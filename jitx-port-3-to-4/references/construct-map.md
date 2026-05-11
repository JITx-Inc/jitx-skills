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
| `set-main-module(design)` (alternate form: marks the module as the design entry) | `Design` subclass discovered automatically by `python -m jitx find` | Stanza: `jitpcb-by-example/Examples/analyze/analyze.stanza:21`; Python: [L823-832] |
| `jstanza` build via `stanza.proj` target | `python -m jitx build --port <PORT> motor_controller.main.StepperMotorController` | Python: [L834-840] |
| `nightly_design_tests/config/designs.yaml` row: `targets: [{project_dir: "demo", stanza_file: "main.stanza", design_name: "DesignCon-demo"}]` | `jitx-test/.github/workflows/integration-testing.yml` runs `python -m jitx build-all` over a checked-out repo (entry resolved via `Design` subclass in `main.py`); a comparable matrix row is `{example-repo-name: essentials-examples, example-repo-url: "https://github.com/JITx-Inc/py-essentials-examples.git"}` | Stanza: `nightly_design_tests/config/designs.yaml:35-48`; Python: `jitx-test/.github/workflows/integration-testing.yml:100-119`, `jitx-test/scripts/jitx-build-design.bash:81` |

## 3. Modules / circuits

| Stanza 3.x | Python 4.x | Source citation |
|---|---|---|
| `pcb-module my-mod : ...` | `class MyMod(Circuit): ...` | Stanza: `tests/test-require.stanza:13`; Python: [L343-349], [L602-615], [L856-865] |
| `inst r : chip-resistor(1.0e3)` (instantiate inside module) | `r = ChipResistor(1.0e3)` declarative class attribute, or `self.r = ChipResistor(1.0e3)` in `__init__` | Stanza: `jitpcb-by-example/Examples/first-design/first-design.stanza:10`; Python: [L343-353], [L394-400] |
| `inst many-rs : chip-resistor(100.0e3)[30]` (instance array) | `timers = [NE555() for _ in range(30)]` (list/dict/tuple OK; generator/set NOT) | Stanza: `jitpcb-by-example/Examples/first-design/first-design.stanza:11`; Python: [L367-382] |
| `port p : pin[2]` (port array on module) | `p = [Port(), Port()]` or `PortArray(...)` | Stanza: `tests/test-require.stanza:14`; Python: [L1361-1372], [L10887] (`class PortArray`) |
| Implicit module-as-schematic-sheet | implicit `SchematicGroup` per `Circuit` (dot-notation labels e.g. `audio.amp.preamp`) | Python: [L441-449] |

## 4. Components

| Stanza 3.x | Python 4.x | Source citation |
|---|---|---|
| `pcb-component cpu : ...` | `class CPU(Component): ...` | Stanza: `jitpcb/src/jitpcb/physical-design/pin-solver/tests/nested-no-restrict.stanza:59`; Python: [L329-333], [L494-498], [L8558] |
| `pcb-bundle dual : pin x; pin y` (logical signal grouping) | `class Dual(Port): x=Port(); y=Port()` (any `Port` subclass with sub-`Port` attrs is a bundle) | Stanza: `jitpcb/src/jitpcb/physical-design/pin-solver/tests/nested-no-restrict.stanza:51-53`; Python: [L503-509], [L1340-1348] |
| `pcb-pad my-pad : ...` (copper pad shape) | `class MyPad(Pad): shape = Circle(diameter=1.0)` | Stanza: `jitpcb/src/jitpcb/parts/legacy-ocdb-landpatterns.stanza:2563`, `jitpcb/src/jitpcb/esir/pose.stanza:116`; Python: [L529-538], [L10427] |
| `pcb-landpattern QFP-100 : ...` | `class MyLandpattern(Landpattern): p1 = MyPad().at(-1.27, 0); p2 = ...` | Stanza: `jitpcb/src/jitpcb/physical-design/pin-solver/tests/nested-no-restrict.stanza:20`; Python: [L530-538], [L10378] |
| `pcb-symbol single-shape : ...` | `class MySymbol(Symbol): vcc_pin = Pin.up((0,2), length=1)` | Stanza: `jitpcb/src/jitpcb/harnesses/schematic-symbol-shape-design-harness.stanza:49`; Python: [L519-523], [L12696] (`class Symbol`), [L12755] (`class Pin`) |
| `pin-properties : [pin:Ref \| pads:Ref \| side:Dir] [p[0] \| p[1] \| Left] ...` | `mapping = PadMapping({GND: [landpattern.p[9], landpattern.thermal_pad], VCC: landpattern.p[1]})` | Stanza: `jitpcb/src/jitpcb/physical-design/pin-solver/tests/nested-no-restrict.stanza:85-90`; Python: [L732-743], [L10457] (`class PadMapping`) |
| (Stanza pin-properties also handles symbol-pin mapping per row) | `SymbolMapping(entries)` for explicit Port -> Symbol Pin mapping | Python: [L12865] (`class SymbolMapping`) |

## 5. Nets and connectivity

| Stanza 3.x | Python 4.x | Source citation |
|---|---|---|
| `net (vdd op-amp.v+ decoupling-cap.p[1])` | `self.vdd = self.op_amp.vp + self.decoupling_cap.p[1]` (the `+` operator returns a `Net`) | Stanza: `jitpcb-by-example/Examples/learn-jitx-main.stanza:185`; Python: [L348-353], [L629-633], [L11101] (`class Net`) |
| `net VDD (a, b, c)` (named net) | `self.VDD = Net((a, b, c), name="VDD")` or build with `+` then assign to attribute (name comes from attribute) | Stanza: `lbstanza` by-example net statement; Python: [L11101] |
| Same-name `net` statements merge (implicit) | `+=` on a `Net` extends it: `GND += self.ssvia.COMMON` | Python: [L1230-1233] |

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
| `pcb-via default-th : ...` (top-level via definition) | `class THVia(Via): start_layer=Side.Top; stop_layer=Side.Bottom; type=ViaType.MechanicalDrill; ...` declared inside the `Substrate` subclass | Stanza: `jitpcb-by-example/src/reference/statements/viastmt/heading.md:62`; Python: [L1031-1106], [L13692] (`class Via`), [L13817] (`class ViaType`) |
| (via referenced by name in routing/code) | `viaType = SampleSubstrate.THVia; self.via = viaType().at(2.0, 3.0)` | Python: [L1110-1121] |
| (3.x has no first-class substrate object — stackup + fab rules are loose top-level definitions) | `class SampleSubstrate(Substrate): stackup = SampleTwoLayerStackup(); constraints = SampleFabConstraints(); ...` ties stackup + constraints + via defs + routing structures together | Python: [L897-921], [L12512] (`class Substrate`), [L12608] (`class FabricationConstraints`) |

## 9. Constraints

| Stanza 3.x | Python 4.x | Source citation |
|---|---|---|
| `constrain-topology(...)` JSL helper plus routing-structure application | `Constrain(Topology(self.A.p, self.B.p)).structure(rs)` — chained call applies routing structure constraint | Stanza: `jitpcb-by-example/src/essentials/usage_patterns.md:161`; Python: [L3463], [L3621], [L11877-11898] |
| (Stanza topology timing constraint via JSL/`si` helpers) | `Constrain(Topology(elem[0], elem[1])).timing(phase_delay)` where `phase_delay = Toleranced(1e-9, 10e-12)` | Python: [L3833-3838], [L11969] (`class TimingConstraint`) |
| (Stanza diff-pair skew handled via JSL `diff-pair-constraint`) | `DiffPairConstraint(skew=Toleranced(0,1e-12), loss=12.0, structure=diff_100); cst.constrain(B1.MCU.LVDS, B2.MCU.LVDS)` | Python: [L3577-3585], [L11735] (`class DiffPairConstraint`), [L11948] (`class ConstrainDiffPair`) |
| (no first-class equivalent — reference plane assignment is implicit/manual) | `ReferencePlanes({0: GND, 1: GND})` declared as class attr, or `with ReferencePlanes(self.GND1):` context manager inside `__init__` | Python: [L12276-12306] |
| (3.x length matching) | `TimingDifferenceConstraint(min_delta, max_delta)` (skew between two topologies) | Python: [L12007-12024] |
| (3.x insertion-loss specified by routing structure layer attrs only) | `InsertionLossConstraint(min_loss, max_loss)` first-class | Python: [L11988-12005] |
| (3.x routing structures defined via JSL `pcb-routing-structure`) | `RoutingStructure(impedance=50*ohm, layers=symmetric_routing_layers({0: RoutingStructure.Layer(trace_width=0.12, clearance=0.2, velocity=vel, insertion_loss=0.018)}))` declared on `Substrate` | Python: [L907-916], [L3744-3766], [L12026-12056] |
| (3.x differential routing structure via JSL) | `DifferentialRoutingStructure(impedance=100*ohm, layers=..., uncoupled_region=...)` | Python: [L912-916], [L3779-3811] |
| (3.x neckdown by parameter) | `RoutingStructure.NeckDown(trace_width=0.09, clearance=0.075)` nested in a `Layer` | Python: [L3759-3765], [L3788-3793] |
| Stanza tags / `design-rule`-style fab constraints | `Tag` subclasses + `design_constraint(condition, effect)` returning `UnaryDesignConstraint` / `BinaryDesignConstraint` (e.g. `trace_width`, `clearance`, `thermal_relief`, `stitch_via`, `fence_via`) | Python: [L2561-2756], [L8970] (`class Tag`), [L9237] (`class DesignConstraint`) |

## 10. Build invocation (CI matrix row shape)

A concrete row from each system (citations above already include path + line). Stanza side is keyed on `stanza_file` + `design_name`; Python side is keyed on a repo URL — the design module path comes from `python -m jitx find` discovering `Design` subclasses in `main.py`.

| Stanza 3.x (`nightly_design_tests/config/designs.yaml`) | Python 4.x (`jitx-test/.github/workflows/integration-testing.yml`) | Source citation |
|---|---|---|
| `- id: designcon2025` <br> `  repo: "git@github.com:JITx-Inc/designcon2025.git"` <br> `  targets:` <br> `    - project_dir: "demo"` <br> `      stanza_file: "main.stanza"` <br> `      design_name: "DesignCon-demo"` | `- example-repo-name: essentials-examples` <br> `  use-prerelease: true` <br> `  example-repo-url: "https://github.com/JITx-Inc/py-essentials-examples.git"` <br> `  jitx-env-var: JITX_ENV_PROD` <br> (build invoked via `python -m jitx build-all` against the cloned repo) | Stanza: `nightly_design_tests/config/designs.yaml:35-48`; Python: `jitx-test/.github/workflows/integration-testing.yml:100-105`, `jitx-test/scripts/jitx-build-design.bash:81` |

## Notes / gaps

- The Stanza-side rows above point to real constructs from the JITX 3.x by-example reference and similar Stanza JITX example designs. Where the Stanza `lbstanza` reference covers only generic language syntax (not the JITX PCB DSL), citations target the JITX-specific example files (`tests/`, `jitpcb/src/`, `jitpcb-by-example/`) instead.
- Python-side line numbers refer to the JITX 4.x Python LLM reference (`jitx-4-1-python-llms.txt`); the `jitx` skill bundles this file for lookups. (The reference filename retains its original `4-1` tag from when it was extracted; the content covers the 4.x Python line.)
- For deeper Python API surfaces (Tag-based design constraints, BOM queries, schematic symbol generation, via structures with ground cages), see the corresponding `jitx-skills:jitx-*` skills rather than expanding these tables.
