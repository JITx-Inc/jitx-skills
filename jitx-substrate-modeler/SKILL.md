---
name: jitx-substrate-modeler
description: This skill should be used when the user asks to "create a substrate", "define a stackup", "add via definitions", "set up routing structures", "configure impedance control", "define differential pairs", "set fabrication rules", or "model a PCB layer structure". Ask the user which fabrication house they are targeting — if they confirm JLCPCB, predefined substrates from jitxlib.jlcpcb (JLC04161H_1080, JLC04161H_7628, JLC06161H_7628) are available with 4/6-layer FR-4, 50/90/100 ohm routing structures, vias, and fab rules. Otherwise, create a custom substrate. Covers Stackup, Symmetric, Conductor, Dielectric, Via (laser, mechanical, backdrilled, blind, buried, stacked), RoutingStructure, DifferentialRoutingStructure, NeckDown, via fencing, geometry, reference planes, and FabricationConstraints.
---

# JITX Substrate Modeler

Generate complete JITX Python substrate definitions — stackups, materials, vias, routing structures, and fabrication constraints — all in a single file.

## Rule 0 — Verify every API before using it

Do not guess at imports, class names, or constructor kwargs. Common landmines that have been caught as wrong guesses:

- Board outline: **there is no `RoundedRectangle` class.** Use the function `rectangle(width, height, *, radius=…)` from `jitx.shapes.composites`. Set the outline as `design.board.shape = rectangle(80.9, 50.0, radius=3.0)`.
- `Design` exposes `.board: Board` and `Board` exposes `.shape: Shape` — set the shape attribute directly, not via a constructor kwarg.
- `SampleDesign` ships a default `SampleBoard` whose shape is `rectangle(50, 50, radius=5)`; override `self.board.shape` (or subclass `Board`) to change it.

Verification order: (1) canonical repos `github.com/JITx-Inc/py-jitx` and `github.com/JITx-Inc/py-jitx-stdlib`; (2) `https://docs.jitx.com/llms.txt`; (3) installed venv site-packages or `~/.jitx/`. If unresolvable, document as unknown — do not invent an import.

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

⚠ **`jitxlib.jlcpcb` may be missing in pre-release jitx wheels.** The
4.1.0a7 pre-release does not ship `jitxlib.jlcpcb`:
`from jitxlib.jlcpcb import JLC04161H_1080` raises `ModuleNotFoundError`,
and `find ~/.venvs/<proj>/lib/python*/site-packages/jitxlib -name 'jlcpcb*'`
returns no matches. If a port's Stanza source uses a JLCPCB stackup
(e.g. `jlcpcb-jlc2313`) but the installed jitx wheel doesn't ship
`jitxlib.jlcpcb`, copy the canonical 4-layer FR4 template from
[`references/templates/four_layer_fr4.py`](references/templates/four_layer_fr4.py)
into the project and specialise the dielectric thicknesses to match
your fab. See §"Hand-rolled 4-layer FR4 substrate" below for the
template walkthrough.

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
- Use matte-side roughness for the bottom surface of a trace; drum-side for the top. The matte side is the rougher of the two — typical Ra range 0.18–0.51 µm for standard foils; the drum side is much smoother. The Ra/Rz ratio depends on the foil profile (commonly ~0.1–0.25 for matte side); if you need an exact Ra, take it from the foil datasheet rather than computing it from Rz with a single constant. The `0.0573 × Rz` factor in the row above is the Cannonball-Huray *nodule radius*, not Ra.

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

### Hand-rolled 4-layer FR4 substrate

When `jitxlib.jlcpcb` isn't installed (e.g. on jitx 4.1.0a7 pre-
releases) but the design needs a 4-layer FR4 stackup with reasonable
50/100 ohm routing, use the canonical template at
[`references/templates/four_layer_fr4.py`](references/templates/four_layer_fr4.py).
Copy-paste into the project's `substrate.py`, rename the class to
match your design, and adjust dielectric thicknesses to match your
fab. The template provides:

- `FourLayerFR4Substrate(Substrate)` — wraps a nested
  `class stackup(Symmetric)` (1080 prepreg, 1 oz outer / 0.5 oz inner
  copper) with fabrication constraints, mechanical-drill via, and 50
  ohm single-ended + 100 ohm differential routing structures
- `FabRules(FabricationConstraints)` — sensible default fab constraints

The same shape works for non-JLCPCB targets — just edit the
dielectric thicknesses and Cu thickness fields to match the fab's
spec sheet. Use the routing-structure block as a starting point and
hand-tune impedance using `phase_velocity(...)` (covered in §"Routing
Structures").

## Via Types

Define as **nested classes** inside Substrate. All properties are `ClassVar`.

> ⚠️ **Two pitfalls observed in the wild** (TEC-example pilot):
>
> 1. **Attribute names are `start_layer` / `stop_layer`** (with `_layer`
>    suffix), NOT `start` / `stop`. Some `Via` docstring examples in the
>    package source show `start = Side.Top; stop = Side.Bottom` — that
>    form is broken and causes
>    `AttributeError: type object 'THVia' has no attribute 'start_layer'`
>    at build time. Always use the `_layer` suffix.
> 2. **Vias must be nested classes, not instance attributes.** Placing
>    `th_via = THVia()` as an instance attribute on a `Substrate` raises
>    `InvalidElementException: THVia element substrate.th_via has no effect`
>    at build time:
>
>    ```python
>    # WRONG — instance attribute:
>    class MySubstrate(Substrate):
>        stackup = MyStackup()
>        th_via = THVia()              # → InvalidElementException
>
>    # RIGHT — nested class:
>    class MySubstrate(Substrate):
>        stackup = MyStackup()
>        class THVia(Via):
>            start_layer = 0
>            stop_layer = 3
>    ```
>
> Prefer **integer layer indices** (`0` = top, `N-1` = bottom) for clarity
> when the substrate has more than two layers. `Side.Top` / `Side.Bottom`
> resolve correctly for `start_layer` / `stop_layer` on a two-sided
> stackup but are ambiguous on a four-layer build — int indices are
> always unambiguous.

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
    start_layer = 0         # Side.Top also works
    stop_layer = -1         # Side.Bottom also works
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

### Thermal vias via `design_constraint(...).stitch_via(...)`

There is **no `add_thermal_vias(net, shape)` helper** in JITX 4.x. To
place a grid of vias under a thermal pad (or any high-current / heat-sink
copper region), use a `design_constraint` with `.stitch_via(...)`:

```python
from jitx.constraints import design_constraint, Tag
from jitx.constraints import SquareViaStitchGrid

class GNDThermalTag(Tag): pass

# In the calling Circuit's __init__:
self.GND_tag = GNDThermalTag()
self.GND += self.GND_tag                              # tag the net

self.thermal_via_rule = design_constraint(
    self.GND_tag,
).stitch_via(
    MySubstrate.THVia,                                # which via class to place
    SquareViaStitchGrid(pitch=1.2, inset=0.3),        # grid pattern (mm)
)
```

**Prerequisites that aren't obvious from the API shape — both must be
true or the constraint silently does nothing:**

1. The target net **must have a `Tag`**, applied via
   `net += MyTag()`. Without the tag, `design_constraint(...)` has
   nothing to attach to.
2. A copper **`Pour` must already cover the area** where vias should
   be stitched (typically the thermal-pad copper). `stitch_via` populates
   an existing pour with vias; it does not create copper. If the pour is
   missing, the router has nothing to stitch and the constraint produces
   zero vias.

Common pattern with a class-D amp / QFN thermal pad:

```python
# Pour copper under the thermal pad on layer 0 (top) and layer -1 (bottom)
self.GND += Pour(rectangle(8.0, 8.0), layer=0,  isolate=0.1, rank=2)
self.GND += Pour(rectangle(8.0, 8.0), layer=-1, isolate=0.1, rank=2)

# Tag the GND net so the constraint can reference it
self.GND += GNDThermalTag()

# Stitch vias through the thermal-pad area
self.therm_rule = design_constraint(GNDThermalTag()).stitch_via(
    MySubstrate.THVia,
    SquareViaStitchGrid(pitch=1.0, inset=0.5),
)
```

This is a **layout-quality concern** (thermal performance), not a
connectivity concern — a Phase 6 / DRC build will pass without thermal
vias even when they should be there. If thermal vias must wait, leave a
visible TODO so they get added before fab.

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
8. **Verify** — `pyright` type check, then `python -m jitx build` with a test design (sequence builds — don't parallelize against the same project; see `jitx/SKILL.md` "Build Safety")

## API Reference

For complete class definitions, all parameters, method signatures, and additional examples, see [JITX Documentation](https://docs.jitx.com).

## Formatting

```bash
ruff format path/to/substrate.py
```
