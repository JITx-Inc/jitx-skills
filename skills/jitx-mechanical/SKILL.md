---
name: jitx-mechanical
description: "Mechanical CAD interface for JITX designs. Use when the user asks to import DXF, EMN, IDF, IDX, or BDF mechanical data; set a board outline from mechanical CAD; export a JITX board to DXF; attach STEP models; or work with mechanical CAD data. Also covers how to export a full board STEP, which has a CLI (`jitx design export legacy-step`) as well as the application UI."
---

# JITX Mechanical Interface Skill

Use this skill when the user has a mechanical drawing to turn into board geometry,
wants a DXF of a JITX design, or needs STEP models for mechanical review.
`jitxlib-mechanical` provides `jitx-mechanical` for inspection/import and the
`dxf` plugin for `jitx design export`.

## Setup

Run the base `jitx` skill's setup first. In the project venv, uninstall the old
`jitx-mechanical` distribution if installed: it supplies the same command as
`jitxlib-mechanical`.

```bash
pip uninstall -y jitx-mechanical
```

Install `jitxlib-mechanical` with the command in the base skill's
[Supported versions](../jitx/SKILL.md#supported-versions) table. The Python API is
`jitxlib.mechanical`.

When regenerating an existing import, remove manual cutout attachments left over
from the old module; the generated Board now carries those features.

Do not suggest the retired per-format commands or packages. Use
`jitx-mechanical inspect`, `jitx-mechanical import`, and `jitx design export dxf`.

## Workflow

| User wants to... | Command or API |
|---|---|
| Inspect DXF or IDF text (.emn/.idf/.idx/.bdf) before import | `jitx-mechanical inspect` |
| Generate a Board-focused JITX Python module from mechanical data | `jitx-mechanical import` |
| Export a captured JITX design to DXF | `jitx design export dxf <module.path.Design>` |
| Attach a STEP/STP model to a component | `jitx.model3d.Model3D` |
| Export a complete board assembly STEP | `jitx design export legacy-step <DESIGN>`, or the JITX application UI |

## Before Importing Holes

Before running `jitx-mechanical import` on a file that may contain circular
features or mounting holes, ask the user whether those holes are:

- **Unplated/non-electrical board geometry**: use `--hole-policy cutout`.
- **Plated, chassis-connected, or otherwise electrical mechanical features**:
  use `--hole-policy component`.

Do not silently rely on the default when the user has not stated the intent.
If the user is unsure, inspect first and then ask with the available summary in
hand. Plated mounting holes are usually best imported as single-pin mechanical
components so the user can connect them explicitly.

With `--hole-policy component`, plated or unknown holes become components;
known NPTH holes remain board cutouts. IDF files with known PTH/NPTH holes do not
need separate imports. DXF circular holes carry unknown plating, so component
policy turns all of them into components. Confirm their intent with the user and
review the report before connecting generated ports. For mixed electrical intent
among unknown holes, edit the generated Board and companion module to restore
non-electrical holes as cutouts.

## Inspect Mechanical Data

Use inspect before import to get a lightweight view of the source file.

```bash
jitx-mechanical inspect board.dxf
jitx-mechanical inspect board.emn
jitx-mechanical inspect board.idf --format idf
```

For DXF, inspect reports file version, source units, extents, layers, and entity
counts. For IDF text data, inspect runs the importer and prints
summary counts for outline, cutouts, holes, regions, annotations, placements,
and messages. Detailed classified follow-up data is written by `import` into the
Markdown/JSON report.

Supported import formats are DXF and IDF 2.0/3.0 text. The extensions `.emn`,
`.idf`, `.idx`, and `.bdf` select the IDF text reader; XML IDX is unsupported.
Use `--format dxf|emn|idf|idx` only when the file extension is ambiguous or wrong.
DXF block inserts, splines, dimensions, open polylines, and unclosed line/arc
chains are reported without conversion.

## Import Board Geometry

Use import to generate a user-editable Python module and a Markdown/JSON report.

```bash
jitx-mechanical import board.dxf --output <ns>/board.py --report <ns>/board.report.md --class-name ProjectBoard --hole-policy cutout

jitx-mechanical import board.emn --output <ns>/board.py --report <ns>/board.report.md --class-name ProjectBoard --hole-policy component
```

### Import Options

| Option | Meaning |
|---|---|
| `--format auto\|dxf\|emn\|idf\|idx` | Override input format detection. |
| `-o`, `--output PATH` | Output Python module path. Defaults to input path with `.py`. |
| `--report PATH` | Output report path, `.md` or `.json`. Defaults beside output module. |
| `--class-name NAME` | Generated `Board` class name. Default: `ImportedBoard`. |
| `--hole-policy cutout\|component` | Cutouts for all holes, or components for plated/unknown holes with NPTH kept as cutouts. Ask the user first. |
| `--unit mm\|in\|mil\|cm\|m` | Force DXF units. |
| `--layer-map LAYER=ROLE ...` | Map DXF layers to roles. |
| `--no-recenter` | Preserve source coordinates instead of recentering. |
| `--precision N` | Coordinate precision. Default: `4`. |

When `--hole-policy component` finds plated or unknown holes,
`jitx-mechanical import` writes a companion module beside the board module named
`<output_stem>_components.py`. For example, importing to
`<ns>/board.py` writes `<ns>/board_components.py` when
component holes are present. The CLI prints a `Components:` line for that file.
The default `cutout` policy does not create the companion file.

Common DXF layer roles for `--layer-map` are `outline`, `cutout`, `hole`,
`keepout`, `soldermask`, `bend`, `height`, and `annotation`. Example:

```bash
jitx-mechanical import board.dxf --layer-map OUTER_PROFILES=outline DRILL=hole SLOTS=cutout --hole-policy component --output <ns>/board.py
```

### Generated Output Shape

The primary import output is Board-focused and does not generate a user-facing
`Design` class. With `--hole-policy component`, imports that contain
plated or unknown holes also generate a companion `_components.py` module with
single-pin `Component` classes and a `MechanicalComponentsCircuit`.

```python
'Board geometry imported from board.emn.'

from jitx.board import Board
from jitx.feature import Cutout, KeepOut, Custom
from jitx.layerindex import LayerSet, Side
from jitx.shapes.primitive import Circle, Polygon, Text


class ProjectBoard(Board):
    shape = Polygon([(-50.0, -25.0), (50.0, -25.0), (50.0, 25.0), (-50.0, 25.0)])

    def __init__(self):
        super().__init__()
        self.cutout_0 = Cutout(Circle(radius=1.6).at(-40.0, -15.0))
        self.region_route_keepout_0 = KeepOut(
            Polygon([(-30.0, -15.0), (-20.0, -15.0), (-20.0, -5.0), (-30.0, -5.0)]),
            layers=LayerSet(0),
            route=True,
        )
        self.region_via_keepout_1 = KeepOut(
            Polygon([(-10.0, -15.0), (0.0, -15.0), (0.0, -5.0), (-10.0, -5.0)]),
            layers=LayerSet.all(),
            via=True,
        )
        self.region_place_keepout_2 = Custom(
            Polygon([(10.0, -15.0), (20.0, -15.0), (20.0, -5.0), (10.0, -5.0)]),
            Side.Bottom, name='PlaceKeepout',
        )
        self.note_0 = Custom(Text('Mechanical note', 1.5).at(0.0, 15.0, rotate=0.0), name="Note")
```

With `--hole-policy component`, a companion module is generated when component
holes are present:

```python
"""Mechanical components imported from board.emn."""

from jitx.circuit import Circuit
from jitx.component import Component
from jitx.feature import Cutout, Soldermask
from jitx.landpattern import Landpattern, Pad
from jitx.layerindex import Side
from jitx.net import Port
from jitx.shapes.primitive import Circle
from jitx.symbol import Pin, Symbol


class _SinglePinSymbol(Symbol):
    """Shared single-pin symbol used by every mechanical-hole Component."""
    p1 = Pin(at=(0, 0))


class _Pad_MechanicalHole_2p0mm_PLATED(Pad):
    shape = Circle(diameter=2.8)
    def __init__(self):
        self.cutout = Cutout(Circle(diameter=2.0))
        self.soldermask = Soldermask(self.shape)
        self.soldermask_bottom = Soldermask(self.shape, side=Side.Bottom)


class _LP_MechanicalHole_2p0mm_PLATED(Landpattern):
    def __init__(self):
        self.p1 = _Pad_MechanicalHole_2p0mm_PLATED().at(0, 0)


class MechanicalHole_2p0mm_PLATED(Component):
    """Single-pin through-hole Component."""
    reference_designator_prefix = "MH"
    p1 = Port()
    landpattern = _LP_MechanicalHole_2p0mm_PLATED()
    symbol = _SinglePinSymbol()


class MechanicalComponentsCircuit(Circuit):
    """Imported holes placed in the generated Board's coordinate frame."""
    ...
```

Generated hole pads have a 0.4 mm radial copper/soldermask margin. Before calling
them ready for fabrication, record a comparison with the project's fabrication
rules and adjust pad shapes if needed. Without that comparison, report the pad
sizing as unqualified for fabrication; exploratory import can continue.

Read the generated report after import. For recognized DXF layer roles, it
records keepouts, placement outlines, bend/height regions, and annotations. For
IDF data, it reports parsed notes, placements, known regions, unsupported
sections, unclassified objects, and warnings that may need source-file follow-up.

### Design Integration

Use the generated `Board` class in the project `Design`. Keep application
circuits and substrate choices in the user's own top-level design code. Import
the companion components module only when the CLI emits a `Components:` path.

```python
from jitx.sample import SampleDesign

from myproject.board import ProjectBoard
from myproject.board_components import MechanicalComponentsCircuit  # if emitted
from myproject.circuits.main import TopLevelCircuit
from myproject.substrate import ProjectSubstrate


class ProjectCircuit(TopLevelCircuit):
    def __init__(self):
        super().__init__()
        self.mechanical_holes = MechanicalComponentsCircuit()
        # Connect generated mechanical-hole `.p1` ports to chassis/ground nets
        # according to the user's electrical intent.


class ProjectDesign(SampleDesign):
    substrate = ProjectSubstrate()
    board = ProjectBoard()
    circuit = ProjectCircuit()
```

The generated Board already includes cutouts and drawing annotations. IDF
route/via keepouts become enforced `KeepOut` features. DXF `keepout` and
`soldermask` regions, and other regions such as IDF placement keepouts, become
drawing-only `Custom` features, not enforced constraints or mask openings.
Component placements and unsupported objects remain in the report. Review those
items with the user, add any needed constraints, and connect the companion
circuit's hole ports in project code.

## Export DXF

Installing `jitxlib-mechanical` registers the `dxf` export plugin. Confirm `dxf`
appears in `jitx design export --help` in the project venv. With its JITX runtime
running, export the design by its Python class path. The CLI submits and captures
the design before writing the drawing.

```bash
jitx design export dxf <module.path.Design> --output board_review.dxf
```

Filter layers when the mechanical team only needs part of the board data:

```bash
jitx design export dxf <module.path.Design> --output outline_and_drill.dxf --layers BoardOutline --layers Drill
```

Output defaults to `<design-name>.dxf`. Use `--overwrite` to replace an existing
file. DXF output uses millimeters and is a mechanical drawing, not a fabrication
packet. Nonuniform scaling, shear, and backdrill depth export are unsupported and
raise errors.

Export options:

| Option | Meaning |
|---|---|
| `--output PATH` | Destination DXF path. |
| `--overwrite` | Allow replacing an existing file. |
| `--layers LAYER` | Emit only named DXF layers; repeat for each layer. |
| `--no-board-outline` | Omit board outline. |
| `--no-components` | Omit component placement shapes. |
| `--no-pads` | Omit pads. |
| `--no-drill` | Omit drill holes. |
| `--no-vias` | Omit vias. |
| `--no-copper` | Omit copper. |
| `--no-annotations` | Omit annotations. |

Component markers, pads, drills, via copper, and other copper are separate
categories. Layer names include `BoardOutline`, `Drill`, `Components`, outer pads
`Pads_Top`/`Pads_Bottom`, and `Pads_<layer>`, `Vias_<layer>`, `Copper_<layer>`, and
`KeepOut_<layer>` using stackup layer names. Drawing features use
`<feature-name>_<side>`. Export an unfiltered drawing first and inspect its actual
layer names before choosing filters: unmatched `--layers` values can write an
empty drawing without an error.

Python callers can pass an already captured `RuntimeDesign` to
`jitxlib.mechanical.export_dxf(design, output)`, with an optional
`DxfExportConfig` for layer/category selection and `overwrite=True` to replace a
file.

## STEP on Components

JITX attaches STEP/STP files with `Model3D` on `Component` or `Landpattern`
objects. A direct attribute on those objects holding a `Model3D` instance, or a
list/dict of them, is picked up by structural dispatch. `model3ds` is the
conventional list name.

```python
from jitx.component import Component
from jitx.landpattern import Landpattern, Pad
from jitx.model3d import Model3D
from jitx.net import Port
from jitx.shapes.composites import rectangle
from jitxlib.symbols.box import BoxSymbol


class ConnectorPad(Pad):
    shape = rectangle(1.0, 0.6)


class ConnectorLandpattern(Landpattern):
    pad1 = ConnectorPad().at(-1.27, 0)
    pad2 = ConnectorPad().at(0, 0)

    model3ds = [
        Model3D("connector.step", rotation=(0, 0, 90)),
    ]


class Connector(Component):
    pin1 = Port()
    pin2 = Port()

    landpattern = ConnectorLandpattern()
    symbol = BoxSymbol()
```

Relative model paths resolve from the Python file containing the `Model3D(...)`
call. `{USER_PROJECT_ROOT}/models/part.step` resolves from the current working
directory at `Model3D` construction time; treat that as the project root only
when the build is launched from the project root. Absolute paths are used as-is.

For generator-produced landpatterns, do not subclass only to attach a STEP
model. Attach the `Model3D` attribute on the `Component` or on the existing
landpattern object when that is the lighter change.

## Board STEP Export

Full board STEP export has a CLI:

```bash
jitx design export legacy-step <module.path.Design>
```

This command requests STEP directly from the JITX runtime. The application UI
also exports STEP after the design builds and the 3D view is available.

The mechanical package provides drawing import and DXF export; board STEP export
is provided by JITX. The Stanza-era `export-step()` does not exist in the Python
runtime.

Checklist before exporting:

- Build succeeds with `jitx build <module.path.Design>`.
- Board shape and substrate thickness are correct.
- Important components have reachable `Model3D` entries.
- 3D view alignment is checked; adjust `Model3D(position=..., rotation=...,
  scale=...)` for off-origin, rotated, or unit-mismatched STEP files.

## Project Builder Notes

During project-builder work:

1. Import or inspect mechanical files in Phase 0 or Phase 3 with
   `jitx-mechanical`.
2. Ask the mounting-hole plating/electrical-intent question before import.
3. Reference the generated `Board` class in the architecture and top-level
   design.
4. Review report items to distinguish attached Board features from drawing-only
   regions, unapplied placements, and unsupported objects that need follow-up.
5. Use `Model3D` during component modeling and board STEP export during final
   mechanical review.
