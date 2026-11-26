# General Gotcha Scrub (Apply to ALL Tasks)

After the task type's checklist.

### Electrical
- [ ] No floating input on any active device; no missing ground.
- [ ] Every open-drain or open-collector output has a pull-up.
- [ ] Analog reference pins decoupled or filtered; crystal load capacitors match the oscillator's load.

### JITX placement
- [ ] Ports at class level, except a `PadMapping` or ports configured at instantiation.
- [ ] Ground pours, net symbols and SI constraints only at the top level (`jitx-circuit-builder`, the grep gates).
- [ ] Shared bus termination (I2C, MDIO, SPI, CAN) at the circuit that composes the bus, never duplicated in a participant.

### Datasheet Compliance
- [ ] Datasheet read for every IC in the circuit.
- [ ] Every external part of the typical application circuit present: transistors (PMOS switches, level shifters, discharge FETs) and passives (bootstrap, snubber, compensation).
- [ ] Every pull-up and pull-down on the right rail, never a high-voltage VBUS.
- [ ] Dual-function pins set through resistors, not hard ties.
- [ ] Pins the datasheet marks NC left unconnected; lines the IC drives internally left open (D+/D- on a PD controller using them for BC1.2).
