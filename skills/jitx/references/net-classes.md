# Net Class Taxonomy (Per-Design Table)

Some nets need non-default physical rules — width, clearance, impedance, keepout, return path, shield. The class catalog isn't fixed; each design enumerates the net classes that apply. Generate this table during Phase 3 and apply rules via `design_constraint(<NetClassTag>(), priority=N).<rule>(...)`.

**Generate one row per applicable class. Skip rows that don't apply. If no nets in this design need non-default rules, record "no non-default net classes" with one-line rationale.**

| Net class | Why it matters | Width / clearance / keepout / impedance / return path | JITX expression |
|-----------|---------------|-------------------------------------------------------|-----------------|
| Switch node (buck/boost) | Hot loop EMI, dV/dt | Width sized for current; tight loop area; pour pulled back from node | `design_constraint(SwTag(), ...).clearance(...)` |
| RF / antenna feed | Impedance, return current, EMI | 50Ω routing structure; return-plane keepout under antenna | Routing structure + `design_constraint(RFTag(), ...)` |
| High-speed differential (USB, Ethernet, PCIe, etc.) | Impedance, skew, EMI | 90/100Ω diff; via stitching; reference-plane continuity | SI constraint + routing structure |
| DDR / LPDDR | Per-byte-lane timing | Per-class width/clearance; length matching | Diff and length-matching constraints |
| Sensitive analog | Coupling, ground loops | Guard rings, shield, separate return | Net class with clearance |
| High-voltage / mains | Creepage, isolation | Class-dependent clearance, no-pour zones | Clearance constraint, layer assignment |
| High-current | I²R, thermal, EMI | Wide trace or pour, multiple vias | Width and via-count constraint |
| Gate drive | dV/dt, ringing | Tight return loop, gate resistor placement | Net class + placement constraint |
| Kelvin sense | Accuracy | Separate trace from current path | Routing rule |
| Isolated domain | Galvanic isolation | Creepage / clearance / barrier | No-pour zone, clearance |

The list is not exhaustive — add new classes as a design demands them (e.g., low-leakage thermocouple inputs, guard rings, motor phase windings).

The Phase 3 → 3b transition confirms the table exists if the design has any non-default net classes; if not, it confirms the explicit "no non-default net classes" statement.

---
