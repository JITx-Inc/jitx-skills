# Safety-Critical Reference (Aerospace / Automotive / Medical)

## When to read this

The design class is aerospace (DO-160, MIL-STD-810, AS-50881), automotive (AEC-Q100/Q101, ISO 7637-2), medical (IEC 60601), or any safety-critical class with explicit regulatory references. The `AERO_*` rules in this reference target aerospace Class 3; the patterns generalize to the other safety-critical classes.

## Authoring-time targets

### Component selection for safety-critical class

- [ ] Class 3 aerospace solder: Sn63/Pb37 eutectic (NOT SAC305) (`AERO_SLD_001`)
- [ ] Lead finish: JESD201 Class 1A whisker-tested (e.g., Vishay -E3, ON Semi -G3)
- [ ] Automotive: AEC-Q200 (passives), AEC-Q100 (ICs), AEC-Q101 (discrete) qualified parts
- [ ] Medical: IEC 60601-1 creepage / clearance for patient-applied parts; isolation barrier requirements
- [ ] Conformal coat compatibility: parts with hollow bodies (electrolytic caps, relays) may need post-coat venting

### Reverse-polarity protection (vehicles)

- [ ] Aircraft / automotive 28 V DC bus: active ideal-diode controller (e.g., TI LM74700-Q1) + low-Rds(on) AEC-Q101 N-FET (`AERO_RPP_001`)
- [ ] NOT a passive Schottky alone — voltage drop is unacceptable at high current and reverse-current safety margin is poor
- [ ] Reverse-polarity FET sized for full continuous load with thermal margin

### Transient suppression (vehicles)

- [ ] Aircraft load-dump / lightning: bidirectional TVS (SMCJ18CA-class, 1500 W) within 50 mm of active-rectifier anode (`AERO_TVS_001`)
- [ ] Clamp voltage Vc(IPP) < 80 V with ≥ 1.5× margin below downstream component abs-max
- [ ] TVS ground: ≥ 2 dedicated vias (`EMC_ESD_004`)
- [ ] Automotive: ISO 7637-2 pulse classes (1, 2a, 2b, 3a, 3b) — TVS rated per the worst case
- [ ] DO-160: equivalent pulse classes per Section 17/18

### Vibration and mechanical hardening

- [ ] High-mass components > 3 g (relays, large electrolytic caps, transformers): RTV staking or mechanical clamp per AS-50881 Method 13 in +6 G environments (`AERO_VIB_001`)
- [ ] Staking locations recorded **in the code** as an annotation on the assembly / fabrication layer (e.g. a silkscreen/assembly-layer note or a documentation property on the staked instance), so the requirement travels with the design and lands on the generated assembly drawing — not just "use staking" in prose
- [ ] Through-hole over SMT for connectors in vibration environments
- [ ] Conformal coat alone is NOT vibration mitigation — it spreads load but doesn't constrain mass

### Chassis bonding (aircraft / EMC-controlled)

- [ ] Single-point chassis ground at designated mount hole only (`AERO_GND_001`)
- [ ] Copper keepout (typical 4 mm) on F.Cu, B.Cu, inner layers around all other NPTH mount holes
- [ ] GND turret / pad-and-finger pattern at the bonding point
- [ ] Stainless hardware (no galvanic mismatch with chassis material); torque per FAA AC 43.13-1B (`#8-32 = 12 in-lb` typical)

### Conformal coat masking (process intent)

- [ ] Field-serviceable terminals (turret posts, screw connectors, edge fingers, test points): masked during conformal coat with latex peelable mask or Kapton dots (`AERO_TERM_001`)
- [ ] Post-coat verification that brass / copper at terminal contacts is bare and bright

## JITX expressions

> **Illustrative.** The `design_constraint(...).METHOD(...)` patterns below show authoring intent, not exact API. The canonical rule-builder methods exported by `jitx.constraints` today are `trace_width`, `clearance`, `stitch_via`, `fence_via`, and `thermal_relief`. Tag subclasses (`SwTag`, `RFTag`, `ThermalPadTag`, `SensitiveAnalogTag`, etc.) are user-defined per the `Tag` base-class docstring — declare them at module scope in the project's tags module (see `project-builder-flow.md`). When a rule below names a method not in the canonical set, treat it as a placeholder for either a future rule-builder method or a project-local helper that calls the canonical methods.

```python
# Active reverse-polarity protection block (subcircuit)
class AircraftRPP(Circuit):
    vin = Power()
    vout = Power()
    def __init__(self):
        self.controller = LM74700_Q1()
        self.fet = AEC_Q101_NFET_Low_Rds()
        # ... wire controller drives FET gate; FET in series with VBUS
        ...

# Chassis ground keepout (substrate / design constraint)
design_constraint(ChassisKeepoutTag()).copper_keepout(4 * MM, all_layers=True)
design_constraint(ChassisBondTag()).hard_connect()
```

## Quantitative layout targets (waiting on introspection)

| Rule | Target | Introspection API needed |
|---|---|---|
| `AERO_VIB_001` | High-mass components staked per AS-50881 Method 13 | `board.component_mass()`, `board.staked_components()` |
| `AERO_GND_001` | 4 mm copper keepout on F.Cu, B.Cu, inner around mount holes; chassis bond at single point | `board.copper_keepout(net)`, `board.distance_to_hole(component)` |

## Out-of-band

| Rule | Why out-of-band | Suggested verification |
|---|---|---|
| `AERO_TERM_001` | Conformal coat masking is an assembly process | Work instruction; first-article inspection with photo |

## Common gotchas

- **AEC-Q part numbering is suffix-based** — `MOSFET-Q1` and `MOSFET-Q` are different qualifications. Verify exact PN.
- **SAC305 in a Class 3 build** — tin whiskers can short fine-pitch pins over months. Use Sn63/Pb37 eutectic or explicitly tin-whisker-tested finishes.
- **Galvanic corrosion at the chassis bond** — copper-to-aluminum or copper-to-stainless contact in salt-fog environments needs a transition material (tin plating, gold flash, conductive grease).
- **TVS rated by peak power but not clamp voltage** — a 1500 W TVS with 36 V clamp may cook a 28 V load. Always check Vc(IPP), not just Ppp.

## Cross-references

- [`external-interfaces.md`](external-interfaces.md) — connector ESD, hot-plug protection
- [`emc-esd.md`](emc-esd.md) — TVS placement, return path
- [`component-selection.md`](component-selection.md) — solder finish, AEC-Q qualifications
- [`mechanical.md`](mechanical.md) — chassis ground hardware, mounting torque
- [`power.md`](power.md) — reverse-polarity protection topology
