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
| `board-shape = RoundedRectangle(W, H, r)` on a Stanza board | `self.board.shape = rectangle(W, H, radius=r)` from `jitx.shapes.composites`. **There is no `RoundedRectangle` class** — `rectangle()` is a function and the `radius=` kwarg rounds corners. `Design.board: Board` and `Board.shape: Shape` (assign the shape attribute; no setter). `SampleDesign` ships a default `SampleBoard(shape=rectangle(50, 50, radius=5))` — override `self.board.shape` or subclass `Board`. | Python: `py-jitx/src/jitx/board.py`, `py-jitx/src/jitx/shapes/composites.py` (`rectangle`) |
| `pcb-board ... outline = ArcPolygon([...])` (Stanza arbitrary curved outline) | `from jitx.shapes.primitive import Arc, ArcPolygon, Polygon, Circle, Rectangle` — module is `jitx.shapes.primitive` (**singular**; `jitx.shapes.primitives` does not exist, nor does `from jitx.shapes import Arc`). Use `ArcPolygon` only when `rectangle(w, h, radius=…)` from `jitx.shapes.composites` can't express the shape (mixed curved/straight outlines, notched boards, etc.). See `side-by-side/03-design-entry.md` §"Board shapes beyond rectangles" for the full decision tree and a worked recipe. | Python: `py-jitx/src/jitx/shapes/primitive.py:36-228` (`Arc`, `ArcPolygon`, `Polygon`, `Circle`) |
| `set-main-module(design)` (alternate form: marks the module as the design entry) | `Design` subclass discovered automatically by `python -m jitx find` | Stanza: `jitpcb-by-example/Examples/analyze/analyze.stanza:21`; Python: [L823-832] |
| `jstanza` build via `stanza.proj` target | `python -m jitx build --port <PORT> motor_controller.main.StepperMotorController` | Python: [L834-840] |
| `nightly_design_tests/config/designs.yaml` row: `targets: [{project_dir: "demo", stanza_file: "main.stanza", design_name: "DesignCon-demo"}]` | `jitx-test/.github/workflows/integration-testing.yml` runs `python -m jitx build-all` over a checked-out repo (entry resolved via `Design` subclass in `main.py`); a comparable matrix row is `{example-repo-name: essentials-examples, example-repo-url: "https://github.com/JITx-Inc/py-essentials-examples.git"}` | Stanza: `nightly_design_tests/config/designs.yaml:35-48`; Python: `jitx-test/.github/workflows/integration-testing.yml:100-119`, `jitx-test/scripts/jitx-build-design.bash:81` |

## 3. Modules / circuits

| Stanza 3.x | Python 4.x | Source citation |
|---|---|---|
| `pcb-module my-mod : ...` | `class MyMod(Circuit): ...` | Stanza: `tests/test-require.stanza:13`; Python: [L343-349], [L602-615], [L856-865] |
| `inst r : chip-resistor(1.0e3)` (instantiate inside module) | `r = ChipResistor(1.0e3)` declarative class attribute, or `self.r = ChipResistor(1.0e3)` in `__init__` | Stanza: `jitpcb-by-example/Examples/first-design/first-design.stanza:10`; Python: [L343-353], [L394-400] |
| `inst many-rs : chip-resistor(100.0e3)[30]` (instance array) | `timers = [NE555() for _ in range(30)]` (list/dict/tuple OK; generator/set NOT) | Stanza: `jitpcb-by-example/Examples/first-design/first-design.stanza:11`; Python: [L367-382] |
| `port p : pin[2]` (port array on module) | `p = [Port(), Port()]` or `PortArray(...)`. **Use a `dict` for non-contiguous indices** (depopulated MCU GPIO arrays, e.g. ESP32-S3 FN8 with GPIOs 0–14, 17–21, 33–38, 45, 46): `GPIO = {i: Port() for i in valid_indices}`. A dense list creates non-physical entries and fails with `port GPIO[15] is not mapped to a symbol pin`. Unpack into a symbol via `*GPIO.values()`. | Stanza: `tests/test-require.stanza:14`; Python: [L1361-1372], [L10887] (`class PortArray`) |
| Implicit module-as-schematic-sheet | implicit `SchematicGroup` per `Circuit` (dot-notation labels e.g. `audio.amp.preamp`) | Python: [L441-449] |
| Parametric `pcb-module my-mod (flag:True\|False) : if flag : ... else : ...` (one definition, two instantiations) | **No single direct mapping** — choose by what the parameter controls. See `side-by-side/02-circuit.md` "Parametric modules". Summary: (a) param affects wiring only → single `Circuit` with `__init__(*, variant=…)` and conditional body; (b) param changes port interface → two separate `Circuit` subclasses (Python class bodies cannot branch port declarations on instance kwargs); (c) variants share most wiring → `@classmethod` factory returning a configured instance. | (this skill, side-by-side/02-circuit.md) |

## 4. Components

| Stanza 3.x | Python 4.x | Source citation |
|---|---|---|
| `pcb-component cpu : ...` | `class CPU(Component): ...` | Stanza: `jitpcb/src/jitpcb/physical-design/pin-solver/tests/nested-no-restrict.stanza:59`; Python: [L329-333], [L494-498], [L8558] |
| `pcb-bundle dual : pin x; pin y` (logical signal grouping) | `class Dual(Port): x=Port(); y=Port()` (any `Port` subclass with sub-`Port` attrs is a bundle) | Stanza: `jitpcb/src/jitpcb/physical-design/pin-solver/tests/nested-no-restrict.stanza:51-53`; Python: [L503-509], [L1340-1348] |
| `pcb-pad my-pad : ...` (copper pad shape) | `class MyPad(Pad): shape = Circle(diameter=1.0)` | Stanza: `jitpcb/src/jitpcb/parts/legacy-ocdb-landpatterns.stanza:2563`, `jitpcb/src/jitpcb/esir/pose.stanza:116`; Python: [L529-538], [L10427] |
| `pcb-landpattern QFP-100 : ...` | `class MyLandpattern(Landpattern): p1 = MyPad().at(-1.27, 0); p2 = ...` | Stanza: `jitpcb/src/jitpcb/physical-design/pin-solver/tests/nested-no-restrict.stanza:20`; Python: [L530-538], [L10378] |
| Stanza pad placement `at loc(x, y, θ)` (rotation as third positional arg, common in hand-coded `pcb-landpattern` blocks and OCDB-generated component files) | `.at(x, y, rotate=θ)` — **`rotate` is keyword-only**. `Pad.at(self, x, y, /, *, rotate=0, on=Side.Top)`. A 1-to-1 port using `.at(x, y, θ)` raises `TypeError: Positionable.at() takes from 2 to 3 positional arguments but 4 were given`. | Python: `py-jitx/src/jitx/placement.py:104-106` |
| Stanza SOT-23 footprint (3/5/6 lead) | `from jitxlib.landpatterns.generators.sot import SOT23_3, SOT23_5, SOT23_6` then `lp = SOT23_3().lead_profile(...).package_body(RectanglePackage(...))`. Variants live under `jitxlib.landpatterns.generators.sot` — `SOT`, `SOT23`, `SOT23_3`, `SOT23_5`, `SOT23_6`. | Python: `py-jitx-stdlib/src/jitxlib/landpatterns/generators/sot.py:162-225` |
| Stanza SOT-89-3 / SOT-89-5 / SOT-223 footprint (asymmetric, with wide thermal-tab middle pad) | **No `SOT89` / `SOT223` generator in jitxlib.** Verified: `jitxlib.landpatterns.generators.sot` only exports SOT-23 variants. Do **not** use `SOT23_3` as a substitute — pin 2 of SOT-89 is a wide thermal/collector tab and SOT-23 will produce wrong pad dimensions and wrong copper-fill area. Use the custom `Landpattern` + `Pad.at(x, y)` path documented in `jitx-component-modeler/references/package-examples.md` §"Custom Landpatterns (irregular footprints)", placing pads at the manufacturer's recommended-footprint coordinates from the datasheet. | Python: `py-jitx-stdlib/src/jitxlib/landpatterns/generators/sot.py` (no SOT-89 entry) |
| (Stanza body-dimension declarations on a `pcb-landpattern`: `body-width`, `body-length`, `body-height`) | `RectanglePackage(width=Toleranced.min_max(4.9, 5.1), length=Toleranced.min_max(4.9, 5.1), height=Toleranced.min_max(0.8, 1.0))`. **`height` is a required keyword-only argument**: omitting it raises `TypeError: __init__() missing 1 required keyword-only argument: 'height'` at class definition time. Maps to datasheet `A` dimension. | Python: `jitxlib.landpatterns.package.RectanglePackage` |
| `pcb-symbol single-shape : ...` | `class MySymbol(Symbol): vcc_pin = Pin.up((0,2), length=1)` | Stanza: `jitpcb/src/jitpcb/harnesses/schematic-symbol-shape-design-harness.stanza:49`; Python: [L519-523], [L12696] (`class Symbol`), [L12755] (`class Pin`) |
| `pin-properties : [pin:Ref \| pads:Ref \| side:Dir] [p[0] \| p[1] \| Left] ...` | `mapping = PadMapping({GND: [landpattern.p[9], landpattern.thermal_pad], VCC: landpattern.p[1]})`. **Multi-pad-per-port**: when a Stanza component shares one port across multiple physical pads (common on power-stage ICs), list every pad in the PadMapping value: `self.PVDD[0]: [lp.p[3], lp.p[4]]`, `self.PGND: [lp.p[25], lp.p[26], lp.p[31], lp.p[32]]`, `self.EP: [lp.thermal_pads[0]]`. Omitted pads stay unconnected at the landpattern level. | Stanza: `jitpcb/src/jitpcb/physical-design/pin-solver/tests/nested-no-restrict.stanza:85-90`; Python: [L732-743], [L10457] (`class PadMapping`) |
| (Stanza pin-properties also handles symbol-pin mapping per row) | `SymbolMapping(entries)` for explicit Port -> Symbol Pin mapping | Python: [L12865] (`class SymbolMapping`) |
| QFN / SON / DFN exposed (thermal) pad in `PadMapping` | `self.EP: [lp.thermal_pads[0]]` (note: `thermal_pads` plural, indexed). The exposed pad lives on a separate accessor from signal pads — `lp.p[N]` will not reach it. **Silent error**: omitting the EP from `PadMapping` produces no build warning, and the thermal/ground tab floats. Always map the EP for QFN/SON parts (typically to `GND`). **Stanza-pin-number trap**: Stanza `pin-properties` tables often list the thermal pad as one past the last lead (e.g. pin 33 on a 32-lead QFN, pin 57 on a 56-lead QFN — the ESP32-S3 FN8 source uses `[GND \| 57 \| Left \| Power]`). In 4.x there is no `lp.p[N+1]` — that pin **is** `lp.thermal_pads[0]`. Map the port to `thermal_pads[0]` only; a literal Stanza-style `lp.p[57]` raises `KeyError: 57`. | Python: `py-jitx-stdlib/src/jitxlib/landpatterns/generators/qfn.py:78`; example: `TEC-example/tec_example/components/texas_instruments_TAS5825MRHBR.py:156` |
| QFN landpattern lead profile (`make-qfn-landpattern` in Stanza, `LeadProfile(...)` in Python) | Use `QFNLead(length, width)` from `jitxlib.landpatterns.generators.qfn`, **not** the base `SMDLead`. `SMDLead` has a required `lead_type` field with no default and raises `TypeError: SMDLead.__init__() missing 1 required positional argument: 'lead_type'`. `QFNLead` inherits from `SMDLead` and defaults `lead_type = QuadFlatNoLeads`. | Python: `py-jitx-stdlib/src/jitxlib/landpatterns/generators/qfn.py:102` (`class QFNLead(SMDLead)`); `py-jitx-stdlib/src/jitxlib/landpatterns/leads/__init__.py:12` (`class SMDLead`) |
| Stanza `make-bga-landpattern(rows, cols, pitch, ball_dia, body_w, body_l, depop)` | `BGA` from `jitxlib.landpatterns.generators.bga` — three non-obvious traps: **(1) kwargs are `num_rows` / `num_cols`** (not `rows` / `columns`); **(2) `.pad_config(SMDPadConfig())` is required** — without it instantiation fails with `No pad configuration specified` (unlike `QFN`, the `BGA` generator provides no default); **(3) pad addressing is AlphaDict** — pads are `lp.A[1]`, `lp.B[2]`, ... (letter-keyed attrs returning a dict of column-indexed `Pad`s), **not** `lp.p[r][c]` or `lp.balls[r][c]`. A Stanza `B[2]` style ref maps almost 1:1 to `lp.B[2]` once you know the form. <br><br>```python<br>from jitxlib.landpatterns.generators.bga import BGA<br>from jitxlib.landpatterns.package import RectanglePackage<br>from jitxlib.landpatterns.pads import SMDPadConfig<br>from jitx.toleranced import Toleranced as T<br><br>self.landpattern = (<br>    BGA(num_rows=5, num_cols=5, pitch=1.0, ball_diameter=0.4)<br>    .pad_config(SMDPadConfig())<br>    .package_body(RectanglePackage(<br>        width=T.min_max(7.9, 8.1),<br>        length=T.min_max(5.9, 6.1),<br>        height=T.min_max(0.95, 1.05),<br>    ))<br>)<br>lp = self.landpattern<br>self.mappings = [PadMapping({self.VDD: lp.B[4], self.VSS: lp.B[3], ...})]<br>``` | Python: `py-jitx-stdlib/src/jitxlib/landpatterns/generators/bga.py:16-74` (`BGABase`, `BGA(A1, AlphaDictNumbering, BGADecorated)`); addressing via `jitxlib.landpatterns.grid_layout.AlphaDictNumbering` |

## 5. Nets and connectivity

| Stanza 3.x | Python 4.x | Source citation |
|---|---|---|
| `net (vdd op-amp.v+ decoupling-cap.p[1])` | `self.vdd = self.op_amp.vp + self.decoupling_cap.p[1]` (the `+` operator returns a `Net`) | Stanza: `jitpcb-by-example/Examples/learn-jitx-main.stanza:185`; Python: [L348-353], [L629-633], [L11101] (`class Net`) |
| `net VDD (a, b, c)` (named net) | `self.VDD = Net([a, b, c], name="VDD")` or build with `+` then assign to attribute (name comes from attribute). **`Net()` takes a single iterable, not varargs** — `Net(a, b, c, name="VDD")` raises `TypeError: Net.__init__() takes from 1 to 2 positional arguments but ...`. Always wrap multiple ports in a list. Also: **only name the net at the top level** of the hierarchy; sibling sub-circuits that each declare `Net([...], name="GND")` build cleanly through translation, then fail with `status: error / message: Public name GND already in use`. Leave nested ground/rail nets anonymous and apply `name=` only on the unified net at the top. | Stanza: `lbstanza` by-example net statement; Python: `py-jitx/src/jitx/net.py:635, 662-668` (`class Net`, signature `Net(ports: Iterable = (), *, name=None, symbol=None)`) |
| Same-name `net` statements merge (implicit) | `+=` on a `Net` extends it: `GND += self.ssvia.COMMON`. **Note: `Port += Port` is forbidden** — circuit-level `Port` attributes are immutable and `self.port += other` raises `NotImplementedError: Ports are immutable. Use + to create a new net instead of +=`. Create a `Net` first: `self.NET = Net(); self.NET += self.port + self.comp.PIN`. | Python: [L1230-1233] |
| `copper-pour(LayerIndex(i), isolate=0.1, rank=1) = shape` (Stanza copper-pour binding) | `self.GND += Pour(shape, layer=i, isolate=0.1, rank=1)`. Signature: `Pour(shape, layer: int, *, isolate=0.0, rank=0, orphans=True)`. **Import from `jitx` (top level) or `jitx.copper` — `Pour` is NOT in `jitx.feature`** despite living alongside the other surface features by naming-analogy. `layer` is a plain `int` keyword (no `LayerIndex` wrapper); the pour attaches via `net += Pour(...)`, not by assignment to a `.geometry` attribute. | Python: `py-jitx/src/jitx/copper.py:45-79` (`class Pour(Copper)`); re-exported by `py-jitx/src/jitx/__init__.py:54` |

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
| `pcb-via default-th : ...` (top-level via definition) | `class THVia(Via): start_layer=0; stop_layer=3; type=ViaType.MechanicalDrill; ...` — declared as a **nested class** inside the `Substrate` subclass (not an instance attribute). Use **integer layer indices** (0 = top, N-1 = bottom) — `Side.Top`/`Side.Bottom` is shown in some docstrings but the build-time translator accesses `via.start_layer: int` and using `Side.*` raises `AttributeError: type object 'THVia' has no attribute 'start_layer'`. | Stanza: `jitpcb-by-example/src/reference/statements/viastmt/heading.md:62`; Python: [L1031-1106], [L13692] (`class Via`), [L13817] (`class ViaType`) |
| (via referenced by name in routing/code) | `viaType = SampleSubstrate.THVia; self.via = viaType().at(2.0, 3.0)` | Python: [L1110-1121] |
| (3.x has no first-class substrate object — stackup + fab rules are loose top-level definitions) | `class SampleSubstrate(Substrate): stackup = SampleTwoLayerStackup(); constraints = SampleFabConstraints(); ...` ties stackup + constraints + via defs + routing structures together | Python: [L897-921], [L12512] (`class Substrate`), [L12608] (`class FabricationConstraints`) |

## 9. Constraints

| Stanza 3.x | Python 4.x | Source citation |
|---|---|---|
| `constrain-topology(...)` JSL helper plus routing-structure application (**single-ended**) | `Constrain(Topology(self.A.p, self.B.p)).structure(rs)` — chained call applies single-ended routing structure constraint. `Constrain.structure()` only accepts `RoutingStructure`, not `DifferentialRoutingStructure` — see row below. | Stanza: `jitpcb-by-example/src/essentials/usage_patterns.md:161`; Python: `py-jitx/src/jitx/si.py:325-357` (`class Constrain`) |
| `structure(path, differential)` / `pcb-differential-routing-structure` applied to a pair of nets (**differential**) | `ConstrainDiffPair(Topology(dp_begin, dp_end)).structure(drs)` where endpoints are `DiffPair()` bundles with `.p`/`.n` sub-ports. **Do not** model a diff pair as two separate `Constrain(Topology(...)).structure(drs)` calls — `Constrain.structure` takes a `RoutingStructure`, not a `DifferentialRoutingStructure`, and using two single-ended constraints leaves P and N uncoupled. See pitfalls. | Python: `py-jitx/src/jitx/si.py:433-471` (`class ConstrainDiffPair`); example: `py-jitx/tests/test_smoke.py:646` |
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
| `add-thermal-vias(net, shape)` (places via grid under a thermal pad) | **No direct function equivalent.** Tag the net, then attach a constraint: `design_constraint(self.GND_tag).stitch_via(MySubstrate.THVia, SquareViaStitchGrid(pitch=1.2, inset=0.3))`. **Prerequisites**: the net needs a `Tag`, and a copper `Pour` must already cover the thermal pad — without the pour, `stitch_via` silently does nothing. | Python: `jitx.constraints.design_constraint`, `SquareViaStitchGrid`, `StitchVia` |

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

## 11. Bundles / common ports

Stanza `power-pin` / `diff-pair` bundle field names **do not** carry over verbatim — the
Python 4.x class field names are different. Always import the bundle class from the
location shown and use the **exact** field names. Verify with
`grep -A 6 "^class Power\b" .venv/lib/python*/site-packages/jitx/common.py` if in doubt.

| Stanza bundle | Python type | Import | Fields (exact names) |
|---|---|---|---|
| `power-pin()` | `Power` | `from jitx.common import Power` | `.Vp` (positive rail), `.Vn` (negative / ground rail). **Not** `.vdd` / `.gnd`. |
| `diff-pair()` | `DiffPair` | `from jitx.net import DiffPair` | `.p`, `.n` (lowercase). **Not** `.P` / `.N`. |
| `i2c()` | `I2C` | `from jitxlib.protocols.serial import I2C` | `.sda`, `.scl` (optional `.intr`, etc. — read class def) |
| `spi()` | `SPI` | `from jitxlib.protocols.serial import SPI` | `.sck`, `.mosi`, `.miso` (`.cs` only when constructed with `SPI(cs=True)`) |
| `i2s()` 3-wire | `I2S` | `from jitxlib.protocols.serial import I2S` | `.sck`, `.ws`, `.sd`. **Note**: Stanza `bclk`/`lrck`/`sdin`/`sdmo` map to `sck`/`ws`/`sd` — rename when porting. |
| `octal-spi()` with DQS | `OctalSPIwDQS` | `from jitxlib.protocols.serial import OctalSPIwDQS` | `.sck`, `.cs`, `.dqs`, `.data[0..7]` |
| (wide / quad / octal SPI variants) | `WideSPI` | `from jitxlib.protocols.serial import WideSPI` | `WideSPI.quad()` / `WideSPI.octal()` classmethods; `.sck`, `.cs`, `.data[…]` |
| `i2s([I2S-MCK])` / `i2s-with-mck()` (4-wire I2S with master clock) | **define locally** | (no jitxlib export) | Subclass `jitx.Bundle` with `sck`, `ws`, `sd`, `mclk`. See "Bundles missing from jitxlib" below. Verified: `jitxlib.protocols.serial.I2S` (py-jitx-stdlib/src/jitxlib/protocols/serial.py:227-238) has **only** `sck`/`ws`/`sd` — there is no `mck` attribute and no `I2SMCK` / `I2SWithMCK` class. |
| `i2s([I2S-MCK I2S-SDMI])` (5-wire full-duplex I2S — MCK + separate SDIN/SDOUT) | **define locally** | (no jitxlib export) | Subclass `jitx.Bundle` with `sck`, `ws`, `sd_out`, `sd_in`, `mclk` — the `.sd` direction is split into two ports because a single `Port()` is symmetric. **Silent omission**: if you collapse this back to a 3-wire `I2S` (as a porter naturally would when no template exists), the receive direction is wired only via `sd` and the transmit/receive split is lost — the consumer cannot route a separate ADC return path. Apply the same provide/require pattern as the basic `I2S` once the bundle is defined. |
| `octal-spi()` without DQS (e.g. some PSRAM) | **define locally** | (no jitxlib export) | Subclass `jitx.Bundle` with `sck`, `cs`, `data[0..7]`. |
| (user-defined `pcb-bundle x : pin a; pin b`) | user-defined `Bundle` subclass | (in your project) | declare sub-`Port`s as class attrs |

### Bundles missing from jitxlib — define locally

When a serial bundle isn't in `jitxlib.protocols.serial`, write a tiny `jitx.Bundle` subclass alongside the design. Example for `I2SMCK` (I²S + master clock for an ADC):

```python
import jitx
from jitx.net import Port

class I2SMCK(jitx.Bundle):
    sck  = Port()   # bit clock (Stanza: bclk)
    ws   = Port()   # word select / LRCK (Stanza: lrck)
    sd   = Port()   # serial data (Stanza: sdin / sdmo)
    mclk = Port()   # master clock (4th wire)
```

Equivalent shape for a bare `OctalSPI` (no DQS):

```python
class OctalSPI(jitx.Bundle):
    sck  = Port()
    cs   = Port()
    data = [Port() for _ in range(8)]
```

The complete `jitxlib.protocols.serial` catalog at the time of writing is `I2C`, `SPI`, `WideSPI` (+ `.quad()` / `.octal()` classmethods), `OctalSPIwDQS`, `I2S`, `UART`, `Microwire`, `JTAG`, `SWD`, `CANPhysical`, `CANLogical`, `SMBus`. Always grep the current source before assuming an import path — bundle additions land in `py-jitx-stdlib`.

Common porting bug: a mechanical Stanza-→-Python translation that writes `self.power.vdd`
or `self.diff.P` will pass pyright (attribute exists implicitly on a `Port` because
`Port` forwards unknown attrs) but produces a **silently disconnected net** at build
time. There is no compile-time error. When in doubt, dump the bundle:
`print(list(jitx.common.Power.__dict__))`.

## 12. Common porting questions

These are constructs that look like they should have a 1-to-1 mapping but don't.

### Do-not-populate (DNP)

There is no `dnp=True` kwarg on `Resistor` / `Capacitor` / `Component`. The two
supported patterns are:

```python
# Pattern A — dedicated subclass (defined in jitx/component.py):
# NOTE: import from `jitx.component`, NOT `from jitx import ...`. On jitx 4.0.5 the
# class is defined at jitx/component.py:150 but is NOT re-exported from
# `jitx/__init__.py`; `from jitx import NonPopulatedComponent` raises ImportError.
from jitx.component import NonPopulatedComponent
class CFG1Pulldown(NonPopulatedComponent):
    ...

# Pattern B — set in_bom / soldered on a regular Component subclass:
class MyOptionalIC(jitx.Component):
    in_bom = False
    soldered = False
    ...
```

For passives, write a thin subclass. The query-based `Resistor` / `Capacitor` / `Inductor` exported from `jitxlib.parts` (defined in `py-jitx-parts/src/jitxlib/parts/query_api.py`) are real `jitx.Component` subclasses, so this multi-inheritance pattern is consistent with `NonPopulatedComponent`:

```python
class DNPResistor(NonPopulatedComponent, Resistor):
    pass

self.r_cfg1 = DNPResistor(resistance=6.8e3)
```

> Verify behaviour per-passive before depending on it for a large design. The MRO is well-defined (both bases are `jitx.Component` subclasses) but the part-DB query path on `Resistor`/`Capacitor`/`Inductor` does substantial work in `__init__`, and a few corners (e.g. `Inductor` in some 4.0.x builds) have hit unrelated runtime errors during the multi-inheritance dance. If `class DNPInductor(NonPopulatedComponent, Inductor)` raises at construction, fall back to a regular `Inductor` with explicit `in_bom = False; soldered = False` overrides — or document the part as a deferred DNP gap until upstream resolves it.

```python
# Pattern C — set in_bom / soldered on the instance (lightest-weight, one-off DNP):
c_usb_filter = Capacitor(capacitance=10.0e-12, case="0402")
c_usb_filter.in_bom   = False
c_usb_filter.soldered = False
self.c_usb_filter = c_usb_filter  # store as self.* — see "Strap helpers" below
```

`in_bom` and `soldered` are real `Component` fields (`py-jitx/src/jitx/component.py:93,98`,
typed `bool | None`, defaulting to `None`). Shadowing them at the instance level is
normal Python attribute assignment, not an implementation accident — but Pattern A
(subclass) is preferable when the same DNP component is reused, since the intent is
declared once and stays with the class definition.

> ⚠️ **DNP subclasses (Pattern A or Pattern B) MUST be declared at module scope.**
>
> The natural translation of "I need one DNP capacitor here" puts the
> subclass next to the single use site inside `Circuit.__init__`. **That
> fails** with:
>
> ```
> TypeError: Creating new JITX classes dynamically during instantiation
> is not supported, please create new classes separately.
> ```
>
> The rule comes from the `jitx` skill's "Don'ts": no JITX-class
> subclassing inside functions or methods. The error fires at build
> time, not class-load time, so `pyright` doesn't catch it.
>
> **Recommended pattern** — define a `<pkg>/dnp.py` module once, reuse
> from any circuit:
>
> ```python
> # pd_audio/dnp.py
> from jitxlib.parts import Capacitor, Inductor, Resistor
>
> class DnpResistor(Resistor):
>     in_bom = False
>     soldered = False
>
> class DnpCapacitor(Capacitor):
>     in_bom = False
>     soldered = False
>
> class DnpInductor(Inductor):
>     in_bom = False
>     soldered = False
> ```
>
> ```python
> # pd_audio/circuits/power_supplies.py
> from pd_audio.dnp import DnpResistor
>
> class PowerSupplies(Circuit):
>     def __init__(self):
>         ...
>         self.r_cfg1 = DnpResistor(resistance=6.8e3)   # at instance level, fine
>         self.r_cfg1.insert(self.pd.CFG1, self.GND)
> ```

| Stanza | Python 4.x |
|---|---|
| `do-not-populate(r_cfg1)` | Three patterns: (A) subclass `NonPopulatedComponent`, (B) set `in_bom = False; soldered = False` as **class** attrs on a `Component` subclass, (C) set the same as **instance** attrs after construction. **`Resistor(..., dnp=True)` is NOT a valid kwarg.** |

### `database-part(...)` — looking up parts by MPN

There is **no `jitx.database_part(...)` function** in 4.x. The 4.x query API is:

```python
# Passives — direct kwargs on Resistor/Capacitor/Inductor:
from jitxlib.parts import Resistor, Capacitor, Inductor
self.r1 = Resistor(mpn="RC0402FR-0710KL", manufacturer="Yageo")
self.c1 = Capacitor(mpn="GRM155R71H103KA88D", manufacturer="Murata")

# Non-passives (crystals, encoders, connectors, etc.) — write a custom Component
# subclass from the datasheet. There is no MPN-lookup path for arbitrary parts.

# MPN-miss fallback: the 4.x parts DB does not have 1-to-1 coverage of the 3.x
# OCDB. A Stanza part that resolved fine can return zero hits in 4.x — observed:
# Vishay IHLP2525CZER4R7M11 (a 4.7uH inductor) raises
#   ValueError: No components meeting requirements:
#     {'category': 'inductor', 'mpn': 'IHLP2525CZER4R7M11', 'manufacturer': 'Vishay'}
# while other MPNs from the same Stanza design (Nichicon UCD1V331MNL1GS, YAGEO
# CC0805KKX7R9BB684) match cleanly. There is no user-visible pattern. If the MPN
# is not load-bearing, fall back to a value-based query:
self.L = Inductor(inductance=4.7e-6)
# If the exact MPN is required (e.g. for vendor compliance), verify it in the
# parts-search UI before hard-coding.
```

| Stanza | Python 4.x |
|---|---|
| `database-part(["mpn" => "...", "manufacturer" => "..."])` on a passive | `Resistor(mpn=..., manufacturer=...)` (or `Capacitor`, `Inductor`) — see `jitxlib/parts/query_api.py` |
| `database-part(["mpn" => "..."])` on a non-passive (crystal, connector) | Write a custom `Component` subclass from the datasheet — invoke the `jitx-component-modeler` skill |
| OCDB connector / mechanical part referenced as `inst foo : vendor/PART-NUMBER` (e.g. `korean-hroparts-elec/TYPE-C-31-M-12`) | **No Python OCDB equivalent.** There is no `jitxlib.connectors` / `jitx.ocdb` module — the open-components-database (Stanza-only) has not been ported. Always treat OCDB parts as custom `Component` subclasses: pull the manufacturer datasheet (the OCDB part name usually maps to a real MPN, e.g. `TYPE-C-31-M-12`), then invoke the `jitx-component-modeler` skill. For irregular pad arrangements (USB-C receptacles, audio jacks, edge connectors) use the custom `Landpattern` + `Pad.at()` pattern shown in `jitx-component-modeler/references/package-examples.md` §"Custom Landpatterns (irregular footprints)". |
| `ceramic-cap(C, "C0G", "0402")` or `database-part(["dielectric" => "C0G", ...])` (dielectric / temperature coefficient filter) | `Capacitor(capacitance=C, temperature_coefficient_code="C0G", case="0402")`. Accepted codes follow the EIA classification: `"C0G"` / `"NP0"` (Class I, ±30ppm/°C), `"X7R"`, `"X5R"`, `"X8R"`, `"Y5V"`. **Use `C0G`/`NP0` for any capacitor whose value must be stable over temperature** — antenna matching networks, crystal load caps, RC filter time constants, oscillator timing. X7R (the implicit default for the part DB) has ±15% capacitance variation over the −55…+125°C range and silently detunes RF circuits. | Python: `py-jitx-parts/src/jitxlib/parts/query_api.py:179, 446` (kwarg `temperature_coefficient_code`) |
| Stanza `closest-std-val(x, 10.0)` / JSL `std-val` helpers (silently snap a computed value to the nearest E-series standard) | **No direct 4.x equivalent.** Round computed passive values to E12 / E24 in Python *before* constructing the part, otherwise the parts query raises `ValueError: No components meeting requirements: {'category': 'capacitor', 'capacitance': 1.375e-08}` — the JITX parts DB only stocks standard values, and the error message names the requested value but does not suggest snapping. Copy-paste helper: <br><br>```python<br>_E12 = (10, 12, 15, 18, 22, 27, 33, 39, 47, 56, 68, 82)<br><br>def _round_e12(value: float) -> float:<br>    import math<br>    if value <= 0:<br>        return value<br>    decade = 10 ** math.floor(math.log10(value))<br>    norm = value / decade<br>    for v in _E12:<br>        if v / 10 >= norm:<br>            return v / 10 * decade<br>    return _E12[0] * decade * 10<br><br># Soft-start cap for a TPS62933 — formula yields 1.375e-8, not a stocked value:<br>css = _round_e12(2.0e-3 * 5.5e-6 / 0.8)   # 1.5e-8, in DB<br>self.c_ss = Capacitor(capacitance=css)<br>``` | Python: no equivalent in `jitxlib.parts` / `jitx.units` as of 4.0.5 |

## 13. Stackup imports — JLCPCB predefined substrates

| Stanza | Python | Layers | Prepreg |
|---|---|---|---|
| `jlcpcb-jlc2313` (closest analog) | `from jitxlib.jlcpcb import JLC04161H_1080` | 4 | 1080 |
| — | `from jitxlib.jlcpcb import JLC04161H_7628` | 4 | 7628 |
| — | `from jitxlib.jlcpcb import JLC06161H_7628` | 6 | 7628 |

There is **no 2-layer JLCPCB class** in `jitxlib.jlcpcb` (as of jitx-4.0.5). For a
2-layer board, build a custom `Substrate` — see the `jitx-substrate-modeler` skill.
Each class above bundles a `Stackup` + via definitions + fab constraints + named
`RoutingStructure`s (e.g. `RS_50`, `DRS_90`, `DRS_100`).

## 14. Routing structures and SI constraints

The Python 4.x classes are `RoutingStructure` and `DifferentialRoutingStructure`
(both in `jitx.si`) — **not** `SingleEnded` / `Differential`. Construction uses the
`symmetric_routing_layers({...})` helper. See row 106-108 above for table form, and
the `jitx-substrate-modeler` skill (§"Routing structures") for full constructor
examples, plus the `jitx-interconnect-constraints` skill for how to attach a
structure to a topology via `Constrain(Topology(...)).structure(rs)`.

## 15a. Stanza helpers with no Python equivalent

The Stanza JITX library exposes a number of one-line helpers — some
mechanical, some schematic / runtime — that have no 1-to-1 Python
analog. Most fail silently if the porter just drops the call (the
build succeeds, but a feature is missing). Surface each one as a
`PORT-DEFERRED.md` entry when it can't be replaced inline.

| Stanza 3.x | Python 4.x | Workaround |
|---|---|---|
| `add-mounting-holes(board-shape, "M3")` (auto-place M3 PTH holes at board corners) | No equivalent in `jitxlib-standard` 4.0.1. There is no `jitxlib.mechanical` module and no top-level `add_mounting_holes` helper (verified by grep over `py-jitx`, `py-jitx-stdlib` on jitx-4.0.5). | Define a PTH mounting-hole `Component` manually (e.g. drill 3.2 mm + annular ring 5.5 mm for M3 clearance), instantiate it 4× at explicit board-relative coordinates, and add a `PORT-DEFERRED.md` entry so the placement is revisited when an upstream `MountingHole` utility lands. Silent omission: the design builds without it and the fabbed board has no mounting points. |
| `add-open-drain-pullups(net_or_port, rail)` (ocdb helper — for each pin on `net_or_port`, instantiate a pull-up `Resistor` from the pin to `rail`) | No equivalent helper. | Expand inline — one explicit `Resistor` per pin. For an `i2c` bundle: `self.r_sda = Resistor(resistance=4.7e3); self.r_sda.insert(i2c.sda, vdd); self.r_scl = ...`. For a `gpio[N]` array: `self.r_pu = [Resistor(resistance=10e3) for _ in range(N)]; for i in range(N): self.r_pu[i].insert(gpio_array[i], vdd)`. Silent omission: the bus floats high inconsistently and the design may appear to work then fail under load. |
| `add-xtal-caps(xtal, gnd)` (places two load caps from crystal pins to ground, sized from the crystal's `crystal-resonator` property) | No equivalent. | Two `Capacitor` instances per crystal, both `self.*`-assigned; value comes from the crystal's load-capacitance datasheet figure (typically 12 pF → 18 pF caps after accounting for board stray). |
| `setup-design(name, board, rules=..., vendors=..., quantity=...)` (Stanza top-level: sets the design name, board, rules, BOM vendors, quantity in one call) | Decomposed into class attributes on the `Design` subclass: `board = MyBoard()`, `substrate = MySubstrate()` (rules folded into the substrate). Vendors / quantity / BOM metadata is not generally surfaced at `Design` level today; treat as `PORT-DEFERRED` if the build target requires it. | Set `board` and `substrate` as class attributes on the `Design` subclass; document the vendor / quantity gap separately. |
| `set-paper(ANSI-A)` | `Design` subclass: `paper = Paper.ANSI_A` from `jitx.paper`. Default is ANSI A; usually omittable. | Set via class attribute on the `Design`. |
| `set-export-backend(\`kicad)` (Stanza-side selects the CAD export target) | No-op in 4.x — KiCad is the only export today. The `python -m jitx build` command emits KiCad-compatible artefacts implicitly. | Drop the call entirely. |
| `set-use-layout-groups()` (enables hierarchical schematic-sheet grouping in Stanza) | No-op — 4.x has implicit `SchematicGroup` per `Circuit`. | Drop the call entirely. |
| `view-board()` / `view-schematic()` / `view-bom()` (Stanza top-level commands that open viewer panes) | No-op in headless `python -m jitx build`. Viewers in 4.x live in the `jitx interactive` server / IDE plugin, not as top-level design entries. | Drop the calls entirely. |

## 15. Strap helpers (`bypass-cap-strap`, `cap-strap`, `res-strap`)

The Stanza JITX library exposes one-line "strap" helpers that instantiate a passive
and wire it between two nets in a single call. Python 4.x has **no equivalent
helper** — expand the strap inline.

| Stanza | Python 4.x |
|---|---|
| `bypass-cap-strap(a, b, value)` | `self.c_N = Capacitor(capacitance=value, case="0402"); a += self.c_N.p[0]; b += self.c_N.p[1]` |
| `cap-strap(a, b, value)` | Same shape as above. |
| `res-strap(a, b, value)` | `self.r_N = Resistor(resistance=value, case="0402"); a += self.r_N.p[0]; b += self.r_N.p[1]` |

**Why the `self.` prefix matters**: store the passive instance as a `self.*`
attribute on the enclosing `Circuit`. Bare local variables get garbage-collected at
the end of `__init__`, and `jitx._structural.Structural.__del__` logs a warning
*"Reference to structural object %s lost during instantiation, it likely needs to
be assigned to an object."* (`py-jitx/src/jitx/_structural.py:609-636`). In a quiet
log this is easy to miss, and the component disappears from the netlist.

When porting a Stanza module that calls dozens of straps in a loop, a small
project-local helper is often cleaner than copy-pasting the four-line idiom:

```python
def bypass(self, hi: Net, gnd: Net, value: float, *, case: str = "0402") -> Capacitor:
    """In-place equivalent of Stanza bypass-cap-strap. Stores the cap as self._bypass_<n>."""
    idx = getattr(self, "_bypass_idx", 0)
    c = Capacitor(capacitance=value, case=case)
    setattr(self, f"_bypass_{idx}", c)
    self._bypass_idx = idx + 1
    hi  += c.p[0]
    gnd += c.p[1]
    return c
```

Then in the circuit body:

```python
class PowerSection(Circuit):
    def __init__(self):
        super().__init__()
        self.DVDD = Net(); self.GND = Net()
        self.bypass(self.DVDD, self.GND, 100.0e-9)
        self.bypass(self.DVDD, self.GND, 1.0e-6)
```

This pattern keeps every cap reachable through `self.*` (no GC warning), and the
auto-numbered names show up in the BOM and schematic with stable identifiers across
builds.

## Notes / gaps

- The Stanza-side rows above point to real constructs from the JITX 3.x by-example reference and similar Stanza JITX example designs. Where the Stanza `lbstanza` reference covers only generic language syntax (not the JITX PCB DSL), citations target the JITX-specific example files (`tests/`, `jitpcb/src/`, `jitpcb-by-example/`) instead.
- Python-side line numbers refer to the JITX 4.x Python LLM reference (`jitx-4-1-python-llms.txt`); the `jitx` skill bundles this file for lookups. (The reference filename retains its original `4-1` tag from when it was extracted; the content covers the 4.x Python line.)
- For deeper Python API surfaces (Tag-based design constraints, BOM queries, schematic symbol generation, via structures with ground cages), see the corresponding `jitx-skills:jitx-*` skills rather than expanding these tables.
