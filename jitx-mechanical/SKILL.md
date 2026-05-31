---
name: jitx-mechanical
description: Mechanical CAD interface for JITX designs. Use when the user asks to import DXF, EMN, IDF, IDX, or BDF mechanical data; set a board outline from mechanical CAD; export a JITX board to DXF; attach STEP models; export board STEP; or work with mechanical CAD data.
---

# JITX Mechanical Interface Skill

Use this skill for mechanical CAD interchange in JITX projects. The only external
mechanical import/export command to surface is `jitx-mechanical`.

## Setup

Environment setup is handled by the base `jitx` skill. Install the mechanical
package into the project venv when the command is missing:

```bash
pip install --extra-index-url "https://pypi.jitx.com/jitx/main/+simple" jitx-mechanical
```

The source repo is at `https://github.com/JITx-Inc/py-jitx-mechanical`. If the
package index is unavailable and GitHub access is available, install from
source:

```bash
pip install git+https://github.com/JITx-Inc/py-jitx-mechanical.git
```

Do not suggest the retired per-format commands or packages. Use
`jitx-mechanical inspect`, `jitx-mechanical import`, and
`jitx-mechanical export-dxf`.

## Workflow

| User wants to... | Command or API |
|---|---|
| Inspect DXF/EMN/IDF/IDX/BDF before import | `jitx-mechanical inspect` |
| Generate a Board-focused JITX Python module from mechanical data | `jitx-mechanical import` |
| Export JITX XML board data to DXF | `jitx-mechanical export-dxf` |
| Attach a STEP/STP model to a component | `jitx.model3d.Model3D` |
| Export a complete board assembly STEP | JITX `export-step()` or UI export |

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

`--hole-policy` is global for one import run, not per-hole. If the user states
mixed intent before import, or the generated report after import shows mixed
hole classification in one file, such as both NPTH board cutouts and
plated/electrical mounting holes, explain the limitation and help the user
choose a conservative next step: split the source/layers, run separate imports,
or manually edit the generated `BOARD_CUTOUTS` and companion component output.

## Inspect Mechanical Data

Use inspect before import to get a lightweight view of the source file.

```bash
jitx-mechanical inspect board.dxf
jitx-mechanical inspect board.emn
jitx-mechanical inspect board.idf --format idf
```

For DXF, inspect reports file version, source units, extents, layers, and entity
counts. For EMN/IDF/IDX/BDF-style IDF data, inspect runs the importer and prints
summary counts for outline, cutouts, holes, regions, annotations, placements,
and messages. Detailed classified follow-up data is written by `import` into the
Markdown/JSON report.

Supported import formats are DXF plus EMN/IDF/IDX/BDF-style IDF data. Use
`--format dxf|emn|idf|idx` only when the file extension is ambiguous or wrong.

## Import Board Geometry

Use import to generate a user-editable Python module and a Markdown/JSON report.

```bash
jitx-mechanical import board.dxf \
  --output src/myproject/board.py \
  --report src/myproject/board.report.md \
  --class-name ProjectBoard \
  --hole-policy cutout

jitx-mechanical import board.emn \
  --output src/myproject/board.py \
  --report src/myproject/board.report.md \
  --class-name ProjectBoard \
  --hole-policy component
```

### Import Options

| Option | Meaning |
|---|---|
| `--format auto|dxf|emn|idf|idx` | Override input format detection. |
| `-o`, `--output PATH` | Output Python module path. Defaults to input path with `.py`. |
| `--report PATH` | Output report path, `.md` or `.json`. Defaults beside output module. |
| `--class-name NAME` | Generated `Board` class name. Default: `ImportedBoard`. |
| `--hole-policy cutout|component` | Global policy for ambiguous/plated circular holes. Ask the user first. |
| `--unit mm|in|mil|cm|m` | Force DXF units. |
| `--layer-map LAYER=ROLE ...` | Map DXF layers to roles. |
| `--no-recenter` | Preserve source coordinates instead of recentering. |
| `--precision N` | Coordinate precision. Default: `4`. |

When `--hole-policy component` finds mechanical/plated holes,
`jitx-mechanical import` writes a companion module beside the board module named
`<output_stem>_components.py`. For example, importing to
`src/myproject/board.py` writes `src/myproject/board_components.py` when
component holes are present. The CLI prints a `Components:` line for that file.
The default `cutout` policy does not create the companion file.

Common DXF layer roles for `--layer-map` are `outline`, `cutout`, `hole`,
`keepout`, `soldermask`, `bend`, `height`, and `annotation`. Example:

```bash
jitx-mechanical import board.dxf \
  --layer-map OUTER_PROFILES=outline DRILL=hole SLOTS=cutout \
  --hole-policy component \
  --output src/myproject/board.py
```

### Generated Output Shape

The primary import output is Board-focused and does not generate a user-facing
`Design` class. With `--hole-policy component`, imports that contain
mechanical/plated holes also generate a companion `_components.py` module with
single-pin `Component` classes and a `MechanicalComponentsCircuit`.

```python
"""Board geometry imported from board.emn."""

from jitx.board import Board
from jitx.shapes.primitive import Circle, Polygon


class ProjectBoard(Board):
    shape = Polygon([
        (-50.0, -25.0),
        (50.0, -25.0),
        (50.0, 25.0),
        (-50.0, 25.0),
    ])


# Interior board cutout geometry imported from the source file.
# Attach these shapes to your board or circuit according to your JITX workflow.
BOARD_CUTOUTS = [
    Circle(radius=1.6).at(-40.0, -15.0),
]

MECHANICAL_ANNOTATIONS = []

# Mechanical/plated holes are emitted as connectable JITX Component
# classes in the companion `_components.py` module — instantiate
# `MechanicalComponentsCircuit` there and net its ports into your design.
```

With `--hole-policy component`, a companion module is generated when component
holes are present:

```python
"""Mechanical components (plated and mounting holes) imported from board.emn."""

from jitx.circuit import Circuit
from jitx.component import Component
from jitx.feature import Cutout, Soldermask
from jitx.landpattern import Landpattern, Pad
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


class _LP_MechanicalHole_2p0mm_PLATED(Landpattern):
    def __init__(self):
        self.p1 = _Pad_MechanicalHole_2p0mm_PLATED()


class MechanicalHole_2p0mm_PLATED(Component):
    """Single-pin through-hole Component."""
    reference_designator_prefix = "MH"
    p1 = Port()
    landpattern = _LP_MechanicalHole_2p0mm_PLATED()
    symbol = _SinglePinSymbol()


class MechanicalComponentsCircuit(Circuit):
    """All imported mechanical/plated holes placed at source coordinates."""
    ...
```

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

If `BOARD_CUTOUTS`, a companion components module, annotations, report regions,
or placements are present, do not pretend they are automatically wired into the
design. Explain what was imported and help the user decide whether to add board
cutouts, connect mechanical components, add keepouts, or add placement
constraints in their project code.

## Export DXF

Use `export-dxf` on the JITX board XML generated by a successful build.

```bash
jitx-mechanical export-dxf \
  designs/<design_name>/design-info/stable.design/board.xml \
  --output board_review.dxf
```

Filter layers when the mechanical team only needs part of the board data:

```bash
jitx-mechanical export-dxf board.xml \
  --output outline_and_drill.dxf \
  --layers BoardOutline Drill
```

Export filters:

| Option | Meaning |
|---|---|
| `--layers LAYER ...` | Emit only named DXF layers. |
| `--no-board-outline` | Omit board outline. |
| `--no-components` | Omit component placement shapes. |
| `--no-pads` | Omit pads. |
| `--no-drill` | Omit drill holes. |
| `--no-vias` | Omit vias. |
| `--no-copper` | Omit copper. |
| `--no-annotations` | Omit annotations. |

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

Full board STEP export is done through the JITX `export-step()` flow or the JITX
application UI after the design builds successfully and the 3D view is
available. The JITX export writes `<design-directory>/step/<design>.step`.
`jitx-mechanical` does not export STEP.

Checklist before exporting:

- Build succeeds with `python -m jitx build <module.path.Design>`.
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
4. Treat report items as follow-up constraints or modeling work, not as
   automatically applied design behavior.
5. Use `Model3D` during component modeling and board STEP export during final
   mechanical review.
