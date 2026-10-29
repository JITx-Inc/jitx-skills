# USB 2.0 through a channel-swappable ESD part, JITX 4.6

Run on 2026-10-29 with `jitx 4.6.0rc10`, `jitxcore 4.6.0rc3`,
`jitxlib-standard 4.6.0rc3`, `pyright 1.1.414`, runtime `4.6.0-rc.16`
(`~/.jitx/current`), on `jitx.sample.SampleSubstrate`.

## Result

| Variant | Routes (D+, D- channel; host side / connector side) | Report |
|---|---|---|
| `Straight` | (1, 2) / (1, 2) | Time 112.879 ps on each leg, skew 0 s against ± 3.75 ps, routing satisfied |
| `SwappedInverted` | (4, 3) / (4, 3) | Time 115.823 ps and 137.724 ps, skew 21.9 ps against ± 3.75 ps, routing satisfied |
| `Illegal` | (1, 3) / (1, 3) | Two code routes dropped; D- measures alone (112.879 ps); no path for D+; no skew |
| `SidesDisagree` | (1, 2) / (3, 4) | Two code routes dropped; no path for either leg; nothing measured |
| `Unrouted` | none | No path for either leg; nothing measured |

- Pin assignment resolves from code routes that end on the ESD part's physical
  pins, on both channel pairs and either way round. The routes of `Straight`
  and `SwappedInverted` land on different channels and neither drops a route,
  so each resolved to the mapping its routes name.
- Once resolved, the constraint on `Topology(host.usb, conn.usb)` measures end
  to end across the ESD channel's `BridgingPinModel`, with plain `+` nets and no
  `>>`.
- A routing that matches no offered mapping is rejected: `Code route dropped: it
  conflicts with other connections`. In `Illegal` the solver kept the D- routes
  (channel 3, part of the offered mapping D+ on 4, D- on 3) and dropped the D+
  routes. In `SidesDisagree` the host side and the connector side each fit an
  offered mapping but no single mapping holds both, so the pass-through coupling
  is enforced.
- The check proves binding, not compliance. The 21.9 ps skew in
  `SwappedInverted` comes from the crossed D+/D- code routes on one layer of the
  sample substrate; it violates the limit and is still a measured line.

## Differs from the spike and the brief

The spike (`raw/si-constraints-without-topology-spike-2026-10-29.md` in
jitx-knowledge) reports `Unassigned Pin on Path` for an unrouted or illegal
pin-assigned pair. There the `Topology` ended on the required port itself. Here
the ends are fixed physical pins (`host.usb`, `conn.usb`) and the assigned ESD
pins sit between them, and the runtime reports the unresolved span as
`No path for signal constraint from host.usb.p to conn.usb.p` instead, with no
`Unassigned Pin` line. The check asserts what this runtime prints for this
topology. Skill text that tells a reader to look for `Unassigned Pin` should
also name `No path for signal constraint` for a path through assigned pins.

## Design decisions

- The provider offers a custom bundle, `ProtectedPair` (a `host` `DiffPair` and
  a `conn` `DiffPair`), so one mapping fixes both sides of a channel. A plain
  `DiffPair` provide cannot say "the connector side uses the same channel as
  the host side". The `jitx.net.provide` docstrings and `_check_options` accept
  any leaf sub-port of the bundle as a mapping key, so no fallback was needed.
- What swaps is which ESD channel carries D+ and which carries D-. Host D+
  always reaches connector D+: USB 2.0 D+/D- polarity is fixed end to end
  (`references/protocol-pin-flexibility.md`, USB 2.0 row), and the part's
  channels are identical, so only the channel choice is free.
- Values: the 3 ps and 0.05 dB per channel are fixture values stated in the
  case prompt. The skew limit is `jitxlib.protocols.usb.USB.v2.skew`,
  `Toleranced(0, 3.75e-12)`, from the installed jitxlib-standard; it was not
  checked against the USB 2.0 specification. The interconnect skill's
  `references/protocol-standards.md` has no USB row to cite. The 1 ns delay
  budget is a fixture value. The sample substrate has only a 100 ohm
  differential structure (`DRS_100`); USB 2.0 asks for 90 ohm.
- `SidesDisagree` is a fifth variant beyond the four in the lane brief. It is
  the only variant that tests the pass-through coupling directly.

## How it was run

From the jitx-skills repository root, with the wave venv's interpreter:

```text
$ python3 -m pyright --pythonpath "$(command -v python3)" skills/jitx-pin-assignment/evals/cases/reference/usb-through-esd-swap/*.py
0 errors, 0 warnings, 0 informations

$ python3 skills/jitx-pin-assignment/evals/cases/reference/usb-through-esd-swap/check_usb_esd_swap.py
```

The check stages a project under the system temp directory (`pyproject.toml`
plus a `usb_esd_ref` package holding a copy of `usb_esd_swap_design.py`), runs
`jitx runtime start --background --project <tmp>`, then for each variant
`jitx design issues usb_esd_ref.usb_esd_swap_design.<Variant> --satisfied --wait 60 --project <tmp>`
with `PYTHONPATH=<tmp>`, and `jitx runtime stop --project <tmp>` in a `finally`.
All five variants took about 10 seconds in total. Output, verbatim:

```text
--- usb_esd_ref.usb_esd_swap_design.Straight (exit 0)
Signal Constraint:
  - Time: 112.879ps - Target: 500ps ± 500ps from host.usb.p to conn.usb.p
  - Time: 112.879ps - Target: 500ps ± 500ps from host.usb.n to conn.usb.n
  - Skew: 0s - Target: ± 3.75ps (longer from host.usb.p to conn.usb.p, shorter from host.usb.n to conn.usb.n)
Routing:
  - Satisfied
PASS variant=straight: time host.usb.p -> conn.usb.p measured; time host.usb.n -> conn.usb.n measured; intra-pair skew measured; no missing path; no unassigned pin; no dropped code route
--- usb_esd_ref.usb_esd_swap_design.SwappedInverted (exit 0)
Signal Constraint:
  - Time: 115.823ps - Target: 500ps ± 500ps from host.usb.p to conn.usb.p
  - Time: 137.724ps - Target: 500ps ± 500ps from host.usb.n to conn.usb.n
  - Skew: 21.9ps - Target: ± 3.75ps (longer from host.usb.n to conn.usb.n, shorter from host.usb.p to conn.usb.p)
Routing:
  - Satisfied
PASS variant=swapped_inverted: time host.usb.p -> conn.usb.p measured; time host.usb.n -> conn.usb.n measured; intra-pair skew measured; no missing path; no unassigned pin; no dropped code route
--- usb_esd_ref.usb_esd_swap_design.Illegal (exit 0)
Signal Constraint:
  - Time: 112.879ps - Target: 500ps ± 500ps from host.usb.n to conn.usb.n
Topology:
  - No path for signal constraint from host.usb.p to conn.usb.p
Routing:
  - 2 issues: Code route dropped: it conflicts with other connections
      - Code route dropped: it conflicts with other connections
      - Code route dropped: it conflicts with other connections
PASS variant=illegal: code route dropped; at least one leg has no path; no skew measured
--- usb_esd_ref.usb_esd_swap_design.SidesDisagree (exit 0)
Topology:
  - No path for signal constraint from host.usb.p to conn.usb.p
  - No path for signal constraint from host.usb.n to conn.usb.n
Routing:
  - 2 issues: Code route dropped: it conflicts with other connections
      - Code route dropped: it conflicts with other connections
      - Code route dropped: it conflicts with other connections
PASS variant=sides_disagree: code route dropped; no path host.usb.p -> conn.usb.p; no path host.usb.n -> conn.usb.n; no time measured; no skew measured
--- usb_esd_ref.usb_esd_swap_design.Unrouted (exit 0)
Topology:
  - No path for signal constraint from host.usb.p to conn.usb.p
  - No path for signal constraint from host.usb.n to conn.usb.n
Routing:
  - Satisfied
PASS variant=unrouted: no path host.usb.p -> conn.usb.p; no path host.usb.n -> conn.usb.n; no time measured; no skew measured; no dropped code route
```

The same numbers came back on an earlier run the same day. `jitx design issues`
exits 0 whatever it reports, so the check reads the report text and exits 1 on
any miss.
