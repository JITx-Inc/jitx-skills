"""A two-layer substrate, the smallest that translates."""

from jitx.stackup import Conductor, Dielectric, Stackup
from jitx.substrate import FabricationConstraints, Substrate


class Core(Dielectric):
    dielectric_coefficient = 4.0
    loss_tangent = 0.02
    thickness = 1.0


class Foil(Conductor):
    thickness = 0.035


class TwoLayer(Stackup):
    top = Foil(name="L1")
    core = Core(name="Core")
    bottom = Foil(name="L2")


class Rules(FabricationConstraints):
    min_copper_width = 0.1
    min_copper_copper_space = 0.1
    min_copper_hole_space = 0.2
    min_copper_edge_space = 0.3
    min_annular_ring = 0.1
    min_drill_diameter = 0.2
    min_pitch_leaded = 0.5
    min_pitch_bga = 0.5
    max_board_width = 400.0
    max_board_height = 400.0
    min_silkscreen_width = 0.15
    min_silk_solder_mask_space = 0.15
    min_silkscreen_text_height = 0.8
    solder_mask_registration = 0.05
    min_soldermask_opening = 0.1
    min_soldermask_bridge = 0.1
    min_th_pad_expand_outer = 0.1
    min_hole_to_hole = 0.3
    min_pth_pin_solder_clearance = 0.2


class TwoLayerSubstrate(Substrate):
    stackup = TwoLayer()
    constraints = Rules()
