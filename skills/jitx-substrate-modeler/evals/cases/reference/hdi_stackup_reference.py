"""20-layer HDI substrate, generated from a fabrication-house stackup report.

Ground truth
------------
Every number in this file is transcribed from one CSV row of

    ACME Circuit Technology quote ACME-Q26-0417, Rev B (2026-07-14)
    evals/cases/fixtures/ACME-HDI20_Fab-Stackup_RevB.csv

Nothing here is estimated or carried over from another design. If you re-issue
the stackup, change the CSV first and re-derive — never edit these constants
directly.

Unit conversions the CSV forces
-------------------------------
JITX is millimetres throughout, and has no field for several things a fab
quotes, so three conversions happen on the way in:

* **mils -> mm.** The report's primary units are mils; it gives mm alongside
  and declares mm controlling where the two disagree. We use the mm column.
* **oz -> mm.** ``Conductor`` has no copper-weight concept. Foil weight is
  expressed only as ``thickness``: 1 oz = 0.0350 mm, 1/2 oz = 0.0175 mm. The
  outer layers add 18 um of panel plating on top of the 1/2 oz base foil, so
  they are 0.0355 mm, not 0.0175 mm — use the report's *finished* thickness
  column, never the nominal weight.
* **Rz um -> mm.** The report states roughness as Rz in micrometres, matte and
  drum side separately. ``Conductor.roughness`` is a single scalar in mm, so we
  take the matte (bonding) side — the surface that faces the dielectric and
  dominates conductor loss — and divide by 1000.

What JITX cannot hold
---------------------
Things the report states that have no field in the API, and therefore survive
only in these docstrings. This list is the result of walking the report column
by column; if a re-issue adds a column, walk it again rather than assuming the
list is closed.

* **Dk/Df frequency.** ``Dielectric`` stores bare scalars. The report quotes
  Dk and Df at 10 GHz.
* **Roughness model.** ``Conductor.roughness`` is one scalar — there is no
  Huray or Hammerstad selection. The drum-side Rz and any Cannonball-Huray
  nodule parameters have to live in the EM tool's own stackup override.
* **Fill material.** ``Via.filled`` is a boolean. The report distinguishes
  copper-filled microvias from resin-filled mechanical drills; both become
  ``filled = True``.
* **Via capping.** The report caps all twelve structures. There is no capping
  attribute, so it is recorded in the via docstrings only.
* **Reference-plane widths.** ``RoutingStructure.Layer.reference`` wants a
  desired plane width per layer. The report names *which* planes reference each
  line, in the IMPEDANCE ``Ref_layers`` column, and never how wide they are, so
  every plane below is declared with a ``None`` width — see ``_se_layers``.
* **Impedance and thickness tolerances.** Both are ±10% in the report.
  ``RoutingStructure.impedance`` and ``Material.thickness`` are scalars.
* **Copper weight.** ``Conductor`` has no ``oz`` concept; see the conversions
  above. The nominal weight survives only in the foil-class docstrings.

Layer structure
---------------
20 copper layers, mirror-symmetric about a 0.800 mm core, built 5 + 10 + 5: a
10-layer sub-composite (L6..L15) with five sequential build-up laminations per
side. Signal layers are L1/L20 (surface microstrip) and L3/L5/L7/L9 plus the
mirrors L18/L16/L14/L12 (symmetric stripline); everything else is a GND plane.

Declared as an explicit :py:class:`~jitx.stackup.Stackup`, not ``Symmetric``.
``Symmetric`` would halve the source but leaves the bottom half as anonymous
proxies with no named Python attributes, and the report describes both halves
explicitly — including per-layer foil assignments that a reader needs to be
able to point at.

Conductor-index map (what vias and routing structures reference)
----------------------------------------------------------------
Indices count **copper layers only** — soldermask and dielectrics are not
indexed. ``0`` is L1 and ``-1`` is L20, so with 20 copper layers::

    L1 = 0    L6  = 5     L11 = 10    L16 = 15 = -5
    L2 = 1    L7  = 6     L12 = 11    L17 = 16 = -4
    L3 = 2    L8  = 7     L13 = 12    L18 = 17 = -3
    L4 = 3    L9  = 8     L14 = 13    L19 = 18 = -2
    L5 = 4    L10 = 9     L15 = 14    L20 = 19 = -1

Negative indices are used for the bottom half so the mirror symmetry is
readable at the call site.

No signal-integrity via models
------------------------------
The vias below carry **no** ``models=`` entry, deliberately. A fab report
supplies geometry, not electrical models, and there is no honest way to derive
via inductance and capacitance from a drill table. JITX will insert placeholder
models, which means any timing or insertion-loss constraint routed through a
via will be reported as unsatisfied — that is the correct signal. Obtain
EM-simulated or measured models per layer pair before relying on SI
constraints, and add them here then.

Spare routing layers
--------------------
L7, L9, L12 and L14 are signal-capable stripline layers that Rev B specifies
no controlled-impedance structure for, so no routing structure covers them.
They are reachable only through ``BuriedVia_L6_L15`` and ``THVia_L1_L20``.

Three API ambiguities this file had to resolve
---------------------------------------------
All three are open questions against the JITX API, tracked under "API findings"
in the kit's internal working notes [pointer redacted for the shipped copy] along with further findings
that don't bear on this file's own choices.

1. **``Conductor.roughness`` has no documented unit.** ``jitxlib.materials``
   uses mm-scale values (``0.003``–``0.005``, i.e. 3–5 µm), and other JITX
   lengths are millimetres throughout, so this file treats roughness as **mm**
   and converts the report's µm accordingly. The attribute's docstring should
   state the unit.
2. **``DifferentialRoutingStructure.Layer.pair_spacing`` is ambiguous.** Its
   docstring says only "internal spacing within the differential pair", without
   saying whether that is edge-to-edge or centre-to-centre. This file uses
   **edge-to-edge**, matching both the substrate-modeler skill and the report's
   own explicit statement.
3. **A reference plane of unstated width is expressible but not typeable.**
   ``RoutingStructure.Layer.reference`` takes either a scalar layer plus a
   ``desired_width``, or a mapping of layers to widths. The report names which
   planes reference each line and never how wide they are, and only the mapping
   form accepts that: the scalar form raises ``TypeError: Must specify
   desired_width if layer is not a mapping``, while the mapping accepts ``None``
   values at runtime and translates correctly. But the parameter is annotated
   ``Mapping[int, float]``, so the one working form fails ``pyright`` — hence the
   two ``reportArgumentType`` suppressions below. Annotating it
   ``Mapping[int, float | None]`` would close the gap. Inventing a width instead
   would be the one thing this file must not do: put a number in the design that
   no CSV row backs.
"""

from __future__ import annotations

from jitx.board import Board
from jitx.layerindex import Side
from jitx.shapes.composites import rectangle
from jitx.si import DifferentialRoutingStructure, RoutingStructure
from jitx.stackup import Conductor, Dielectric, Stackup
from jitx.substrate import FabricationConstraints, Substrate
from jitx.units import ohm
from jitx.via import Via, ViaType
from jitxlib.physics import phase_velocity

FAB_REPORT = "ACME-Q26-0417 Rev B"
"""Quote and revision every constant in this module is transcribed from."""

# ---------------------------------------------------------------------------
# Materials — one class per MATERIALS_DIELECTRIC / MATERIALS_COPPER row
# ---------------------------------------------------------------------------
# Thickness is a class attribute rather than a constructor argument because
# each of these materials appears at exactly one thickness in this stackup.
# Material.__init__ rejects both at once.


class Soldermask(Dielectric):
    """D-SM — LPI soldermask. Dk 3.80 / Df 0.0200. 0.50 mil."""

    material_name = "LPI soldermask"
    dielectric_coefficient = 3.80
    loss_tangent = 0.0200
    thickness = 0.0127


class BuildUpPrepreg(Dielectric):
    """D-BU — Isola Astra MT77 prepreg, 1035 glass, 76% resin.

    Dk 2.96 / Df 0.0016 at 10 GHz. 3.94 mil pressed. The high resin content is
    what makes the layer laser-drillable; it is also why Rev B's Dk dropped
    from 3.00 (1078 glass) and every controlled line width had to be re-solved.

    Carries all ten build-up laminations, which is every dielectric adjacent to
    a *controlled-impedance* routing layer (L1/L3/L5 and their mirrors), so it
    is the only dielectric the impedance model uses. The spare L7/L9/L12/L14
    striplines sit in bonding prepreg and have no structure specified.
    """

    material_name = "Isola Astra MT77 prepreg 1035"
    dielectric_coefficient = 2.96
    loss_tangent = 0.0016
    thickness = 0.1000


class BondingPrepreg(Dielectric):
    """D-BOND — Isola Astra MT77 prepreg, 1078 glass, 68% resin.

    Dk 3.00 / Df 0.0017 at 10 GHz. 3.94 mil pressed. Bonds the sub-composite
    (L6..L15) around the core. Same nominal thickness as the build-up prepreg
    but a different glass style and a different Dk, so it is a distinct
    material — do not collapse the two.
    """

    material_name = "Isola Astra MT77 prepreg 1078"
    dielectric_coefficient = 3.00
    loss_tangent = 0.0017
    thickness = 0.1000


class LaminateCore(Dielectric):
    """D-CORE — Isola Astra MT77 laminate, 2x2116 glass, 52% resin.

    Dk 3.12 / Df 0.0019 at 10 GHz. 31.50 mil. The higher glass content raises
    Dk above both prepregs. L10-L11 only.
    """

    material_name = "Isola Astra MT77 laminate 2x2116"
    dielectric_coefficient = 3.12
    loss_tangent = 0.0019
    thickness = 0.8000


class OuterCopper(Conductor):
    """CU-OUT — 1/2 oz HVLP-2 base foil plus 18 um panel plating.

    Finished 35.5 um = 0.0355 mm. Rz matte 2.0 um -> roughness 0.0020 mm.
    L1 and L20. Note this is twice the base-foil weight: plating is why the
    surface layers are thicker than the inner signal layers.
    """

    material_name = "HVLP-2 0.5 oz + 18 um plate"
    thickness = 0.0355
    roughness = 0.0020


class SignalCopper(Conductor):
    """CU-SIG — 1/2 oz HVLP-2 foil, unplated.

    Finished 17.5 um = 0.0175 mm. Rz matte 2.0 um -> roughness 0.0020 mm.
    The eight inner signal layers.
    """

    material_name = "HVLP-2 0.5 oz"
    thickness = 0.0175
    roughness = 0.0020


class PlaneCopper(Conductor):
    """CU-PLN — 1 oz reverse-treated foil, unplated.

    Finished 35.0 um = 0.0350 mm. Rz matte 6.0 um -> roughness 0.0060 mm.
    The ten GND planes. Rougher and cheaper than the HVLP-2 signal foil, which
    is acceptable because plane copper carries return current over a wide area
    rather than a narrow trace.
    """

    material_name = "RTF 1 oz"
    thickness = 0.0350
    roughness = 0.0060


# ---------------------------------------------------------------------------
# Stackup — the STACKUP section, top to bottom, all 41 entries
# ---------------------------------------------------------------------------


class HDIStackup(Stackup):
    """20 copper layers + 19 dielectrics + 2 soldermask = 41 entries.

    Thickness accounting, which must reconcile with the report's DOCUMENT
    section::

        soldermask   2 x 0.0127 = 0.0254
        outer copper 2 x 0.0355 = 0.0710
        signal foil  8 x 0.0175 = 0.1400
        plane foil  10 x 0.0350 = 0.3500
        build-up    10 x 0.1000 = 1.0000
        bonding      8 x 0.1000 = 0.8000
        core         1 x 0.8000 = 0.8000
                       overall  = 3.1864 mm  (report: 3.1864)
        finished, excluding mask = 3.1610 mm  (report: 3.161)
    """

    name = FAB_REPORT

    top_mask = Soldermask(name="Soldermask-Top")

    L1 = OuterCopper(name="L1-Signal")
    d_1_2 = BuildUpPrepreg(name="Build-up-5-Top")
    L2 = PlaneCopper(name="L2-GND")
    d_2_3 = BuildUpPrepreg(name="Build-up-4-Top")
    L3 = SignalCopper(name="L3-Signal")
    d_3_4 = BuildUpPrepreg(name="Build-up-3-Top")
    L4 = PlaneCopper(name="L4-GND")
    d_4_5 = BuildUpPrepreg(name="Build-up-2-Top")
    L5 = SignalCopper(name="L5-Signal")
    d_5_6 = BuildUpPrepreg(name="Build-up-1-Top")
    L6 = PlaneCopper(name="L6-GND")

    # Sub-composite: L6..L15, laminated around the core before build-up.
    d_6_7 = BondingPrepreg(name="Bond-L6-L7")
    L7 = SignalCopper(name="L7-Signal")
    d_7_8 = BondingPrepreg(name="Bond-L7-L8")
    L8 = PlaneCopper(name="L8-GND")
    d_8_9 = BondingPrepreg(name="Bond-L8-L9")
    L9 = SignalCopper(name="L9-Signal")
    d_9_10 = BondingPrepreg(name="Bond-L9-L10")
    L10 = PlaneCopper(name="L10-GND")

    d_10_11 = LaminateCore(name="Core")

    L11 = PlaneCopper(name="L11-GND")
    d_11_12 = BondingPrepreg(name="Bond-L11-L12")
    L12 = SignalCopper(name="L12-Signal")
    d_12_13 = BondingPrepreg(name="Bond-L12-L13")
    L13 = PlaneCopper(name="L13-GND")
    d_13_14 = BondingPrepreg(name="Bond-L13-L14")
    L14 = SignalCopper(name="L14-Signal")
    d_14_15 = BondingPrepreg(name="Bond-L14-L15")
    L15 = PlaneCopper(name="L15-GND")

    d_15_16 = BuildUpPrepreg(name="Build-up-1-Bottom")
    L16 = SignalCopper(name="L16-Signal")
    d_16_17 = BuildUpPrepreg(name="Build-up-2-Bottom")
    L17 = PlaneCopper(name="L17-GND")
    d_17_18 = BuildUpPrepreg(name="Build-up-3-Bottom")
    L18 = SignalCopper(name="L18-Signal")
    d_18_19 = BuildUpPrepreg(name="Build-up-4-Bottom")
    L19 = PlaneCopper(name="L19-GND")
    d_19_20 = BuildUpPrepreg(name="Build-up-5-Bottom")
    L20 = OuterCopper(name="L20-Signal")

    bottom_mask = Soldermask(name="Soldermask-Bottom")


# ---------------------------------------------------------------------------
# Fabrication constraints — the FAB_RULES section
# ---------------------------------------------------------------------------


class HDIFabRules(FabricationConstraints):
    """All 19 constraints JITX requires, from the report's FAB_RULES rows.

    Every field is mandatory — translation fails on a missing one. Only the
    four ``min_copper_*`` rules are engine-enforced and override trace width
    and clearance; the rest are recorded for query and documentation.

    Five capability rows in the report have **no** JITX field and are enforced
    by review rather than by the engine:

    * the 0.200 mm minimum *mechanical* drill — ``min_drill_diameter`` below is
      the 0.100 mm **laser** minimum, the smaller of the two;
    * the 10:1 mechanical and 0.80:1 laser aspect-ratio ceilings;
    * the 5-level stacked-microvia limit;
    * the 0.075 mm minimum dielectric between adjacent copper layers — this
      quote uses 0.100 mm build-up prepreg, so there is 0.025 mm of headroom if
      the stack is ever re-issued thinner.

    The tests assert the via table against the two aspect-ratio ceilings and
    the mechanical-drill minimum; the other two are review-only.
    """

    min_copper_width = 0.050
    min_copper_copper_space = 0.050
    min_copper_hole_space = 0.075
    min_copper_edge_space = 0.250

    min_annular_ring = 0.050
    min_drill_diameter = 0.100
    min_pitch_leaded = 0.400
    min_pitch_bga = 0.350

    max_board_width = 500.0
    max_board_height = 400.0

    min_silkscreen_width = 0.100
    min_silk_solder_mask_space = 0.075
    min_silkscreen_text_height = 0.500
    solder_mask_registration = 0.025
    min_soldermask_opening = 0.100
    min_soldermask_bridge = 0.075

    min_th_pad_expand_outer = 0.075
    min_hole_to_hole = 0.200
    min_pth_pin_solder_clearance = 0.250


# ---------------------------------------------------------------------------
# Routing-structure helpers
# ---------------------------------------------------------------------------
# The report specifies each structure twice — once for the surface microstrip
# layers and once for the inner striplines — because the same impedance target
# needs a different width, and resolves to a different effective permittivity,
# on each. These helpers turn one IMPEDANCE row into per-layer entries.

MICROSTRIP_LAYERS: tuple[int, ...] = (0, -1)
"""L1 and L20 — coated microstrip, referenced to the plane immediately below."""

STRIPLINE_LAYERS: tuple[int, ...] = (2, 4, -3, -5)
"""L3, L5 and mirrors L18, L16 — symmetric stripline between two planes."""

REFERENCE_PLANES: dict[int, tuple[int, ...]] = {
    0: (1,),  # L1 over L2
    2: (1, 3),  # L3 between L2 and L4
    4: (3, 5),  # L5 between L4 and L6
    -1: (-2,),  # L20 under L19
    -3: (-2, -4),  # L18 between L19 and L17
    -5: (-4, -6),  # L16 between L17 and L15
}
"""Reference plane indices per routing layer, from the IMPEDANCE Ref_layers
column. A design must supply :py:class:`~jitx.si.ReferencePlanes` covering
these layers for any topology that uses one of these structures.

Passed to ``reference()`` as ``dict.fromkeys(...)``, i.e. with a ``None``
desired width, because the report states which planes reference each line and
never how wide they are. The mapping form is what makes that expressible: the
scalar ``reference(layer)`` form fails to instantiate without a width, so the
alternative would be inventing one."""


def _se_layers(
    layers: tuple[int, ...],
    *,
    width: float,
    clearance: float,
    eps_eff: float,
    insertion_loss: float,
    neck_width: float | None = None,
    neck_clearance: float | None = None,
) -> dict[int, RoutingStructure.Layer]:
    """Expand one single-ended IMPEDANCE row across its layer group.

    ``eps_eff`` comes straight from the report rather than being guessed from
    Dk: for the coated microstrip rows it already folds in the soldermask, and
    it varies with line width, so there is no single ``(Dk + 1) / 2`` that
    would be right for every structure.

    The neck-down arguments are optional because the report leaves the
    ``Neck_*`` columns blank on some rows. Omit them there rather than
    borrowing a neck geometry from a different row.
    """
    neck = (
        RoutingStructure.NeckDown(
            trace_width=neck_width,
            clearance=neck_clearance,
        )
        if neck_width is not None or neck_clearance is not None
        else None
    )
    return {
        layer: RoutingStructure.Layer(
            trace_width=width,
            clearance=clearance,
            velocity=phase_velocity(eps_eff),
            insertion_loss=insertion_loss,
            neck_down=neck,
            # `None` width: the report names the planes, never their width. See
            # the module docstring's third API ambiguity for why this is the
            # only form that expresses that, and why it needs the suppression.
        ).reference(dict.fromkeys(REFERENCE_PLANES[layer]))  # pyright: ignore[reportArgumentType]
        for layer in layers
    }


def _diff_layers(
    layers: tuple[int, ...],
    *,
    width: float,
    pair_gap: float,
    clearance: float,
    eps_eff: float,
    insertion_loss: float,
    neck_width: float,
    neck_gap: float,
    neck_clearance: float,
) -> dict[int, DifferentialRoutingStructure.Layer]:
    """Expand one differential IMPEDANCE row across its layer group.

    ``pair_gap`` is **edge to edge**, per the report's explicit statement.
    ``DifferentialRoutingStructure.Layer.pair_spacing`` is documented only as
    "internal spacing within the differential pair" and does not say which
    convention it takes; edge-to-edge is what the substrate-modeler skill
    specifies, so that is what we pass.
    """
    return {
        layer: DifferentialRoutingStructure.Layer(
            trace_width=width,
            pair_spacing=pair_gap,
            clearance=clearance,
            velocity=phase_velocity(eps_eff),
            insertion_loss=insertion_loss,
            neck_down=DifferentialRoutingStructure.NeckDown(
                trace_width=neck_width,
                pair_spacing=neck_gap,
                clearance=neck_clearance,
            ),
            # `None` width, same as `_se_layers` — see the module docstring.
        ).reference(dict.fromkeys(REFERENCE_PLANES[layer]))  # pyright: ignore[reportArgumentType]
        for layer in layers
    }


# ---------------------------------------------------------------------------
# Substrate
# ---------------------------------------------------------------------------


class HDISubstrate(Substrate):
    """The stackup, fab rules, 12 via structures and 4 routing structures.

    Every ``Via`` nested class here is registered on the board automatically —
    the substrate is walked by introspection, and there is no opt-in list. So
    this class contains exactly the 12 structures the report's VIAS table
    offers and nothing held back "for later". In particular the sub-composite's
    internal L10-L11 core drill is part of ACME's own process, is not offered
    to the designer, and is therefore absent.
    """

    stackup = HDIStackup()
    constraints = HDIFabRules()

    # --- Laser microvias, one per build-up level ---------------------------
    # UV-1..UV-5 top, UV-6..UV-10 bottom mirror. All identical geometry:
    # 0.125 mm finished hole, 0.275 mm pad, 0.075 mm annular ring, copper
    # filled and capped, via-in-pad permitted. Each spans exactly one 0.100 mm
    # build-up dielectric, giving aspect ratio 0.80 — ACME's stated ceiling.
    # Stacking up to 5 levels is permitted, so L1 reaches L6 by stacking these
    # rather than by any single deeper laser via.

    class MicroVia_L1_L2(Via):
        """UV-1 — build-up level 5. L1 -> L2."""

        type = ViaType.LaserDrill
        start_layer = 0
        stop_layer = 1
        diameter = 0.275
        hole_diameter = 0.125
        filled = True
        tented = True
        via_in_pad = True

    class MicroVia_L2_L3(Via):
        """UV-2 — build-up level 4. L2 -> L3."""

        type = ViaType.LaserDrill
        start_layer = 1
        stop_layer = 2
        diameter = 0.275
        hole_diameter = 0.125
        filled = True
        tented = True
        via_in_pad = True

    class MicroVia_L3_L4(Via):
        """UV-3 — build-up level 3. L3 -> L4."""

        type = ViaType.LaserDrill
        start_layer = 2
        stop_layer = 3
        diameter = 0.275
        hole_diameter = 0.125
        filled = True
        tented = True
        via_in_pad = True

    class MicroVia_L4_L5(Via):
        """UV-4 — build-up level 2. L4 -> L5."""

        type = ViaType.LaserDrill
        start_layer = 3
        stop_layer = 4
        diameter = 0.275
        hole_diameter = 0.125
        filled = True
        tented = True
        via_in_pad = True

    class MicroVia_L5_L6(Via):
        """UV-5 — build-up level 1. L5 -> L6."""

        type = ViaType.LaserDrill
        start_layer = 4
        stop_layer = 5
        diameter = 0.275
        hole_diameter = 0.125
        filled = True
        tented = True
        via_in_pad = True

    class MicroVia_L20_L19(Via):
        """UV-6 — mirror of UV-1. L20 -> L19."""

        type = ViaType.LaserDrill
        start_layer = -1
        stop_layer = -2
        diameter = 0.275
        hole_diameter = 0.125
        filled = True
        tented = True
        via_in_pad = True

    class MicroVia_L19_L18(Via):
        """UV-7 — mirror of UV-2. L19 -> L18."""

        type = ViaType.LaserDrill
        start_layer = -2
        stop_layer = -3
        diameter = 0.275
        hole_diameter = 0.125
        filled = True
        tented = True
        via_in_pad = True

    class MicroVia_L18_L17(Via):
        """UV-8 — mirror of UV-3. L18 -> L17."""

        type = ViaType.LaserDrill
        start_layer = -3
        stop_layer = -4
        diameter = 0.275
        hole_diameter = 0.125
        filled = True
        tented = True
        via_in_pad = True

    class MicroVia_L17_L16(Via):
        """UV-9 — mirror of UV-4. L17 -> L16."""

        type = ViaType.LaserDrill
        start_layer = -4
        stop_layer = -5
        diameter = 0.275
        hole_diameter = 0.125
        filled = True
        tented = True
        via_in_pad = True

    class MicroVia_L16_L15(Via):
        """UV-10 — mirror of UV-5. L16 -> L15."""

        type = ViaType.LaserDrill
        start_layer = -5
        stop_layer = -6
        diameter = 0.275
        hole_diameter = 0.125
        filled = True
        tented = True
        via_in_pad = True

    # --- Mechanical drills ------------------------------------------------

    class BuriedVia_L6_L15(Via):
        """BV-1 — the sub-composite through-drill. L6 -> L15.

        Drilled, plated, resin-filled and capped before the build-up
        laminations go on, so it is buried in the finished board. 1.880 mm
        deep on a 0.250 mm hole = aspect ratio 7.52. The only path between the
        two build-up regions other than the full-stack through hole, and the
        only way to reach the spare L7/L9/L12/L14 routing layers.
        """

        type = ViaType.MechanicalDrill
        start_layer = 5
        stop_layer = 14
        diameter = 0.500
        hole_diameter = 0.250
        filled = True
        tented = True

    class THVia_L1_L20(Via):
        """TH-1 — full-stack plated through hole, drilled last. L1 -> L20.

        3.161 mm deep on a 0.350 mm hole = aspect ratio 9.03, inside ACME's
        10:1 ceiling but only just — this is why the hole is 0.350 mm and not
        the 0.250 mm used for the buried drill. Too large to sit inside a
        0.35 mm-pitch BGA pad, so ``via_in_pad`` stays off; use stacked
        microvias for pad escape.
        """

        type = ViaType.MechanicalDrill
        start_layer = Side.Top
        stop_layer = Side.Bottom
        diameter = 0.650
        hole_diameter = 0.350
        filled = True
        tented = True

    # --- Routing structures -----------------------------------------------
    # Four structures, each covering L1/L3/L5 and the mirrors L20/L18/L16.
    # Widths, clearances, eps_eff and insertion loss are the report's modelled
    # values; impedance is its target. Clearance is the isolation the model
    # assumes — 2x line width single-ended (the 3W rule), 4x differential (5W)
    # — and the impedance only holds where that clearance is met.
    #
    # Lookup is by exact impedance, so the four nominal values (55, 40, 50,
    # 100) never collide.

    SE_Default = RoutingStructure(
        name="55 ohm general purpose (SE-DEFAULT)",
        impedance=55 * ohm,
        layers={
            **_se_layers(
                MICROSTRIP_LAYERS,
                width=0.1841,
                clearance=0.3682,
                eps_eff=2.4316,
                insertion_loss=0.00907,
                neck_width=0.1500,
                neck_clearance=0.1500,
            ),
            **_se_layers(
                STRIPLINE_LAYERS,
                width=0.0876,
                clearance=0.1752,
                eps_eff=2.9600,
                insertion_loss=0.01367,
                neck_width=0.0762,
                neck_clearance=0.0762,
            ),
        },
    )
    """General-purpose single-ended structure — the one to reach for when a net
    has no specific impedance target.

    Note there is no *automatic* default: ``Substrate.routing_structure()``
    wraps its query in ``Toleranced.exact``, so lookup matches exactly and a
    design has to ask for ``55 * ohm`` by name.

    ACME also quotes a STANDARD default line and space (0.150 mm / 0.150 mm)
    for nets with no impedance target. That geometry is deliberately not
    modelled here: applied unchanged on every routing layer it produces 41.87
    ohm on the inner striplines and 60.99 ohm on the surface microstrip, and
    a ``RoutingStructure`` carries a single impedance, so declaring one value
    for it would be a fiction. A controlled 55 ohm target holds one impedance
    on all six routing layers, which is what the lookup needs.
    """

    SE_40 = RoutingStructure(
        name="40 ohm (SE-40)",
        impedance=40 * ohm,
        layers={
            **_se_layers(
                MICROSTRIP_LAYERS,
                width=0.3179,
                clearance=0.6358,
                eps_eff=2.5133,
                insertion_loss=0.00884,
                neck_width=0.1500,
                neck_clearance=0.1500,
            ),
            **_se_layers(
                STRIPLINE_LAYERS,
                width=0.1622,
                clearance=0.3244,
                eps_eff=2.9600,
                insertion_loss=0.01246,
                neck_width=0.0762,
                neck_clearance=0.0762,
            ),
        },
    )
    """40 ohm single-ended.

    Note the surface width: 40 ohm over 0.100 mm of Dk-2.96 build-up prepreg
    needs 0.3179 mm (12.5 mil) of copper. That is simply what the geometry
    gives, and it is why a dense escape on L1 necks down to 0.1500 mm — which
    is a ~61 ohm line, not a 40 ohm one. Keep necked runs short.
    """

    SE_50 = RoutingStructure(
        name="50 ohm (SE-50)",
        impedance=50 * ohm,
        layers={
            **_se_layers(
                MICROSTRIP_LAYERS,
                width=0.2193,
                clearance=0.4386,
                eps_eff=2.4572,
                insertion_loss=0.00898,
                neck_width=0.1500,
                neck_clearance=0.1500,
            ),
            **_se_layers(
                STRIPLINE_LAYERS,
                width=0.1075,
                clearance=0.2150,
                eps_eff=2.9600,
                insertion_loss=0.01326,
                neck_width=0.0762,
                neck_clearance=0.0762,
            ),
        },
    )
    """50 ohm single-ended."""

    DRS_100 = DifferentialRoutingStructure(
        name="100 ohm differential (DIFF-100)",
        impedance=100 * ohm,
        layers={
            **_diff_layers(
                MICROSTRIP_LAYERS,
                width=0.1486,
                pair_gap=0.1000,
                clearance=0.5944,
                eps_eff=2.4010,
                insertion_loss=0.01082,
                neck_width=0.1000,
                neck_gap=0.0750,
                neck_clearance=0.2000,
            ),
            **_diff_layers(
                STRIPLINE_LAYERS,
                width=0.0762,
                pair_gap=0.0762,
                clearance=0.3048,
                eps_eff=2.9600,
                insertion_loss=0.01579,
                neck_width=0.0635,
                neck_gap=0.0635,
                neck_clearance=0.1270,
            ),
        },
        uncoupled_region=RoutingStructure(
            name="100 ohm differential, uncoupled (DIFF-100-UNC)",
            impedance=58 * ohm,
            layers={
                # No neck-down: the report leaves the Neck_* columns blank on
                # the DIFF-100-UNC rows, so there is nothing to transcribe.
                # Borrowing the coupled row's neck geometry would be invention.
                **_se_layers(
                    MICROSTRIP_LAYERS,
                    width=0.1486,
                    clearance=0.5944,
                    eps_eff=2.4010,
                    insertion_loss=0.00918,
                ),
                **_se_layers(
                    STRIPLINE_LAYERS,
                    width=0.0762,
                    clearance=0.3048,
                    eps_eff=2.9600,
                    insertion_loss=0.01394,
                ),
            },
        ),
    )
    """100 ohm differential, edge-coupled, gap stated edge to edge.

    The uncoupled region keeps the coupled line width but each trace now
    behaves as an isolated single-ended line, which the report models at 58.35
    ohm on stripline and 61.27 ohm on microstrip. It is declared at 58 ohm —
    the stripline value, since that is where the bulk of the routing runs — and
    not at half the differential target, because the geometry does not change
    when the pair splits.
    """


# ---------------------------------------------------------------------------
# Board
# ---------------------------------------------------------------------------
# 80 x 80 mm with a 4 mm corner radius, per the report's DOCUMENT section.

BOARD_WIDTH = 80.0
BOARD_HEIGHT = 80.0
BOARD_CORNER_RADIUS = 4.0
"""Board outline, from the report's DOCUMENT section ("Board size")."""

_EDGE_KEEPOUT = HDIFabRules.min_copper_edge_space
"""Inset for ``signal_area``, taken from the fab rule rather than picked: the
engine enforces ``min_copper_edge_space`` on generated copper anyway, so insetting
the placement and routing area by the same amount keeps the two consistent."""


class HDIBoard(Board):
    """80 x 80 mm board on the 20-layer HDI substrate.

    ``Board`` holds only ``shape`` and ``signal_area``. Via registration and
    substrate binding are **not** board concerns — vias come from walking the
    substrate, and the substrate is bound on the ``Design``.
    """

    shape = rectangle(BOARD_WIDTH, BOARD_HEIGHT, radius=BOARD_CORNER_RADIUS)
    signal_area = rectangle(
        BOARD_WIDTH - 2 * _EDGE_KEEPOUT,
        BOARD_HEIGHT - 2 * _EDGE_KEEPOUT,
        radius=BOARD_CORNER_RADIUS - _EDGE_KEEPOUT,
    )
