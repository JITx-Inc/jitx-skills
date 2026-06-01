# External Interfaces Reference

## When to read this

You are placing any connector or interface that exposes the board to the outside world: USB (any), Ethernet, audio jacks, power input (barrel, terminal, USB-PD, PoE), debug headers if user-accessible, expansion connectors, antenna connectors, edge-card fingers. Also applies to exposed switches, jumpers, push-button terminals, and edge castellations — any user-touchable conductor. (PCB antenna geometry itself is in `references/net-classes.md` → RF.)

Quantitative thresholds (TVS placement distance, ESD capacitance budgets, connector current ratings, retention) are folded into the checklists below.

## Authoring-time targets

### Per-connector decisions

- [ ] **Orientation / pin mirroring** — USB-C is symmetric (CC1/CC2 mirror); standard USB-A/B is not. Verify pin map matches chosen orientation.
- [ ] **Shield / chassis strategy** — connected to chassis ground via short trace, ferrite bead, capacitor, or hard-tied — picked deliberately.
- [ ] **Current rating** — connector ampacity exceeds worst-case load with margin
- [ ] **Polarity / hot-plug protection** — reverse-voltage, surge, inrush handled per source class
- [ ] **Mechanical retention** — through-hole tabs, screw mount, locking mechanism, or none, matched to expected use (`MEC_CONN_001`)
- [ ] **Function-label intent recorded in JITX** — `J1_USB`, `J2_SWD`, not just `J1`; rendered silkscreen is out-of-band visual verification until tooling supports it (`DFT_CONN_LABEL_001`)

### ESD-or-justification (one row per external pin)

For every external or user-accessible signal pin — connector pins, exposed switches/jumpers, push-button terminals, test points, edge fingers, castellations, any user-touchable conductor — the design must say one of:

- **TVS / ESD diode specified**, with capacitance compatible with signaling speed
  - Low-cap TVS (< 10 pF, often < 1 pF) for USB / Ethernet / DisplayPort / PCIe (`EMC_ESD_006`)
  - Standard TVS for low-speed signals
- **Internal-only** — not user-accessible (board-to-board internal link, sealed enclosure, controlled environment)
- **Omitted by design** — explicit reason (RF impedance budget, cost-constrained prototype, EMC-controlled fixture); user confirms

### TVS / EMI filter placement (authoring-time)

- [ ] TVS ground pad: ≥ 2 dedicated vias, no thermal reliefs on the TVS pad (`EMC_ESD_004`)
- [ ] EMI filter (ferrite bead or RC) at connector boundary on signal lines (`EMC_ESD_002`)
- [ ] TVS placement intent: ≤ 10 mm from connector pin (`EMC_ESD_001`) — enforced at layout time, see Quantitative section below

### Polarity and labeling

- [ ] Power connectors: polarity-marking and voltage/current label intent recorded in JITX; rendered silkscreen is out-of-band visual verification until tooling supports it (`DFT_POL_001`)
- [ ] Function-label intent per connector recorded in JITX; rendered silkscreen is out-of-band visual verification until tooling supports it (`DFT_CONN_LABEL_001`)
- [ ] Power-rail test point near the connector for bring-up (also `dft.md`)

## Protocol-specific sub-checklists

These are examples, not required coverage. Pick the ones that apply.

### USB-C / USB-PD
- CC1/CC2 pull-down or PD configuration resistors per role (sink / source / DRP)
- CC capacitance limits per spec
- VBUS protection rated for negotiated voltages (5 V / 9 V / 15 V / 20 V)
- D+/D− low-cap ESD
- Configuration-trap pins per controller datasheet

### Ethernet (RJ45)
- Magnetics or LAN module per spec
- MDI / MDIX termination
- Bob Smith terminations on unused pairs
- Shield bond strategy: chassis-to-circuit-ground bond per EMC plan
- Bob Smith capacitor voltage rating ≥ 2 kV typical

### Audio (3.5 mm TRS / TRRS)
- Switching contacts on TRS detect insertion (if used)
- AC coupling on signal lines (or DC-coupled with explicit reason)
- ESD on tip / ring
- Ground-loop strategy for line-out

### Antenna connector / feed (U.FL, SMA, board-edge contact)
- 50 Ω routing structure to the connector
- Return-plane keepout under the feed (`net-classes.md` → RF)
- Connector type matched to frequency and mate strategy

### Debug headers (if user-accessible)
- ESD on signals
- Protection if user can short pins (e.g., reverse-insertion protection)
- Pin keying or marking to prevent reverse insertion
- (Internal-only debug headers in sealed enclosures may justify omitting ESD — note explicitly)

### Barrel / terminal power input
- Reverse-polarity protection: passive Schottky for low-current, active ideal-diode controller for higher currents (`AERO_RPP_001` for aircraft)
- Bidirectional TVS for transient suppression (`AERO_TVS_001` for aircraft; ISO 7637-2 for automotive)
- Inrush limiter (NTC or active soft-start) for large input bulk

### PoE
- Diode bridge for polarity-agnostic input
- PD controller per IEEE 802.3 class
- Isolation barrier creepage per the regulatory class

## Quantitative layout targets (waiting on introspection)

Record authoring intent in JITX now. Classify placement checks with named layout APIs as `awaiting-introspection`; rendered silkscreen/label checks remain out-of-band visual verification.

| Rule | Target | Introspection API needed |
|---|---|---|
| `EMC_ESD_001` | TVS within 10 mm of connector pin | `board.distance(component, component)` |
| `EMC_ESD_003` | TVS placement as close to connector as possible | `board.distance(component, component)` |
| `EMC_ESD_005` | No sensitive signals parallel to ESD-exposed traces | `board.parallel_traces(net1, net2)` |
| `DFM_COMP_EDGE_001` | Components ≥ 100 mils (2.5 mm) from board edge | `board.component_to_edge()` |

## Common gotchas

- **TVS on USB-C SBU pins forgotten** — easy to remember TVS on D+/D−/SS but miss SBU1/SBU2 and CC1/CC2.
- **PoE shield bond done as a hard tie** — needs to be through capacitance or ferrite bead unless explicitly tied for safety-ground reasons; hard tie creates ground loops.
- **Edge castellation without ESD** — castellated module fingers are user-touchable when the module is on the bench. Treat as external.
- **"Sealed enclosure" assumption** — verify the enclosure is actually sealed at the relevant ports during the user's expected handling; field service often exposes debug headers.

## Cross-references

- [`emc-esd.md`](emc-esd.md) — return paths, plane stitching, aggressor separation
- [`safety-critical.md`](safety-critical.md) — aircraft / automotive transient suppression
- [`dft.md`](dft.md) — test points and named connectors
- [`net-classes.md`](../net-classes.md) — `ESDExposedTag`, `RFTag`
