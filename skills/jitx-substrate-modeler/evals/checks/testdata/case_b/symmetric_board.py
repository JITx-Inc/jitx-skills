"""Known-good test board for the symmetric no-report variant of case B.

Test data for test_grade_pdf_report.py, not a golden reference. With no report,
every value here is a stand-in default.
"""

from jitx.stackup import Conductor, Dielectric, Symmetric
from jitx.substrate import FabricationConstraints, Substrate


class FR4(Dielectric):
    dielectric_coefficient = 4.4
    loss_tangent = 0.02


class Mask(Dielectric):
    dielectric_coefficient = 3.5
    loss_tangent = 0.02


class Foil(Conductor):
    thickness = 0.035


class FourLayer(Symmetric):
    top_mask = Mask(thickness=0.0127)
    top = Foil(name="L1")
    prepreg = FR4(thickness=0.2)
    inner = Foil(name="L2")
    core = FR4(thickness=1.065)


class Rules(FabricationConstraints):
    min_copper_width = 0.127
    min_copper_copper_space = 0.127
    min_copper_hole_space = 0.2
    min_copper_edge_space = 0.3
    min_annular_ring = 0.13
    min_drill_diameter = 0.3
    min_pitch_leaded = 0.5
    min_pitch_bga = 0.5
    max_board_width = 500.0
    max_board_height = 500.0
    min_silkscreen_width = 0.15
    min_silk_solder_mask_space = 0.15
    min_silkscreen_text_height = 1.0
    solder_mask_registration = 0.05
    min_soldermask_opening = 0.1
    min_soldermask_bridge = 0.1
    min_th_pad_expand_outer = 0.1
    min_hole_to_hole = 0.25
    min_pth_pin_solder_clearance = 0.1


class FourLayerFR4(Substrate):
    stackup = FourLayer()
    constraints = Rules()
