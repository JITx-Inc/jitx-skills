# Net Classes Reference

## Purpose

Some nets need non-default physical rules — width, clearance, impedance, keepout, return path, shield. Net classes attach those rules to the design code via tag types, so the substrate / routing engine can apply them uniformly. Each design enumerates which classes it needs during Phase 3, generates the table below, and skips rows that do not apply.

Each net class is its own section below, with quantitative defaults where they exist and pointers to the relevant domain reference.

**Generate one section per applicable class. Skip sections that do not apply.** If no nets in the design need non-default rules, record "no non-default net classes" with a one-line rationale in the project's Phase 3 doc.

---

## Switch Node (`SwTag`)

**Used for:** Buck / boost / SMPS switching nodes — the high-dV/dt nets between the FET and the inductor.

**Why it matters:** Hot loop EMI, ringing voltage stress on the input cap, copper-area driven E-field radiation. The narrower the switch-node copper, the less it radiates.

**Quantitative targets:**
- Input-cap → switch-FET → GND loop area ≤ 20 mm² (`PWR_BUCK_001`)
- Switch-node copper area minimized (`PWR_BUCK_005`)
- No pour or signal routing under inductor (`PWR_BUCK_004`)

**JITX expressions:**

> **Illustrative.** The `design_constraint(...).METHOD(...)` patterns below show authoring intent, not exact API. The canonical rule-builder methods exported by `jitx.constraints` today are `trace_width`, `clearance`, `stitch_via`, `fence_via`, and `thermal_relief`. Tag subclasses (`SwTag`, `RFTag`, `ThermalPadTag`, `SensitiveAnalogTag`, etc.) are user-defined per the `Tag` base-class docstring — declare them at module scope in the project's tags module (see `project-builder-flow.md`). When a rule below names a method not in the canonical set, treat it as a placeholder for either a future rule-builder method or a project-local helper that calls the canonical methods.
```python
design_constraint(SwTag(), priority=HIGH).clearance(0.5 * MM)
# Width sized for I_load via routing structure; not over-wide
```

**Future introspection checks (Phase 3b audit):**
- `board.loop_area([vin, sw, gnd_in]) <= 20`
- `board.copper_area(sw_net) <= threshold`
- `board.copper_under(inductor) is None`

**Domain references:** [`power.md`](domains/power.md), [`emc-esd.md`](domains/emc-esd.md)

---

## RF / Antenna Feed (`RFTag`)

**Used for:** 50 Ω routed RF traces, antenna feeds (U.FL, SMA, board-edge contacts), RF transceiver outputs.

**Why it matters:** Impedance control, return-current discontinuity, EMI radiation.

**Quantitative targets:**
- 50 Ω routing structure (singled-ended) or 100 Ω (differential)
- Return-plane keepout under antenna footprint
- No vias on RF traces if avoidable; if used, ground vias adjacent
- ≥ 10–15 mils from board / plane edges (`HS_DIFF_005`)

**JITX expressions:**
```python
design_constraint(RFTag()).routing_structure(rf_50ohm)
design_constraint(RFTag()).reference_plane_keepout(under_antenna=True)
# Edge clearance ≥ 10–15 mils from board / plane edges (HS_DIFF_005).
design_constraint(RFTag()).min_edge_clearance(0.3 * MM)
```

**Future introspection checks:**
- `board.via_count(rf_net) == 0` (or with explicit ground-via-pairs)
- `board.distance_to_edge(rf_net) >= 3 * trace_width`
- `board.plane_keepout_present(antenna_footprint)`

**Domain references:** [`high-speed-si.md`](domains/high-speed-si.md), [`external-interfaces.md`](domains/external-interfaces.md)

---

## Clock Distribution (`ClockTag`)

**Used for:** Oscillator outputs, clock-buffer fanout, reference-clock distribution (REFCLK), any periodic high-dV/dt net that is a deliberate EMI aggressor.

**Why it matters:** Clocks are the dominant radiated-emissions source on most digital boards. Length and routing discipline bound both EMI and downstream skew.

**Quantitative targets:**
- Series source termination (≈ 33 Ω) on point-to-point clocks (`HS_CLK_001`)
- Short traces to minimize EMI and skew (`HS_CLK_002`)
- ≥ 20 mm separation from RF / sensitive-analog victims (`EMC_AGG_001`)

**JITX expressions:**
```python
design_constraint(ClockTag()).clearance(0.3)            # keep victims away
design_constraint(ClockTag(), RFTag()).min_distance(20 * MM)
```

**Future introspection checks:**
- `board.trace_length(clock_net)` within budget
- `board.distance(clock_components, sensitive_nets)`

**Domain references:** [`high-speed-si.md`](domains/high-speed-si.md), [`emc-esd.md`](domains/emc-esd.md)

---

## High-Heat-Dissipation (`HighDissTag`)

**Used for:** Components dissipating > 1 W continuous — regulators, power FETs, motor drivers, high-current LEDs. Distinct from `ThermalPadTag` (which tags the pad geometry): `HighDissTag` tags the *component* for power-density budgeting and spread.

**Why it matters:** Local hot spots that exceed the board's copper-area heat budget drive junction temperature past the datasheet margin.

**Quantitative targets:**
- Adequate copper on adjacent layers (`THM_PWR_001`); ≥ 15.3 cm²/W for a 40 °C rise, ≈ 7.7 cm²/W with airflow (`THM_PWR_002`)
- Heat-dissipating components spread across the board, not clustered (`THM_SPREAD_001`)

**JITX expressions:**
```python
design_constraint(HighDissTag()).copper_area_min_per_watt(15.3 * CM2)  # 7.7 with airflow (THM_PWR_002)
```

**Future introspection checks:**
- `board.thermal_distribution()` — flag clustered dissipators

**Domain references:** [`thermal.md`](domains/thermal.md), [`thermal-and-emc-workflow.md`](domains/thermal-and-emc-workflow.md)

---

## High-Speed Differential (`HighSpeedDiffTag`)

**Used for:** USB SuperSpeed, PCIe, MIPI, DisplayPort, HDMI, Ethernet (100M+), JESD204.

**Why it matters:** Impedance, intra-pair skew, EMI, plane-discontinuity loss.

**Quantitative targets:**
- 85 Ω or 90 Ω or 100 Ω differential impedance per protocol
- Intra-pair skew ≤ 5 ps (typical); per protocol spec
- Reference-plane continuity (no splits) (`HS_DIFF_001`)
- ≤ 2 vias per high-speed serial trace; minimize via count (`HS_SER_002`)
- Inner-layer routing preferred (`HS_DIFF_006`)

**JITX expressions:**
```python
design_constraint(HighSpeedDiffTag()).routing_structure(diff_90ohm)
ConstrainDiffPair(
    pair=self.usb3.tx,
    intra_pair_skew=Toleranced.max(5 * PS),
)
```

**Future introspection checks:**
- `board.plane_continuity_under(net)`
- `board.via_count(net) <= 2`
- `board.layer(net) in inner_layers`

**Domain references:** [`high-speed-si.md`](domains/high-speed-si.md), [`emc-esd.md`](domains/emc-esd.md)

---

## DDR / LPDDR (`DDRTag`, `LPDDRTag`)

**Used for:** DDR3/4/5 and LPDDR4/5 memory interfaces.

**Why it matters:** Per-byte-lane timing margin, VREF/VTT rail integrity.

**Quantitative targets:**
- DQ-to-DQS matching per byte lane: ±25 mil typical (`HS_DDR_001`)
- CK differential pair impedance per spec
- Command / address timing per spec
- VREF / VTT / VDDQ decoupling per `HS_DDR_002`

**JITX expressions:**
```python
design_constraint(DDRTag()).routing_structure(ddr_50ohm_se)
ConstrainReferenceDifference(
    reference=self.ddr.dqs0,
    signals=self.ddr.dq[0:8],
    skew=Toleranced.max(25 * MIL),
)
```

**Future introspection checks:**
- `board.trace_length_match(dqs, dq[:]) <= 25 * MIL`

**Domain references:** [`high-speed-si.md`](domains/high-speed-si.md)

---

## Sensitive Analog (`SensitiveAnalogTag`)

**Used for:** High-impedance sensor traces, precision ADC inputs, instrumentation amplifier inputs, voltage references.

**Why it matters:** Coupling pickup, ground-loop offsets, leakage into high-Z nodes.

**Quantitative targets:**
- Guard ring around trace if input impedance > 1 MΩ (`AN_SENSOR_001`)
- ≥ 50 mm from switching aggressors (`EMC_AGG_001`)
- Dedicated return path

**JITX expressions:**
```python
design_constraint(SensitiveAnalogTag()).clearance(0.5 * MM)
design_constraint(SwTag(), SensitiveAnalogTag()).min_distance(50 * MM)
design_constraint(SensitiveAnalogTag()).guard_ring(connect_to=ref_gnd)
```

**Future introspection checks:**
- `board.guard_ring(net)`
- `board.distance(switching_components, sensitive_nets)`

**Domain references:** [`analog-mixed-signal.md`](domains/analog-mixed-signal.md), [`emc-esd.md`](domains/emc-esd.md)

---

## High-Voltage / Mains (`HighVoltageTag`)

**Used for:** Mains-adjacent traces, high-voltage rails > 60 V, isolation barriers.

**Why it matters:** Creepage, clearance, regulatory (UL, IEC 60601, IEC 61010).

**Quantitative targets:**
- Class-dependent creepage / clearance (e.g., reinforced insulation 8 mm for 250 V mains)
- No-pour zones across isolation barriers
- Layer assignment: avoid inner layers near high-voltage traces

**JITX expressions:**
```python
design_constraint(HighVoltageTag()).clearance(8 * MM)
design_constraint(HighVoltageTag()).no_pour_zone()
```

**Future introspection checks:**
- `board.clearance_to_class(HighVoltageTag, LowVoltageTag) >= 8 * MM`
- `board.copper_in_keepout(barrier_zone)`

**Domain references:** [`safety-critical.md`](domains/safety-critical.md)

---

## High-Current (`HighCurrentTag`)

**Used for:** Power-rail traces > 1 A continuous, motor phase windings, battery connections.

**Why it matters:** I²R drop, thermal rise, IR-induced inductance.

**Quantitative targets:**
- Trace width sized for ≤ 20 mV drop at full current (`PWR_TRACE_002`)
- Multiple vias for any layer-to-layer transition
- 50% derating on rated trace current capacity (`DFM_TRACE_005`)

**JITX expressions:**
```python
design_constraint(HighCurrentTag()).width_for_current(load_amps=5.0)
design_constraint(HighCurrentTag()).min_vias_per_transition(4)
```

**Future introspection checks:**
- `board.trace_resistance(net) * load_amps <= 20 * MV`
- `board.via_count_at_transition(net) >= 4`

**Domain references:** [`power.md`](domains/power.md), [`thermal.md`](domains/thermal.md)

---

## Gate Drive (`GateDriveTag`)

**Used for:** MOSFET / IGBT gate signals from driver IC to FET gate.

**Why it matters:** dV/dt ringing, gate oscillation, ground-bounce kickback into the driver.

**Quantitative targets:**
- Tight return loop (driver return to FET source, Kelvin-connected if possible)
- Gate resistor placement adjacent to FET gate pin
- No long unterminated stub on the gate

**JITX expressions:**
```python
design_constraint(GateDriveTag()).clearance(0.3 * MM)
design_constraint(GateDriveTag()).short_trace()
```

**Future introspection checks:**
- `board.kelvin_connect(driver.return, fet.source)`
- `board.trace_length(gate_net) < 20 * MM`

**Domain references:** [`power.md`](domains/power.md), [`emc-esd.md`](domains/emc-esd.md)

---

## Kelvin Sense (`KelvinSenseTag`)

**Used for:** Current-sense resistor traces, precision voltage-sense connections, four-wire measurements.

**Why it matters:** Accuracy — any current flow in the sense trace degrades the measurement.

**Quantitative targets:**
- Sense trace routed separately from current-carrying trace
- Sense pickup at the resistor pad, not at a downstream point
- Differential pair if signal is across a small resistance

**JITX expressions:**
```python
design_constraint(KelvinSenseTag()).separate_from(HighCurrentTag())
design_constraint(KelvinSenseTag()).pickup_at_pad()
```

**Future introspection checks:**
- `board.kelvin_pickup_geometry(sense_net, current_net)`

**Domain references:** [`analog-mixed-signal.md`](domains/analog-mixed-signal.md)

---

## Isolated Domain (`IsolatedDomainTag`)

**Used for:** Galvanically isolated sections — opto-isolators, digital isolators, medical isolation barriers, transformer secondaries.

**Why it matters:** Safety, regulatory compliance, ground loop prevention.

**Quantitative targets:**
- Creepage / clearance per regulatory class
- No-pour zone across barrier
- No copper inside the isolation slot

**JITX expressions:**
```python
design_constraint(IsolatedDomainTag()).barrier_clearance(creepage=8 * MM, clearance=4 * MM)
design_constraint(IsolatedDomainTag()).no_pour_zone()
```

**Future introspection checks:**
- `board.barrier_intact(isolation_zone)`
- `board.copper_in_keepout(isolation_zone)`

**Domain references:** [`safety-critical.md`](domains/safety-critical.md)

---

## Thermal Pad (`ThermalPadTag`)

**Used for:** Component thermal pads requiring via array to inner plane heat sink.

**Why it matters:** Heat removal from package, prevention of thermal runaway.

**Quantitative targets:**
- Via density 8–12 / cm² (`THM_VIA_001`, `THM_VIA_004`)
- Via diameter 0.2–0.4 mm (`THM_VIA_002`)
- Via spacing > 2 mm (`THM_VIA_003`)
- Paste subdivision if pad > 4 mm²

**JITX expressions:**
```python
design_constraint(ThermalPadTag()).thermal_via_density(
    density=10 * PER_CM2,
    via_diameter=0.3 * MM,
    # Center-to-center spacing >= 2 mm to prevent solder reflow wicking
    # (THM_VIA_003). For staggered grids, use the row pitch here and rely on
    # the density target to constrain the offset.
    via_spacing=2.0 * MM,
)
```

**Future introspection checks:**
- `board.thermal_via_density(component) >= 8 * PER_CM2`

**Domain references:** [`thermal.md`](domains/thermal.md)

---

## ESD-Exposed (`ESDExposedTag`)

**Used for:** External connector pins, exposed switches, board-edge contacts, anything user-touchable.

**Why it matters:** ESD strike routing, TVS-to-victim coupling.

**Quantitative targets:**
- TVS within 10 mm of connector pin (`EMC_ESD_001`)
- TVS GND ≥ 2 dedicated vias (`EMC_ESD_004`)
- No sensitive signals parallel to ESD-exposed traces (`EMC_ESD_005`)

**JITX expressions:**
```python
design_constraint(ESDExposedTag()).max_distance_to(TVSTag(), 10 * MM)
design_constraint(ESDExposedTag(), SensitiveAnalogTag()).min_parallel_run(0)
```

**Future introspection checks:**
- `board.distance(connector_pin, tvs) <= 10 * MM`
- `board.parallel_traces(esd_net, sensitive_net) == 0`

**Domain references:** [`external-interfaces.md`](domains/external-interfaces.md), [`emc-esd.md`](domains/emc-esd.md)

---

## Adding new classes

Net classes are not a closed set. New classes get added as designs demand them:

- Low-leakage thermocouple inputs
- Motor-phase windings (specific Kelvin / gate-drive overlap)
- Optical-link receive trace (very high impedance, very low signal)
- High-energy capacitor discharge paths (defibrillator-style)

When adding a new class:
1. Create a `Tag` subclass in the project's tags module.
2. Define the quantitative targets here (this file).
3. Add an entry to [`phase-3b-check-stubs.md`](phase-3b-check-stubs.md) if introspection checks are needed.
4. Cross-reference from the relevant `domains/*.md` files.

## Phase 3 → 3b transition

The Phase-3 net-class table confirms which classes apply to *this* design. The Phase-3 → 3b transition gate either:
- Lists the applicable classes and their constraint assignments, or
- States explicitly "no non-default net classes" with rationale
