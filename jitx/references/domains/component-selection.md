# Component Selection Reference

## When to read this

The user asks "which capacitor / resistor / inductor should I use" without giving a specific MPN, OR you are about to instantiate a passive whose value is correct but whose *type* (dielectric, package, technology) is not specified. This domain reference lives under `jitx/references/domains/` and is linked from `jitx-component-modeler` because selection and creation are usually contiguous turns.

## Capacitors

### Dielectric choice (ceramic)

| Class | Use for | Avoid for |
|---|---|---|
| C0G / NP0 (Class I) | Precision filters, oscillator load caps, low-noise circuits, snubbers | Decoupling (low capacitance density) |
| X7R | General decoupling, bulk-ish caps up to ~10 µF, signal coupling | Precision filters (Δ20% across temp) |
| X5R | Compact decoupling (smaller package at same value) | Wide-temp applications (only −55 / +85) |
| Y5V / Z5U | Avoid in new designs | Anything precision; loses up to 80% C under DC bias (`COMP_CAP_001`) |

### Voltage derating

- [ ] Ceramic caps: voltage rating ≥ 1.5–2× applied voltage to maintain capacitance under DC bias (`COMP_CAP_004`)
  - A 10 µF / 10 V X5R cap on a 9 V rail can drop to 4 µF effective. Use 25 V rated.
- [ ] Polar caps (electrolytic, tantalum, polymer): rating ≥ 1.5× applied; verify reverse-voltage conditions (`SCH_POL_001`)

### Electrolytic specifics

- [ ] Ripple current rating ≥ measured (or calculated) ripple at expected load
- [ ] Life halves per 10 °C above rated temperature; size for worst-case ambient + self-heating (`COMP_CAP_005`)
- [ ] ESR matters for SMPS output filtering — parallel smaller caps reduce impedance (`COMP_CAP_006`)
- [ ] Avoid electrolytic for high-impedance sample-and-hold (leakage incompatible) (`COMP_CAP_003`)

### Precision filters and oscillators

- [ ] Use C0G / NP0 (`COMP_CAP_002`) — temperature coefficient ≈ 0 ppm/°C
- [ ] Verify SRF above operating frequency

### Package selection for HF decoupling

- [ ] Prefer 0402 / 0603 over 0805 — lower parasitic inductance (`PWR_DECPL_004`)
- [ ] For BGAs, plan for via-in-pad if signal density requires (`PWR_DECPL_003`)

## Resistors

### Technology choice

| Type | Use for | Avoid for |
|---|---|---|
| Thick film (most common) | Pull-ups, dividers, general | Low-noise audio, precision (`COMP_RES_001`) |
| Thin film | Precision dividers, low-noise, matched pairs | Cost-sensitive bulk roles |
| Metal film | Audio, low noise, mid-precision | HF (parasitic L worse than chip) |
| Wirewound | High power, low value | HF (significant parasitic L, `COMP_RES_004`) |

### Quantitative gates

- [ ] Power derating to 50% of rated power; account for ambient temperature (`COMP_RES_003`)
- [ ] Matched pairs / dividers in precision applications: use resistor networks for tempco matching (`COMP_RES_002`)
- [ ] HF (> 10 MHz): chip resistors only, no wirewound (`COMP_RES_004`)

## Inductors

### Quantitative gates

- [ ] Saturation current Isat ≥ 1.3× peak operating current (`COMP_IND_002`); derate further for elevated temperature
- [ ] Self-resonant frequency (SRF) ≥ 10× operating frequency for stable inductance (`COMP_IND_003`)
- [ ] Q factor: check the Q-vs-frequency curve, not just the rated Q (`COMP_IND_004`)
- [ ] Cored inductor tolerance ±20% typical; match part-to-part tolerance in resonant filters (`COMP_IND_001`)

### Core material guidance

- [ ] Ferrite cores: < 1 MHz, low DC bias
- [ ] Powdered iron: high DC bias, gradual saturation curve
- [ ] Air-core / multilayer ceramic: > 100 MHz RF chokes
- [ ] Composite / metal alloy (e.g., XAL series): modern high-current SMPS, replaces shielded ferrite

## Special-purpose components

### TVS diodes (also see [`external-interfaces.md`](external-interfaces.md))

- [ ] Standoff voltage > maximum operating voltage
- [ ] Clamp voltage (Vc at IPP) < tolerable transient at the protected pin, with ≥ 1.5× margin
- [ ] Capacitance < 10 pF for high-speed data lines (USB, Ethernet, DisplayPort) (`EMC_ESD_006`)
- [ ] Unidirectional for DC; bidirectional for AC or bipolar signals

### Solder finish (safety-critical / aerospace)

- [ ] Aerospace Class 3: Sn63/Pb37 eutectic, JESD201 Class 1A whisker-tested leads (`AERO_SLD_001`)
- [ ] Commercial: SAC305 is fine; avoid pure-tin lead finishes in long-life designs (whisker risk)

## Out of scope here

- Specific MPN selection from a distributor catalog — use `jitx/references/parts-sourcing.md`
- Footprint and pin mapping — that's the rest of the `jitx-component-modeler` skill

## Cross-references

- [`power.md`](power.md) — decoupling discipline, regulator selection
- [`analog-mixed-signal.md`](analog-mixed-signal.md) — precision filter caps, low-noise resistors
- [`external-interfaces.md`](external-interfaces.md) — TVS selection for protection
- [`safety-critical.md`](safety-critical.md) — aerospace solder, AEC-Q101 FETs
