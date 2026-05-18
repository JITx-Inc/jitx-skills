"""Canonical 4-layer FR4 substrate template.

Copy this file into your project (e.g. as `substrate.py`), rename the
classes to match your design, and adjust dielectric / copper thicknesses
to match your fabrication house's spec sheet.

Use this when:
- the design needs a 4-layer FR4 stackup with 50 ohm single-ended +
  100 ohm differential routing, AND
- `jitxlib.jlcpcb` is not available in the installed jitx wheel
  (notably the 4.1.0a7 pre-release does not ship it), OR
- the target fab is not JLCPCB.

The values below match a typical 4-layer 1.6mm board with 1080 prepreg
and 1 oz outer / 0.5 oz inner copper. Override `prepreg_thickness`,
`core_thickness`, etc. on a copy if your fab differs.

Verified against jitx 4.1.0a7 / launcher 4.1.0-develop.15 (2026-05-14).
"""

from jitx.container import inline
from jitx.si import (
    DifferentialRoutingStructure,
    RoutingStructure,
    symmetric_routing_layers,
)
from jitx.stackup import Conductor, Dielectric, Symmetric
from jitx.substrate import FabricationConstraints, Substrate
from jitx.units import ohm
from jitx.via import Via, ViaType

from jitxlib.physics import phase_velocity


# ----- Materials --------------------------------------------------------

# 1080-prepreg dielectric constants — JLC-PCB published values.
# Adjust if your fab publishes different numbers.
#
# Naming convention: Dk (dielectric constant / relative permittivity Er) is
# dimensionless; Df (dissipation factor / loss tangent tan δ) is dimensionless.
# These are *material* properties, distinct from the trace-level insertion
# loss (dB/mm) used by RoutingStructure.Layer.insertion_loss below.
Dk_1080 = 3.91     # dielectric constant (Er)
Df_1080 = 0.0178   # loss tangent (Df)

# Per-mm insertion loss for a 50-ohm microstrip on this stack. Order of
# magnitude only — replace with a field-solver number for high-speed work.
# Units: dB / mm.
insertion_loss_db_per_mm = 0.018


class FR4_1080(Dielectric):
    """FR4 Prepreg 1080. Tune dielectric_coefficient / loss_tangent
    to your fab's published values."""

    dielectric_coefficient = Dk_1080  # @ 1 GHz
    loss_tangent = Df_1080  # @ 1 GHz


class FR4_Core(Dielectric):
    """FR4 Core. Adjust to your fab's spec."""

    dielectric_coefficient = 4.4  # @ 1 GHz, typical
    loss_tangent = 0.02  # @ 1 GHz, typical


# 1 oz outer / 0.5 oz inner copper. Override thicknesses for non-1oz designs.
cu_1oz = Conductor(thickness=0.035)
cu_halfoz = Conductor(thickness=0.0175)


# Effective mid-stack velocity for 50 ohm single-ended traces on outer layer.
# This approximation uses (Er + 1) / 2 — adequate for non-critical designs.
# For high-speed work, use full-wave field-solver output.
med_velocity = phase_velocity((Dk_1080 + 1) / 2)


# ----- Fabrication constraints -----------------------------------------


class FabRules(FabricationConstraints):
    """Sensible defaults for a typical 4-layer FR4 fab. Tighten or
    relax to match your fab's published capabilities."""

    # copper rules
    min_copper_width = 0.09
    min_copper_copper_space = 0.09
    min_copper_hole_space = 0.254
    min_copper_edge_space = 0.3
    # soldermask rules
    solder_mask_registration = 0.05
    min_soldermask_opening = 0.0
    min_soldermask_bridge = 0.08
    # silkscreen rules
    min_silkscreen_width = 0.153
    min_silk_solder_mask_space = 0.15
    min_silkscreen_text_height = 1.0
    # via rules
    min_annular_ring = 0.13
    min_drill_diameter = 0.3
    # pitch rules
    min_pitch_leaded = 0.127 + 0.09
    min_pitch_bga = 0.377
    # pad rules
    min_hole_to_hole = 0.5
    min_pth_pin_solder_clearance = 0
    min_th_pad_expand_outer = 0.2
    # board size
    max_board_width = 500
    max_board_height = 400


# ----- Substrate --------------------------------------------------------


class FourLayerFR4Substrate(Substrate):
    """4-layer FR4 substrate with mechanical-drill via and 50 ohm
    single-ended + 100 ohm differential routing structures.

    Layer order (top to bottom, mirrored by Symmetric):
        soldermask / top (1oz) / FR4-1080 prepreg / inner (0.5oz) / FR4 core (1.265mm)
    Inner symmetrically mirrored: prepreg / inner-bottom / soldermask
    """

    @inline
    class stackup(Symmetric):
        """4 layer stackup with 1080 prepreg."""

        top = cu_1oz
        prepreg = FR4_1080(thickness=0.0764)
        inner = cu_halfoz
        core = FR4_Core(thickness=1.265)

    constraints = FabRules()

    class StdVia(Via):
        """Top-to-bottom mechanical-drill via."""

        name = "Standard Through-Hole Via"
        start_layer = 0
        stop_layer = -1
        diameter = 0.45
        hole_diameter = 0.3
        type = ViaType.MechanicalDrill
        via_in_pad = False

    RS_50 = RoutingStructure(
        impedance=50 * ohm,
        layers=symmetric_routing_layers(
            {
                0: RoutingStructure.Layer(
                    trace_width=0.1176,
                    clearance=0.2,
                    velocity=med_velocity,
                    insertion_loss=insertion_loss_db_per_mm,
                )
            }
        ),
    )

    DRS_100 = DifferentialRoutingStructure(
        impedance=100 * ohm,
        name="100 Ohm Differential Routing Structure",
        layers=symmetric_routing_layers(
            {
                0: DifferentialRoutingStructure.Layer(
                    trace_width=0.09,
                    pair_spacing=0.137,
                    clearance=0.2,
                    velocity=med_velocity,
                    insertion_loss=insertion_loss_db_per_mm,
                )
            }
        ),
        uncoupled_region=RoutingStructure(
            impedance=100 * ohm,
            name="100 Ohm Differential Routing Structure, Uncoupled",
            layers=symmetric_routing_layers(
                {
                    0: RoutingStructure.Layer(
                        trace_width=0.09,
                        clearance=0.2,
                        velocity=med_velocity,
                        insertion_loss=insertion_loss_db_per_mm,
                    )
                }
            ),
        ),
    )
