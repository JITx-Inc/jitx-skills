"""Pellingham Circuits 4-layer substrates for the layout-constraints eval fixtures.

Values come from ``pellingham_lc_fab_sheet.md`` (fictional fab, capability sheet
PC-CAP-4L rev C); each line names its row. The substrates carry the fab floors
and the via and routing-structure definitions only. They carry no design rule:
adding rules is the runner's job.
"""

from jitx.board import Board
from jitx.shapes.composites import rectangle
from jitx.si import DifferentialRoutingStructure, RoutingStructure
from jitx.stackup import Conductor, Dielectric, Stackup
from jitx.substrate import FabricationConstraints, Substrate
from jitx.units import ohm
from jitx.via import Via, ViaType
from jitx.feature import Soldermask


class LcSoldermask(Dielectric):
    representing = Soldermask


class LcFR4(Dielectric):
    pass


class LcCopper(Conductor):
    pass


class LcStandard4Stackup(Stackup):
    """Row 1: four 1 oz layers."""

    top_surface = LcSoldermask(thickness=0.02)
    l1 = LcCopper(thickness=0.035, name="L1")
    d1 = LcFR4(thickness=0.2)
    l2 = LcCopper(thickness=0.035, name="L2")
    d2 = LcFR4(thickness=1.06)
    l3 = LcCopper(thickness=0.035, name="L3")
    d3 = LcFR4(thickness=0.2)
    l4 = LcCopper(thickness=0.035, name="L4")
    bottom_surface = LcSoldermask(thickness=0.02)


class LcHeavyInner4Stackup(Stackup):
    """Row 2: L2 is 2 oz, L3 is 0.5 oz."""

    top_surface = LcSoldermask(thickness=0.02)
    l1 = LcCopper(thickness=0.035, name="L1")
    d1 = LcFR4(thickness=0.2)
    l2 = LcCopper(thickness=0.070, name="L2")
    d2 = LcFR4(thickness=1.042)
    l3 = LcCopper(thickness=0.018, name="L3")
    d3 = LcFR4(thickness=0.2)
    l4 = LcCopper(thickness=0.035, name="L4")
    bottom_surface = LcSoldermask(thickness=0.02)


class LcFabConstraints(FabricationConstraints):
    min_copper_width = 0.100  # row 3
    min_copper_copper_space = 0.100  # row 4
    min_copper_hole_space = 0.200  # row 7
    min_copper_edge_space = 0.300  # row 8
    min_annular_ring = 0.125  # row 13
    min_drill_diameter = 0.200  # row 14
    min_hole_to_hole = 0.250  # row 15

    min_silkscreen_width = 0.127
    min_pitch_leaded = 0.35
    min_pitch_bga = 0.35
    max_board_width = 400.0
    max_board_height = 400.0
    min_silk_solder_mask_space = 0.15
    min_silkscreen_text_height = 1.0
    solder_mask_registration = 0.05
    min_soldermask_opening = 0.15
    min_soldermask_bridge = 0.1
    min_th_pad_expand_outer = 0.1
    min_pth_pin_solder_clearance = 3.0


class LcStandard4(Substrate):
    """Row 1 stackup, rows 3 to 15 floors."""

    stackup = LcStandard4Stackup()
    constraints = LcFabConstraints()

    class ThVia(Via):
        start_layer = 0
        stop_layer = -1
        diameter = 0.500  # row 11
        hole_diameter = 0.250  # row 12
        type = ViaType.MechanicalDrill

    # Grounded coplanar 50 ohm line on L1 over the L2 ground. Defined here,
    # applied to no net, and not fenced.
    CPWG_50 = RoutingStructure(
        name="CPWG_50",
        impedance=50 * ohm,
        layers={
            0: RoutingStructure.Layer(
                trace_width=0.30,
                clearance=0.20,
                velocity=1.6e11,
                insertion_loss=0.02,
            ),
        },
    )

    # 100 ohm edge-coupled pair on L1 over the L2 ground.
    DIFF_100 = DifferentialRoutingStructure(
        name="DIFF_100",
        impedance=100 * ohm,
        layers={
            0: DifferentialRoutingStructure.Layer(
                trace_width=0.15,
                pair_spacing=0.20,
                clearance=0.25,
                velocity=1.6e11,
                insertion_loss=0.02,
            ),
        },
        uncoupled_region=RoutingStructure(
            name="DIFF_100_uncoupled",
            impedance=50 * ohm,
            layers={
                0: RoutingStructure.Layer(
                    trace_width=0.15,
                    clearance=0.15,
                    velocity=1.6e11,
                    insertion_loss=0.02,
                ),
            },
        ),
    )

    # Narrow 50 ohm-class neck for the last segment into a fine-pitch pad.
    NECK_50 = RoutingStructure(
        name="NECK_50",
        impedance=50 * ohm,
        layers={
            0: RoutingStructure.Layer(
                trace_width=0.12,
                clearance=0.12,
                velocity=1.6e11,
                insertion_loss=0.03,
            ),
        },
    )


class LcHeavyInner4(Substrate):
    """Row 2 stackup (L2 2 oz, L3 0.5 oz), rows 3 to 15 floors."""

    stackup = LcHeavyInner4Stackup()
    constraints = LcFabConstraints()

    class ThVia(Via):
        start_layer = 0
        stop_layer = -1
        diameter = 0.500  # row 11
        hole_diameter = 0.250  # row 12
        type = ViaType.MechanicalDrill


class LcBoard(Board):
    """A 40 x 30 mm rectangle with square corners, centred on the origin."""

    shape = rectangle(40, 30)
