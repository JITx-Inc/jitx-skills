---
name: jitx-substrate-modeler
description: "Use when the user asks to create a substrate, define a stackup, add via definitions, set up routing structures, configure impedance control, define differential pairs, set fabrication rules, ring a shape with fence vias, fence a pour outline, fence an antipad, model a PCB layer structure, model a substrate from a fabrication house's stackup report (CSV, PDF, or quote), or verify a substrate against its source report. Covers Stackup, Symmetric, materials, vias, routing structures, differential routing structures, via fencing, fenced pours, geometry, reference planes, and FabricationConstraints."
---

# JITX Substrate Modeler

Write one Python file holding the substrate: materials, stackup, vias, routing structures and `FabricationConstraints`. API shapes, units and pitfalls are in the docstrings of `jitx.stackup`, `jitx.via`, `jitx.si`, `jitx.substrate`, `jitx.constraints`, `jitx.inspect`, `jitx.test` and `jitxlib.physics`, and in the JITX docs page [Substrate & Stackup](https://docs.jitx.com/en/latest/essentials/design/substrate.html) (its Vias section: layer indices count conductors only). The task is not done until the [completeness check](#substrate-completeness-check-run-before-calling-it-done) is filled in the completion summary.

`jitxlib.jlcpcb`'s substrates are a reference implementation of a complete substrate.

## Route first

- Environment and Design assembly: the base `jitx` skill.
- Design rules and pour clearance: `jitx-layout-constraints`. The substrate declares no design rule except a fenced pour's `fence_via` rule.
- Substrate-shaped tables (layer-to-via maps) live on the substrate; instantiate a generic stackup, never inline-subclass it: the `jitx` skill's [architectural patterns 4a](../jitx/references/architectural-patterns.md#sub-example-4a-substrate-shaped-tables) and [7](../jitx/references/architectural-patterns.md#7-dont-pass-through-inline-subclass--instantiate).
- Self-review: `jitx-code-review`.

## The source document is ground truth

Trace every value to a source row, cell or field. The only derived values are this skill's named defaults, each labelled at its call site and under Provenance; anything else unstated is a question for the user. With no document, Dk, Df and their frequency come from a datasheet: ask for it, and label any value used without one at its call site (`# skill default: example value, no datasheet`) and list it as an open item. Before code, restate the document to the user: construction, each dielectric's Dk/Df and frequency, foil weights and Rz, vias, impedance targets, fab rules, and what is ambiguous.

A stackup report in any format (a CSV, a PDF, a fab's own export) carries the same content: layer order and thickness, materials, vias, impedance targets, fab rules, notes and revisions. Map its structure onto those before writing code. Traps that hold in every format:

- Follow the unit the report declares controlling, and read per cell, since a unit column can be half empty. Use finished copper thickness, not nominal weight.
- `impedance=` takes the target the fab was asked to hit, never the figure its solver returned.
- An uncoupled-region row belongs inside the pair it names, not in a structure of its own: count structures against controlled rows.
- Where the report states two limits for one JITX field, the field holds the looser and you hand-check the other (laser and mechanical drill minimums: `min_drill_diameter` takes the laser figure). A rule with no JITX field is a hand-checked capability limit.
- On a revised report, re-derive every figure computed from a changed row.

Then:

- A report naming both halves gets an explicit `Stackup`, not `Symmetric`, so each layer keeps its source id; name copper layers for source id and function.
- One material class per distinct source row. A named product goes in `material_name`, which reaches the translated design; generic constants get a generic name. Record matte and drum Rz (µm, as stated) in the conductor's docstring. If you set the `roughness` scalar, it is read as mm: matte-side Rz ÷ 1000.
- Define exactly the source's vias, since every `Via` class on the substrate registers on the board. Set no `models=`: a report has none (see `Via.models`). Code laser vias in drill direction: a bottom-side via drilled from L12 to L11 is `start_layer = -1, stop_layer = -2`. A stacked microvia is one laser `Via` spanning the stack (L1 to L3 is `start_layer = 0, stop_layer = 2`).
- One structure per controlled target, with a layer entry for each geometry the report lists. A row with no controlled target (a default line/space) is documentation, not a structure. Velocity is `phase_velocity(eps_eff)` from the report's modelled eps_eff when it gives one; its docstring gives closed forms otherwise.
- To give part of a route its own impedance structure, define that structure on the substrate, tag the route segment, and apply the structure by tag (`design_constraint(SegmentTag()).routing_structure(...)`; see the `jitx.constraints` Tags and design_constraint docstrings). A neck region the report quotes becomes such a structure, of its parent's kind and on its layers, with the report's neck width, gap and clearance and the parent's reference planes; regions with identical neck geometry may share one. Velocity and loss come from the parent row, labelled at the call site as a default. The impedance is the report's modelled neck impedance, not the parent's target: `Substrate.routing_structure()` finds structures by impedance.
- The report names each line's reference planes, never their width. Carry them on every layer entry, uncoupled regions and neck structures included. Width: this skill's default, 3 x the dielectric thickness between line and plane (only dielectric rows, summed when not adjacent), one mapping entry per line with its label on that line, a summed separation named first: `2: 3 * H_L1_L3,  # skill default: 3x dielectric height`. Strict source-only: omit `.reference()`, docstring the planes and name the omission as an open item; never pass `None` widths.
- `symmetric_routing_layers` cannot mirror a fence whose via is not symmetric about the board centre (see its docstring): list each fenced layer explicitly.
- All 19 `FabricationConstraints` fields are mandatory; a missing one fails translation. Only the four `min_copper_*` fields are engine-enforced; the rest are documentation the design reads. A limit that is not a length in mm (an `N:1` ratio, a stacked-level count) goes in the rules class docstring with its unit, not in an attribute.
- Capability limits are inclusive unless the source says otherwise; where it is silent and a value sits on a limit, ask, or name the convention you assumed as an open item. Check each aspect ratio on the depth basis the source states for its drill type.
- A stated value with no JITX field (modelled impedance, tolerances, finish, fill material, drum Rz) goes in a docstring, never dropped.

## Fenced Pour Outlines (Antipads, RF Cavities, BGA Breakouts)

Worked pattern: the jitxexamples package's `jitxexamples.patterns.fenced_pour_outline` module.

## Verify

1. Run the base `jitx` skill's [`check.py`](../jitx/scripts/check.py) on the substrate's directory, then [`check_labels.py`](scripts/check_labels.py) with the project's interpreter: `python <this skill's directory>/scripts/check_labels.py <substrate.py>` (exit 1 lists labels `ruff format` would split).
2. Write a design file whose own `Design` binds your substrate (the jitxexamples package's `jumpstart_kits/js1_stackup_components/hdi_stackup/main.py` is a minimal one). The scaffold's seeded design subclasses `SampleDesign`, binds `SampleSubstrate` and proves nothing about yours: use neither. Run `jitx build`; with no runtime, `jitx build --dry --no-dependency-check` still translates, but passes no build gate. One build per project at a time.
3. Report-driven: write tests that read the source document at test time, from a path taken at run time (an environment variable, say), and compare it with the built substrate: layer order and names, thicknesses, Dk/Df, via spans and geometry, every fab rule, per-layer widths and reference planes, never a re-typed copy of its numbers. Subclass `jitx.test.TestCase` (outside its context a design reads as empty and raises nothing), assert the layer count first, and pass `strict=True` to every `zip`. Test default widths against their formula, not the source.
4. Fill the block below.

## Substrate completeness check: run before calling it done

```
## Substrate check
Source: <document + revision/date | user spec>
Stackup: <N> copper layers, soldermask included; summed <x.xxx> mm vs stated <x.xxx> mm under the source's inclusions and precision: reconciles | MISMATCH | not performed: <unstated row>
Materials: <N> dielectrics, <N> conductors, one class per distinct row; Dk/Df, frequency, thickness, roughness; no-field values docstringed
Units: one converted row's arithmetic (mil x 0.0254; 1 oz base foil is 0.035 mm): <row>
Vias: <N> defined / <N> in source: <ids>; spans, drill direction, pad/hole, fill/cap/tent; annular rings and aspect ratios on the stated depth basis
Routing structures: <N> / <N> controlled rows and how they collapse; target impedance; layer entries <list>; velocity from eps_eff; pair gap edge-to-edge; uncoupled regions; neck structures; reference planes
Fab rules: <N>/<N> mapped; capability limits documented: <list>; contended fields, held vs hand-checked: <list | none>
No-field walk: every section walked; docstringed: <list>
Provenance: values with no source row: NONE | <list + labelled rule>
Checks: check.py and check_labels.py lines verbatim; source-driven tests <N passed | failures | n/a>; build <clean | not run: reason>
Verdict: complete | open items: <list>
```

Derive the Verdict from the rows: a mismatch, an unsupported claim, or a skipped or unavailable check is an open item, and "complete" with a caveat is "open items". A thickness solved as the balancing term makes the Stackup row tautological: an unstated thickness is an open question, and the row reads "not performed".
