"""Pellingham Circuits 4-layer substrate for the code-layout eval fixtures.

Values come from ``pellingham_cl_fab_sheet.md`` (fictional fab, capability
sheet PC-CAP-4L rev D); each line names its row. The substrate carries the fab
floors, the via definitions and the routing structures. It carries no design
rule and applies no structure to a net.
"""

from jitx.board import Board
from jitx.constraints import ViaFencePattern
from jitx.feature import Soldermask
from jitx.shapes.composites import rectangle
from jitx.si import DifferentialRoutingStructure, RoutingStructure
from jitx.stackup import Conductor, Dielectric, Stackup
from jitx.substrate import FabricationConstraints, Substrate
from jitx.units import ohm
from jitx.via import Via, ViaType


class ClSoldermask(Dielectric):
    representing = Soldermask


class ClFR4(Dielectric):
    pass


class ClCopper(Conductor):
    pass


class ClStandard4Stackup(Stackup):
    """Row 1: four 1 oz layers."""

    top_surface = ClSoldermask(thickness=0.02)
    l1 = ClCopper(thickness=0.035, name="L1")
    d1 = ClFR4(thickness=0.2)
    l2 = ClCopper(thickness=0.035, name="L2")
    d2 = ClFR4(thickness=1.06)
    l3 = ClCopper(thickness=0.035, name="L3")
    d3 = ClFR4(thickness=0.2)
    l4 = ClCopper(thickness=0.035, name="L4")
    bottom_surface = ClSoldermask(thickness=0.02)


class ClFabConstraints(FabricationConstraints):
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


class ClStandard4(Substrate):
    """Row 1 stackup, rows 3 to 16."""

    stackup = ClStandard4Stackup()
    constraints = ClFabConstraints()

    class ThVia(Via):
        """Rows 11 and 12: open drill, not for use inside a pad."""

        start_layer = 0
        stop_layer = -1
        diameter = 0.500  # row 11
        hole_diameter = 0.250  # row 12
        type = ViaType.MechanicalDrill
        via_in_pad = False

    class VipVia(Via):
        """Row 16: filled and capped, accepted inside an SMD pad."""

        start_layer = 0
        stop_layer = -1
        diameter = 0.450  # row 16
        hole_diameter = 0.200  # row 16
        type = ViaType.MechanicalDrill
        filled = True
        via_in_pad = True

    # 50 ohm microstrip on L1 over the L2 ground.
    MS_50 = RoutingStructure(
        name="MS_50",
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

    # Grounded coplanar 50 ohm line on L1, fenced with two rows of ThVia on
    # each side, rows 0.60 and 1.20 from the trace edge, 1.0 pitch.
    CPWG_50_FENCED = RoutingStructure(
        name="CPWG_50_FENCED",
        impedance=50 * ohm,
        layers={
            0: RoutingStructure.Layer(
                trace_width=0.30,
                clearance=0.20,
                velocity=1.6e11,
                insertion_loss=0.02,
            ).fence(
                ThVia,
                ViaFencePattern(pitch=1.0, offset=0.6, initial_offset=0.6, num_rows=2),
                reference_layer=0,
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

    # The pair's narrow form for the ball field of a fine-pitch BGA: 0.08
    # traces, 0.10 apart, 0.05 clearance. Its width and gap sit below rows 3
    # and 4.
    DIFF_100_FIELD = DifferentialRoutingStructure(
        name="DIFF_100_FIELD",
        impedance=100 * ohm,
        layers={
            0: DifferentialRoutingStructure.Layer(
                trace_width=0.08,
                pair_spacing=0.10,
                clearance=0.05,
                velocity=1.6e11,
                insertion_loss=0.04,
            ),
        },
        uncoupled_region=RoutingStructure(
            name="DIFF_100_FIELD_uncoupled",
            impedance=50 * ohm,
            layers={
                0: RoutingStructure.Layer(
                    trace_width=0.08,
                    clearance=0.05,
                    velocity=1.6e11,
                    insertion_loss=0.04,
                ),
            },
        ),
    )


class ClBoard(Board):
    """A 60 x 40 mm rectangle with square corners, centred on the origin."""

    shape = rectangle(60, 40)


BOARD_W = 60.0
BOARD_H = 40.0
