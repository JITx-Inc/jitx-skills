# Component Modeling (All Components)

`jitx-component-modeler` "Verification and halt" owns the pin, land pattern, symbol and build checks. Add:

- [ ] No two ports share a name.
- [ ] Each port's function (input, output, bidirectional, power, ground) matches the pin table.
- [ ] Lead width and length from the recommended land pattern, or an IPC calculation where there is none.
- [ ] Thermal pad size from the mechanical drawing (D2/E2, Dpad/Epad); paste split into windows above 4 mm².
- [ ] Pin 1 matches the package marking.
- [ ] Symbol grouping: power up, ground down, inputs left, outputs right; a part over about 40 pins split, or the reason it is one box recorded.
- [ ] An explicit `PadMapping` names only pads the land pattern has.

---

## MCU / FPGA Components (Additional)

After the base list:

### Clock
- [ ] Crystal or oscillator inputs (XTAL_IN/XTAL_OUT, HSE_IN/HSE_OUT), external clock input, RTC crystal (LSE) where supported, transceiver PLL reference clocks.
- [ ] Shared reference clocks a protocol needs (PCIe REFCLK to every endpoint of a clock domain) and the clock-tree topology (point to point, fanout buffer, generator) planned at decomposition.

### Programming, reset, boot
- [ ] JTAG (TCK, TMS, TDI, TDO, optional nTRST) or SWD (SWCLK, SWDIO); UART bootloader pins.
- [ ] FPGA configuration pins (nCONFIG, CONF_DONE, nSTATUS); boot mode pins (BOOT0/BOOT1, MSEL); power-on configuration pins.
- [ ] Reset polarity documented (nRST active low) and named as the datasheet names it.

### Power domains
- [ ] Every core, IO bank, PLL/analog, transceiver and auxiliary supply pin, every bank even at one voltage.
- [ ] Supply roster taken from the pin inventory, not the multi-pin lists: single-pin sense, calibration and backup rails (VCCINT_SENSE, VCCAUX_SMON, VCC_BATT, VCC_FUSE) drop out of a roster built from the lists. A rail with its own dedicated return is a separate ground domain, never merged into the main one.
- [ ] Transceiver analog and bias rails modeled at the level the packaging manual's bank or power diagram shows (often one supply group and calibration pair across several lanes), never inferred from name suffixes or ball proximity. A shared rail modeled per lane leaves lanes with none.
- [ ] Rails bonded in the package whose consumer is not bonded are exposed like any other rail and reported, not dropped or given an invented termination; what to do with them is a question for the vendor's power design guidance.

### IO banks
- [ ] Every IO bank modeled, used or not; bank-to-pin mapping in a comment or docstring.
