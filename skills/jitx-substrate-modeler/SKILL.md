---
name: jitx-substrate-modeler
description: "Use when the user asks to create a substrate, define a stackup, add via definitions, set up routing structures, configure impedance control, define differential pairs, set fabrication rules, ring a shape with fence vias, fence a pour outline, fence an antipad, model a PCB layer structure, model a substrate from a fabrication house's stackup report (CSV, PDF, or quote), or verify a substrate against its source report. Ask which fabrication house is targeted. If JLCPCB is confirmed, use available jitxlib.jlcpcb predefined substrates; otherwise create a custom substrate. Covers Stackup, Symmetric, materials, vias, routing structures, differential routing structures, NeckDown, via fencing, fenced pours, geometry, reference planes, and FabricationConstraints."
---

# JITX Substrate Modeler

Generate complete JITX Python substrate definitions — stackups, materials, vias, routing structures, and fabrication constraints — all in a single file.

A substrate task is **not complete** until the **Substrate completeness check** block (near the end of this skill) is filled out, row by row, in your completion summary. Prose that paraphrases some of its rows is not the block. Where the base `jitx` skill's task-acceptance block is in play, embed this block inside it rather than producing two competing completion artifacts. No filled block, no "done".

## Predefined Substrates (JLCPCB Only)

If the user has confirmed they are targeting **JLCPCB** as their fabrication house, predefined substrates from `jitxlib.jlcpcb` are available. These are production-validated with correct materials, vias, fab rules, and impedance-matched routing structures:

| Class | Layers | Prepreg | Routing Structures | Import |
|-------|--------|---------|-------------------|--------|
| `JLC04161H_1080` | 4 | 1080 | RS_50, DRS_90, DRS_100 | `from jitxlib.jlcpcb import JLC04161H_1080` |
| `JLC04161H_7628` | 4 | 7628 | RS_50, DRS_90, DRS_100 | `from jitxlib.jlcpcb import JLC04161H_7628` |
| `JLC06161H_7628` | 6 | 7628 | RS_50, DRS_100 | `from jitxlib.jlcpcb import JLC06161H_7628` |

Each includes: Symmetric stackup, JLCPCBRules (FabricationConstraints), 9 JLCPCB via definitions (StdVia, StdViaPreferred, MultiLayerVia1-3 + Preferred variants, StdViaTentedFilled for via-in-pad), and routing structures for 50/90/100 ohm impedance targets.

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

For a same-model self-critique pass on the substrate after writing (catches what these rules don't), invoke `jitx-code-review`. Optional for single-task use.

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

## Source Documents

**A description of a document is not a document, and it does not yield a substrate.**
A user relaying a stackup in prose, in a chat message or from memory, has given you a
handful of the roughly forty facts a real report carries, and the ones they omit are the
ones they did not think to mention rather than the ones that do not matter. Do not
generate a substrate from it. Not a partial one, not a scaffold, not one with the gaps
named: every value that traces to no source row is an invented number, and labelling it
`UNSOURCED` is a disclosure rather than a provenance. A file that looks like a substrate
will be built on, and the label will not travel with the number.

**The deliverable is the transcription, with the blanks visible.** Write the source
document out in this skill's fab-CSV schema, fill the cells the relay actually states,
and leave every other cell empty. That artifact has zero invented values in it, tells the
user exactly what to ask the fab for, and becomes a substrate the moment the empty cells
are filled. Lead with the count of empty cells and group them by who can answer them:
most stackups need one email to the fab.

Ask for the report as well. It exists, because the fab produced it to build against, and
a stackup nobody can produce a document for is not one anyone should build to.

This is the whole of the answer for a relayed stackup. There is no path here that
produces substrate code, and a user asking again for one is asking for a file whose
numbers nobody can stand behind. Say that plainly rather than producing it with caveats.

When the substrate comes from a source document — a fab's stackup report or quote, a laminate datasheet, a written spec — the document is **ground truth**: transcribe it, and trace every value in the substrate to a row, table cell, or field of the source. The only derived values are this skill's named engineering defaults (e.g. the reference-plane width default), each labeled at its call site and in the completeness check's Provenance row; anything else the source doesn't state is a question for the user, not an estimate. Parse the document and restate it to the user before writing code — layer count and construction, each dielectric's Dk/Df and their quoted frequency, foil weights and Rz, the via inventory, the impedance targets, the fab rules — and flag anything ambiguous; everything downstream is a transcription of that reading. Where the source disagrees with this skill's reference tables (a Dk, an Rz), the source wins. A format not listed below (a PDF report, an HFSS 3D Layout stackup XML) gets the same treatment: find the document's own structure, then map it onto the sections of this skill.

### Fab stackup report CSV

The JITX-recommended layout for a fab's impedance-controlled stackup report as CSV — the JumpStart kits ship one, and a fab's own export can be annotated into it. It is organized as `SECTION` blocks: `DOCUMENT` (quote metadata, board size, thickness totals, tolerances, finishes, the primary-units declaration), `REVISION_HISTORY`, `MATERIALS_DIELECTRIC`, `MATERIALS_COPPER`, `STACKUP`, `VIAS`, `IMPEDANCE`, `FAB_RULES`, `NOTES`. A differently shaped export gets mapped onto these concepts, not forced through this parsing. Conventions that matter:

- **Dual unit columns.** Dimensions carry `_mil` and `_mm` columns; the schema declares the mm values controlling where the two disagree (JITX is mm-native). Some rows populate only one column, so parse per cell, not per column.
- **`FAB_RULES` maps by the `JITX_attribute` column, not row order.** A row naming an attribute maps onto a mandatory `FabricationConstraints` field (see Fabrication Constraints for the full set). A row with an empty `JITX_attribute` is a capability limit (drill minimums, aspect-ratio ceilings, stacked-microvia counts, minimum dielectric between coppers): read it as written and check it by hand — some state an `N:1` string or a bare count, so they must not go through the same numeric parsing as the mappable rules. See "Capability limits and derived checks" under Fabrication Constraints. **Where a source states two limits for one JITX field, the field can only hold one, and it is usually the looser** — a board with laser and mechanical drilling quotes two drill minimums, `min_drill_diameter` takes the laser figure, and the mechanical minimum stays a hand-checked capability limit. A floor that admits a hole the fab cannot drill is worse than no floor, because it reads as enforced — so the completeness check's **Fab rules** row will not fill without naming which value the field holds and which one you hand-check.
- **`IMPEDANCE` quotes each controlled target once per geometry** — surface microstrip and inner stripline need different widths for the same impedance — with the modelled `eps_eff`, the loss, and a `Ref_layers` column naming that line's reference planes. A row with `Controlled = No` is the fab's default line/space: documentation, not a routing structure.
- **A target column and a modelled column are not interchangeable.** `impedance=` takes the **target** the fab was asked to hit, never the figure its solver returned; the two differ wherever the solve did not land exactly on the target, and a structure declaring the solver's output as its impedance has replaced the design intent with a result. This is the one place the "prefer the fab's modelled figure" habit — right for `eps_eff`, where the field solver beats any closed form — points the wrong way. The modelled impedance, the impedance tolerance and any propagation-delay column have no JITX field: docstring them, and the completeness check's **No-field walk** row is where they are accounted for.
- **A `*-UNC` row is the uncoupled region of the pair it names, not a structure of its own.** It belongs inside that `DifferentialRoutingStructure` as its `uncoupled_region`. Two tells beyond the name: its width equals the coupled row's on every geometry, and its clearance follows the differential rule the source states rather than the single-ended one, because it is still spaced as half of a pair. Counting such a row as a separate target emits a standalone structure whose clearance quietly violates the source's own clearance rule — which is why the completeness check's **Routing structures** row asks for structure count against controlled-row count and how the rows collapse, rather than for a bare count.
- **`NOTES` states the depth basis per drill type** (laser and mechanical depths are not measured the same way) — read it before deriving any aspect ratio.
- **`REVISION_HISTORY` is the re-issue signal.** On a revised report, re-derive everything that is arithmetic over a changed row (annular ring, aspect ratio) and re-run the capability hand-checks rather than carrying stale figures. When *you* are the one issuing the revision, the edit is not finished at the history line: `DOCUMENT`'s own `Revision` and issue date move with it, or the report contradicts itself in the two fields a reader checks first. Neither is an invented value — both follow from the act of issuing a revision — so they are inside even a strict "change only what I give you" instruction. A revision in the *filename* is a third copy of the same fact and the one you cannot keep in sync; prefer `DOCUMENT.Revision` as the single source of truth.

## Materials

Set properties as **class attributes**. Thickness goes on the class (fixed-thickness materials like copper foils) **or** is passed at instantiation (per-stackup dielectric thickness) — **never both**: `Material.__init__` raises `ValueError` if thickness is set as a class attribute and also passed to the constructor.

Soldermask is a `Dielectric` — define it like any other dielectric material:

```python
class SoldermaskLayer(Dielectric):
    """Soldermask — typically Er ≈ 3.8"""
    dielectric_coefficient = 3.8
    loss_tangent = 0.02
    # no thickness here — passed per-stackup at instantiation

class FR4_Prepreg(Dielectric):
    # material_name reaches the translated payload as materialName, so when a
    # source names a manufacturer and product, put it HERE -- not only in the
    # docstring. A docstring is a Python-side record; this crosses into the design.
    # Name and numbers move together: a product name over generic FR-4 constants
    # is a mislabel that now ships. Generic constants get a generic name.
    material_name = "FR-4 2116 prepreg"
    dielectric_coefficient = 4.4   # Dk (dielectric constant / relative permittivity)
    loss_tangent = 0.0168          # Df (dissipation factor)

class FR408HR_2116(Dielectric):
    # Named product, so the constants are that product's -- see the laminate
    # table below, and confirm against the manufacturer's current datasheet.
    material_name = "Isola FR408HR 2116 prepreg"
    dielectric_coefficient = 3.68  # Dk
    loss_tangent = 0.0092          # Df

class FR4_Core(Dielectric):
    dielectric_coefficient = 4.6   # Dk
    loss_tangent = 0.0168          # Df

class Copper1oz(Conductor):
    """RTF foil. Rz matte 6.0 µm / drum 3.5 µm — docstring is the durable record."""
    thickness = 0.035   # mm
    roughness = 0.0060  # mm (matte Rz ÷ 1000); field slated for deprecation — see below

class CopperHalfOz(Conductor):
    """HVLP-2 foil. Rz matte 2.0 µm / drum 0.7 µm."""
    thickness = 0.0175  # mm
    roughness = 0.0020  # mm (matte Rz ÷ 1000)
```

**`Conductor.roughness` is slated for deprecation — the durable home for roughness data is the material docstring.** Fab reports state roughness as Rz in **micrometres**, matte and drum side separately; record both sides in the docstring in the source's own units (the matte side faces the dielectric and dominates conductor loss) so simulation-side tools can consume them. On versions that still carry the field, you may also set the scalar (read as mm: matte-side Rz ÷ 1000) — but don't build logic on it, and never drop the source's roughness data just because the field is going away.

**Unit conversions — JITX is mm throughout; convert as you transcribe:**

- **mils → mm**: × 0.0254. When a source gives both units, follow the unit it declares controlling; absent a declaration, prefer the mm figure (JITX is mm-native) and use the other column as a cross-check.
- **Copper weight (oz) → mm**: prefer the source's **finished** thickness where it states one — outer layers gain panel plating past the nominal foil weight (1 oz ≈ 0.035 mm base foil), and `Conductor` has no copper-weight field, so the finished thickness is the number the stackup actually sums to. Record the nominal weight in the docstring.
- **Rz (µm) → mm**: ÷ 1000, matte side, if setting the deprecated `roughness` scalar (see above).

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

### Choosing Symmetric vs explicit Stackup

`Symmetric` is for boards you are designing symmetric by construction. **When you are transcribing a source document that names both halves — a fab stackup report numbering L1..L20 with a function per layer — use the explicit `Stackup` instead**, even when the construction happens to be symmetric: `Symmetric`'s mirrored half is generated proxies that cannot carry the source's layer ids, so a design-side layer name no longer identifies a source row and row-by-row traceability breaks for half the board.

### Symmetric (boards symmetric by construction)

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

**Code laser vias in drill direction**: `start_layer` is the surface the via is drilled from. A bottom-side microvia the source states as "from L20 to L19" is `start_layer = -1, stop_layer = -2` (negative indices count from the bottom) — not an ascending positive pair that reverses the entry surface.

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

Add `models=` only from simulated or measured data. A fab report contains no electrical models — with no `models=`, JITX inserts placeholders that correctly flag SI constraints until simulated ones exist. That is the right signal, not a gap to paper over with invented numbers.

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

**When the source's impedance table quotes a modelled `eps_eff`, use it directly — `phase_velocity(eps_eff)`.** The fab's field-solved figure already includes what closed forms only approximate (a coated microstrip's eps_eff folds in the soldermask and varies with line width), so no single formula reproduces it. The formulas below are fallbacks for when no modelled figure exists:

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

**Other routing-structure units:** `insertion_loss` is dB/mm; `pair_spacing` (differential) is the edge-to-edge gap between P and N.

### From a fab impedance table

One structure per controlled impedance target, with a layer entry for every layer/geometry the table lists — the same target needs a different width on surface microstrip than on inner stripline, keyed by conductor index (see the fab-CSV schema's `IMPEDANCE` conventions). Include neck-down and uncoupled-region entries where the table quotes them, and only there — never borrow a neck geometry from another row. Rows with no controlled target are documentation, not structures.

### symmetric_routing_layers()

Define top half only — mirrors to bottom using `-layer - 1` index:

```python
layers = symmetric_routing_layers({
    0: RoutingStructure.Layer(...),   # → also creates layer -1
    2: RoutingStructure.Layer(...),   # → also creates layer -3
})
```

### Layer with NeckDown

Neckdown parameters describe the structure only; how a neckdown region is activated, and the code-side alternative for stepping a width down into a package pad, are in the `jitx-layout-constraints` skill, "Fanout".

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

**Reference planes of unstated width:** source documents usually say *which* planes reference each line (a `Ref_layers` column) and never how wide they are. Carry the column — it is part of the impedance model, not decoration. For the width, use the skill's engineering default: **desired width = 3 × the dielectric thickness between the signal layer and that reference plane** (return current concentrates within a few dielectric heights of the trace; 3× captures it). Each plane gets 3× its *own* separation — a stripline's two references can differ — and a reference more than one dielectric away sums the dielectric thicknesses between. Label the value as the skill default at the point of use, and record it in the completeness check's Provenance row as `skill default (3× dielectric height)` — a named, rule-backed default is not an invented number, but an unlabeled one is:

**Label every call site.** Write the width as its derivation with the label on the same line — a section comment above the block is not enough; a reviewer reads the call site, and the summary's claim "labeled at every call site" must be literally true:

```python
# Ref planes L2 (above) and L4 (below), each across one 0.100 mm build-up:
.reference({1: 3 * 0.100, 3: 3 * 0.100})  # skill default: 3× dielectric height, not a source value
```

Do **not** pass `None` widths (`.reference(dict.fromkeys(...))`): construction accepts the mapping, but translation assigns `desired_width` straight into a protobuf float and **fails at build time** — a trap, not a fallback (verified against jitx 4.2.2 `_translate/routing.py`). If the user insists on strict source-only transcription with no defaults, record the `Ref_layers` identities in the docstring, omit `.reference()`, and name the omission as an open item in the completeness check. The scalar form `reference(layer)` without a width raises `TypeError: Must specify desired_width if layer is not a mapping`. Either way, never silently fill in a width nothing backs — the unlabeled invented number is exactly the failure the completeness check exists to catch.

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

**Differential with NeckDown (parameters for a neckdown region activated in the UI; for code-side escape rules see `jitx-layout-constraints`):**

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

Custom attributes are allowed for fab-house-specific rules that are genuinely numeric lengths in mm (not engine-enforced, but shaped like the 19 real fields). **Capability limits that are not mm lengths — `N:1` aspect-ratio ceilings, stacked-microvia counts, available-on-request options — go in the class docstring, not as class attributes**: an unenforced count sitting in the same namespace as engine-enforced floats reads as enforced when it isn't. `FabricationConstraints` declares exactly 19 fields; a missing mandatory field fails translation.

### Capability limits and derived checks

Capability limits are verified by review and by tests against the area they govern — drill and aspect-ratio limits against the via inventory, minimum-dielectric limits against the stackup — the engine does not enforce them. The two standard derivations:

- **Annular ring** = `(pad − hole) / 2`, checked against the source's minimum annular ring.
- **Aspect ratio** = drill depth ÷ finished hole diameter, **on the depth basis the source states for that drill type** — laser depths are typically the ablated dielectric span, mechanical depths the full drilled depth; one convention applied to both gives wrong ratios.

**A value landing exactly on a limit is not a violation.** Fab capability limits are inclusive unless the source says otherwise, and a build-up designed to its own stated ratio will sit on the limit for every via of that type — by construction, not by accident. Reading a maximum as exclusive turns a correct stackup into a wall of capability failures and stops the task. If the source genuinely leaves the convention open and the answer changes your verdict, ask rather than picking.

## Design Constraints (Tags)

Design rules (`design_constraint(...)`, `UnaryDesignConstraint`,
`BinaryDesignConstraint`, builtin tags, `OnLayer`, priority, every rule
effect, and why a rule did not fire) are owned by the **jitx-layout-constraints**
skill. This skill owns what those rules read from: `FabricationConstraints`
(the enforced floors), via definitions, and routing structures. The one
substrate-side rule still declared here is the fenced pour outline below,
because its via class and fence pattern live on the substrate.

### Substrate sharp edges (verified on real boards)

- **Fenced differential structures can't use `symmetric_routing_layers`** (seen on
  4.2: the fence via's layer endpoints can't be mirrored, layers stay a lazy
  attribute, and applying the DRS via a rule dies with `DesignTranslationContext
  is not active`). Enumerate the fenced coupled layers explicitly
  (`layers={0: ..., -1: ..., 1: ..., -2: ...}`); keep `symmetric_routing_layers`
  for fence-less structures. A module-scope `RoutingStructure` (not an attribute
  of a Substrate class) hits the same lazy-layers error.
- **Cannonball-Huray roughness tuples don't fit `Conductor.roughness`** (scalar
  only, `TypeError: must be real number, not tuple`). Keep a scalar on the
  substrate; carry the Huray pair as a simulation-side surface-roughness override
  (e.g. the SI tool's stackup override), not on the jitx stackup.

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

Do not set `isolate=` on the fence Pour; it is deprecated. Pour clearance is a design rule; see the `jitx-layout-constraints` skill, Pours.

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

## Smoke-Test Wiring (Board and Design)

The minimum design that proves a substrate builds. Full Design assembly is the base `jitx` skill's territory; the substrate-relevant facts are: the substrate binds on the `Design`, not the `Board`, and `Board` holds only `shape` and `signal_area` — via availability is not a Board concern, because every `Via` class on the substrate registers automatically off the substrate walk:

```python
from jitx.board import Board
from jitx.design import Design
from jitx.shapes.composites import rectangle

# The source's stated board size, when it gives one (DOCUMENT section).
BOARD_W, BOARD_H, CORNER_R = 80.0, 80.0, 4.0
EDGE_KEEPOUT = MyFabRules.min_copper_edge_space

class MyBoard(Board):
    shape = rectangle(BOARD_W, BOARD_H, radius=CORNER_R)
    # Inset by the fab rule rather than a picked number: the engine enforces
    # min_copper_edge_space on copper anyway, so the placement/routing area
    # stays consistent with what it will enforce.
    signal_area = rectangle(BOARD_W - 2 * EDGE_KEEPOUT, BOARD_H - 2 * EDGE_KEEPOUT,
                            radius=CORNER_R - EDGE_KEEPOUT)

class MyDesign(Design):
    board = MyBoard()
    substrate = MySubstrate()
    circuit = MyCircuit()  # an empty Circuit suffices for a substrate smoke test
```

**With no runtime, `jitx build --dry --no-dependency-check` still translates.** It answers "does this substrate translate at all" offline — stackup, vias and fab rules all reach the payload and a structural error surfaces. Both flags are needed: `--dry` skips the runtime probe, but the pyproject dependency sync is gated on `--no-dependency-check` alone and runs regardless of `--dry`, so `--dry` by itself still reaches the network and fails offline for a reason that has nothing to do with your substrate. The CLI's own `--dry` help text claims it skips the dependency check; it does not — read the behaviour, not the help string. It needs a project, which is often the only thing missing: a minimal `pyproject.toml` is four lines away, and "no project, so no build" is not the same claim as "cannot be translated". Run it and record the real message. It does **not** satisfy a build gate — see the base `jitx` skill — but reporting a substrate unverified when `--dry` was available is a check skipped, not a check unavailable.

**This design, not the scaffold's seeded one, is what a substrate task builds to be done.** `jitx project layout init` seeds a design that subclasses `SampleDesign` and overrides only `circuit`, so it binds **`SampleSubstrate`** — a two-layer sample stackup — and never yours. That build is green and meaningless for your work: it exercises none of your substrate file, which could be empty. Bind your own substrate on your own `Design` and build that. It proves the toolchain, which is worth doing before you write code, and proves nothing about your work afterwards. Add the design above as a **new** class rather than editing the seeded one: the scaffold's smoke target stays intact, and a fresh target has no previously-built design directory to diff against, so the runtime does not stop to ask about the component instances that vanished.

## Layer Index Convention

- Indices count **conductors only** — dielectrics and soldermask are not indexed. For an N-copper stackup: `0`…`N-1` from the top, `-1`…`-N` from the bottom (20 copper: `0` is L1, `-1` is L20).
- `0` / `Side.Top` = top conductor
- `1` = second conductor from top
- `-1` / `Side.Bottom` = bottom conductor
- `-2` = second from bottom
- `symmetric_routing_layers` maps layer `i` to `-i - 1`

## Verifying a Substrate Against Its Source

For a report-driven substrate, back the completeness check with tests that **parse the source at test time and compare it to the built design**. Re-typing the report's numbers into `EXPECTED_*` constants beside the test is not this: it compares one transcription against another, so a re-issued report needs *both* files edited and the suite goes green either way. The entire value is that the source moves and the suite notices; read the file. Cover layer order and names, thicknesses, Dk/Df, via spans and geometry, every `FabricationConstraints` field, per-layer widths and reference planes, so a re-issued report fails the suite instead of drifting past it. Compare reference-plane *identities* against the source; assert any skill-default widths against the default's own formula (3× dielectric height) — the source never stated them, so testing them against the source would be circular.

**Tests must subclass `jitx.test.TestCase`, never plain `unittest.TestCase`** (verified on jitx 4.2.2–4.4.0rc1). It activates the JITX instantiation context, and needs no runtime — instantiating a design works offline. Without the context the design does not error, it **reads as empty**: `decompose(stackup, Material)` returns zero layers and raises nothing, and iterating `stackup.conductors` hangs. Defend in depth:

- assert the layer count against the source's row count **before** any per-row comparison, and
- pass `strict=True` to every `zip` of source rows against design elements.

A suite that zipped a full report against an empty layer list and compared nothing at all would otherwise report green.

**`decompose()` yields proxies, so read `ClassVar`s off the instance, not off the type.** `decompose(stackup, Material)` returns `Proxy` objects rather than instances of your material classes. Instance attribute access forwards fine, but only for the fields that layer's own class declares: `thickness` is on `Material`, `roughness` on `Conductor` alone, `dielectric_coefficient` and `loss_tangent` on `Dielectric` alone. So `decompose(stackup, Material)` hands back a mixed list where `layer.roughness` raises on every dielectric and `layer.dielectric_coefficient` raises on every conductor — decompose by `Conductor` or `Dielectric` when you want the subtype fields. Reading through the type fails for a second reason: `type(layer).roughness` raises `AttributeError: type object 'Proxy' has no attribute 'roughness'` on every layer, whatever its kind. Since `roughness`, `dielectric_coefficient` and `loss_tangent` are all declared `ClassVar` in `jitx/stackup.py`, reaching for them through the class is the natural first attempt when writing exactly these tests. Unlike the empty-stackup trap above this one fails loudly, so it costs a minute rather than a false green.

## Workflow

1. **Gather specs** — from the source document when one exists (see Source Documents — it is ground truth): stackup cross-section, dielectric properties (Dk, Df), copper weights, fab house rules, impedance targets
2. **Define materials** — `Dielectric` and `Conductor` subclasses with Dk/Df/roughness
3. **Build stackup** — explicit `Stackup` whenever the source names both halves (fab reports do); `Symmetric` only for boards symmetric by construction
4. **Set fab constraints** — `FabricationConstraints` with all manufacturing rules
5. **Define vias** — all via types needed (through, micro, stacked, blind, buried, backdrilled)
6. **Add routing structures** — `RoutingStructure` and `DifferentialRoutingStructure` for each impedance target
7. **Add substrate-side rules** — the fenced pour outline rule when the design needs one; board design rules (defaults, clearances, net classes, escapes) are the `jitx-layout-constraints` skill's step, not the substrate's
8. **Verify** — `pyright` type check, then `jitx build` with a test design (sequence builds — don't parallelize against the same project; see `jitx/SKILL.md` "Build Safety"); for a report-driven substrate add source-driven tests (see "Verifying a Substrate Against Its Source"); then fill the **Substrate completeness check** below. No filled block, no "done".

## Substrate completeness check — run before calling it done

A substrate is judged by whether every value in it traces back to its source — a fab stackup report (CSV or PDF), a laminate datasheet, or the user's spec. The predictable failure mode is not a missing feature; it is an **invented number sitting where it looks authoritative**: a plane width the source never stated, a Dk carried over from another design, a via added "for later." Before presenting a substrate as complete, fill this block in the completion summary, each row with its evidence (source row/section → class or attribute). A row you cannot check is an open item to name to the user — not a silent pass.

```
## Substrate check
Source: <document + revision/date, or "user spec, conversation">
Stackup: <N> copper layers, every physical layer present incl. soldermask;
         summed thickness <x.xxx> mm vs source's stated total <x.xxx> mm — reconciles | MISMATCH
Materials: one class per distinct source material row — <N> dielectrics, <N> conductors;
           Dk/Df, thickness, roughness carried; quoted frequency + values with no JITX field docstringed
Units: everything in mm — spot-check arithmetic for one converted row: <mils→mm, oz→finished mm, or Rz µm→mm>
Vias: <N> defined / <N> the source offers — itemize the source ids; spans, drill type,
      pad/hole, fill/cap/tent reconciled per source (say where fill material/capping has
      no JITX field); aspect ratios checked on the depth basis the source states per drill type
Routing structures: <N> structures / <N> controlled rows the source lists — say how the
      rows collapse; impedance taken from the source's target column, not its modelled
      column; with a layer entry for every geometry/layer the source lists: <list>;
      velocity from eps_eff where the source gives it; pair gap edge-to-edge;
      neck-down + uncoupled regions where given; reference planes carried
Fab rules: <N>/<N> mappable rules in FabricationConstraints; capability limits with no
      JITX field documented: <list | none>; where two source limits contend for one
      field, which value the field holds and which is hand-checked: <list | none>
No-field walk: every source section walked (document-level tolerances, surface finish,
      plating class, quote metadata included) — stated values with no JITX field
      docstringed: <list>
Provenance: values traceable to no source row: NONE | <list + the labeled rule backing each>
Checks: pyright <clean | N errors>; build <clean | not run: <reason>>
Verdict: complete | open items: <list>
      Derive this line from the Checks row above, do not compose it: every check
      there that is not clean — failed, skipped, or unavailable in this
      environment — is copied here as an open item, and the count must match.
      "complete" with an empty open-items list asserts every check ran clean.
      An unavailable environment is an open item, not an exemption: "no runtime,
      so no build" is exactly the case this line exists to record.
```

Row-by-row intent — the *why*, so the block stays evidence rather than ceremony:

- **A total you solved for is not a total you checked.** Where a dielectric thickness is
  unstated and the finished thickness is known, it is arithmetically tempting to solve the
  unknown as the balancing term. Do that and the reconciliation becomes tautological: the
  total agrees because it was constructed to agree, and the check that would have caught a
  transcription slip can no longer fail. If a thickness is unstated, it is an open question
  with the fab, and the reconciliation is reported as not performed rather than performed
  and passed.
- **Stackup** — the summed thickness must reconcile with the source's stated totals under the document's own stated inclusions and precision (which layers each total includes, how many digits it prints); an unexplained residual is a transcription slip to chase, not rounding to wave off. Name copper layers for their source id and function.
- **Materials** — one class per distinct material/property set: never collapse two source rows that differ in any modeled property (Dk, Df, roughness, thickness); the collapsed row is untraceable. What the source states but JITX has no field for survives in docstrings, not by being dropped — and the walk covers *every* section of the document (tolerances, surface finish, plating class), not just the material tables.
- **Vias** — every `Via` class on a substrate registers on the board automatically, so define exactly the source's inventory and nothing speculative. Fab reports state drill depth on different bases for laser vs mechanical drills — check each aspect ratio on the basis that matches its drill, not one convention for all.
- **Routing structures** — the same impedance target usually needs a different width on each geometry (surface microstrip vs inner stripline); carry every layer the source lists. A source's default line/space row with no impedance target is documentation, not a `RoutingStructure` — modelling it means inventing the numbers it doesn't quote.
- **Fab rules** — mandatory `FabricationConstraints` fields fail translation when missing; capability limits with no JITX field are recorded as documentation, never force-fit through the same numeric parsing as the mappable rules.
- **Provenance** — if the source doesn't state a value, ask the user or document the omission. Never invent a number to satisfy a type checker or complete a struct; suppress the type error with a comment saying why instead.

## API Reference

For complete class definitions, all parameters, method signatures, and additional examples, see [JITX Documentation](https://docs.jitx.com).

## Formatting

```bash
ruff format path/to/substrate.py
```
