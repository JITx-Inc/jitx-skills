---
name: jitx-jlcpcb
description: "Use when the user has chosen JLCPCB or LCSC as fab, assembler or parts source: a board to be made or assembled at JLCPCB, an LCSC C-number (C2874116), JLCPCB basic, preferred or extended parts, an LCSC or EasyEDA catalogue footprint, lcsc.lock.json, or a JLCPCB order packet (gerbers, BOM, CPL, order sheet); also when a user asked which fab to use for an example or demo board picks JLCPCB. Covers jitxlib-jlcpcb: its predefined substrates, the JLCPCB and LCSC parts providers, LCSCPart, LCSCLandpattern, the lock file and the jlcpcb export. Opt-in: JLCPCB is one fab option and never a default, so a board with no fab named goes to jitx-project-builder, which asks. Not for a custom stackup from a fab's report (jitx-substrate-modeler), passive queries with no JLCPCB channel (jitx-circuit-builder), or KiCad or drawing-based footprints (jitx-component-modeler)."
---

# JITX JLCPCB

`jitxlib-jlcpcb` covers one fab end to end, from supply chain to release: substrates, catalogue parts and footprints, and the order packet. JITX ships no default fab, and this skill never chooses JLCPCB for a user: it starts once the user has.

The API is in the package docstrings, read with `help()`: `jitxlib.jlcpcb` (substrates, export and lock file usage), `jitxlib.jlcpcb.parts`, `jitxlib.jlcpcb.parts.library` and `jitxlib.jlcpcb.landpattern`.

## Route first

- Environment, runtime, builds and the parts gates: the base `jitx` skill.
- A whole board from requirements: `jitx-project-builder`. Once the user picks JLCPCB, its substrate, parts and release work come here.
- A stackup outside JLCPCB's predefined set: `jitx-substrate-modeler`.
- Component code, generators and KiCad footprint import: `jitx-component-modeler`. Wiring and placement: `jitx-circuit-builder`.

## Opt in

Only after the user chose JLCPCB, add `"jitxlib-jlcpcb>=4,<5"` to `dependencies` in `pyproject.toml`, then install the project as the `jitx` skill's install step does, so the project's `jitx` pin holds:

```bash
pip install -e .
```

Tell the user what installing changes: the package publishes a parts chain, so a project that names none resolves its passives through JLCPCB's catalogue, while a project that names a chain keeps it. If another installed package also publishes a chain, resolution is a hard error until the project names one.

Name the chain:

```toml
[tool.jitx.parts]
chain = ["csv:parts/approved-parts.csv", "jlcpcb"]
```

The user's approved list comes first, the catalogue behind it, and no `ideal`, so a passive the catalogue cannot supply fails the build rather than becoming an unorderable `IDEAL-` stand-in. Take that passive to the user, change its value, case or tier only with their sign-off, and never put `ideal` back. In an existing chain, keep its entries in order and put `"jlcpcb"` where `"ideal"` was.

- An approved-list part reaches the BOM with no C-number, because the exporter reads only an `LCSCPart`, and the user matches it by hand in JLCPCB's BOM step. Tell the user which parts those are.
- With no approved list of the user's own, cut `parts/approved-parts.csv` to the header row of the example CSV the `jitx` skill copies. The example parts carry no C-number, and first in the chain they would outrank the catalogue.
- Use `"lcsc"` in place of `"jlcpcb"` only when the user asks for LCSC's source. It is faster and can filter a chip resistor's rated voltage, but it has no assembly-library tier (`jitxlib.jlcpcb.parts.jlcpcb`).

The `jitx` skill's parts gates still apply, and the user approves the final build's MPNs and C-numbers before anything is ordered.

## Substrate

| Class | Copper layers | Prepreg | Routing structures | On layers | Vias |
|---|---|---|---|---|---|
| `JLC04161H_1080` | 4 | 1080 | `RS_50`, `DRS_90`, `DRS_100` | outer only | 3 standard |
| `JLC04161H_7628` | 4 | 7628 | `RS_50`, `DRS_90`, `DRS_100` | outer only | 3 standard |
| `JLC06161H_7628` | 6 | 7628 | `RS_50`, `DRS_100` | outer and the first inner layer each side | 9: standard plus extra-cost multilayer |

Import from `jitxlib.jlcpcb`; each class carries its stackup, fab rules and a tented, filled via for via-in-pad. Pick by layer count and the impedances the design's interfaces need, then read the structure's trace widths in the class source: a 50 ohm trace is 0.1176 mm on the 1080 build and 0.3244 mm on the 4-layer 7628 build, so fine-pitch parts favour 1080. The 6-layer class has no 90 ohm pair, so USB 2.0 on six layers has no predefined structure.

A structure the class lacks, a non-FR-4 material, or a layer count outside the set (two layers included) means a custom substrate through `jitx-substrate-modeler`. Via set and fab rules: the classes in `jitxlib.jlcpcb.vias` and `jitxlib.jlcpcb.rules`.

## Parts

The assembly-library tier is the query attribute `library`: `basic`, `preferred`, `extended`, cheapest to assemble first. Prefer basic with `rank=Minimize("library")`, per query or on a design-level `ResistorQuery` or `CapacitorQuery` context. Filter with `library="basic"` only when the user asks for basic parts alone: the basic library is small, and a filter can find nothing. `jitxlib.jlcpcb.parts.library` states what each tier costs.

A queried passive in a case the chip generator does not build (a tantalum or aluminum electrolytic) gets the catalogue footprint through `LCSCLandpattern`, attached by the provider with in-order ports. Name a chip case in the query to avoid it, or treat it as below.

Every other assembled component names its part with `lcsc = LCSCPart("C...")`, a field of the component itself, never of a circuit or landpattern.

Before writing code for a named C-number, save its channel evidence (stock, lifecycle, datasheet URL and pinout, from its catalogue page) to `datasheets/sourcing/<mpn>-lcsc.txt`, and cite it in the part's data source row: PLAN.md's Data Sources table, or the COMPLETION.md block below when there is no PLAN.md. The manufacturer's datasheet outranks it for pins and dimensions; record any disagreement.

## Landpatterns

Generator first, as `jitx-component-modeler` orders it, then the manufacturer's KiCad footprint. `LCSCLandpattern` builds pads from third-party catalogue data. Use it only:

- with the user's explicit approval for this project, recorded under the component's `Notes` for a component class you write, or in its data source row for a footprint a parts provider attached;
- in a component class you write, with `ports={...}` from the manufacturer's pinout, not left to pad order;
- after checking it pad by pad against the manufacturer's drawing.

For a polarized part, check the anode and cathode pads against the drawing: the in-order mapping assumes the catalogue draws the anode as pad 1. Read every warning the build logs for the footprint: dropped vias, skipped pads, and pads left unmapped.

## The lock file

`lcsc.lock.json` at the project root records, by C-number, each catalogue footprint and each measured placement orientation. It is a checked-in project file, not a cache: commit it. The first build and export need network access to jlcpcb.com, wmsc.lcsc.com and easyeda.com; later runs read the lock. Correct a wrong orientation by editing that part's entry, which outranks `LCSCPart(orientation=...)`; delete one entry to fetch that part again.

## Export

```bash
jitx design export jlcpcb --output <packet-dir> <module.Design>
```

`<module.Design>` is the build target `jitx find` prints. `--no-assembly` writes a bare-board packet (gerber archive and order sheet only) and is the way to give the user gerbers alone. Do not use the docstring's `jitx design export gerber --names jlcpcb`: it writes drills as Gerber, not the NC drill file JLCPCB expects, and skips the packet's macro-rotation fix. `--overwrite` allows a non-empty output directory.

The export fails on any unplaced soldered component. The packet is orderable only when exported after the board is routed and the design rule check is clean: the gerbers are written at export. Routing is the user's step; report the check as clean, or not run with the reason. Until both hold, tell the user the packet is not yet orderable, what is missing, and that the export must run again afterwards.

Done means:

- the build passes, `jitx design export parts-check <module.Design> --fail all` passes, and no MPN read from the design starts with `IDEAL-`;
- the packet holds `<stem>-gerber.zip` and `<stem>-order.md`, and for an assembled order `<stem>-bom.csv` and `<stem>-cpl.csv`;
- for an assembled order, every BOM row's `JLCPCB Part #` is a C-number, or each row without one is named to the user;
- the order sheet's layer count and thickness match the substrate.

Report the packet listing to the user, with the order sheet's "Footprints taken from landpattern class names" and "Placed with no orientation correction" lists. Ask them to check rotations in JLCPCB's Confirm Parts Placement preview and to confirm the surface finish, which the sheet marks preliminary. Never upload or order.

Write this block in `COMPLETION.md`, each row with its evidence:

```
## JLCPCB check
Opt-in: <where the user chose JLCPCB>; dependency and chain as written
Substrate: <class> for <layers, impedances> | custom: <reason>
Parts: tier <ranked | filtered: user asked>; <N> LCSCPart components; IDEAL- MPNs: none
Sources: <C-number: datasheets/sourcing/<mpn>-lcsc.txt>
Catalogue footprints: none | <part: approval text or its location, pads checked against <drawing>>
Packet: <file listing>; BOM rows without a C-number: none | <list>; orderable | not yet, re-export after: <routing, DRC>
Approval: MPNs and C-numbers <approved by the user | awaiting the user>
```
