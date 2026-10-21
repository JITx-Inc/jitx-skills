"""Known-good test board for case B, written by hand from the case's report.

Test data for test_grade_pdf_report.py, not a golden reference: it holds the
values the grader expects and nothing more.
"""

from jitx.layerindex import Side
from jitx.si import DifferentialRoutingStructure, RoutingStructure
from jitx.stackup import Conductor, Dielectric, Stackup
from jitx.substrate import FabricationConstraints, Substrate
from jitx.units import ohm
from jitx.via import Backdrill, BackdrillSet, Via, ViaDiameter, ViaType
from jitxlib.physics import phase_velocity


class Mask(Dielectric):
    material_name = "CV-12"
    dielectric_coefficient = 3.60
    loss_tangent = 0.0200


class BuildUp(Dielectric):
    material_name = "AL-330"
    dielectric_coefficient = 3.30
    loss_tangent = 0.0025


class Core(Dielectric):
    material_name = "AL-360"
    dielectric_coefficient = 3.60
    loss_tangent = 0.0080


class Prepreg(Dielectric):
    material_name = "AL-355"
    dielectric_coefficient = 3.55
    loss_tangent = 0.0070


class ThickCore(Dielectric):
    material_name = "AL-370"
    dielectric_coefficient = 3.70
    loss_tangent = 0.0090


INNER_CU = 0.0350  # skill default: 1 oz finished copper; the report gives 1 oz only
FINISHED = 2.0320  # report: finished thickness, 80.00 mil
THICK_CORE = FINISHED - (
    2 * 0.0381 + 6 * INNER_CU + 2 * 0.0762 + 2 * 0.1270 + 2 * 0.1016
)  # derived: the report states no L5-L6 core thickness; finished less every other layer


class OuterFoil(Conductor):
    """Rz matte 2.5 um, drum 0.8 um."""

    thickness = 0.0381


class InnerFoil(Conductor):
    """1 oz. Rz matte 4.0 um, drum 2.0 um."""

    thickness = INNER_CU


class EightLayer(Stackup):
    top_mask = Mask(thickness=0.0127)
    l1 = OuterFoil(name="L1-Signal")
    bu1 = BuildUp(thickness=0.0762)
    l2 = InnerFoil(name="L2-Signal")
    bu2 = BuildUp(thickness=0.0762)
    l3 = InnerFoil(name="L3-GND")
    core1 = Core(thickness=0.1270)
    l4 = InnerFoil(name="L4-Signal")
    pp1 = Prepreg(thickness=0.1016)
    l5 = InnerFoil(name="L5-GND")
    thick = ThickCore(thickness=THICK_CORE)
    l6 = InnerFoil(name="L6-PWR")
    core2 = Core(thickness=0.1270)
    l7 = InnerFoil(name="L7-GND")
    pp2 = Prepreg(thickness=0.1016)
    l8 = OuterFoil(name="L8-Signal")
    bottom_mask = Mask(thickness=0.0127)


class Rules(FabricationConstraints):
    """Capability limits: mechanical drill 6.0 mil, mechanical aspect ratio
    10:1, laser aspect ratio 1.25:1, 2 stacked levels, dielectric 2.5 mil."""

    min_copper_width = 0.0762
    min_copper_copper_space = 0.0762
    min_copper_hole_space = 0.1524
    min_copper_edge_space = 0.2540
    min_annular_ring = 0.0635
    min_drill_diameter = 0.1016
    min_pitch_leaded = 0.4064
    min_pitch_bga = 0.3556
    max_board_width = 457.2
    max_board_height = 609.6
    min_silkscreen_width = 0.1270
    min_silk_solder_mask_space = 0.1016
    min_silkscreen_text_height = 0.7620
    solder_mask_registration = 0.0508
    min_soldermask_opening = 0.0762
    min_soldermask_bridge = 0.1016
    min_th_pad_expand_outer = 0.1016
    min_hole_to_hole = 0.2540
    min_pth_pin_solder_clearance = 0.2032


H_L1_L3 = 0.0762 + 0.0762


class TICSubstrate(Substrate):
    stackup = EightLayer()
    constraints = Rules()

    class UV1(Via):
        type = ViaType.LaserDrill
        start_layer = 0
        stop_layer = 1
        diameter = 0.2540
        hole_diameter = 0.1016
        filled = True
        via_in_pad = True

    class SV1(Via):
        type = ViaType.LaserDrill
        start_layer = 0
        stop_layer = 2
        diameter = 0.3048
        hole_diameter = 0.1524
        filled = True
        via_in_pad = True

    class BD1(Via):
        type = ViaType.MechanicalDrill
        start_layer = Side.Top
        stop_layer = 3
        diameter = 0.5080
        hole_diameter = 0.2540
        filled = True
        backdrill = BackdrillSet(
            bottom=Backdrill(
                diameter=0.4064,
                startpad_diameter=0.6096,
                solder_mask_opening=0.6604,
                copper_clearance=0.7112,
            )
        )

    class TH1(Via):
        type = ViaType.MechanicalDrill
        start_layer = Side.Top
        stop_layer = Side.Bottom
        diameter = 0.4064
        diameters = {(1, 2, 3, 4, 5, 6): ViaDiameter(0.4064, nfp=0.2794)}
        hole_diameter = 0.2032

    SE_50 = RoutingStructure(
        impedance=50 * ohm,
        layers={
            0: RoutingStructure.Layer(
                trace_width=0.2794,
                clearance=0.5588,
                velocity=phase_velocity(2.7000),
                insertion_loss=0.00600,
            ).reference({2: 3 * H_L1_L3}),
            3: RoutingStructure.Layer(
                trace_width=0.1143,
                clearance=0.2286,
                velocity=phase_velocity(3.5800),
                insertion_loss=0.00950,
            ).reference({2: 3 * 0.1270, 4: 3 * 0.1016}),
            -1: RoutingStructure.Layer(
                trace_width=0.1905,
                clearance=0.3810,
                velocity=phase_velocity(2.6600),
                insertion_loss=0.00680,
            ).reference({-2: 3 * 0.1016}),
        },
    )
    DIFF_100 = DifferentialRoutingStructure(
        impedance=100 * ohm,
        layers={
            3: DifferentialRoutingStructure.Layer(
                trace_width=0.1016,
                pair_spacing=0.1524,
                clearance=0.3048,
                velocity=phase_velocity(3.5800),
                insertion_loss=0.01050,
            ).reference({2: 3 * 0.1270, 4: 3 * 0.1016}),
            -1: DifferentialRoutingStructure.Layer(
                trace_width=0.1397,
                pair_spacing=0.1778,
                clearance=0.3556,
                velocity=phase_velocity(2.6200),
                insertion_loss=0.00750,
            ).reference({-2: 3 * 0.1016}),
        },
    )
