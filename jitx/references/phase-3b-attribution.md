# Phase 3b Design Audit — Attribution & Adaptation

This is the single, canonical attribution for the ThomsonLint-derived material in the JITX Phase 3b Design Audit. Other Phase 3b files point here rather than restating provenance.

## Source

The Phase 3b design-audit ruledeck and several of its conventions are **adapted from ThomsonLint**, an open knowledge-and-rule framework for AI-assisted hardware design review.

- **Project:** ThomsonLint — "AI Hardware Design Review Framework"
- **Repository:** https://github.com/holla2040/ThomsonLint (canonical source, not a fork)
- **License:** MIT — `Copyright (c) 2025` (ThomsonLint authors). See the MIT-notice section below.
- **Ruledeck pin:** `ontology/ontology.json` at commit **`91f0937`** (2026-04-29) — the latest upstream commit that modifies the ontology as of this writing. This is the single source of the pin; the freshness check in `phase-3b-roadmap.md` "Staying current with upstream ThomsonLint" compares against it.

## Adapted, not copied

ThomsonLint is a **post-layout review** framework: it ingests CAD exports (KiCad / Fusion) and emits a findings report. The JITX Phase 3b audit is an **authoring-time self-review** that runs against the JITX design graph and constraint system. The rules and checks have been adapted to that different execution model:

| ThomsonLint artifact | JITX adaptation | File |
|---|---|---|
| `ontology/ontology.json` (167 review rules) | Classified into JITX **execution states** (`now` / `awaiting-evidence-format` / `awaiting-introspection` / `out-of-band`) by what the JITX design graph can answer today vs. what needs introspection or human evidence | `phase-3b-coverage-matrix.csv`, `phase-3b-check-stubs.md` |
| `tests/findings_schema.json` (findings contract) | The **evidence-row format** (`label / datasheet / design / margin / verdict / source`, source mandatory) and the **verified-checks-are-deliverables** discipline in the Phase 3b audit block | `completion-blocks.md` "Phase 3b Design Audit Block" |
| `tools/validate_findings.py` (input/source coverage gate — hard-fails on uncited design inputs and on any evidence row missing a `source`; its ontology rule-citation summary is advisory) | **Generalized** into the JITX rule-coverage gate (every applicable rule terminates in a finding / verified check / `awaiting-*` stub / `n/a`). Adapted as a *self-reported* discipline — the JITX side has no validator script yet (see the honesty note in `completion-blocks.md`) | `completion-blocks.md` |
| `tools/kicad-export.py` (what a laid-out board exposes) | The **extraction-precedent tiers** (`demonstrated` / `computable` / `needs-geometry` / `needs-3d/ext`) on the layout-introspection API wishlist — grounds which checks are near-term | `phase-3b-introspection-apis.md` |
| Rule IDs (`PWR_*`, `HS_*`, `AN_*`, `EMC_*`, `THM_*`, `DFT_*`, `DFM_*`, `AERO_*`, …) | **Preserved verbatim**, so JITX findings cross-reference cleanly to the ThomsonLint ontology and its knowledge base | all of the above |

Key differences from upstream:

- **Execution model.** ThomsonLint parses static CAD exports; the JITX audit queries the live design graph and (for layout rules) a forthcoming jitx-client introspection API. Many rules ThomsonLint runs against geometry are `awaiting-introspection` on the JITX side until that API ships.
- **Quantitative thresholds** from the ontology (e.g. 10–15 mils edge clearance, 8–12 thermal vias/cm², ≥ 1.5× voltage derating) are folded into the per-domain references under `domains/` where they inform authoring, with the rule ID cited.
- **Verbatim redistribution, disclosed.** The generated `phase-3b-coverage-matrix.csv` and `phase-3b-check-stubs.md` reproduce **all 167 upstream rule IDs, names, and full descriptions verbatim** (the descriptions are carried unchanged so the cross-reference to the ThomsonLint ontology and knowledge base is exact). This redistribution is permitted under ThomsonLint's MIT license; the MIT notice is reproduced below per its terms. The per-domain references under `domains/` adapt selected quantitative thresholds rather than reproducing rule bodies.

## Files in this repo derived from ThomsonLint

- `phase-3b-coverage-matrix.csv` — generated; 167 rules × {execution state, responsible skill/ref, introspection API, notes}
- `phase-3b-check-stubs.md` — generated; per-rule stubs grouped by execution state
- `phase-3b-introspection-apis.md` — generated; layout-API wishlist with extraction-precedent tiers
- `domains/*.md` — per-domain references; ThomsonLint thresholds folded in with rule-ID citations
- `net-classes.md` — net-class taxonomy with ThomsonLint quantitative defaults

The generators (`build_matrix.py`, `gen_stubs.py`) live in the ThomsonLint working area at `houston/.context/jitx-thomsonlint-comparison/`; the regeneration and freshness procedures are in `phase-3b-roadmap.md`.

## MIT notice (ThomsonLint)

ThomsonLint is distributed under the MIT License. The notice below is reproduced **verbatim** from the upstream `LICENSE` (including its blank copyright-holder line) per the license's terms:

```
MIT License

Copyright (c) 2025

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
```

The upstream `LICENSE` leaves the copyright-holder line blank (`Copyright (c) 2025`), so it is reproduced as-is above. The attributable party is the ThomsonLint project authors (https://github.com/holla2040/ThomsonLint); if upstream fills in a specific holder, copy the updated line here verbatim.
