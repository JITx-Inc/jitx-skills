# 05 — Parametric `pcb-module` with closed-form formulas

A common pattern in Stanza application-circuit modules: the body
**computes** component values from kwargs, snaps each to a standard
E-series value, then instantiates the resulting passives. The naive
Python port picks the values that fall out of one example call and
hardcodes them — which silently breaks the moment kwargs change.

This file walks the TPS62933 buck-regulator module (from
`pd-audio_stanza/components/Texas-Instruments/TPS62933DRLR.stanza`)
side-by-side and shows how to preserve the formula in the port.

## Stanza 3.x source — extracted from `TPS62933DRLR.stanza`

```stanza
public pcb-module module (-- output-voltage:Double = 3.3
                             input-voltage:Double = 25.0
                             soft-start:Double = 2.0e-3
                             output-current:Double = 3.0
                             ripple:Double = 30.0e-3) :
  pin vin
  pin vout
  pin gnd
  pin pg
  pin en

  inst buck : components/Texas-Instruments/TPS62933DRLR/component
  net (vin, buck.VIN) ; net (en buck.EN) ; net (pg buck.SS)
  net GND (buck.GND gnd)
  val RT-res = res-strap(buck.RT, gnd, 0.0)   ; 1.2 MHz switching

  ; Feedback divider — voltage-divider generator picks two resistors
  ; to produce target ratio at the named divider current.
  inst feedback : ocdb/modules/passive-circuits/voltage-divider(
    source-voltage = typ(output-voltage),
    divider-output = 0.8 +/- (3 %),
    current = 0.800 / 10.0e3,
  )
  net (feedback.in vout)
  net (feedback.out buck.FB)
  net (feedback.lo gnd)

  ; Soft-start cap: Css = Tss * 5.5 µA / 0.8 V
  val css = soft-start * 5.5e-6 / 0.8
  val c-ss = cap-strap(buck.SS, gnd, closest-std-val(css, 10.0))

  ; Bootstrap cap + series resistor (datasheet: R_BST < 10 Ω)
  inst cbst : ceramic-cap(["capacitance" => 0.1e-6
                           "min-rated-voltage" => 16.0
                           "temperature-coefficient.code" => "X7R" ])
  net (cbst.p[1], buck.SW)
  val r-bst = res-strap(cbst.p[2] buck.BST, 2.7)

  ; Inductor sizing — closed-form from datasheet
  val fsw = 1.2e6
  val K = (40 %)
  val L = closest-std-val(
    output-voltage / input-voltage *
    (input-voltage - output-voltage) / (fsw * K * output-current),
    20.0
  )
  val ripple-current = output-voltage / input-voltage *
                       (input-voltage - output-voltage) / (fsw * L)
  inst inductor : database-part(["mpn" => "WPN4020H6R8MT",
                                 "manufacturer" => "Sunlord"])
  net (inductor.p[1] buck.SW)
  net (inductor.p[2] vout)

  ; Output cap count derived from ripple-current + derating
  val D = output-voltage / input-voltage
  val cout-min = ripple-current / (fsw * ripple * K) *
                 ((1. - D) * (1. + 1.0 * K) + pow(1.0 * K, 2.) / 12.0 * (2. - D))
  val derated-capacitance = cout-min * 3.        ; 3× derating
  val cap = 22.0e-6                              ; per-cap value
  val min-output-caps:Int = to-int(derated-capacitance / cap) + 1
  val output-caps = to-tuple $
    for i in 0 to min-output-caps seq :
      bypass-cap-strap(inductor.p[2], gnd,
                       ["capacitance" => cap, "case" => "0805",
                        "temperature-coefficient.code" => "X7R",
                        "min-rated-voltage" => output-voltage * 2.])

  ; Input caps + feedforward cap
  bypass-cap-strap(buck.VIN, gnd, ["capacitance" => 10.0e-6,
                                   "temperature-coefficient.code" => "X7R",
                                   "min-rated-voltage" => input-voltage * 1.5])
  bypass-cap-strap(buck.VIN, gnd, ["capacitance" => 10.0e-6,
                                   "temperature-coefficient.code" => "X7R",
                                   "min-rated-voltage" => input-voltage * 1.5])
  bypass-cap-strap(buck.VIN, gnd, ["capacitance" => 0.1e-6,
                                   "temperature-coefficient.code" => "X7R",
                                   "min-rated-voltage" => input-voltage * 1.0])
  cap-strap(feedback.in, feedback.out, 100.0e-12)   ; feedforward

  property(vout.voltage) = typ(output-voltage)
```

## The naive port (anti-pattern)

A common mistake is to expand the module for the call site `module(output-voltage=3.3, input-voltage=20.0, output-current=0.75, ripple=30.0e-3)` and **hardcode** the values that fall out:

```python
class TPS62933Module(Circuit):
    def __init__(self, output_voltage=3.3, input_voltage=20.0,
                 output_current=3.0, ripple=30.0e-3, soft_start=2.0e-3):
        self.buck = TPS62933()
        # ❌ Hardcoded 4.7 µH — formula picks ~6.8-8.2 µH for these kwargs.
        # If a caller changes output-current to 0.5 A, this stays 4.7 µH
        # and is under-sized; if they change to 2 A, it's over-sized.
        self.L = Inductor(inductance=4.7e-6, current_rating=4.0)
        # ❌ Branching on a specific value — code smell.
        # The whole point of a parametric module is that kwargs vary;
        # this branch only handles 3.3 V cleanly.
        r_hi_value = 31.6e3 if abs(output_voltage - 3.3) < 0.01 \
                     else ((output_voltage / 0.8 - 1.0) * 10.0e3)
        self.r_fb_hi = Resistor(resistance=r_hi_value)
        # ❌ Output cap count fixed at 3, ignoring ripple-current derivation.
        self.c_out1 = Capacitor(capacitance=22e-6, case="0805")
        self.c_out2 = Capacitor(capacitance=22e-6, case="0805")
        self.c_out3 = Capacitor(capacitance=22e-6, case="0805")
        # ...
```

The build passes and the call with `output_voltage=3.3, output_current=0.75` even produces approximately the right BoM. But every parameter that wasn't the example value is now wrong.

## The correct port — keep the formula

```python
from jitx import Circuit, Net
from jitx.net import Port
from jitxlib.parts import Capacitor, Inductor, Resistor
# Hypothetical helper covered in jitx-skills:jitx-circuit-builder
# §"Snap computed values to a standard E-series":
from <project>.helpers.e_series import closest_std_val


class TPS62933Module(Circuit):
    vin = Port()
    vout = Port()
    gnd = Port()
    pg = Port()
    en = Port()

    def __init__(self, *,
                 output_voltage: float = 3.3,
                 input_voltage: float = 25.0,
                 soft_start: float = 2.0e-3,
                 output_current: float = 3.0,
                 ripple: float = 30.0e-3):
        self.buck = TPS62933()

        # Direct port-to-pin nets
        self.vin_net = self.buck.VIN + self.vin
        self.en_net = self.buck.EN + self.en
        self.pg_net = self.buck.SS + self.pg
        self.gnd_net = Net([self.buck.GND, self.gnd])

        # RT to GND for 1.2 MHz switching
        self.r_rt = Resistor(resistance=0.0)
        self.r_rt.insert(self.buck.RT, self.gnd)

        # ✓ Voltage divider — port the math, not the snapped result.
        #
        # source_voltage / divider_output / divider_current together fix
        # both resistor values. R_lo = V_ref / I_div ; R_hi solves for
        # the voltage ratio.
        v_ref = 0.8
        divider_current = v_ref / 10.0e3                    # 80 µA, per Stanza source
        r_lo_value = closest_std_val(v_ref / divider_current, 96)
        r_hi_value = closest_std_val(
            r_lo_value * (output_voltage / v_ref - 1.0), 96
        )
        self.r_fb_hi = Resistor(resistance=r_hi_value)
        self.r_fb_hi.insert(self.vout, self.buck.FB)
        self.r_fb_lo = Resistor(resistance=r_lo_value)
        self.r_fb_lo.insert(self.buck.FB, self.gnd)

        # ✓ Soft-start cap from datasheet formula
        css = soft_start * 5.5e-6 / v_ref
        self.c_ss = Capacitor(capacitance=closest_std_val(css, 10))
        self.c_ss.insert(self.buck.SS, self.gnd)

        # Bootstrap cap + R_BST series resistor
        self.c_bst = Capacitor(capacitance=100e-9, rated_voltage=16.0,
                               temperature_coefficient_code="X7R")
        self.r_bst = Resistor(resistance=2.7)
        self.r_bst.insert(self.c_bst.p2, self.buck.BST)
        self.bst_sw_net = self.c_bst.p1 + self.buck.SW

        # ✓ Inductor sizing — closed-form, snapped to E-series
        fsw = 1.2e6
        K = 0.40
        L_raw = (output_voltage / input_voltage *
                 (input_voltage - output_voltage) /
                 (fsw * K * output_current))
        L_value = closest_std_val(L_raw, 20)
        ripple_current = (output_voltage / input_voltage *
                          (input_voltage - output_voltage) / (fsw * L_value))
        self.L = Inductor(inductance=L_value)
        self.L_sw_net = self.L.p1 + self.buck.SW
        self.L_vout_net = self.L.p2 + self.vout

        # ✓ Output cap count — derived from ripple + derating
        D = output_voltage / input_voltage
        cout_min = (ripple_current / (fsw * ripple * K) *
                    ((1.0 - D) * (1.0 + 1.0 * K) +
                     (1.0 * K) ** 2 / 12.0 * (2.0 - D)))
        derated_capacitance = cout_min * 3.0       # 3× derating
        per_cap = 22.0e-6                          # MLCC unit value
        n_caps = int(derated_capacitance / per_cap) + 1
        self.c_out = [
            Capacitor(capacitance=per_cap, case="0805",
                      temperature_coefficient_code="X7R",
                      rated_voltage=output_voltage * 2.0)
            for _ in range(n_caps)
        ]
        for c in self.c_out:
            c.insert(self.vout, self.gnd)

        # Input caps — fixed count from Stanza source (not derived)
        self.c_in = [
            Capacitor(capacitance=10e-6,
                      temperature_coefficient_code="X7R",
                      rated_voltage=input_voltage * 1.5)
            for _ in range(2)
        ]
        for c in self.c_in:
            c.insert(self.buck.VIN, self.gnd)
        self.c_in_sm = Capacitor(capacitance=100e-9,
                                 temperature_coefficient_code="X7R")
        self.c_in_sm.insert(self.buck.VIN, self.gnd)

        # Feedforward cap
        self.c_ff = Capacitor(capacitance=100e-12)
        self.c_ff.insert(self.vout, self.buck.FB)
```

The Python port is no longer than the naive version, but every value
flows from the same closed-form formulas the Stanza source used.
Calling `TPS62933Module(output_voltage=5.0, output_current=2.0,
ripple=20e-3)` now picks the correct inductor, feedback divider, and
output-cap count automatically.

## Audit checklist for parametric modules

For each Stanza module signature with `(-- kw1:Type = default, kw2:Type
= default, ...)`:

- [ ] The Python `__init__` accepts the same kwargs with matching
      defaults (use `*,` to force keyword-only — Stanza named-kwarg
      syntax is keyword-only on the Stanza side).
- [ ] Every `closest-std-val(...)` call on the Stanza side has a
      Python equivalent that recomputes from the kwargs.
- [ ] Every `for i in 0 to <computed-int> seq : ...` loop on the
      Stanza side has a Python list comprehension whose count is
      computed from the kwargs.
- [ ] No Python `if abs(<kwarg> - <constant>) < epsilon:` branches in
      the body — that's the smoke for "hardcoded one example call".
- [ ] No magic numbers in the Python body that aren't derived from
      either the datasheet (cite the equation) or the formula
      (computed inline).
- [ ] Generator-provided child instances like
      `ocdb/modules/passive-circuits/voltage-divider` are ported as
      **two-resistor math**, not as a single-resistor MPN lookup.
