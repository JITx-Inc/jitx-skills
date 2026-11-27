# Power Circuit

### Ratings
- [ ] Input range covers the actual source with its tolerance; output voltage matches the load.
- [ ] Output current with at least 20% headroom; efficiency acceptable at the expected load (datasheet curves).
- [ ] Ripple and noise within the load's limit (analog, RF and PLL supplies especially); transient response fits the load profile.
- [ ] Dissipation within the package rating at the expected ambient; thermal pad on ground copper.

### Enable
- [ ] EN never floating: tied to the input (direct or through a resistor, within its maximum voltage), or driven at the right logic level; an open-drain driver has a pull-up.
- [ ] UVLO threshold suits the source (an EN divider where needed).

### Feedback
- [ ] A fixed-output part's FB or VOUT pin wired as the datasheet shows.
- [ ] Adjustable: divider from output to FB to GND, Vref exactly the datasheet's; values on a named E-series with VOUT recomputed, and rounding error, each resistor's tolerance times (1 - Vref/Vout) and the datasheet's Vref accuracy together within the rail's tolerance.

### Soft-start and sequencing
- [ ] Soft-start capacitor where the pin exists.
- [ ] With several rails: the order documented and correct (core before IO, analog before digital where required), and its mechanism named (PGOOD chain, enable sequencing, a sequencer IC).

### Capacitors (every regulator)
- [ ] Input decoupling and output capacitance per the datasheet (value, type, ESR), output at its minimum for stability and transient response, each rated above the maximum voltage it sees.

### Switching regulators
- [ ] Inductor saturation current above peak current; DCR and core material suit the frequency.
- [ ] Bootstrap or boost capacitor where required; compensation per the datasheet (Type II/III).
- [ ] Frequency-setting and current-sense resistors correct where present.
- [ ] Layout-sensitive parts (input cap, bootstrap cap, inductor) named for placement.

### Linear regulators
- [ ] Output capacitor ESR inside the stability range, minimum ESR included where the LDO needs one.

### Power-good and faults
- [ ] PGOOD output type from the datasheet: open-drain takes a pull-up to the right rail (1 kΩ to 100 kΩ), push-pull none; PGOOD goes to a monitor input or an indicator.
- [ ] Fault pins (OVP, OCP, thermal shutdown) handled.
