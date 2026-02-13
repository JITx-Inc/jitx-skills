---
name: jitx-substrate-modeler
description: Model JITX substrates including stackups, materials, vias, routing structures, and fabrication constraints. Use when user asks to create a substrate, define a stackup, add via definitions, set up routing structures, configure impedance control, define differential pairs, set fabrication rules, or model a PCB layer structure. Covers Stackup, Symmetric, Conductor, Dielectric, Via (laser, mechanical, backdrilled, blind, buried, stacked), RoutingStructure, DifferentialRoutingStructure, NeckDown, via fencing, geometry, reference planes, and FabricationConstraints.
---

# JITX Substrate Modeler

Generate complete JITX Python substrate definitions — stackups, materials, vias, routing structures, and fabrication constraints — all in a single file.

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

Set properties as **class attributes**, instantiate with thickness:

```python
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

| Copper Type | Surface Roughness (Rz) | Use Case |
|-------------|------------------------|----------|
| Standard (STD) | 5–10 μm | Inner layers, low frequency |
| Reverse Treated Foil (RTF) | 3–5 μm | Inner layers, better adhesion |
| Low Profile (LoPro) | 2–3 μm | RF signal layers |
| Very Low Profile (VLP) | 1–2 μm | High-frequency RF (>10 GHz) |
| Hyper VLP (HVLP) | <1 μm | mmWave applications |

**Rule of thumb:** For signals above 5 GHz, use LoPro or smoother. Above 10 GHz, use VLP. For mmWave (>24 GHz), use HVLP.

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

Top-to-bottom order. Named attributes or list:

```python
class My8LayerStackup(Stackup):
    top_mask = SoldermaskLayer(thickness=0.02)
    L8 = ThinCopper(name="L8-Patch")
    sub7 = Prepreg326(thickness=0.068)
    L7 = ThinCopper(name="L7-GND")
    # ... all layers top to bottom ...
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

```python
class BackdrilledVia(Via):
    type = ViaType.MechanicalDrill
    start_layer = Side.Top
    stop_layer = Side.Bottom
    diameter = 0.6
    hole_diameter = 0.3
    # Single Backdrill — assumed from bottom
    backdrill = Backdrill(
        diameter=0.5, startpad_diameter=0.7,
        solder_mask_opening=0.8, copper_clearance=0.6,
    )
```

**Dual backdrill (both sides):**

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
8. **Verify** — `pyright` type check, then `python -m jitx build` with a test design

## API Reference

For complete class definitions, all parameters, method signatures, and additional examples, see [https://docs.jitx.com].

## Formatting

```bash
ruff format path/to/substrate.py
```
