# General Gotcha Scrub (Apply to ALL Tasks)

After the domain-specific checklist, verify these universal items:

### Electrical
- [ ] No floating inputs on any active device
- [ ] No missing ground connections
- [ ] Open-collector/open-drain outputs have pull-up resistors
- [ ] Analog reference pins properly decoupled/filtered
- [ ] Crystal load capacitors match oscillator requirements (if applicable)
- [ ] All voltage dividers use the solver function, not manual values

### JITX Code Correctness
- [ ] All nets stored on `self` — bare `a + b` expressions without assignment are silently dropped
- [ ] All components stored on `self` — anonymous `Component().insert()` fails at build time
- [ ] All topologies stored on `self` — bare `a >> b` without assignment is silently dropped
- [ ] No aliasing of component ports: `self.x = self.r1.p2` causes multiple-parent errors
- [ ] Port definitions at class level (not inside `__init__`) except for PadMapping and dynamically-configured ports set at instantiation time

### Top-Level Only (do NOT put these in subcircuits)
- [ ] `GroundSymbol` on GND net — applied at top-level design only
- [ ] `PowerSymbol` on every power rail — applied at top-level design only
- [ ] SI constraints (`Constrain`, `ConstrainDiffPair`, `ConstrainReferenceDifference`) — applied at top-level within `ReferencePlanes(GND)` context, not inside subcircuits
- [ ] Ground pours on ground plane layers — applied at top-level design only
- [ ] **I2C pull-ups** — placed at the bus-aggregation level (the circuit that composes master + slaves on the bus). Usually the top-level design because most buses span subcircuits; but if one subcircuit fully encloses both ends of a private bus, the pull-ups belong inside that subcircuit. Never local to a single bus participant.
- [ ] **Shared bus termination** (I2C, SPI, CAN) — pull-ups/termination at top-level only, never duplicated in subcircuits

### Datasheet Compliance (CRITICAL for circuit tasks)
- [ ] **Downloaded and read the datasheet** for every IC in this circuit
- [ ] **Application circuit matches datasheet** — every external component shown in the datasheet's typical application circuit is present in the JITX code
- [ ] No missing transistors (PMOS switches, level shifters, discharge FETs)
- [ ] No missing passives (bootstrap caps, snubber circuits, compensation networks)
- [ ] **Voltage domains checked** — every pull-up and pull-down goes to the correct rail (NOT VBUS if VBUS is high-voltage)
- [ ] Dual-function pins use resistors, not hard ties to VCC/GND
- [ ] Pins that should not be connected (NC per datasheet) are actually left unconnected
