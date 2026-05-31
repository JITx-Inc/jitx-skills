# Phase 3b Audit — Activation Roadmap

This file describes how to move check stubs from `awaiting-introspection` and `awaiting-evidence-format` into the `now` state as the JITX platform gains the capabilities each stub depends on. It is the bridge between the Phase 3b Design Audit Block (see `completion-blocks.md`) and the framework changes that unblock individual checks.

Read this if you are:

- A jitx-client maintainer about to ship a new layout introspection API and wondering which Phase 3b checks it activates.
- A jitx framework maintainer adding a metadata field to a JITX type (`Capacitor`, `Inductor`, `Component`, etc.) and wondering which Phase 3b checks it activates.
- A skill maintainer regenerating the check stubs after a matrix change.
- An automation author looking for the next batch of high-leverage checks to land.

## Artifacts in this loop

| File | Role | Owner |
|---|---|---|
| `phase-3b-coverage-matrix.csv` | 167 ThomsonLint rules × {status, responsible_skill, introspection_api, gap_notes}. Source of truth | classifier (`build_matrix.py`) |
| `phase-3b-check-stubs.md` | Per-rule stubs grouped by execution state and domain. Read by the Phase 3b audit agent | generator (`gen_stubs.py`) |
| `phase-3b-introspection-apis.md` | Deduplicated layout-introspection APIs the stubs need. Severity-weighted priority list | generator (`gen_stubs.py`) |
| `phase-3b-roadmap.md` | This file. Activation discipline + open requests | maintained by hand |
| `phase-3b-attribution.md` | Single canonical attribution: ThomsonLint repo, license, pinned ontology commit, what was adapted | maintained by hand |
| `completion-blocks.md` "Phase 3b Design Audit Block" | Per-pass templates the audit agent fills | maintained by hand |
| `build_matrix.py`, `gen_stubs.py` | Live in the houston repo at `houston/.context/jitx-thomsonlint-comparison/` | maintained alongside the ThomsonLint ontology |

## Execution states (recap)

| State | Meaning | What unblocks it |
|---|---|---|
| `now` | Check runs against the circuit graph (the JITX design code) today | — |
| `awaiting-introspection` | Requires a jitx-client layout introspection API not yet shipped | The named API lands in jitx-client |
| `awaiting-evidence-format` | Rule needs human-supplied evidence (BOM, fab note, vendor cert, datasheet field on a JITX type) that the type system does not carry today | A metadata field is added to the relevant JITX type (or a BOM column / fab-note convention is documented) |
| `out-of-band` | Requires data the JITX toolchain does not produce (thermal simulation, EMC chamber, conformal-coat photo, mechanical 3D fit) | Not in scope; verify externally |

## Activation: `awaiting-introspection` → `now`

49 checks are currently in this state. `phase-3b-introspection-apis.md` lists the 44 distinct APIs they collectively need, ranked by severity-weighted rules unblocked.

When jitx-client ships a new layout introspection API:

1. **Find the matching API entry** in `phase-3b-introspection-apis.md`. The entry lists the rules it enables.
2. **Verify the new API meets the contract requirements** before flipping any stub:
   - Input types (component / net / pin / via / layer / pad — be precise)
   - Units (`mm`, `mil`, `µm`, `°C`, `nH`, etc.)
   - Return schema (scalar / list / table / structured record)
   - Object identity source (how does the caller name the entity being measured?)
   - One rule-level acceptance example showing the call and the expected return for a known design
3. **Update the matrix**: in `build_matrix.py`, change the status of each affected rule from `future-design-review` to `covered` (or `partial` if quantitative thresholds still require human review). Update `introspection_api` to the final API signature.
4. **Regenerate**:
   ```bash
   python3 houston/.context/jitx-thomsonlint-comparison/build_matrix.py
   python3 houston/.context/jitx-thomsonlint-comparison/gen_stubs.py
   ```
5. **Commit the regenerated `phase-3b-coverage-matrix.csv`, `phase-3b-check-stubs.md`, and `phase-3b-introspection-apis.md` into the skills repo.**
6. **Drop the API entry** from `phase-3b-introspection-apis.md` (the regenerator does this automatically since the rule no longer has `future-design-review` status).
7. **Optional but recommended**: implement the actual check inline in the Phase 3b audit agent so the stub becomes runnable rather than just labelled `now`.

Activation discipline: until the contract requirements in step 2 are met, the stub stays `awaiting-introspection` and the audit raises a visible "not yet runnable" message. Silent passing is forbidden.

### Highest-leverage APIs (top 6 by severity score)

The matrix as of 2026-05-25 ranks these as the highest-value additions:

| Rank | API | Score | Rules unblocked |
|---:|---|---:|---:|
| 1 | `board.distance(component, component)` | 10 | 4 |
| 2 | `board.placement_side(component)` | 6 | 2 |
| 3 | `board.copper_under(component)` | 6 | 2 |
| 4 | `board.thermal_via_density(component)` | 5 | 2 |
| 5 | `board.return_path(net)` | 5 | 2 |
| 6 | `board.trace_length(net)` | 5 | 2 |

See `phase-3b-introspection-apis.md` for the full prioritized list (44 APIs) and per-API rule mappings.

## Activation: `awaiting-evidence-format` → `now`

5 checks are currently in this state. Each one names a piece of data that needs to live on a JITX type or in the BOM / fab-note conventions before the check can run.

When a JITX type gains a new metadata field (or a BOM / fab-note convention is adopted):

1. **Find the affected rule(s)** in `phase-3b-check-stubs.md` under "State: `awaiting-evidence-format`".
2. **Verify the field's predicate is well-defined**: the field has a documented domain (enum, numeric range, named values), a default behavior when unspecified (warn? assume worst-case? reject?), and a way to spot it via grep / AST inspection in the project's source.
3. **Update the matrix**: change the status from `evidence-required` to the appropriate `now`-compatible status (`covered` if fully enforced, `partial` if the audit reads the field but human review still needed, `uncovered-authorable` if the rule moves to a domain reference). Update `gap_notes` to name the field.
4. **Regenerate and commit** per the discipline above.
5. **Optional**: add the field check to the Phase 3b audit agent so it runs rather than just being labelled `now`.

### Current `evidence-required` rules and what would unblock them

| Rule | Severity | Required field / convention | Suggested home |
|---|---|---|---|
| `AERO_SLD_001` | Critical | Solder alloy and lead-finish whisker class on each `Component` (e.g. `solder_finish: Sn63Pb37 \| SAC305`, `lead_finish_whisker_class: JESD201_1A \| …`). Source: BOM + fab note | `Component` |
| `AERO_VIB_001` | Critical | Component mass in grams (`mass_g`). Source: datasheet field. Two-stage rule: this field gates the staking-introspection check `board.staked_components()` | `Component` |
| `COMP_CAP_005` | Major | Electrolytic ripple-current rating, rated temperature, expected ambient (`electrolytic_ripple_current_A`, `rated_temp_C`, `expected_ambient_C`). Source: datasheet | `Capacitor` |
| `COMP_IND_001` | Minor | Inductor tolerance (`tolerance_pct`) and core type (`core: ferrite \| powdered_iron \| air \| metal_alloy`). Source: datasheet | `Inductor` |
| `COMP_RES_002` | Major | Resistor technology (`technology: thick_film \| thin_film \| metal_film \| wirewound`) and tempco (`tempco_ppm_per_C`). Source: datasheet | `Resistor` |

Each of these is small in isolation — one field, one rule-flip. The recommended sequence is by severity: ship `solder_finish` and `mass_g` on `Component` first (both Critical, both aerospace-class), then `electrolytic_ripple_current_A` on `Capacitor`, then the resistor / inductor fields.

## Staying current with upstream ThomsonLint

The repository identity, license, and the **pinned ontology commit** are recorded once in `phase-3b-attribution.md` — that is the single source of the pin. This section is the operational procedure for detecting and absorbing a newer ruledeck.

To check whether a newer ruledeck exists upstream:

```bash
# In a clone of the ThomsonLint repo (URL in phase-3b-attribution.md):
git fetch origin
git log -1 --format='%h %cs %s' origin/main -- ontology/ontology.json
```

If the returned commit is newer than the pin recorded in `phase-3b-attribution.md`, the upstream ruledeck has changed. Pull it and regenerate:

1. Update the local ThomsonLint checkout (`git pull`), confirming `ontology/ontology.json` advanced.
2. Diff the new ontology's rule IDs against the classifier in `build_matrix.py`:
   - **New rule IDs** → `build_matrix.py` will emit `UNCLASSIFIED` warnings on regen. Add a classification entry (status, responsible skill / domain ref, introspection API, gap notes) for each.
   - **Removed rule IDs** → the classifier's `RULES` dict has a stale entry; remove it.
   - **Edited rules** (same ID, changed text/severity/conditions) → re-read the rule and confirm its classification still holds; the regenerated matrix will carry the new text automatically.
3. Regenerate and re-copy per "Regenerating the matrix from scratch" below.
4. Update the pinned commit in **`phase-3b-attribution.md`** (the one place it lives) to the new ontology commit.
5. Run `/jitx-skills-review` on the regenerated artifacts — a ruledeck change is a substantial change set.

A ruledeck refresh is the one case where the generated files legitimately change without a skill-authoring edit. The pinned commit in `phase-3b-attribution.md` is the audit trail: if it doesn't match the current upstream ontology commit, the skill is behind.

## Regenerating the matrix from scratch

Re-classification (or an ontology update on the ThomsonLint side) triggers a full regen:

```bash
# Edit the classifier or the upstream ontology
$EDITOR houston/.context/jitx-thomsonlint-comparison/build_matrix.py
$EDITOR houston/ontology/ontology.json     # if ThomsonLint changed

# Regenerate the matrix and the per-rule artifacts
python3 houston/.context/jitx-thomsonlint-comparison/build_matrix.py
python3 houston/.context/jitx-thomsonlint-comparison/gen_stubs.py

# Copy the regenerated artifacts into the skills repo
cp houston/.context/jitx-thomsonlint-comparison/coverage-matrix.csv \
   jitx-skills/jitx/references/phase-3b-coverage-matrix.csv
cp houston/.context/jitx-thomsonlint-comparison/drafts/jitx-design-review/references/check-stubs.md \
   jitx-skills/jitx/references/phase-3b-check-stubs.md
cp houston/.context/jitx-thomsonlint-comparison/drafts/jitx-design-review/references/introspection-api-wishlist.md \
   jitx-skills/jitx/references/phase-3b-introspection-apis.md
```

The regen is idempotent — re-running it on an unchanged matrix produces the same output. Commit the regenerated files together; never edit them by hand (they are derived).

The exception is anchor changes: if the audit-execution-state names in `completion-blocks.md` are renamed (e.g. `awaiting-introspection` → something else), the `state_map` in `gen_stubs.py` needs the same rename. Otherwise the matrix-to-skill mapping breaks.

## Compliance-theater watch (preventive)

These surfaces in the Phase 3b audit are gameable — agents may fill them without backing evidence. Concrete improvements queued for future hardening:

- **`Notes:` field in per-stub blocks**: currently free-form prose. Future improvement: require either a link to a domain reference file with a section anchor, or a JITX code-graph predicate that the audit can verify.
- **Pass 5 / Pass 6 row templates have a `State` column that lists multiple states** (e.g. `now` (presence) + `awaiting-introspection` (placement)). Honest, but agents may pick the more-permissive label without recording why. Future improvement: split into per-state rows.
- **`evidence-required` stubs** currently describe the needed field in prose. Once the field lands on the JITX type, name it explicitly in `Notes:` so the audit can grep for it.

None of these is a `block`-level concern today; they belong in the activation roadmap so they get addressed when the related infrastructure lands.

## Cross-references

- `completion-blocks.md` — Phase 3b Design Audit Block template
- `phase-3b-check-stubs.md` — per-rule stubs grouped by execution state
- `phase-3b-introspection-apis.md` — prioritized introspection API wishlist
- `phase-3b-coverage-matrix.csv` — source of truth for stub generation
- `project-builder-flow.md` — Phase 3b → Phase 4 transition gate
- `outside-voice-review.md` — codex pass that follows the six-pass audit
- `phase-3b-attribution.md` — ThomsonLint source, license, pinned commit, and adaptation table (the single attribution location)
