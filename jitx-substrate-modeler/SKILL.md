---
name: jitx-substrate-modeler
description: This skill should be used when the user asks to "create a substrate", "define a stackup", "add via definitions", "set up routing structures", "configure impedance control", "define differential pairs", "set fabrication rules", "ring a shape with fence vias", "fence a pour outline", "fence an antipad", or "model a PCB layer structure". Ask the user which fabrication house they are targeting — if they confirm JLCPCB, predefined substrates from jitxlib.jlcpcb (JLC04161H_1080, JLC04161H_7628, JLC06161H_7628) are available with 4/6-layer FR-4, 50/90/100 ohm routing structures, vias, and fab rules. Otherwise, create a custom substrate. Covers Stackup, Symmetric, Conductor, Dielectric, Via (laser, mechanical, backdrilled, blind, buried, stacked), RoutingStructure, DifferentialRoutingStructure, NeckDown, via fencing along traces, fenced pour outlines (Tag + fence_via rule paired with a Pour + optional same-shape KeepOut — covers antipads, RF cavities, BGA breakouts), geometry, reference planes, and FabricationConstraints.
---

# JITX Substrate Modeler

Generate complete JITX Python substrate definitions — stackups, materials, vias, routing structures, and fabrication constraints — all in a single file.

## Predefined Substrates (JLCPCB Only)

If the user has confirmed they are targeting **JLCPCB** as their fabrication house, predefined substrates from `jitxlib.jlcpcb` are available. These are production-validated with correct materials, vias, fab rules, and impedance-matched routing structures:

| Class | Layers | Prepreg | Routing Structures | Import |
|-------|--------|---------|-------------------|--------|
| `JLC04161H_1080` | 4 | 1080 | RS_50, DRS_90, DRS_100 | `from jitxlib.jlcpcb import JLC04161H_1080` |
| `JLC04161H_7628` | 4 | 7628 | RS_50, DRS_90, DRS_100 | `from jitxlib.jlcpcb import JLC04161H_7628` |
| `JLC06161H_7628` | 6 | 7628 | RS_50, DRS_100 | `from jitxlib.jlcpcb import JLC06161H_7628` |

Each includes: Symmetric stackup, JLCPCBRules (FabricationConstraints), 11 JLCPCB via definitions (StdVia, StdViaPreferred, MultiLayerVia1-3 + Preferred variants, StdViaTentedFilled for via-in-pad), and routing structures for 50/90/100 ohm impedance targets.

**Use directly** — no substrate file needed:
```python
from jitxlib.jlcpcb import JLC04161H_1080
substrate = JLC04161H_1080()

# Access routing structures for SI constraints:
# substrate.RS_50, substrate.DRS_90, substrate.DRS_100
```

**When to use predefined:** User has explicitly confirmed JLCPCB as fab house + 4 or 6 layer FR-4 + standard impedance targets (50/90/100 ohm). This covers USB, Ethernet, I2C, SPI, I2S, and most common protocols.

**When to create custom (use the rest of this skill):** User has not confirmed JLCPCB, non-FR-4 materials (Rogers, Megtron), unusual layer count, non-standard impedance, or additional routing structures needed. **This is the default path** — always create a custom substrate unless the user opts in to a predefined one.

## Environment

Environment setup is handled by the base `jitx` skill. Ensure it has been invoked first.

## Package Architecture

```python
# Core imports — use these exactly
from jitx.stackup import Stackup, Symmetric, Conductor, Dielectric
from jitx.substrate import Substrate, FabricationConstraints
from jitx.via import Via, ViaType, ViaDiameter, Backdrill, BackdrillSet
from jitx.si import RoutingStructure, DifferentialRoutingStructure, symmetric_routing_layers
from jitx.layerindex import Side, LayerSet
from jitx.units import ohm
from jitx.constraints import ViaFencePattern
from jitx.feature import KeepOut, Soldermask
from jitxlib.physics import phase_velocity
from jitx.container import inline

```

**These DO NOT EXIST — never import:**
`jitx.material`, `jitx.layer`, `jitx.routing`, `jitx.impedance`, `jitx.pcb`,
`jitx.dielectric`, `jitx.conductor`, `jitxlib.stackup`, `jitxlib.substrate`

## Anti-string-hacking — read before adding per-layer / per-via tables

Substrate-shaped data (layer-to-via maps, layer-pair tables, per-layer trace widths) belongs **on the substrate**, queried by the design — not duplicated as design-level constants. The design should write `self.substrate.via[(a, b)]`, not maintain its own `_SIGNAL_LAYER_TO_VIA` dict. See `jitx/references/architectural-patterns.md` § "Substrate-shaped tables live on the substrate" before adding per-layer constant tables. Also: instantiate generic substrates (`stackup = Generic_Stackup()`), don't inline-subclass them (`@inline class stackup(Generic_Stackup): pass`) — § "Instantiate, don't inline-subclass".

A "generic" substrate must be reusable across designs. Design-specific tags (`AntipadFenceTag` named after a particular escape design), design-specific trace widths (`DESKEW_TRACE_WIDTH`), or design-specific fence definitions do **not** belong in `generic_*.py` — push them into the consuming design. **Comments and docstrings are part of this surface too:** a generic substrate must not claim it's tuned for one downstream tool's extraction/export flow (`jitx-ansys` / HFSS, `odb++`) or state a fact the code doesn't back — that couples the reusable artifact to one consumer and asserts facts not in evidence. A neutral, evidenced mention of a tool isn't the problem; an unbacked tool-specific *suitability* claim is.

For a same-model self-critique pass on the substrate after writing (catches what these rules don't), invoke `jitx-skills:jitx-code-review`. Optional for single-task use.

## File Structure

Everything goes in **one Python file** per substrate:

```python
# 1. Material definitions (Dielectric, Conductor subclasses)
# 2. Stackup class (Stackup or Symmetric)
# 3. FabricationConstraints class
# 4. Substrate class containing:
#    - stackup instance
#    - constraints instance
#    - Via nested classes (all types needed)
#    - RoutingStructure instances
#    - DifferentialRoutingStructure instances
```

## Materials

Set properties as **class attributes**, instantiate with thickness.

Soldermask is a `Dielectric` — define it like any other dielectric material:

```python
class SoldermaskLayer(Dielectric):
    """Soldermask — typically Er ≈ 3.8"""
    dielectric_coefficient = 3.8
    loss_tangent = 0.02

class FR4_Prepreg(Dielectric):
    dielectric_coefficient = 4.4   # Dk (dielectric constant / relative permittivity)
    loss_tangent = 0.0168          # Df (dissipation factor)

class FR4_Core(Dielectric):
    dielectric_coefficient = 4.6   # Dk
    loss_tangent = 0.0168          # Df

class Copper1oz(Conductor):
    thickness = 0.035  # mm (can also be set at instantiation)

class CopperHalfOz(Conductor):
    thickness = 0.0175  # mm (can also be set at instantiation)

class SoldermaskLayer(Dielectric):
    thickness = 0.020
```

**Terminology:** `dielectric_coefficient` is the JITX attribute name for Dk (dielectric constant, also called relative permittivity or Er). `loss_tangent` is the JITX attribute name for Df (dissipation factor). Datasheets typically specify Dk and Df at a given frequency (e.g., 1 GHz or 10 GHz).

### Common Dielectric Materials

Reference table of common PCB dielectric materials. Values are typical at 10 GHz unless noted. Always confirm with the manufacturer's datasheet for your specific construction.

| Material | Manufacturer | Family | Dk | Df | Notes |
|----------|-------------|--------|----|----|-------|
| **Standard FR-4** |
| FR408HR | Isola | High-Tg epoxy | 3.68 | 0.0092 | Workhorse high-Tg FR-4; widely available |
| I-Speed | Isola | Low-loss epoxy | 3.64 | 0.0060 | Step down in loss vs standard FR-4 |
| N4000-13 EP | AGC/Nelco | High-speed epoxy | 3.60 | 0.0090 | High-speed digital backplanes |
| N7000-2HT | AGC/Nelco | High-speed laminate | 3.50 | 0.0090 | Dk/Df available at 2.5 and 10 GHz |
| **Low-Loss** |
| I-Tera MT40 | Isola | Very low-loss epoxy | 3.45 | 0.0031 | High-speed digital/RF |
| Megtron 6 | Panasonic | Low-loss multilayer | 3.34 | 0.0037 | Common in high-speed digital (at 13 GHz) |
| RO4350B | Rogers | Hydrocarbon/ceramic | 3.48 | 0.0037 | Popular RF laminate; FR-4 processable |
| RO4003C | Rogers | Hydrocarbon/ceramic | 3.38 | 0.0027 | Standard RF laminate |
| 25N | Arlon | Ceramic-filled woven glass | 3.38 | 0.0025 | Low loss with standard FR-4 processes |
| **Ultra-Low-Loss** |
| Astra MT77 | Isola | Ultra-low-loss | 3.00 | 0.0017 | RF/microwave and very-high-speed |
| Tachyon 100G | Isola | Ultra-low-loss | ~3.05 | ~0.0017 | Values vary by construction |
| Megtron 7 | Panasonic | Ultra-low-loss | varies | varies | Capture exact row for glass style/resin |
| **PTFE / RF** |
| RT/duroid 5880 | Rogers | Glass microfiber PTFE | 2.20 | 0.0009 | Ultra-low loss; microwave/RF |
| RT/duroid 5870 | Rogers | Glass microfiber PTFE | 2.33 | 0.0012 | Low Dk/loss; antennas/stripline |
| RO3003 | Rogers | Ceramic-filled PTFE | 3.00 | 0.0010 | Low loss PTFE; common RF choice |
| RO3035 | Rogers | Ceramic-filled PTFE | 3.50 | 0.0015 | PTFE with Dk ~3.5 |
| TLY-5A | Taconic/AGC | Low-loss PTFE | 2.17–2.40 | ~0.0009 | Selectable Dk range |
| TLX-0 | Taconic/AGC | Fiberglass PTFE | 2.45 | 0.0012 | Lowest Dk in TLX series |
| **High-Dk (miniaturization)** |
| RO3006 | Rogers | Ceramic-filled PTFE | 6.15 | 0.0020 | Higher Dk for size reduction |
| RO3010 | Rogers | Ceramic-filled PTFE | 10.20 | 0.0022 | High Dk for compact RF |
| CER-10 | Taconic/AGC | Organic-ceramic | 10.0 | 0.0035 | High Dk; check tolerances per lot |

### Copper Foil Types

Copper surface roughness affects insertion loss at high frequencies. Choose foil type based on your frequency range.

Rz values below are for the **matte/bonding side** (the side laminated to the dielectric core), which is the surface that dominates conductor loss. The drum/resist side is typically 2–5× smoother; use its Ra value when modelling the top surface of a trace.

| Copper Type | Rz — Matte/Bonding Side | Rz — Drum/Resist Side | Use Case |
|-------------|-------------------------|-----------------------|----------|
| Standard HTE (STD) | 5–10 μm | 3–5 μm | <1 GHz, general FR-4 inner layers |
| Reverse Treated Foil (RTF) | 5–10 μm | 3–5 μm | <5 GHz; adhesion treatment moves to drum side |
| Low Profile (LP / LoPro) | 2–4 μm | 1–2 μm | 1–10 GHz signal layers |
| Very Low Profile (VLP) | 2.5–5 μm | 1–2 μm | 5–25 Gbps; Megtron 6, Isola IS415/FR408HR |
| Hyper VLP (HVLP / SVLP) | 1–3 μm | 0.5–1 μm | 25–56 Gbps; high-speed SerDes |
| Ultra Low Profile (ULP) | 0.5–1.5 μm | 0.3–0.5 μm | >56 Gbps, mmWave (>24 GHz) |
| Rolled Annealed (RA) | 0.3–0.8 μm | 0.3–0.8 μm | RF/microwave, flex circuits; both sides smooth |

**Rule of thumb:** For signals above 5 GHz, use LP or smoother. Above 10 GHz, use VLP. For 25 Gbps+, use HVLP. For mmWave (>24 GHz) or >56 Gbps, use ULP or RA.

**Cannonball-Huray parameters** (for HFSS/EM simulation using the average HCPES+SCPES model):
- Nodule radius: `a = 0.0573 × Rz` (µm)
- Surface ratio: `Sr = 5.117` (constant, independent of foil type)
- Use matte-side roughness for the bottom surface of a trace; drum-side for the top. The matte side is the rougher of the two — typical Ra range 0.18–0.51 µm for standard foils; the drum side is much smoother — Ra ≈ Rz × 0.0573 (matches the Cannonball-Huray nodule-radius formula, ≈ 0.18 µm at Rz = 3.05 µm).

| Copper Type | Representative Rz (µm) | Nodule radius a (µm) |
|-------------|------------------------|----------------------|
| STD HTE | 8.0 | 0.458 |
| RTF | 6.0 | 0.344 |
| LP / LoPro | 3.0 | 0.172 |
| VLP | 3.5 | 0.201 |
| HVLP | 2.0 | 0.115 |
| ULP | 1.0 | 0.057 |
| RA | 0.5 | 0.029 |

## Stackup

### Symmetric (preferred for most boards)

Define top half only — bottom auto-mirrors. **Last layer MUST be dielectric** (symmetry plane):

```python
class My4LayerStackup(Symmetric):
    soldermask = SoldermaskLayer(thickness=0.015)
    top = Copper1oz()
    prepreg = FR4_Prepreg(thickness=0.076)
    inner = CopperHalfOz()
    core = FR4_Core(thickness=1.265)  # center — MUST be dielectric
```

### Explicit Stackup (non-symmetric boards)

Top-to-bottom order. Named attributes or list. **Give copper layers informative names** describing their function (signal, ground, power) — these appear in the JITX UI and help users navigate the design:

```python
class My8LayerStackup(Stackup):
    top_mask = SoldermaskLayer(thickness=0.02)
    L8 = ThinCopper(name="L8-Patch")
    sub7 = Prepreg326(thickness=0.068)
    L7 = ThinCopper(name="L7-GND3")
    sub6 = Prepreg322(thickness=0.104)
    L6 = ThinCopper(name="L6-Signal")
    # ... all layers top to bottom ...
    L2 = ThinCopper(name="L2-GND1")
    sub1 = Prepreg325(thickness=0.068)
    L1 = ThickCopper(name="L1-Signal")
    bottom_mask = SoldermaskLayer(thickness=0.02)
```

### Inline Stackup (in Substrate class)

```python
class MySubstrate(Substrate):
    @inline
    class stackup(Symmetric):
        soldermask = SoldermaskLayer(thickness=0.015)
        top = Copper1oz()
        prepreg = FR4_Prepreg(thickness=0.076)
        inner = CopperHalfOz()
        core = FR4_Core(thickness=1.265)
```

## Via Types

Define as **nested classes** inside Substrate. All properties are `ClassVar`.

### Through-Hole (Standard)

```python
class THVia(Via):
    type = ViaType.MechanicalDrill
    start_layer = 0        # Side.Top also works
    stop_layer = -1        # Side.Bottom also works
    diameter = 0.45        # pad diameter (mm)
    hole_diameter = 0.3    # drill hole (mm)
```

### Through-Hole (Tented + Filled, Via-in-Pad)

```python
class THViaFilled(Via):
    type = ViaType.MechanicalDrill
    start_layer = Side.Top
    stop_layer = Side.Bottom
    diameter = 0.45
    hole_diameter = 0.3
    tented = True
    filled = True
    via_in_pad = True
```

### Laser Microvia (Single Span)

```python
class MicroVia_L1_L2(Via):
    type = ViaType.LaserDrill
    start_layer = 0
    stop_layer = 1
    diameter = 0.356
    hole_diameter = 0.178
    filled = True
    via_in_pad = True
```

### Stacked Microvia (Multi-Span Laser)

```python
class StackedVia_L1_L3(Via):
    type = ViaType.LaserDrill
    start_layer = 0
    stop_layer = 2
    diameter = 0.356
    hole_diameter = 0.178
    filled = True
    via_in_pad = True
```

### Buried Via (Internal Only)

```python
class BuriedVia_L3_L12(Via):
    type = ViaType.MechanicalDrill
    start_layer = 2
    stop_layer = 11
    diameter = 0.356
    hole_diameter = 0.178
    filled = True
```

### Backdrilled Via

Backdrill depth is set via `stop_layer` — set it to the target signal layer, then use `BackdrillSet` to remove the stub. The backdrill side is opposite to the signal entry:

```python
bd = Backdrill(
    diameter=0.5, startpad_diameter=0.7,
    solder_mask_opening=0.8, copper_clearance=0.6,
)

class BackdrilledVia_L3(Via):
    """Signal enters from top, connects at L3 — backdrill from bottom removes stub"""
    type = ViaType.MechanicalDrill
    start_layer = Side.Top
    stop_layer = 3             # target signal layer controls backdrill depth
    diameter = 0.6
    hole_diameter = 0.3
    filled = True
    via_in_pad = True
    backdrill = BackdrillSet(bottom=bd)  # backdrill from opposite side
```

**Dual backdrill (both sides) — incredibly uncommon, almost never needed:**

```python
    backdrill = BackdrillSet(
        top=Backdrill(diameter=0.5, startpad_diameter=0.7,
                      solder_mask_opening=0.8, copper_clearance=0.6),
        bottom=Backdrill(diameter=0.5, startpad_diameter=0.7,
                         solder_mask_opening=0.8, copper_clearance=0.6),
    )
```

### Per-Layer Pad Diameter (NFP Removal)

```python
class AdvancedVia(Via):
    type = ViaType.MechanicalDrill
    start_layer = 0
    stop_layer = -1
    diameter = 0.6
    hole_diameter = 0.3
    diameters = {
        0: 0.5,
        1: ViaDiameter(0.5, nfp=0.2),  # non-functional pad on layer 1
    }
```

### Via SI Models

```python
from jitx.si import PinModel

class ModeledVia(Via):
    # ... standard attributes ...
    models = {
        (0, -1): PinModel(5e-12, 0.05),  # top-to-bottom: 5ps delay, 0.05dB loss
        (0, 1): PinModel(2e-12, 0.02),
    }
```

## Routing Structures

### Single-Ended (RoutingStructure)

```python
RS_50 = RoutingStructure(
    impedance=50 * ohm,
    layers=symmetric_routing_layers({
        0: RoutingStructure.Layer(
            trace_width=0.12,       # mm
            clearance=0.2,          # mm
            velocity=phase_velocity((4.4 + 1) / 2),  # mm/s — microstrip effective Dk
            insertion_loss=0.018,   # dB/mm
        )
    }),
)
```

### Velocity Calculation

```python
from jitxlib.physics import phase_velocity

vel_microstrip = phase_velocity((Dk + 1) / 2)   # microstrip effective Dk
vel_stripline = phase_velocity(Dk)               # stripline uses full Dk
vel_mixed = phase_velocity((Dk_pp + Dk_core) / 2)  # mixed dielectric
```

**`velocity` must be in mm/s, NOT m/s.** `phase_velocity()` returns mm/s. Passing a raw m/s value will be 1000x too small, producing wrong timing constraints.

```python
# WRONG — velocity in m/s (1000x too small, timing constraints will be wrong)
velocity = 1.5e8  # m/s — DO NOT USE

# CORRECT — always use phase_velocity() which returns mm/s
velocity = phase_velocity(4.2)  # returns ~1.46e11 mm/s
```

### symmetric_routing_layers()

Define top half only — mirrors to bottom using `-layer - 1` index:

```python
layers = symmetric_routing_layers({
    0: RoutingStructure.Layer(...),   # → also creates layer -1
    2: RoutingStructure.Layer(...),   # → also creates layer -3
})
```

### Layer with NeckDown

```python
RoutingStructure.Layer(
    trace_width=0.15, clearance=0.1,
    velocity=vel, insertion_loss=0.05,
    neck_down=RoutingStructure.NeckDown(
        trace_width=0.09, clearance=0.075,
    ),
)
```

### Layer with Via Fence

```python
RoutingStructure.Layer(
    trace_width=0.203, clearance=0.076,
    velocity=phase_velocity(1.99), insertion_loss=0.05,
).fence(
    MicroVia_L1_L2,   # via class
    ViaFencePattern(
        pitch=0.4,     # via-to-via spacing along route
        offset=0.43,   # trace center to via center
        num_rows=1,
    ),
    reference_layer=1, # ground reference for fence net
)
```

**Offset formula:** `offset = trace_width/2 + gap + via_pad_radius`

### Layer with Geometry and Reference

```python
RoutingStructure.Layer(
    trace_width=0.12, clearance=0.08,
    velocity=phase_velocity(3.26), insertion_loss=0.08,
)
.geometry(Soldermask, 0.25, side=Side.Top)        # soldermask opening
.geometry(KeepOut, 1.2, layers=LayerSet(1), pour=True)  # keepout on layer 1
.reference(2, 1.0)                                 # reference plane on layer 2
.fence(FenceViaClass, ViaFencePattern(pitch=0.5, offset=0.35, num_rows=1),
       reference_layer=2)
```

### Differential Routing Structure

```python
DRS_100 = DifferentialRoutingStructure(
    name="100 Ohm Differential",
    impedance=100 * ohm,
    layers=symmetric_routing_layers({
        0: DifferentialRoutingStructure.Layer(
            trace_width=0.09,
            pair_spacing=0.137,    # edge-to-edge between P and N
            clearance=0.2,
            velocity=vel,
            insertion_loss=0.018,
        )
    }),
    uncoupled_region=RoutingStructure(
        name="50 Ohm SingleEnded, Uncoupled",
        impedance=50 * ohm,
        layers=symmetric_routing_layers({
            0: RoutingStructure.Layer(
                trace_width=0.09, clearance=0.2,
                velocity=vel, insertion_loss=0.018,
            )
        }),
    ),
)
```

**Differential with NeckDown (for BGA escape or constrained areas):**

```python
DRS_100_ND = DifferentialRoutingStructure(
    name="100 Ohm Differential w/ NeckDown",
    impedance=100 * ohm,
    layers=symmetric_routing_layers({
        0: DifferentialRoutingStructure.Layer(
            trace_width=0.09,
            pair_spacing=0.137,
            clearance=0.2,
            velocity=vel,
            insertion_loss=0.018,
            neck_down=DifferentialRoutingStructure.NeckDown(
                trace_width=0.075,
                pair_spacing=0.1,
                clearance=0.15,
            ),
        )
    }),
    uncoupled_region=RoutingStructure(
        name="100 Ohm Differential w/ NeckDown, Uncoupled",
        impedance=50 * ohm,  # half of differential impedance
        layers=symmetric_routing_layers({
            0: RoutingStructure.Layer(
                trace_width=0.09, clearance=0.2,
                velocity=vel, insertion_loss=0.018,
                neck_down=RoutingStructure.NeckDown(
                    trace_width=0.075, clearance=0.15,
                ),
            )
        }),
    ),
)
```

**Multi-layer differential (different trace widths per layer):**

```python
DRS_82 = DifferentialRoutingStructure(
    impedance=82 * ohm,
    layers=symmetric_routing_layers({
        0: DifferentialRoutingStructure.Layer(
            trace_width=0.154, pair_spacing=0.2,
            clearance=0.23, velocity=VEL, insertion_loss=0.018,
        ),
        2: DifferentialRoutingStructure.Layer(
            trace_width=0.137, pair_spacing=0.15,
            clearance=0.21, velocity=VEL, insertion_loss=0.018,
        ),
    }),
    uncoupled_region=RoutingStructure(
        impedance=41 * ohm,
        layers=symmetric_routing_layers({
            0: RoutingStructure.Layer(trace_width=0.154, clearance=0.15,
                                      velocity=VEL, insertion_loss=0.018),
            2: RoutingStructure.Layer(trace_width=0.137, clearance=0.15,
                                      velocity=VEL, insertion_loss=0.018),
        }),
    ),
)
```

## Fabrication Constraints

All values in mm.

```python
class MyFabRules(FabricationConstraints):
    min_copper_width = 0.09           # minimum trace width
    min_copper_copper_space = 0.09    # minimum copper spacing
    min_copper_hole_space = 0.254     # copper-to-hole spacing
    min_copper_edge_space = 0.3       # copper-to-board-edge
    min_annular_ring = 0.13           # via annular ring
    min_drill_diameter = 0.3          # minimum drill hole
    min_hole_to_hole = 0.5            # hole-to-hole spacing
    min_pitch_leaded = 0.217          # leaded package pitch
    min_pitch_bga = 0.377             # BGA pitch
    max_board_width = 500
    max_board_height = 400
    min_silkscreen_width = 0.153
    min_silk_solder_mask_space = 0.15
    min_silkscreen_text_height = 1.0
    solder_mask_registration = 0.05
    min_soldermask_opening = 0.0
    min_soldermask_bridge = 0.08
    min_th_pad_expand_outer = 0.2
    min_pth_pin_solder_clearance = 0.0
```

Custom attributes are allowed for fab-house-specific rules (not engine-enforced).

## Design Constraints (Tags)

This section defines the *rules* (`design_constraint(...)`) a tag triggers. Choosing
*which* layout objects to tag and why — fanout/escape tags on package escapes,
direct-connect on high-current pads, tagging a code-based `Route` — is covered in the
**jitx-physical-layout** subskill.

For net-to-net clearances and via stitching rules:

```python
from jitx.constraints import Tag, design_constraint

class RFSignalTag(Tag): pass
class GNDTag(Tag): pass

# Trace width for tagged nets (unary constraint — single tag)
self.rule1 = design_constraint(RFSignalTag(), priority=1).trace_width(0.102)

# Net-to-net clearance (binary constraint — two tags)
self.rule2 = design_constraint(RFSignalTag(), RFSignalTag()).clearance(1.05)
self.rule3 = design_constraint(RFSignalTag(), GNDTag()).clearance(0.15)
```

**Board-wide defaults belong on the Design class, not the substrate.** The four canonical defaults — trace width, copper clearance, thermal relief, wider power/ground — go in `self.rules` on the top-level Design via `UnaryDesignConstraint(IsTrace)` / `BinaryDesignConstraint(IsCopper, IsCopper)` / `UnaryDesignConstraint(IsPad)` / `UnaryDesignConstraint(PowerTag() | GroundTag(), priority=1)`. See `jitx/references/project-builder-flow.md` "Default design rules" for the full pattern. The substrate's `FabricationConstraints` are the fab-minimum floor; the Design rules are the production-friendly defaults that sit above the floor.

`design_constraint(...)` and `UnaryDesignConstraint(...)` / `BinaryDesignConstraint(...)` are equivalent — the lowercase form is a factory that returns the right subtype based on arity. Use either.

### Tag inheritance & proliferation

**Tags form a hierarchy through class inheritance, and a rule on a base tag applies to every subclass tag.** This is a first-class JITX feature, not a trick — a tag can subclass *another tag*, not just `Tag`:

```python
class FenceTag(Tag): pass
class AntipadFenceTag(FenceTag): pass        # subclass of FenceTag
class DeskewAntipadFenceTag(AntipadFenceTag): pass   # subclass of AntipadFenceTag

# Applies to ALL fence tags — antipad, deskew, and any future FenceTag subclass:
self.fence_clearance = design_constraint(FenceTag(), GNDTag()).clearance(0.15)

# Applies only to the deskew variant; give it higher priority to override the base
# rule where they overlap (higher priority wins when multiple rules match):
self.deskew_fence = design_constraint(DeskewAntipadFenceTag(), priority=10).fence_via(...)
```

A net/pour/object tagged `DeskewAntipadFenceTag()` matches rules written against `DeskewAntipadFenceTag`, `AntipadFenceTag`, **and** `FenceTag`. Where two matching rules conflict, the higher `priority=` wins — that's how a specific subtag rule overrides the general base-tag rule. (Tags also combine with `&` / `|` / `~` and `Tag.any(...)` when a hierarchy isn't the right shape.)

**Flat tag proliferation is a smell.** A row of near-identical sibling tags that all inherit straight from `Tag` and differ only by name — each wired to its own rule that mostly restates the others — usually wants one of:
- a **base tag** carrying the shared rule, with subtags only where behavior actually differs (the neckdown case: one clearance rule for *all* neckdown via `NeckDownTag`, plus a higher-priority rule for the one neckdown level that's special), or
- a single **combined rule** (`design_constraint(TagA() | TagB())…`) when the tags aren't really distinct concepts.

Reach for many flat tags only when the rule sets are genuinely distinct. Mapping a spreadsheet of per-combination rules into a flat tag-per-row table is the usual way this goes wrong — the hierarchy expresses the same intent with far fewer rules.

## Fenced Pour Outlines (Antipads, RF Cavities, BGA Breakouts)

Trick for placing fence vias along an arbitrary closed shape — antipad rings around signal-via pairs, RF cavity perimeters, BGA breakout boundaries, deskew arc cutouts. Three pieces compose:

1. **Substrate-side rule** — a Tag and a `design_constraint(...).fence_via(...)` declaring that any pour carrying the Tag gets fence vias of the given class placed along it.
2. **Design-side Pour** — created on the fence net (typically GND) with the Tag assigned. The Pour exists to give the constraint engine a shape to ring with vias; its copper may or may not be wanted.
3. **Optional matching KeepOut** — same shape, voids the pour's copper. Add it when the pour is purely a fence-via trigger (you want the vias, not the copper). Omit it when the pour's copper is real (e.g. a stitching region that doubles as a return-path pour).

### Substrate-side declaration

```python
from jitx.constraints import Tag, design_constraint, ViaFencePattern

class FenceOutlineTag(Tag):
    """Pours with this tag get fence vias along their outline."""

class MySubstrate(Substrate):
    # ... other vias ...
    class uGndStitch(Via):
        """Example fence via — adjust to your fab's microvia capability."""
        type = ViaType.LaserDrill
        start_layer = 0
        stop_layer = 6
        diameter = 0.25
        hole_diameter = 0.1
        filled = True

    _FENCE_PATTERN = ViaFencePattern(
        pitch=0.35,   # via-to-via spacing along each row
        offset=0.15,  # row-to-row spacing; also the default boundary-to-first-row offset
        num_rows=1,
    )

    outline_fence_rule = design_constraint(
        FenceOutlineTag(), priority=20
    ).fence_via(uGndStitch, _FENCE_PATTERN)
```

`ViaFencePattern.input_shape_only` (pour-only, defaults to `True`) controls which pour shape gets fenced — the pre-isolation input outline (default) or the post-isolation computed copper. Leaving it default is correct for nearly every fenced-outline case; set `False` only if downstream clearance rules will reshape the pour and the fence vias should track the reshaped boundary.

### Design-side usage

The tagged pour must sit on a conductor layer the fence via reaches — fence vias inherit the pour's net, so the pour has to be on a layer they can land on. Typically the pour goes on the reference/termination layer being fenced (here, the via's `stop_layer = 6`, so the pour goes on `layer=6`).

```python
from jitx import Pour
from jitx.feature import KeepOut
from jitx.layerindex import LayerSet

# `shape` is the outline to fence — e.g. a capsule around a signal-via pair,
# an RF cavity perimeter, a BGA breakout boundary, or a deskew arc cutout.
fence_pour = Pour(shape, layer=6)
FenceOutlineTag().assign(fence_pour)
self.GND += fence_pour

# Add this ONLY when the pour copper itself is unwanted (cavity / antipad opening).
# Omit when the pour doubles as a real GND region.
self.fence_outline_keepout = KeepOut(shape, layers=LayerSet(6), pour=True, via=True)
```

Do not set `isolate=` on the fence Pour — it's legacy. Pour clearance is governed by `FabricationConstraints` + Tag-based `design_constraint(...).clearance(...)`.

## Via Mixin Pattern

Reuse via definitions across substrates:

```python
class MyVias:
    class StdVia(Via): ...
    class StdViaFilled(Via): ...

class SubstrateA(Substrate, MyVias):
    stackup = StackupA()
    constraints = RulesA()

class SubstrateB(Substrate, MyVias):
    stackup = StackupB()
    constraints = RulesB()
```

## Layer Index Convention

- `0` / `Side.Top` = top conductor
- `1` = second conductor from top
- `-1` / `Side.Bottom` = bottom conductor
- `-2` = second from bottom
- `symmetric_routing_layers` maps layer `i` to `-i - 1`

## Workflow

1. **Gather specs** — stackup cross-section, dielectric properties (Dk, Df), copper weights, fab house rules, impedance targets
2. **Define materials** — `Dielectric` and `Conductor` subclasses with Dk/Df/roughness
3. **Build stackup** — `Symmetric` for symmetric boards, `Stackup` for asymmetric
4. **Set fab constraints** — `FabricationConstraints` with all manufacturing rules
5. **Define vias** — all via types needed (through, micro, stacked, blind, buried, backdrilled)
6. **Add routing structures** — `RoutingStructure` and `DifferentialRoutingStructure` for each impedance target
7. **Add design rules** — Tags and `design_constraint()` for clearances if needed
8. **Verify** — `pyright` type check, then `jitx build` with a test design (sequence builds — don't parallelize against the same project; see `jitx/SKILL.md` "Build Safety")

## API Reference

For complete class definitions, all parameters, method signatures, and additional examples, see [JITX Documentation](https://docs.jitx.com).

## Formatting

```bash
ruff format path/to/substrate.py
```
