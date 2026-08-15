# ACME APR Series — Thick Film Chip Resistors

> Fictional manufacturer, prepared as an eval fixture. The body and termination
> dimensions below are the physically standard EIA/IEC chip geometries; the
> part-number grammar, packaging codes, resistance limits and lifecycle flags are
> invented. Any resemblance to a real ordering scheme is coincidental.

**ACME Passive Components** · Document APC-DS-0113 · Rev C · Page 1 of 6

---

## 1. Product overview (page 1)

The APR series is a general-purpose thick-film chip resistor on a 96 % alumina
substrate with nickel-barrier terminations, supplied on tape and reel. Cases
conform to the standard EIA and IEC 60115-8 size codes, so the APR footprint for a
given case is the standard footprint for that case — no ACME-specific land pattern
is published.

Series designator: **APR**. Every case is offered in the same tolerance and
temperature-coefficient grades except where §4 says otherwise.

---

## 2. Case sizes and metric equivalents (page 2)

The ACME size label is the imperial designation, except for the smallest case,
which ACME labels **0075** for historical reasons; its body is 0.30 × 0.15 mm.

| ACME size label | IEC / metric code | Body (mm) | Status |
|---|---|---|---|
| 0075 | RR0315M | 0.30 × 0.15 | Active |
| 0402 | RR1005M | 1.00 × 0.50 | Active |
| 0603 | RR1608M | 1.60 × 0.80 | Active |
| 0805 | RR2012M | 2.00 × 1.25 | Active |
| 1206 | RR3216M | 3.20 × 1.60 | Active |
| 1210 | RR3225M | 3.20 × 2.50 | Active |
| 1218 | RR3246M | 3.20 × 4.60 | **NRFND** — not recommended for new designs; no new orders after 2027-01-01 |
| 2010 | RR5025M | 5.00 × 2.50 | Active |
| 2512 | RR6332M | 6.35 × 3.20 | Active |

---

## 3. Outline drawing (page 3, Figure 3-1)

Figure 3-1 shows the chip in cross-section and plan view. Four dimensions are
called out on the cross-section:

- **L** — overall body length, termination end face to termination end face.
- **W** — overall body width.
- **H** — overall body height, measured from the seating plane to the top face.
- **T1** — the termination extent measured **along the seating plane**, from the
  end face inward. The dimension line for T1 lies on the bottom face of the
  cross-section, coincident with the seating plane.
- **T2** — the termination extent measured **on the end face**, from the seating
  plane upward. The dimension line for T2 is vertical, on the end face of the
  chip.

Both T1 and T2 are nickel-barrier plated over the same silver base electrode. The
drawing does not annotate either dimension further.

---

## 4. Dimensions and mass (page 4)

**DIMENSIONS AND MASS** — all dimensions in millimetres.

| ACME size | L | W | H | T1 | T2 | Mass (mg) |
|---|---|---|---|---|---|---|
| 0075 | 0.30 ± 0.01 | 0.15 ± 0.01 | 0.13 ± 0.01 | 0.11 ± 0.01 | 0.10 ± 0.01 | 0.05 |
| 0402 | 1.00 ± 0.10 | 0.50 ± 0.10 | 0.35 ± 0.05 | 0.25 ± 0.15 | 0.30 ± 0.10 | 0.6 |
| 0603 | 1.60 ± 0.15 | 0.80 ± 0.15 | 0.45 ± 0.10 | 0.35 ± 0.15 | 0.45 ± 0.15 | 2.0 |
| 0805 | 2.00 ± 0.20 | 1.25 ± 0.10 | 0.55 ± 0.10 | 0.50 ± 0.30 | 0.60 ± 0.20 | 4.7 |
| 1206 | 3.20 ± 0.20 | 1.60 ± 0.20 | 0.55 ± 0.10 | 0.50 ± 0.25 | 0.65 ± 0.20 | 9.4 |
| 1210 | 3.20 ± 0.20 | 2.50 ± 0.20 | 0.55 ± 0.10 | 0.50 ± 0.25 | 0.65 ± 0.20 | 15.0 |
| 1218 | 3.20 ± 0.10 | 4.60 ± 0.15 | 0.55 ± 0.10 | 0.45 ± 0.20 | 0.60 ± 0.20 | 27.0 |
| 2010 | 5.00 ± 0.10 | 2.50 ± 0.15 | 0.60 ± 0.10 | 0.55 ± 0.10 | 0.70 ± 0.20 | 31.0 |
| 2512 | 6.35 ± 0.25 | 3.20 ± 0.25 | 0.60 ± 0.10 | 0.60 ± 0.20 | 0.75 ± 0.20 | 52.0 |

**Recommended solder pad dimensions** are per IPC-7351 nominal density for the
corresponding IEC case code; ACME publishes no series-specific land pattern.

---

## 5. Electrical ratings (page 4)

| ACME size | Rated power at 70 °C (W) | Max working voltage (V) | Resistance range (Ω) |
|---|---|---|---|
| 0075 | 0.02 | 15 | 10 – 1.0 M |
| 0402 | 0.063 | 50 | 1.0 – 10 M |
| 0603 | 0.10 | 75 | 1.0 – 10 M |
| 0805 | 0.125 | 150 | 1.0 – 22 M |
| 1206 | 0.25 | 200 | 1.0 – 22 M |
| 1210 | 0.33 | 200 | 1.0 – 22 M |
| 1218 | 0.50 | 200 | 1.0 – 10 M |
| 2010 | 0.75 | 200 | 1.0 – 10 M |
| 2512 | 1.00 | 200 | 1.0 – 10 M |

---

## 6. Tolerance and temperature coefficient (page 5)

**Tolerance codes.** Resistance values follow the E-series grid appropriate to the
grade: ±5 % parts are supplied on **E24**, ±1 % and ±0.5 % parts on **E96**. ACME
does not offer ±2 % in this series, and does not supply APR on E192 at any grade.

| Code | Tolerance | E-series |
|---|---|---|
| D | ± 0.5 % | E96 |
| F | ± 1 % | E96 |
| J | ± 5 % | E24 |

**Temperature-coefficient codes.**

| Code | TCR (ppm/°C) | Available on |
|---|---|---|
| K | ± 100 | all sizes |
| L | ± 200 | all sizes |
| M | ± 50 | 0603, 0805, 1206, 2010, 2512 only |

The ± 50 ppm grade (**M**) is offered only in combination with tolerance code
**D** or **F**. The 0075 case is offered only with tolerance code **J** and TCR
code **L**.

---

## 7. Packaging (page 5)

| Code | Packaging | Available on |
|---|---|---|
| T | 7-inch paper tape and reel | all sizes |
| R | 13-inch paper tape and reel | 0402 and larger |
| E | 7-inch embossed tape and reel | 1210, 1218, 2010, 2512 |

---

## 8. Ordering information (page 6)

Part numbers are assembled as:

```
APR - <size><tolerance><tcr> - <value><packaging>
       ^^^^ ^^^^^^^^^ ^^^^^     ^^^^^ ^^^^^^^^^
       §2   §6        §6        below §7
```

**Value field** — four characters. The first three are the resistance significand
rounded to **three significant figures**; the fourth is the decade multiplier, the
count of zeros that follow. Round the resistance to three significant figures
*before* splitting it into significand and multiplier, so a value that rounds up
across a decade carries into the multiplier.

Worked examples:

| Requested resistance | 3 s.f. | Significand | Multiplier | Value field |
|---|---|---|---|---|
| 100 Ω | 100 Ω | 100 | 0 | `1000` |
| 1.00 kΩ | 1.00 kΩ | 100 | 1 | `1001` |
| 10.0 kΩ | 10.0 kΩ | 100 | 2 | `1002` |
| 49.9 kΩ | 49.9 kΩ | 499 | 2 | `4992` |
| 9.99 kΩ | 9.99 kΩ | 999 | 1 | `9991` |
| **9.995 kΩ** | **10.0 kΩ** | **100** | **2** | **`1002`** — carries; not `9995`, not `9991` |
| 2.21 MΩ | 2.21 MΩ | 221 | 4 | `2214` |

**Complete ordering examples:**

| Part number | Reads as |
|---|---|
| `APR-0603FK-1002T` | 0603 case, ± 1 %, ± 100 ppm/°C, 10.0 kΩ, 7-inch paper tape |
| `APR-2512JL-1000R` | 2512 case, ± 5 %, ± 200 ppm/°C, 100 Ω, 13-inch paper tape |
| `APR-0402FK-4992R` | 0402 case, ± 1 %, ± 100 ppm/°C, 49.9 kΩ, 13-inch paper tape |
| `APR-2010DM-2214E` | 2010 case, ± 0.5 %, ± 50 ppm/°C, 2.21 MΩ, 7-inch embossed tape |
| `APR-0075JL-1004T` | 0075 case, ± 5 %, ± 200 ppm/°C, 1.00 MΩ, 7-inch paper tape |

Reference designator prefix: **R**.
