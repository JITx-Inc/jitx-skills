"""Known-good test substrate for case C, written by hand from the case's report
and spec.

Test data for test_grade_fenced_rf.py, not a golden reference: it holds the
values the grader expects and nothing more.
"""

from jitx.constraints import Tag, ViaFencePattern, design_constraint
from jitx.feature import KeepOut
from jitx.layerindex import LayerSet, Side
from jitx.si import DifferentialRoutingStructure, RoutingStructure
from jitx.stackup import Conductor, Dielectric, Stackup
from jitx.substrate import FabricationConstraints, Substrate
from jitx.units import ohm
from jitx.via import Via, ViaType
from jitxlib.physics import phase_velocity


class Mask(Dielectric):
    material_name = "PS-40"
    dielectric_coefficient = 3.60
    loss_tangent = 0.0200


class RF(Dielectric):
    material_name = "PL-350"
    dielectric_coefficient = 3.50
    loss_tangent = 0.0030


class Core(Dielectric):
    material_name = "PL-420"
    dielectric_coefficient = 4.20
    loss_tangent = 0.0150


class Prepreg(Dielectric):
    material_name = "PL-410"
    dielectric_coefficient = 4.10
    loss_tangent = 0.0160


class Foil(Conductor):
    thickness = 0.0350
    roughness = 0.0020


class Six(Stackup):
    m1 = Mask(thickness=0.0150)
    l1 = Foil(name="L1-Signal")
    d1 = RF(thickness=0.1000)
    l2 = Foil(name="L2-GND")
    d2 = Core(thickness=0.2000)
    l3 = Foil(name="L3-GND")
    d3 = Prepreg(thickness=0.4000)
    l4 = Foil(name="L4-Signal")
    d4 = Core(thickness=0.2000)
    l5 = Foil(name="L5-GND")
    d5 = RF(thickness=0.1000)
    l6 = Foil(name="L6-Signal")
    m2 = Mask(thickness=0.0150)


class Rules(FabricationConstraints):
    min_copper_width = 0.075
    min_copper_copper_space = 0.075
    min_copper_hole_space = 0.150
    min_copper_edge_space = 0.300
    min_annular_ring = 0.075
    min_drill_diameter = 0.100
    min_pitch_leaded = 0.400
    min_pitch_bga = 0.400
    max_board_width = 450.0
    max_board_height = 600.0
    min_silkscreen_width = 0.120
    min_silk_solder_mask_space = 0.100
    min_silkscreen_text_height = 0.700
    solder_mask_registration = 0.040
    min_soldermask_opening = 0.080
    min_soldermask_bridge = 0.090
    min_th_pad_expand_outer = 0.100
    min_hole_to_hole = 0.250
    min_pth_pin_solder_clearance = 0.200


class CavityFence(Tag):
    """Pours with this tag get fence vias along their outline."""


class RFSubstrate(Substrate):
    stackup = Six()
    constraints = Rules()

    class TH1(Via):
        type = ViaType.MechanicalDrill
        start_layer = Side.Top
        stop_layer = Side.Bottom
        diameter = 0.550
        hole_diameter = 0.250

    class UV1(Via):
        type = ViaType.LaserDrill
        start_layer = 0
        stop_layer = 1
        diameter = 0.275
        hole_diameter = 0.125
        filled = True
        via_in_pad = True

    class UV2(Via):
        type = ViaType.LaserDrill
        start_layer = -1
        stop_layer = -2
        diameter = 0.275
        hole_diameter = 0.125
        filled = True
        via_in_pad = True

    CPW_FENCE = ViaFencePattern(pitch=0.50, offset=0.40, num_rows=1)
    PAIR_FENCE = ViaFencePattern(pitch=0.50, offset=0.60, num_rows=1)

    RS_50 = RoutingStructure(
        impedance=50 * ohm,
        layers={
            0: RoutingStructure.Layer(
                trace_width=0.28,
                clearance=0.15,
                velocity=phase_velocity(2.91),
                insertion_loss=0.006,
            )
            .geometry(KeepOut, 0.60, layers=LayerSet(1), pour=True)
            .reference({2: 3 * 0.300})
            .fence(UV1, CPW_FENCE, reference_layer=1)
        },
    )
    DRS_100 = DifferentialRoutingStructure(
        impedance=100 * ohm,
        layers={
            0: DifferentialRoutingStructure.Layer(
                trace_width=0.16,
                pair_spacing=0.20,
                clearance=0.40,
                velocity=phase_velocity(2.68),
                insertion_loss=0.007,
            )
            .reference({1: 3 * 0.100})
            .fence(UV1, PAIR_FENCE, reference_layer=1),
            -1: DifferentialRoutingStructure.Layer(
                trace_width=0.16,
                pair_spacing=0.20,
                clearance=0.40,
                velocity=phase_velocity(2.68),
                insertion_loss=0.007,
            )
            .reference({-2: 3 * 0.100})
            .fence(UV2, PAIR_FENCE, reference_layer=-2),
        },
    )
    cavity_fence = design_constraint(CavityFence(), priority=20).fence_via(
        UV1, ViaFencePattern(pitch=0.50, offset=0.30, num_rows=1)
    )
