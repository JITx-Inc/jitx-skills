# ACME ACC Series — Multilayer Ceramic Capacitors (Overview Catalog)

> Fictional manufacturer, prepared as an eval fixture. The body and termination
> dimensions below are the physically standard EIA/IEC chip geometries; the
> part-number grammar, voltage and thickness codes and the capacitance grid are
> invented. Any resemblance to a real ordering scheme is coincidental.

**ACME Passive Components** · Document APC-CAT-0207 · Rev C · Overview edition · Page 1 of 4

---

## 1. Scope of this document (page 1)

This is the **overview** edition of the ACC catalog. It carries the complete
ordering grammar, the case-size dimension table, the dielectric and rated-voltage
lineup, the tolerance codes and the capacitance significand grid.

> ※ This overview does **not** publish the per-case capacitance lineup — which
> capacitance values are actually offered in a given case size, dielectric and
> voltage combination. For the detailed lineup, use the product search on the
> ACME Passive Components website.

---

## 2. Case sizes (page 2)

| ACME size code | EIA size | IEC / metric code |
|---|---|---|
| 02 | 0402 | CC1005M |
| 03 | 0603 | CC1608M |
| 05 | 0805 | CC2012M |
| 10 | 1206 | CC3216M |

---

## 3. Outline drawing (page 2, Figure 2-1)

Figure 2-1 shows the capacitor in cross-section. Four dimensions are called out:

- **L** — overall body length, end face to end face.
- **W** — overall body width.
- **H** — overall body height, measured from the seating plane to the top face.
- **BW** — the termination extent measured **along the seating plane**, from the
  end face inward. The BW dimension line lies on the bottom face of the
  cross-section, coincident with the seating plane.
- **BE** — the termination extent measured **on the end face**, from the seating
  plane upward. The BE dimension line is vertical, on the end face of the chip.

Both bands are the same plated finish; the drawing does not annotate either
further.

---

## 4. Dimensions (page 2)

**DIMENSIONS** — all dimensions in millimetres.

| ACME size code | EIA | L | W | H | BW | BE |
|---|---|---|---|---|---|---|
| 02 | 0402 | 1.00 ± 0.10 | 0.50 ± 0.10 | 0.50 ± 0.10 | 0.25 ± 0.15 | 0.30 ± 0.10 |
| 03 | 0603 | 1.60 ± 0.15 | 0.80 ± 0.15 | 0.80 ± 0.15 | 0.35 ± 0.15 | 0.45 ± 0.15 |
| 05 | 0805 | 2.00 ± 0.20 | 1.25 ± 0.10 | 1.25 ± 0.20 | 0.50 ± 0.30 | 0.60 ± 0.20 |
| 10 | 1206 | 3.20 ± 0.20 | 1.60 ± 0.20 | 1.60 ± 0.20 | 0.50 ± 0.25 | 0.65 ± 0.20 |

---

## 5. Dielectric codes (page 3)

| Code | Dielectric | Class | Temperature characteristic |
|---|---|---|---|
| C | C0G (NP0) | I | 0 ± 30 ppm/°C, −55 to +125 °C |
| R | X7R | II | ± 15 %, −55 to +125 °C |
| P | X5R | II | ± 15 %, −55 to +85 °C |

X5R (**P**) is not offered in the 02 case.

---

## 6. Rated voltage codes (page 3)

| Code | Rated voltage (VDC) | Available on |
|---|---|---|
| 4 | 16 | all sizes |
| 5 | 25 | all sizes |
| 6 | 50 | all sizes |
| 7 | 100 | 05, 10 |
| 8 | 250 | 10 |

---

## 7. Capacitance tolerance codes (page 3)

| Code | Tolerance | Applies to |
|---|---|---|
| B | ± 0.10 pF | class I only, capacitance ≤ 10 pF |
| C | ± 0.25 pF | class I only, capacitance ≤ 10 pF |
| J | ± 5 % | class I and class II |
| K | ± 10 % | class II only |
| M | ± 20 % | class II only |

---

## 8. Capacitance code and significand grid (page 3)

Capacitance is encoded as **three characters in picofarads**: two significant
digits followed by the decade multiplier (the count of zeros). Values below
10 pF use the letter **R** as a decimal point in place of the multiplier.

Round the capacitance to **two significant figures** before splitting it into
significand and multiplier, so a value that rounds up across a decade carries
into the multiplier.

**Significand grid.** Class II parts are supplied on the **E6** significand grid
(10, 15, 22, 33, 47, 68); class I parts on **E12** (10, 12, 15, 18, 22, 27, 33,
39, 47, 56, 68, 82).

Worked examples:

| Capacitance | 2 s.f. | Code |
|---|---|---|
| 1.0 pF | 1.0 pF | `1R0` |
| 4.7 pF | 4.7 pF | `4R7` |
| 100 pF | 100 pF | `101` |
| 1.0 nF | 1000 pF | `102` |
| 10 nF | 10000 pF | `103` |
| 100 nF | 100000 pF | `104` |
| **99.5 nF** | **100 nF** | **`104`** — carries; not `995` |
| 1.0 µF | 1000000 pF | `105` |

---

## 9. Ordering information (page 4)

Part numbers are assembled as:

```
ACC <size><dielectric><capacitance><tolerance><voltage><thickness>
    ^^^^^^ ^^^^^^^^^^ ^^^^^^^^^^^^ ^^^^^^^^^ ^^^^^^^^ ^^^^^^^^^^^
    §2     §5         §8           §7        §6       below
```

**Thickness code** — the maximum body height ACME will ship for the ordered
combination:

| Code | Max height (mm) | Available on |
|---|---|---|
| A | 0.50 | 02 |
| B | 0.80 | 03 |
| C | 1.25 | 05 |
| D | 1.60 | 10 |

**Complete ordering examples:**

| Part number | Reads as |
|---|---|
| `ACC03R104K6B` | 0603, X7R, 100 nF, ± 10 %, 50 V, 0.80 mm max |
| `ACC02C101J5A` | 0402, C0G, 100 pF, ± 5 %, 25 V, 0.50 mm max |
| `ACC05R105M6C` | 0805, X7R, 1.0 µF, ± 20 %, 50 V, 1.25 mm max |
| `ACC10P475K4D` | 1206, X5R, 4.7 µF, ± 10 %, 16 V, 1.60 mm max |
| `ACC03C4R7C6B` | 0603, C0G, 4.7 pF, ± 0.25 pF, 50 V, 0.80 mm max |

Reference designator prefix: **C**.
