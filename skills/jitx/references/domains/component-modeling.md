# Component Modeling (All Components)

### Pins and Ports
- [ ] ALL pins from datasheet accounted for — not just signal pins
- [ ] Every VCC/VDD/VDDIO pin has a port
- [ ] Every GND/VSS/AGND pin has a port
- [ ] NC pins: if they have physical pads, they need ports
- [ ] Thermal/exposed pad included if present in package drawing
- [ ] Pin naming matches datasheet convention exactly
- [ ] Pin functions correct (input / output / bidirectional / power / ground)
- [ ] Pin arrays indexed correctly where names increment (e.g., `GND[0]` through `GND[N]`)
- [ ] No duplicate pin names

### Package and Landpattern
- [ ] Package type matches datasheet (QFN vs SON vs DFN vs SOIC, etc.)
- [ ] Body dimensions taken from MECHANICAL DRAWING page (not overview or ordering info)
- [ ] Lead pitch matches datasheet exactly
- [ ] Lead width and length from recommended land pattern or IPC calculation
- [ ] Toleranced values use min/nom/max from datasheet (not nominal only)
- [ ] Thermal pad dimensions from mechanical drawing (usually labeled D2/E2 or Dpad/Epad)
- [ ] Thermal pad has paste subdivision if area > 4mm^2 (prevents solder voids)
- [ ] Pin 1 orientation matches datasheet marking
- [ ] Correct landpattern generator chosen (QFN vs SON for 2-sided vs 4-sided no-lead)

### Symbol
- [ ] All ports appear in BoxSymbol
- [ ] Logical grouping: power pins up, ground pins down, inputs left, outputs right
- [ ] Pin count > ~40: symbol checked for readability — usually split into multiple boxes (by functional group, or by pin-slice for parts with no natural grouping; see `jitx-component-modeler` "Multi-Unit Symbols"), or rationale recorded if kept as one box. Partitioned symbols can go on separate schematic pages via `SchematicGroup`.

### Build Test
- [ ] Test harness created using TestDesign pattern
- [ ] Builds with `status: ok`
- [ ] PadMapping verified (if explicit mapping used — pad names match landpattern)

---

## Two-Terminal Chip Components (Additional)

Chip resistors, MLCCs, chip inductors, ferrite beads. Run the base Component checklist above FIRST,
then verify these — each is a failure that leaves a land pattern valid, building, and wrong:

- [ ] Size key matched to the standard chip table by body L × W, not by the vendor's size label
- [ ] Termination length taken from the band dimensioned on the **seating plane**, not the end-face
      wrap-up band
- [ ] Where the standard table's dimensions were used, they are asserted against the datasheet per
      size, with any override commented
- [ ] Density level set to what the datasheet asks for, or the installed default checked and
      recorded as matching — the default has changed between jitxlib versions, so assume neither
- [ ] Two ports declared in pad order; standard two-pin symbol, not a `BoxSymbol`
- [ ] `.value` renders as the value asked for, asserted in a submitted and
      captured test harness rather than on a constructor proxy outside a design
      context

---

## MCU / FPGA Components (Additional)

Run the base Component checklist above FIRST, then verify these:

### Clock System
- [ ] Crystal/oscillator input pins present (XTAL_IN, XTAL_OUT or HSE_IN, HSE_OUT)
- [ ] External clock input pins present (if supported)
- [ ] PLL reference clock pins present (for FPGAs with transceivers)
- [ ] RTC crystal pins (LSE_IN, LSE_OUT) if RTC is supported
- [ ] Clock distribution requirements identified — protocols like PCIe require shared reference clocks (REFCLK) to all endpoints on the same clock domain. Plan clock tree topology (point-to-point, fanout buffer, clock generator) during decomposition.

### Programming and Debug
- [ ] JTAG pins present: TCK, TMS, TDI, TDO (and optionally nTRST)
- [ ] SWD pins present: SWCLK, SWDIO (for ARM MCUs)
- [ ] UART bootloader pins identified (if applicable)
- [ ] Configuration pins present (nCONFIG, CONF_DONE, nSTATUS for FPGAs)

### Reset
- [ ] Reset pin present with correct polarity documented (nRST = active-low, RST = active-high)
- [ ] Reset pin labeled consistently with datasheet convention

### Power Domains
- [ ] Core supply pins (VCC, VCCINT) — all of them, not just one
- [ ] IO bank supply pins (VCCIO, VDDIO) — every bank, even if same voltage
- [ ] PLL/analog supply pins (VCCA, VCCPLL) — separate from digital
- [ ] Transceiver supply pins (VCC_XCVR, VCCR, VCCT) if applicable
- [ ] Auxiliary supply pins (VCCAUX) if present
- [ ] **Single-pin supplies counted as supplies.** Sense, calibration and battery-backup rails
      (VCCINT_SENSE, VCCAUX_SMON, VCC_BATT, VCC_FUSE) often get exactly one pin. Enumerate the
      supply roster from the pin inventory, not from whichever rails happen to be multi-pin lists —
      a roster built by walking the lists drops these silently, and the count still looks plausible.
      Where such a rail carries its own dedicated return, that return is a **separate ground domain**
      and must not be merged into the main one.
- [ ] **Transceiver analog and bias rails modeled at the hierarchy the vendor states.** These are
      often shared above the lane — a supply group or bank spanning several lanes, with one
      calibration pair serving all of them — but the level varies by device family, so read it off
      the packaging manual's bank/power diagram rather than assuming any particular one. Two rules
      hold regardless: the assignment is **not** inferable from pin-name suffixes or ball proximity,
      and modeling a shared rail as a per-lane member produces lanes that have none.
- [ ] **Bonded-but-unused rails identified.** A package may bond a supply group whose consumer is
      not bonded in that package. Those pins are real and belong in the component and its roster —
      expose them like any other rail and say so, rather than dropping them or inventing a
      termination. What to *do* with them is a power-integrity question the packaging manual does
      not answer; it belongs to the vendor's PCB/power design guidance.

### Boot and Configuration
- [ ] Boot mode pins present (BOOT0, BOOT1 for STM32; MSEL for Intel FPGAs)
- [ ] Configuration select pins if applicable
- [ ] Power-on-reset configuration pins if applicable

### IO Banks
- [ ] All IO banks modeled (not just the ones used in the current design)
- [ ] Bank-to-pin mapping documented in comments or docstring

---
