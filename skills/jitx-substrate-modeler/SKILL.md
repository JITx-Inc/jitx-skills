---
name: jitx-substrate-modeler
description: "Use when the user asks to create a substrate, define a stackup, add via definitions, set up routing structures, configure impedance control, define differential pairs, set fabrication rules, ring a shape with fence vias, fence a pour outline, fence an antipad, model a PCB layer structure, model a substrate from a fabrication house's stackup report (CSV, PDF, or quote), or verify a substrate against its source report. Covers Stackup, Symmetric, materials, vias, routing structures, differential routing structures, via fencing, fenced pours, geometry, reference planes, and FabricationConstraints."
---

# JITX Substrate Modeler

Write one Python file holding the substrate. API shapes, units and pitfalls are in the docstrings of `jitx.stackup`, `jitx.via`, `jitx.si`, `jitx.substrate`, `jitx.constraints`, `jitx.inspect`, `jitx.test` and `jitxlib.physics`, and in the JITX docs page [Substrate & Stackup](https://docs.jitx.com/en/latest/essentials/design/substrate.html) (its Vias section: layer indices count conductors only).

`jitxlib.jlcpcb` (the separate `jitxlib-jlcpcb` distribution) is a reference implementation of substrates.

## Route first

- Environment and Design assembly: the base `jitx` skill.
- Design rules and pour clearance: `jitx-layout-constraints`. The substrate declares no design rule except a fenced pour's `fence_via` rule.
- Substrate-shaped tables (layer-to-via maps) live on the substrate; instantiate a generic stackup rather than inline-subclass it with an empty body: the `jitx` skill's [architectural patterns 4a](../jitx/references/architectural-patterns.md#sub-example-4a-substrate-shaped-tables) and [7](../jitx/references/architectural-patterns.md#7-dont-pass-through-inline-subclass--instantiate).
- Self-review: `jitx-code-review`.

## The source document is ground truth

Trace every value to a source row, cell or field. The only derived values are this skill's named defaults, each labelled at its call site and under Provenance; anything else unstated is a question for the user. With no document, ask for a datasheet for Dk, Df and their frequency; label any value used without one at its call site (`# skill default: assumed, no datasheet`) and list it as an open item. Before code, restate the document to the user: layer count and construction, each dielectric's Dk/Df and frequency, foil weights and Rz, vias, impedance targets, fab rules, and what is ambiguous.

Traps in any report format:

- Follow the unit the report declares controlling, and read per cell, since a unit column can be half empty. Use finished copper thickness when stated; for a weight alone, convert at 1 oz base foil = 0.035 mm, label the value and list it as an open item.
- On a controlled row's structure, `impedance=` is the target the fab was asked to hit, not its solver's figure.
- An uncoupled-region row belongs inside the pair it names, not in a structure of its own: count structures against controlled rows.
- Where the report states two limits for one JITX field, the field holds the looser and you hand-check the other (laser and mechanical drill minimums: `min_drill_diameter` takes the laser figure). A rule with no JITX field is a hand-checked capability limit.
- On a revised report, re-derive every figure computed from a changed row.

Then:

- A report naming both halves gets an explicit `Stackup`, not `Symmetric`, so each layer keeps its source id; name copper layers for source id and function.
- One material class per distinct source row. A named product goes in `material_name`; generic constants get a generic name. Record matte and drum Rz (µm, as stated) in the conductor's docstring. If you set the `roughness` scalar, it is read as mm: matte-side Rz ÷ 1000.
- Define exactly the source's vias: every `Via` class on the substrate registers on the board. Set `models=` only from simulated or measured models the source supplies; a fab report has none (see `Via.models`). A via the report caps sets `filled = True`. Code laser vias in drill direction: a bottom-side via drilled from L12 to L11 is `start_layer = -1, stop_layer = -2`. A stacked microvia the source lists as one row is one laser `Via` spanning the stack (L1 to L3 is `start_layer = 0, stop_layer = 2`).
- One structure per controlled target, with a layer entry for each geometry the report lists. A row with no controlled target is documentation, not a structure. Velocity is `phase_velocity(eps_eff)` from the report's modelled eps_eff when it gives one; its docstring gives closed forms otherwise.
- The design applies each structure by a tag rule: the parent by its net's tag, a pair included. A neck region the report quotes becomes a structure of its own, of its parent's kind, on its rows' layers, with each row's neck width, gap and clearance and the parent's reference planes; regions with identical neck geometry may share one. Velocity and loss come from the parent row, labelled as a default. Its impedance is one of its rows' modelled neck impedances, labelled with that row, never the parent's target: `Substrate.routing_structure()` looks structures up by impedance. Apply it, like any structure for part of a route, by tagging the code-placed `Route` covering that part (for a pair, the pair's `Route`) with your own `Tag` subclass, above the parent rule's priority: `design_constraint(NeckTag(), priority=1).routing_structure(MySubstrate.NECK, ref_net=self.GND)` (see `Tags` and `UnaryDesignConstraint.routing_structure`). No build has confirmed a structure applied by a `Route` tag: list it as an open item.
- Carry the report's reference planes on every layer entry, uncoupled regions and neck structures included. Their width, which reports never state, is this skill's default: 3 x the dielectric thickness between line and plane (only dielectric rows, summed when not adjacent), one mapping entry per line with its label on that line. Name a sum of rows first (`H_L1_L3 = 0.100 + 0.150`, the dielectrics between L1 and L3), then write `2: 3 * H_L1_L3,  # skill default: 3x dielectric height`. Strict source-only: omit `.reference()`, docstring the planes and name the omission as an open item; never pass `None` widths.
- `symmetric_routing_layers` cannot mirror a fence whose via is not symmetric about the board centre: list each fenced layer explicitly.
- All 19 `FabricationConstraints` fields are mandatory; a missing one fails translation. Only the four `min_copper_*` fields are engine-enforced. Each capability limit with no JITX field goes in the rules class docstring with its unit (`N mm`, `N:1`, `N stacked levels`); a length may instead be a custom mm attribute on the rules class; a ratio or count is never an attribute.
- Capability limits are inclusive unless the source says otherwise; where it is silent and a value sits on a limit, ask or list your assumed convention as an open item. Check each aspect ratio on the depth basis the source states for its drill type.
- A stated value with no JITX field (modelled impedance, tolerances, finish, fill material, drum Rz) goes in a docstring.

## Fenced Pour Outlines (Antipads, RF Cavities, BGA Breakouts)

Worked pattern: `jitxexamples.patterns.fenced_pour_outline`.

## Verify

1. Run the base `jitx` skill's [`check.py`](../jitx/scripts/check.py) on the substrate's directory, then [`check_labels.py`](scripts/check_labels.py) on the substrate file with the project's interpreter.
2. Write a design file whose own `Design` binds your substrate (the jitxexamples package's `jumpstart_kits/js1_stackup_components/hdi_stackup/main.py` is a minimal one), never a `SampleDesign` subclass or `SampleSubstrate`. Run `jitx build`; with no runtime, `jitx build --dry --no-dependency-check` still translates, but passes no build gate.
3. Report-driven: write tests that read the source document from a path given at run time, never a re-typed copy of its numbers, and compare it with the built substrate: layer order and names, thicknesses, Dk/Df, via spans and geometry, every fab rule, per-layer widths and reference planes. Subclass `jitx.test.TestCase` (outside its context most reads of a design fail silently), assert the layer count first, and pass `strict=True` to every `zip`. Test default widths against their formula, not the source.
4. Fill the block below in the completion summary, each row with its evidence (source row or section to class or attribute).

## Substrate completeness check: run before calling it done

```
## Substrate check
Source: <document + revision/date | user spec>
Stackup: <N> copper layers, soldermask included; summed <x.xxx> mm vs stated <x.xxx> mm under the source's inclusions and precision: reconciles | MISMATCH | not performed: <unstated row>
Materials: <N> dielectrics, <N> conductors, one class per distinct row; Dk/Df, frequency, thickness, roughness; no-field values docstringed
Units: one converted row's arithmetic (mil x 0.0254): <row>
Vias: <N> defined / <N> in source: <ids>; spans, drill direction, pad/hole, fill/cap/tent; annular rings and aspect ratios on the stated depth basis
Routing structures: <N> / <N> controlled rows and how they collapse; target impedance; layer entries <list>; velocity from eps_eff; pair gap edge-to-edge; uncoupled regions; neck structures; reference planes
Fab rules: <N>/<N> mapped; capability limits documented: <list>; contended fields, held vs hand-checked: <list | none>
No-field walk: every section walked; docstringed: <list>
Provenance: values with no source row: NONE | <list + labelled rule>
Checks: check.py and check_labels.py lines verbatim; source-driven tests <N passed | failures | n/a>; build <clean | not run: reason>
Verdict: complete | open items: <list>
```

Derive the Verdict from the rows: a mismatch, an unsupported claim, or a skipped or unavailable check is an open item, and "complete" with a caveat is "open items". A thickness solved as the balancing term is an open question, and the Stackup row reads "not performed".
