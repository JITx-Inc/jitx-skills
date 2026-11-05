# Corrow Power CPI-4833 isolated DC/DC module: datasheet excerpt (synthetic example)

Corrow Power is a fictional manufacturer. This excerpt is from datasheet
CPI-4833-DS revision 2, sections 1, 6 and 9. All dimensions are millimetres.

## 1. Summary

The CPI-4833 is a 2 W isolated DC/DC converter module: 36 to 60 V input, 3.3 V
output, transformer isolated. Pads 1 (+VIN) and 2 (-VIN) are the input side.
Pads 3 (+VOUT) and 4 (-VOUT) are the output side.

## 6. Isolation

| Line | Parameter | Value |
|---|---|---|
| 6.1 | Isolation test voltage, input to output, 60 s | 1500 VDC |
| 6.2 | Insulation resistance at 500 VDC | 1 GOhm min |
| 6.3 | Isolation capacitance | 50 pF typ |

## 9. PCB layout

| Line | Recommendation |
|---|---|
| 9.1 | Land pattern: four 1.6 x 1.0 pads; pads 1 and 2 at x -5.0, pads 3 and 4 at x +5.0, y +1.27 and -1.27. |
| 9.2 | Keep at least 2.0 between any copper connected to pads 1 or 2 and any copper connected to pads 3 or 4, on every layer of the board. Pours and planes included. |
| 9.3 | The clearance in 9.2 holds the module's 1500 VDC test rating at the board. Creepage over the board surface, and any larger clearance or creepage the end product's safety standard requires, are set by that standard and are not given here. |
