# Phase 3b Introspection API Wishlist

The set of jitx-client layout introspection APIs the Phase 3b Design Audit needs to activate its `awaiting-introspection` check stubs (see `completion-blocks.md` "Phase 3b Design Audit Block" and `phase-3b-check-stubs.md`).

Each API entry lists the ThomsonLint rules it enables. Prioritization is by number of rules unblocked and the severity distribution of those rules.

**Status of the signatures below: illustrative, NOT contractual.** Each entry shows the API shape the audit stubs need, derived from the rule text. The actual jitx-client API will dictate the canonical form. Before any stub flips from `awaiting-introspection` to `now`, the corresponding API entry here needs: input types, units, return schema, object-identity source (component vs net vs pin), and one rule-level acceptance example.

Generated from `phase-3b-coverage-matrix.csv`. Regenerate after matrix changes. **Source & attribution:** adapted from ThomsonLint — see `phase-3b-attribution.md`.

---

## Extraction precedent

Each API carries a **precedent** tier indicating whether ThomsonLint's CAD exporter (`tools/kicad-export.py`) already produces the underlying data — see `phase-3b-attribution.md` for the source repo and license. This grounds which APIs are near-term vs. blocked on new geometry, independent of the severity ranking:

| Tier | Meaning |
|---|---|
| `demonstrated` | ThomsonLint already computes this — near-term, the data is proven available |
| `computable` | raw primitives are extracted; query not yet computed but needs no new geometry |
| `needs-geometry` | needs filled-pour polygon or true outline path (ThomsonLint drops these) |
| `needs-3d/ext` | 3D model, assembly metadata, or external DRC — beyond a geometry query |

The `demonstrated` and `computable` tiers are the recommended first wave: ThomsonLint proves the data is extractable from a laid-out board, so a JITX introspection API exposing the same primitives (per-net segments, via positions, pad coordinates, placements, layer assignment) unblocks them. The `needs-geometry` tier requires the JITX API to expose filled-pour polygons and the true board-outline path — data ThomsonLint's export deliberately drops (zones are `{net, layers}` only; outline is a bounding box). The `needs-3d/ext` tier is beyond any geometry query.

---

**Total APIs requested:** 43

## Priority-ordered API list

| Rank | API signature | Precedent | Severity score | Rules unblocked |
|---:|---|---|---:|---:|
| 1 | `board.distance(component, component)` | `demonstrated` | 10 | 4 |
| 2 | `board.placement_side(component)` | `demonstrated` | 6 | 2 |
| 3 | `board.copper_under(component)` | `needs-geometry` | 6 | 2 |
| 4 | `board.thermal_via_density(component)` | `computable` | 5 | 2 |
| 5 | `board.return_path(net)` | `needs-geometry` | 5 | 2 |
| 6 | `board.trace_length(net)` | `demonstrated` | 5 | 2 |
| 7 | `board.distance(pin, component)` | `demonstrated` | 4 | 1 |
| 8 | `board.plane_continuity_under(net)` | `needs-geometry` | 4 | 1 |
| 9 | `board.loop_area(net_set)` | `computable` | 4 | 1 |
| 10 | `board.via_stub_length(via)` | `computable` | 4 | 1 |
| 11 | `board.plane_splits(layer)` | `needs-geometry` | 4 | 1 |
| 12 | `board.drc_violations()` | `needs-3d/ext` | 4 | 1 |
| 13 | `board.guard_ring(net)` | `needs-geometry` | 3 | 1 |
| 14 | `board.distance_to_edge(net)` | `computable` | 3 | 1 |
| 15 | `board.ground_topology()` | `computable` | 3 | 1 |
| 16 | `board.component_to_edge()` | `demonstrated` | 3 | 1 |
| 17 | `board.component_height(component)` | `needs-3d/ext` | 3 | 1 |
| 18 | `board.ground_vias_near(pad)` | `computable` | 3 | 1 |
| 19 | `board.distance(component_set, component_set)` | `demonstrated` | 3 | 1 |
| 20 | `board.guard_trace(net)` | `computable` | 3 | 1 |
| 21 | `board.adjacent_ground(net)` | `computable` | 3 | 1 |
| 22 | `board.paste_coverage(pad)` | `needs-geometry` | 3 | 1 |
| 23 | `board.courtyard_overlap()` | `needs-geometry` | 3 | 1 |
| 24 | `board.copper_keepout(net)` | `needs-geometry` | 3 | 1 |
| 25 | `board.stitch_via_spacing(layer)` | `computable` | 2 | 1 |
| 26 | `board.copper_area(net)` | `needs-geometry` | 2 | 1 |
| 27 | `board.via_in_pad(component)` | `needs-geometry` | 2 | 1 |
| 28 | `board.layer(net)` | `computable` | 2 | 1 |
| 29 | `board.parallel_traces(net1, net2)` | `computable` | 2 | 1 |
| 30 | `board.pour_via_density(net)` | `needs-geometry` | 2 | 1 |
| 31 | `board.placement_zone(component)` | `computable` | 2 | 1 |
| 32 | `board.via_count(net)` | `demonstrated` | 2 | 1 |
| 33 | `board.trace_length_match` | `computable` | 2 | 1 |
| 34 | `board.thermal_via_spacing(component)` | `computable` | 2 | 1 |
| 35 | `board.serpentine_spacing(net)` | `computable` | 2 | 1 |
| 36 | `board.trace_crossings_angle()` | `computable` | 2 | 1 |
| 37 | `board.acid_traps()` | `needs-geometry` | 2 | 1 |
| 38 | `board.copper_slivers()` | `needs-geometry` | 2 | 1 |
| 39 | `board.thermal_distribution()` | `computable` | 2 | 1 |
| 40 | `board.trace_crossings()` | `computable` | 2 | 1 |
| 41 | `board.probe_access(net)` | `needs-3d/ext` | 2 | 1 |
| 42 | `board.copper_balance(layer)` | `needs-geometry` | 2 | 1 |
| 43 | `board.trace_corners(net)` | `computable` | 1 | 1 |

**By precedent tier:** `demonstrated` 7 · `computable` 19 · `needs-geometry` 14 · `needs-3d/ext` 3


---

## API detail

### 1. `board.distance(component, component)`

**Severity score:** 10 · **Rules unblocked:** 4 · **Precedent:** `demonstrated` — compute_decoupling_proximity pad-to-pad, generalizes

**Suggested signature (illustrative — actual jitx-client API will dictate):**

```python
board.distance(component, component)  # called from Phase 3b audit stubs
```

**Rules this enables:**

- `PWR_BUCK_006` (Minor, Power) — Output capacitor must be separated from input capacitor
- `EMC_ESD_003` (Major, EMC) — TVS diode must be placed as close as possible to connector
- `HS_XTAL_001` (Major, HighSpeed+Analog) — Crystal must be placed close to MCU oscillator pins
- `HS_XTAL_005` (Minor, HighSpeed+Analog) — Crystal load capacitors must be within 5mm with matched traces

### 2. `board.placement_side(component)`

**Severity score:** 6 · **Rules unblocked:** 2 · **Precedent:** `demonstrated` — _extract_footprints → side (F.Cu/B.Cu)

**Suggested signature (illustrative — actual jitx-client API will dictate):**

```python
board.placement_side(component)  # called from Phase 3b audit stubs
```

**Rules this enables:**

- `PWR_BUCK_002` (Major, Power) — Buck converter input/output capacitor placement
- `PWR_BUCK_003` (Major, Power) — Buck converter input capacitor must be on same layer as IC

### 3. `board.copper_under(component)`

**Severity score:** 6 · **Rules unblocked:** 2 · **Precedent:** `needs-geometry` — zones are {net, layers} only — no pour polygon

**Suggested signature (illustrative — actual jitx-client API will dictate):**

```python
board.copper_under(component)  # called from Phase 3b audit stubs
```

**Rules this enables:**

- `PWR_BUCK_004` (Major, Power+EMC) — No GND plane or signal routing directly under inductor
- `HS_XTAL_003` (Major, HighSpeed+EMC) — No routing under crystal on multi-layer PCBs

### 4. `board.thermal_via_density(component)`

**Severity score:** 5 · **Rules unblocked:** 2 · **Precedent:** `computable` — via positions + footprint extent

**Suggested signature (illustrative — actual jitx-client API will dictate):**

```python
board.thermal_via_density(component)  # called from Phase 3b audit stubs
```

**Rules this enables:**

- `THM_VIA_001` (Major, Thermal) — Thermal via arrays for heat transfer to other layers
- `THM_VIA_004` (Minor, Thermal) — Thermal via density should be 8-12 vias per square centimeter

### 5. `board.return_path(net)`

**Severity score:** 5 · **Rules unblocked:** 2 · **Precedent:** `needs-geometry` — needs reference-plane / pour geometry

**Suggested signature (illustrative — actual jitx-client API will dictate):**

```python
board.return_path(net)  # called from Phase 3b audit stubs
```

**Rules this enables:**

- `AN_ADC_006` (Major, Analog+MixedSignal) — Digital switching currents must not flow through ADC ground
- `HS_XTAL_004` (Minor, HighSpeed+EMC) — Crystal oscillator return currents must be locally contained

### 6. `board.trace_length(net)`

**Severity score:** 5 · **Rules unblocked:** 2 · **Precedent:** `demonstrated` — compute_signal_stats → trace_length_mm

**Suggested signature (illustrative — actual jitx-client API will dictate):**

```python
board.trace_length(net)  # called from Phase 3b audit stubs
```

**Rules this enables:**

- `HS_SHORT_001` (Minor, HighSpeed) — Keep component connections short
- `HS_CLK_002` (Major, HighSpeed+EMC) — Keep digital clock traces short to reduce EMI

### 7. `board.distance(pin, component)`

**Severity score:** 4 · **Rules unblocked:** 1 · **Precedent:** `demonstrated` — same pad-to-pad primitive

**Suggested signature (illustrative — actual jitx-client API will dictate):**

```python
board.distance(pin, component)  # called from Phase 3b audit stubs
```

**Rules this enables:**

- `PWR_DECPL_001` (Critical, Power) — IC power pins must be locally decoupled

### 8. `board.plane_continuity_under(net)`

**Severity score:** 4 · **Rules unblocked:** 1 · **Precedent:** `needs-geometry` — needs filled-pour polygon

**Suggested signature (illustrative — actual jitx-client API will dictate):**

```python
board.plane_continuity_under(net)  # called from Phase 3b audit stubs
```

**Rules this enables:**

- `HS_DIFF_001` (Critical, HighSpeed+EMC) — Differential pair must not cross plane splits

### 9. `board.loop_area(net_set)`

**Severity score:** 4 · **Rules unblocked:** 1 · **Precedent:** `computable` — segments present (arcs dropped — caveat)

**Suggested signature (illustrative — actual jitx-client API will dictate):**

```python
board.loop_area(net_set)  # called from Phase 3b audit stubs
```

**Rules this enables:**

- `PWR_BUCK_001` (Critical, Power) — Buck converter hot loop minimization

### 10. `board.via_stub_length(via)`

**Severity score:** 4 · **Rules unblocked:** 1 · **Precedent:** `computable` — via layer-span + net layer usage

**Suggested signature (illustrative — actual jitx-client API will dictate):**

```python
board.via_stub_length(via)  # called from Phase 3b audit stubs
```

**Rules this enables:**

- `HS_DIFF_003` (Critical, HighSpeed) — Via stubs must be minimized for high-speed signals above 3 Gbps

### 11. `board.plane_splits(layer)`

**Severity score:** 4 · **Rules unblocked:** 1 · **Precedent:** `needs-geometry` — needs filled-pour polygon

**Suggested signature (illustrative — actual jitx-client API will dictate):**

```python
board.plane_splits(layer)  # called from Phase 3b audit stubs
```

**Rules this enables:**

- `EMC_PLANE_002` (Critical, EMC) — Minimize holes and slots in ground planes

### 12. `board.drc_violations()`

**Severity score:** 4 · **Rules unblocked:** 1 · **Precedent:** `needs-3d/ext` — external DRC engine, not a geometry query

**Suggested signature (illustrative — actual jitx-client API will dictate):**

```python
board.drc_violations()  # called from Phase 3b audit stubs
```

**Rules this enables:**

- `DFT_DRC_002` (Critical, DFT) — Run layout DRC before release

### 13. `board.guard_ring(net)`

**Severity score:** 3 · **Rules unblocked:** 1 · **Precedent:** `needs-geometry` — needs ring polygon geometry

**Suggested signature (illustrative — actual jitx-client API will dictate):**

```python
board.guard_ring(net)  # called from Phase 3b audit stubs
```

**Rules this enables:**

- `AN_SENSOR_001` (Major, Analog) — High-impedance nodes isolation

### 14. `board.distance_to_edge(net)`

**Severity score:** 3 · **Rules unblocked:** 1 · **Precedent:** `computable` — compute_edge_distances does component-center-to-bbox only; trace-to-edge needs segments+outline, and true clearance on non-rectangular boards needs the outline polygon

**Suggested signature (illustrative — actual jitx-client API will dictate):**

```python
board.distance_to_edge(net)  # called from Phase 3b audit stubs
```

**Rules this enables:**

- `HS_DIFF_005` (Major, HighSpeed+EMC) — High-speed traces must maintain edge clearance

### 15. `board.ground_topology()`

**Severity score:** 3 · **Rules unblocked:** 1 · **Precedent:** `computable` — ground-plane layers extracted; topology derivable

**Suggested signature (illustrative — actual jitx-client API will dictate):**

```python
board.ground_topology()  # called from Phase 3b audit stubs
```

**Rules this enables:**

- `AN_ADC_005` (Major, Analog+MixedSignal) — Connect AGND and DGND at single point at ADC

### 16. `board.component_to_edge()`

**Severity score:** 3 · **Rules unblocked:** 1 · **Precedent:** `demonstrated` — compute_edge_distances — component-center-to-bbox, exactly this query

**Suggested signature (illustrative — actual jitx-client API will dictate):**

```python
board.component_to_edge()  # called from Phase 3b audit stubs
```

**Rules this enables:**

- `DFM_COMP_EDGE_001` (Major, DFT) — Component placement near board edges

### 17. `board.component_height(component)`

**Severity score:** 3 · **Rules unblocked:** 1 · **Precedent:** `needs-3d/ext` — 3D model height not in any static export

**Suggested signature (illustrative — actual jitx-client API will dictate):**

```python
board.component_height(component)  # called from Phase 3b audit stubs
```

**Rules this enables:**

- `MEC_HEIGHT_001` (Major, Mechanical) — Verify component height restrictions

### 18. `board.ground_vias_near(pad)`

**Severity score:** 3 · **Rules unblocked:** 1 · **Precedent:** `computable` — via + pad positions present

**Suggested signature (illustrative — actual jitx-client API will dictate):**

```python
board.ground_vias_near(pad)  # called from Phase 3b audit stubs
```

**Rules this enables:**

- `PWR_DECPL_005` (Major, Power) — Decoupling capacitors need dedicated ground via

### 19. `board.distance(component_set, component_set)`

**Severity score:** 3 · **Rules unblocked:** 1 · **Precedent:** `demonstrated` — same pad-to-pad primitive

**Suggested signature (illustrative — actual jitx-client API will dictate):**

```python
board.distance(component_set, component_set)  # called from Phase 3b audit stubs
```

**Rules this enables:**

- `EMC_AGG_001` (Major, EMC) — Separate aggressors from sensitive circuits

### 20. `board.guard_trace(net)`

**Severity score:** 3 · **Rules unblocked:** 1 · **Precedent:** `computable` — segment adjacency

**Suggested signature (illustrative — actual jitx-client API will dictate):**

```python
board.guard_trace(net)  # called from Phase 3b audit stubs
```

**Rules this enables:**

- `HS_SENS_001` (Major, HighSpeed+Analog) — Route sensitive signals with care

### 21. `board.adjacent_ground(net)`

**Severity score:** 3 · **Rules unblocked:** 1 · **Precedent:** `computable` — compute_ground_plane_layers returns which layers carry a GND zone; per-net adjacency derivable from the net layer + stackup, not pre-computed

**Suggested signature (illustrative — actual jitx-client API will dictate):**

```python
board.adjacent_ground(net)  # called from Phase 3b audit stubs
```

**Rules this enables:**

- `HS_SENS_001` (Major, HighSpeed+Analog) — Route sensitive signals with care

### 22. `board.paste_coverage(pad)`

**Severity score:** 3 · **Rules unblocked:** 1 · **Precedent:** `needs-geometry` — needs paste-layer polygon

**Suggested signature (illustrative — actual jitx-client API will dictate):**

```python
board.paste_coverage(pad)  # called from Phase 3b audit stubs
```

**Rules this enables:**

- `DFM_PASTE_001` (Major, DFT) — Check paste layer for correct pads

### 23. `board.courtyard_overlap()`

**Severity score:** 3 · **Rules unblocked:** 1 · **Precedent:** `needs-geometry` — placements present; courtyard polygons not exported

**Suggested signature (illustrative — actual jitx-client API will dictate):**

```python
board.courtyard_overlap()  # called from Phase 3b audit stubs
```

**Rules this enables:**

- `DFM_COURT_001` (Major, DFT) — Check courtyard spacing for assembly

### 24. `board.copper_keepout(net)`

**Severity score:** 3 · **Rules unblocked:** 1 · **Precedent:** `needs-geometry` — needs keepout / pour polygon

**Suggested signature (illustrative — actual jitx-client API will dictate):**

```python
board.copper_keepout(net)  # called from Phase 3b audit stubs
```

**Rules this enables:**

- `AERO_GND_001` (Major, Aerospace+EMC) — Aircraft DC boards: single-point chassis ground; NPTH mount holes need copper keepout on all layers

### 25. `board.stitch_via_spacing(layer)`

**Severity score:** 2 · **Rules unblocked:** 1 · **Precedent:** `computable` — via positions present

**Suggested signature (illustrative — actual jitx-client API will dictate):**

```python
board.stitch_via_spacing(layer)  # called from Phase 3b audit stubs
```

**Rules this enables:**

- `EMC_STITCH_001` (Minor, EMC) — Ground stitching near board edges and layer changes

### 26. `board.copper_area(net)`

**Severity score:** 2 · **Rules unblocked:** 1 · **Precedent:** `needs-geometry` — needs pour polygon area

**Suggested signature (illustrative — actual jitx-client API will dictate):**

```python
board.copper_area(net)  # called from Phase 3b audit stubs
```

**Rules this enables:**

- `PWR_BUCK_005` (Minor, Power+EMC) — Switching node copper area must be minimized

### 27. `board.via_in_pad(component)`

**Severity score:** 2 · **Rules unblocked:** 1 · **Precedent:** `needs-geometry` — export gives pad centers, not pad copper extents — in-pad containment needs pad geometry

**Suggested signature (illustrative — actual jitx-client API will dictate):**

```python
board.via_in_pad(component)  # called from Phase 3b audit stubs
```

**Rules this enables:**

- `PWR_DECPL_003` (Minor, Power) — Use via-in-pad for BGA decoupling capacitors

### 28. `board.layer(net)`

**Severity score:** 2 · **Rules unblocked:** 1 · **Precedent:** `computable` — segment/zone layer fields present; a per-net layer query is derivable, not pre-computed

**Suggested signature (illustrative — actual jitx-client API will dictate):**

```python
board.layer(net)  # called from Phase 3b audit stubs
```

**Rules this enables:**

- `HS_DIFF_006` (Minor, HighSpeed) — Prefer inner layer routing for differential pairs

### 29. `board.parallel_traces(net1, net2)`

**Severity score:** 2 · **Rules unblocked:** 1 · **Precedent:** `computable` — segment geometry

**Suggested signature (illustrative — actual jitx-client API will dictate):**

```python
board.parallel_traces(net1, net2)  # called from Phase 3b audit stubs
```

**Rules this enables:**

- `EMC_ESD_005` (Minor, EMC) — Avoid parallel routing near ESD-exposed traces

### 30. `board.pour_via_density(net)`

**Severity score:** 2 · **Rules unblocked:** 1 · **Precedent:** `needs-geometry` — needs pour polygon to bound the density

**Suggested signature (illustrative — actual jitx-client API will dictate):**

```python
board.pour_via_density(net)  # called from Phase 3b audit stubs
```

**Rules this enables:**

- `EMC_STITCH_002` (Minor, EMC) — Ground stitching via grid required for copper pours

### 31. `board.placement_zone(component)`

**Severity score:** 2 · **Rules unblocked:** 1 · **Precedent:** `computable` — placements extracted; zone definition TBD

**Suggested signature (illustrative — actual jitx-client API will dictate):**

```python
board.placement_zone(component)  # called from Phase 3b audit stubs
```

**Rules this enables:**

- `AN_ADC_004` (Minor, Analog+MixedSignal) — ADC should be placed at analog/digital boundary

### 32. `board.via_count(net)`

**Severity score:** 2 · **Rules unblocked:** 1 · **Precedent:** `demonstrated` — compute_signal_stats → via_by_net

**Suggested signature (illustrative — actual jitx-client API will dictate):**

```python
board.via_count(net)  # called from Phase 3b audit stubs
```

**Rules this enables:**

- `HS_XTAL_002` (Minor, HighSpeed+Analog) — Avoid vias in crystal oscillator traces

### 33. `board.trace_length_match`

**Severity score:** 2 · **Rules unblocked:** 1 · **Precedent:** `computable` — per-segment geometry emitted for diff/HS nets; differencing not done

**Suggested signature (illustrative — actual jitx-client API will dictate):**

```python
board.trace_length_match  # called from Phase 3b audit stubs
```

**Rules this enables:**

- `HS_XTAL_005` (Minor, HighSpeed+Analog) — Crystal load capacitors must be within 5mm with matched traces

### 34. `board.thermal_via_spacing(component)`

**Severity score:** 2 · **Rules unblocked:** 1 · **Precedent:** `computable` — via positions

**Suggested signature (illustrative — actual jitx-client API will dictate):**

```python
board.thermal_via_spacing(component)  # called from Phase 3b audit stubs
```

**Rules this enables:**

- `THM_VIA_003` (Minor, Thermal) — Thermal via spacing should prevent solder wicking

### 35. `board.serpentine_spacing(net)`

**Severity score:** 2 · **Rules unblocked:** 1 · **Precedent:** `computable` — segment geometry

**Suggested signature (illustrative — actual jitx-client API will dictate):**

```python
board.serpentine_spacing(net)  # called from Phase 3b audit stubs
```

**Rules this enables:**

- `HS_ROUTE_001` (Minor, HighSpeed) — Serpentine routing for length matching

### 36. `board.trace_crossings_angle()`

**Severity score:** 2 · **Rules unblocked:** 1 · **Precedent:** `computable` — segment intersection + angle

**Suggested signature (illustrative — actual jitx-client API will dictate):**

```python
board.trace_crossings_angle()  # called from Phase 3b audit stubs
```

**Rules this enables:**

- `MX_ROUTE_001` (Minor, MixedSignal) — Routing techniques for mixed-signal design

### 37. `board.acid_traps()`

**Severity score:** 2 · **Rules unblocked:** 1 · **Precedent:** `needs-geometry` — needs trace/pad polygon angle analysis

**Suggested signature (illustrative — actual jitx-client API will dictate):**

```python
board.acid_traps()  # called from Phase 3b audit stubs
```

**Rules this enables:**

- `DFM_ACID_001` (Minor, DFT) — Acid trap prevention

### 38. `board.copper_slivers()`

**Severity score:** 2 · **Rules unblocked:** 1 · **Precedent:** `needs-geometry` — needs copper polygon

**Suggested signature (illustrative — actual jitx-client API will dictate):**

```python
board.copper_slivers()  # called from Phase 3b audit stubs
```

**Rules this enables:**

- `DFM_SLIVER_001` (Minor, DFT) — Copper and solder mask slivers

### 39. `board.thermal_distribution()`

**Severity score:** 2 · **Rules unblocked:** 1 · **Precedent:** `computable` — placements (+ power annotation)

**Suggested signature (illustrative — actual jitx-client API will dictate):**

```python
board.thermal_distribution()  # called from Phase 3b audit stubs
```

**Rules this enables:**

- `THM_SPREAD_001` (Minor, Thermal) — Spread heat-dissipating components across PCB

### 40. `board.trace_crossings()`

**Severity score:** 2 · **Rules unblocked:** 1 · **Precedent:** `computable` — segment intersection

**Suggested signature (illustrative — actual jitx-client API will dictate):**

```python
board.trace_crossings()  # called from Phase 3b audit stubs
```

**Rules this enables:**

- `HS_CROSS_001` (Minor, HighSpeed) — Minimize crossing signal traces

### 41. `board.probe_access(net)`

**Severity score:** 2 · **Rules unblocked:** 1 · **Precedent:** `needs-3d/ext` — 3D / keepout clearance

**Suggested signature (illustrative — actual jitx-client API will dictate):**

```python
board.probe_access(net)  # called from Phase 3b audit stubs
```

**Rules this enables:**

- `DFT_GND_003` (Minor, DFT) — Ground measurement point for probing

### 42. `board.copper_balance(layer)`

**Severity score:** 2 · **Rules unblocked:** 1 · **Precedent:** `needs-geometry` — needs per-layer copper-area polygon

**Suggested signature (illustrative — actual jitx-client API will dictate):**

```python
board.copper_balance(layer)  # called from Phase 3b audit stubs
```

**Rules this enables:**

- `DFM_COPPER_001` (Minor, DFT) — Check copper balance for PCB reliability

### 43. `board.trace_corners(net)`

**Severity score:** 1 · **Rules unblocked:** 1 · **Precedent:** `computable` — segment geometry

**Suggested signature (illustrative — actual jitx-client API will dictate):**

```python
board.trace_corners(net)  # called from Phase 3b audit stubs
```

**Rules this enables:**

- `HS_XTAL_006` (Advisory, HighSpeed) — Avoid right-angle bends in crystal traces

