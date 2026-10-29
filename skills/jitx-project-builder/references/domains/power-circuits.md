# Power Circuit

### Electrical Correctness
- [ ] Input voltage range of regulator covers the actual source voltage (with tolerance)
- [ ] Output voltage matches the load requirement
- [ ] Output current rating sufficient with margin (>20% headroom recommended)
- [ ] Efficiency acceptable at expected load (check datasheet curves)
- [ ] Output noise/ripple within load IC requirements (especially for analog, RF, PLL supplies)
- [ ] Transient load response adequate for the load profile (check datasheet load transient plots)

### Enable Pin — CRITICAL (commonly missed)
- [ ] Enable pin is NOT left floating
- [ ] If always-on: tied to input voltage through resistor or direct (check datasheet for max voltage)
- [ ] If controlled: connected to control signal at correct logic level
- [ ] If open-drain/open-collector: has pull-up to appropriate rail
- [ ] UVLO threshold appropriate for input source (EN pin voltage divider if needed)

### Feedback Network
- [ ] Fixed output: verify FB/VOUT pin wiring matches datasheet (some go to output, some to a divider)
- [ ] Adjustable output: voltage divider from output to FB pin to GND
- [ ] Voltage divider MUST use `voltage_divider_from_constraints()` — NEVER manual resistor values
- [ ] Reference voltage (Vref) matches datasheet exactly (0.6V, 0.8V, 1.0V, etc.)
- [ ] `v_out` uses `Toleranced.percent()` not `Toleranced.exact()`

### Soft-Start and Sequencing
- [ ] Soft-start capacitor included if pin is available (prevents inrush)
- [ ] Power sequencing requirements documented if multiple rails
- [ ] Sequencing order correct: core supplies before IO supplies, analog before digital where required
- [ ] Sequencing implementation identified: PGOOD chaining, enable sequencing, or dedicated sequencer IC

### Switching Regulator Specifics (skip for LDOs)
- [ ] Inductor selected: saturation current > peak current, DCR acceptable for efficiency, core material appropriate for frequency
- [ ] Bootstrap capacitor present if required (buck converters with high-side FET)
- [ ] Compensation network matches datasheet recommendation (Type II/III, values from datasheet or calculator)
- [ ] Input capacitance meets datasheet minimum (low-ESR ceramic + bulk), voltage rating exceeds max input
- [ ] Output capacitance meets datasheet minimum for stability AND transient response
- [ ] Boost capacitor present if required (e.g., charge pump pin on some converters)
- [ ] Frequency-setting resistor correct if oscillator frequency is configurable
- [ ] Current sense resistor value correct (if external current sensing)
- [ ] Layout-sensitive components identified (input cap, bootstrap cap, inductor — must be close to IC)

### Output Stage
- [ ] Output capacitance meets datasheet minimum
- [ ] Output capacitor ESR within stability range (check datasheet — some LDOs require minimum ESR)
- [ ] Output decoupling: at minimum 100nF ceramic + bulk cap per datasheet

### Input Stage
- [ ] Input decoupling per datasheet recommendations (value, type, ESR)
- [ ] Input capacitor voltage rating exceeds maximum input voltage

### Power-Good and Fault — CRITICAL (commonly missed)
- [ ] PGOOD pin type identified: open-drain or push-pull (check datasheet)
- [ ] If open-drain: pull-up resistor to appropriate voltage rail (1k-100k typical)
- [ ] If push-pull: direct connection, no pull-up needed
- [ ] PGOOD connected to monitoring input or indicator LED
- [ ] Fault pins (OVP, OCP, THERMAL_SHUTDOWN) handled if present

### Thermal
- [ ] Thermal/exposed pad connected to ground copper (not left floating)
- [ ] Power dissipation within component ratings for expected ambient temperature

---
