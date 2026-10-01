"""Layer-2 and bottom ground pours, stitched, with an antenna keepout.

Four-layer board on the JLCPCB ``JLC04161H_7628`` stackup (top, inner-1,
inner-2, bottom). "Layer 2" is conductor index 1, the first inner layer;
"bottom" is index -1, which the runtime normalizes to 3 on this substrate.

What this module authors, and the owner each decision came from:

Pour outlines. Board outlines get no automatic pullback, so both pours are the
board profile buffered inward by the substrate's ``min_copper_edge_space``
(0.3 mm on ``JLCPCBRules``). That is the circuit-builder inward-buffer recipe
(``jitx-circuit-builder``, references/advanced-patterns.md, "Pours"), including
its emptiness and geom-type guard. ``isolate=`` is deprecated on 4.4 and is not
used here.

Anchoring. ``jitx-physical-layout`` SKILL.md, "Pour and stitch runtime
observations": a same-net pad or via must reach each pour layer before
stitching, top-side pads cannot anchor inner or bottom pours, and
solver-emitted stitches cannot keep a pour alive. An unanchored inner pour was
observed on 4.4.0 emitting nine vias and still capturing ``Empty()``. So four
through vias (``StdViaPreferred``, layer 0 to -1) are placed explicitly, stored
structurally on the circuit, and joined directly to ``GND``. They are anchors,
not stitching.

Stitching. Expressed as a rule, not as placed geometry: a ``Tag`` on both pours
plus ``design_constraint(...).stitch_via(...)``. Shape follows the working
reference design ``jitxexamples.patterns.stitch_via``, whose receipt shows the
via class object itself is what the rule resolves.

Antenna keepout. ``KeepOut`` flags are read from installed ``jitx/feature.py``:
``pour=True`` keeps pours out, ``via=True`` avoids auto-placed vias,
``route=True`` disallows autorouter traces. All three are wanted under an
antenna, so all three are set. The keepout covers all four conductor layers.
``KeepOut(pour=True)`` wins at every pour rank, so no rank juggling is needed.

Antenna copper. Netless ``OverlappableCopper`` on layer 0, per the
``jitx-physical-layout`` copper-selection rules: it is ignored by routing and
overlap checks and is not taggable. There is no matching feed component in this
probe, so the radiator carries no net; that is stated as an open item in the
report rather than papered over.

Rules other than the stitch rule (default trace width, copper clearance,
thermal relief, power width) belong to ``jitx-layout-constraints`` and are out
of scope for this task; none are declared here.
"""

from __future__ import annotations

from jitx import Circuit, Net, OverlappableCopper, Pour, current
from jitx.board import Board
from jitx.constraints import SquareViaStitchGrid, Tag, design_constraint
from jitx.design import Design
from jitx.feature import KeepOut
from jitx.layerindex import LayerSet
from jitx.shapes.composites import rectangle
from jitxlib.jlcpcb import JLC04161H_7628

# --- Board and stackup -------------------------------------------------------

BOARD_W = 50.0  # skill default: probe board width, mm.
BOARD_H = 30.0  # skill default: probe board height, mm.

# Conductor indices on a 4-layer stackup. 0 top, 1 "layer 2" (first inner),
# 2 (second inner), -1 bottom.
LAYER_TOP = 0
LAYER_2 = 1
LAYER_BOTTOM = -1
CONDUCTOR_LAYERS = (0, 1, 2, -1)

# JLCPCBRules.min_copper_edge_space, jitxlib/jlcpcb/rules.py.
EDGE_SPACE = JLC04161H_7628.constraints.min_copper_edge_space

# --- Antenna region ----------------------------------------------------------

# Top-right corner of the board. Board spans x in [-25, 25], y in [-15, 15];
# this region spans x in [6, 24], y in [4, 14], so it clears the outline by
# 1.0 mm on both sides it approaches.
ANTENNA_KEEPOUT_W = 18.0
ANTENNA_KEEPOUT_H = 10.0
ANTENNA_KEEPOUT_CENTER = (15.0, 9.0)

# --- Stitching ---------------------------------------------------------------

STITCH_PITCH = 4.0  # skill default: 4.0 mm stitch-via centre pitch.
STITCH_INSET = 1.0  # skill default: 1.0 mm boundary inset for the grid.
STITCH_VIA = JLC04161H_7628.StdViaPreferred  # 0.45 mm pad, 0.3 mm hole, 0 to -1.

# Explicit GND anchors, all west of the antenna region so none lands inside the
# keepout. Each is a through via and therefore reaches both pour layers.
ANCHOR_VIA_POSITIONS = (
    (-20.0, -10.0),
    (-20.0, 10.0),
    (-4.0, -10.0),
    (-4.0, 10.0),
)


class GndPourTag(Tag):
    """Marks the ground pours the stitch rule selects."""


class StitchedBoard(Board):
    shape = rectangle(BOARD_W, BOARD_H)
    # Without this the build warns "Using board outline as signal boundary:
    # Missing signal boundary". Pulled back by the same fabrication
    # copper-to-edge clearance the pours use.
    signal_area = rectangle(BOARD_W - 2.0 * EDGE_SPACE, BOARD_H - 2.0 * EDGE_SPACE)


def _edge_pulled_back_outline():
    """The board profile buffered inward by the fabrication edge clearance.

    jitx-circuit-builder, advanced-patterns "Pours": board outlines receive no
    automatic pullback. The guard is part of that recipe, and the shapely
    emptiness/geom-type assertion is the general rule from
    jitx-physical-layout SKILL.md before feeding a fabrication feature.
    """
    fab = current.design.substrate.constraints
    outline = current.design.board.shape.to_shapely().buffer(-fab.min_copper_edge_space)
    if outline.g.is_empty or outline.g.geom_type not in ("Polygon", "MultiPolygon"):
        raise ValueError("board edge pullback removed or invalidated the pour outline")
    return outline


class GroundPlaneCircuit(Circuit):
    """Board-wide ground pours, their anchors, the antenna and its keepout.

    Board-wide pours belong at the top level of the circuit tree, and the local
    antenna keepout is kept beside the antenna copper it must follow, per the
    jitx-physical-layout workflow step 4.
    """

    place_anchor_vias = True
    """Whether the explicit GND through vias are placed. The no-anchor control
    flips this and changes nothing else."""

    def __init__(self) -> None:
        outline = _edge_pulled_back_outline()

        # Ground pours. rank=1 rather than the default 0 so the fill is
        # rendered as real copper rather than treated as a cullable
        # background, following the gnd_pours in
        # jitxexamples.demos.si_bga_optimization.bga_escape.
        self.gnd_pour_l2 = Pour(outline, layer=LAYER_2, rank=1)
        self.gnd_pour_bottom = Pour(outline, layer=LAYER_BOTTOM, rank=1)
        GndPourTag().assign(self.gnd_pour_l2)
        GndPourTag().assign(self.gnd_pour_bottom)

        # Anchors. Structural on the circuit and joined directly to the net:
        # jitx-physical-layout workflow step 3 (a via reachable only through a
        # Net is dropped from downstream exports).
        self.anchor_vias = (
            [STITCH_VIA().at(x, y) for x, y in ANCHOR_VIA_POSITIONS]
            if self.place_anchor_vias
            else []
        )

        self.GND = Net(
            [self.gnd_pour_l2, self.gnd_pour_bottom, *self.anchor_vias],
            name="GND",
        )

        # Antenna radiator: netless OverlappableCopper on the top layer, wholly
        # inside the keepout region.
        self.antenna_radiator = OverlappableCopper(
            rectangle(16.0, 1.0).at(15.0, 12.0), layer=LAYER_TOP
        )
        self.antenna_feed_leg = OverlappableCopper(
            rectangle(0.5, 5.0).at(10.0, 9.0), layer=LAYER_TOP
        )
        self.antenna_short_stub = OverlappableCopper(
            rectangle(0.5, 5.0).at(8.0, 9.0), layer=LAYER_TOP
        )

        # One keepout object per layer rather than a single multi-layer set, so
        # a per-layer witness exists in capture for each conductor.
        keepout_shape = rectangle(ANTENNA_KEEPOUT_W, ANTENNA_KEEPOUT_H).at(
            *ANTENNA_KEEPOUT_CENTER
        )
        self.antenna_keepouts = [
            KeepOut(
                shape=keepout_shape,
                layers=LayerSet(layer),
                pour=True,
                via=True,
                route=True,
            )
            for layer in CONDUCTOR_LAYERS
        ]


class StitchedGroundDesign(Design):
    board = StitchedBoard()
    substrate = JLC04161H_7628()
    circuit = GroundPlaneCircuit()

    def __init__(self) -> None:
        self.rules = [
            design_constraint(GndPourTag()).stitch_via(
                STITCH_VIA,
                SquareViaStitchGrid(pitch=STITCH_PITCH, inset=STITCH_INSET),
            )
        ]


class ControlNoStitchRuleDesign(Design):
    """Same board, substrate and circuit with no stitch rule.

    Identical via counts across variants are only evidence if the count is zero
    without the rule. This is the control the stitch_via reference design uses
    for exactly that reason.
    """

    board = StitchedBoard()
    substrate = JLC04161H_7628()
    circuit = GroundPlaneCircuit()

    def __init__(self) -> None:
        self.rules = []


class UnanchoredGroundCircuit(GroundPlaneCircuit):
    """GroundPlaneCircuit with the anchor vias removed and nothing else.

    Same pours, same tag, same antenna copper, same keepouts, so the control
    differs from the main design in exactly one variable.
    """

    place_anchor_vias = False


class ControlNoAnchorDesign(Design):
    """Same pours and stitch rule with no explicit anchor vias.

    Discriminates "the pours realized because the rule stitched them" from "the
    pours realized because a placed through via anchored them", which is the
    4.4.0 behaviour the skill records.
    """

    board = StitchedBoard()
    substrate = JLC04161H_7628()
    circuit = UnanchoredGroundCircuit()

    def __init__(self) -> None:
        self.rules = [
            design_constraint(GndPourTag()).stitch_via(
                STITCH_VIA,
                SquareViaStitchGrid(pitch=STITCH_PITCH, inset=STITCH_INSET),
            )
        ]
