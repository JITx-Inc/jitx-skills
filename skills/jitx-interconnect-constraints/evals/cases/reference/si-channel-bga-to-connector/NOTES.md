# SI channel, BGA to connector, without `>>`: jitx 4.6.0rc10, runtime 4.6.0-rc.16

## Result

On jitx 4.6 the reference's timing, loss, intra-pair skew and bundle skew
constraints all measure and pass on a channel built from plain nets: BGA ball,
escape via, bottom-layer trace, AC cap, connector, two pairs. Removing the
terminating models lowers every path by exactly 50 ps and 0.25 dB; zeroing the
via model lowers it by exactly 8 ps and 0.05 dB. Each mutation (a cap without
its bridging model, no routes, a via without a model) is rejected by the
reference checks and named in the issue report.

## Environment

- Python packages: `jitx 4.6.0rc10`, `jitxcore 4.6.0rc3`, `jitxlib-standard 4.6.0rc3`, pyright 1.1.414.
- Runtime: `~/.jitx/current` -> `4.6.0-rc.16`.
- Substrate: `jitx.sample.SampleSubstrate`. Two copper layers, so the bottom
  layer stands in for the inner routing layer the prompt describes. `DRS_100`
  covers layers 0 and 1; `RS_50` and `DRS_100` use velocity 191335235228 and
  insertion loss 0.0178 per unit length.
- Run 2026-10-29.

## How the check runs

`check_si_channel.py <variant>` stages a project in the system temp directory
(`pyproject.toml` declaring `jitx>=4.6.0rc10,<5`, and a package
`si_channel_check/` holding `__init__.py` and a copy of
`si_channel_design.py`), then, from that directory with `PYTHONPATH` set to it:

```text
jitx runtime start --background --project <dir>
jitx --format json design issues si_channel_check.si_channel_design.<Design> --satisfied --wait 60 --project <dir>
jitx runtime stop --project <dir>
```

The stop runs in a `finally`, and the temp directory is removed after it.
`jitx` is the executable beside the interpreter running the script.

The check reads the JSON form of the report rather than the text. Each issue
carries its class (`UnmetTime`, `UnmetLoss`, `UnmetTimeDiff`,
`MissingPinModel`, `UnconnectedTopology`, `MissingStructureModel`, ...), its
text, its pins, and, for a measurement, `detail.signal_integrity` with
`measured_range`, `acceptable_range` and `satisfied`. Path ends are parsed from
the text with the pattern `from ([\w.\[\]]+) to ([\w.\[\]]+)`. Forbidden texts
are matched case-insensitively: `unconnected topology`, `no path`,
`missing routing structure`, `not routed yet`, `placeholder model`,
`unassigned pin`, `missing connection`, `unable to find path`. The last two
were seen once, in a throwaway copy with the bottom-side caps at `rotate=0`:
pad `a` then lands on the connector side, the router reports
`Unable to find path for requested route`, and the constraints report
`Missing Connection on Path: caps[0].b, conn.tx0.p`. That run is why the caps
are placed at `rotate=180`.

How the models are proved to move the numbers: by difference against two probe
designs on the same routes, not by predicting absolute times. Trace length
comes from the realized code routes, which the check does not measure, so an
absolute prediction would need the routed geometry. The differences are exact:
`NoTerminationDesign` drops the BGA and connector terminating models, and
`IdealViaDesign` gives the via a zero-delay, zero-loss model. Tolerances are
0.01 ps and 1e-6 dB.

## Lines the check parsed

Text form (`jitx design issues ... --satisfied --wait 60`) of each design, run
in a hand-staged copy of the same project before the check script existed. The
JSON the check reads carries the same texts.

`SiChannelDesign`:

```text
Signal Constraint:
  - Time: 211.953ps - Target: 200ps ± 200ps from bga.tx0.p to conn.tx0.p
  - Time: 211.953ps - Target: 200ps ± 200ps from bga.tx0.n to conn.tx0.n
  - Time: 211.953ps - Target: 200ps ± 200ps from bga.tx1.p to conn.tx1.p
  - Time: 211.953ps - Target: 200ps ± 200ps from bga.tx1.n to conn.tx1.n
  - Loss: 0.907db ± 0db - Target: 1db ± 1db from bga.tx0.p to conn.tx0.p
  - Loss: 0.907db ± 0db - Target: 1db ± 1db from bga.tx0.n to conn.tx0.n
  - Loss: 0.907db ± 0db - Target: 1db ± 1db from bga.tx1.p to conn.tx1.p
  - Loss: 0.907db ± 0db - Target: 1db ± 1db from bga.tx1.n to conn.tx1.n
  - Skew: 0fs - Target: ± 1ps (longer from bga.tx0.p to conn.tx0.p, shorter from bga.tx0.n to conn.tx0.n)
  - Skew: 0fs - Target: ± 1ps (longer from bga.tx1.p to conn.tx1.p, shorter from bga.tx1.n to conn.tx1.n)
  - Skew: 0fs - Target: ± 5ps (longer from bga.tx0.p to conn.tx0.p, shorter from bga.tx1.p to conn.tx1.p)
  - Skew: 0fs - Target: ± 5ps (longer from bga.tx0.p to conn.tx0.p, shorter from bga.tx1.n to conn.tx1.n)
Routing:
  - Satisfied
```

The bundle constraint gives two Skew lines, one per tx1 leg against the tx0.p
guide. Skew is 0 fs because every leg is the same route shape shifted by the
1.0 mm row pitch. Each measured path's pins run `bga.<leg>`, `caps[i].a`,
`caps[i].b`, `conn.<leg>`, with three route segments.

`NoTerminationDesign`: same twelve lines with `Time: 161.953ps` and
`Loss: 0.657db`. `IdealViaDesign`: same twelve lines with `Time: 203.953ps` and
`Loss: 0.857db`.

`CapNoModelDesign` (cap on `tx0.p` without its bridging model):

```text
Signal Constraint:
  - Time: 211.953ps - Target: 200ps ± 200ps from bga.tx0.n to conn.tx0.n
  - Time: 211.953ps - Target: 200ps ± 200ps from bga.tx1.p to conn.tx1.p
  - Time: 211.953ps - Target: 200ps ± 200ps from bga.tx1.n to conn.tx1.n
  - Loss: 0.907db ± 0db - Target: 1db ± 1db from bga.tx0.n to conn.tx0.n
  - Loss: 0.907db ± 0db - Target: 1db ± 1db from bga.tx1.p to conn.tx1.p
  - Loss: 0.907db ± 0db - Target: 1db ± 1db from bga.tx1.n to conn.tx1.n
  - Skew: 0fs - Target: ± 1ps (longer from bga.tx1.p to conn.tx1.p, shorter from bga.tx1.n to conn.tx1.n)
Topology:
  - No path for signal constraint from bga.tx0.p to conn.tx0.p: the ends are only connected through the part between caps[0].a and caps[0].b, which has no pin model. If the signal is meant to pass through it, give it a pin model between them; otherwise check the wiring.
Routing:
  - Satisfied
```

Every measurement that involves `bga.tx0.p` is gone: its Time and Loss, pair
0's skew, and both bundle skews, since the guide is `tx0.p`.

`NoRoutesDesign`: no measurements. Each constraint's group lists
`Unconnected Topology on Path: <a>, <b>` for each segment either side of the
cap, for example:

```text
  - 2 issues: Unconnected Topology on Path: bga.tx0.p, caps[0].a
      - Unconnected Topology on Path: bga.tx0.p, caps[0].a
      - Unconnected Topology on Path: caps[0].b, conn.tx0.p
```

`NoViaModelDesign` (via without `models`): every path still measures, using a
placeholder, and each group carries a warning:

```text
  - 2 issues: Structure model from [0] to [1] not found in "BareEscapeVia". Using placeholder model for proxy of bga.tx0.p.
      - Structure model from [0] to [1] not found in "BareEscapeVia". Using placeholder model for proxy of bga.tx0.p.
      - Time: 223.953ps - Target: 200ps ± 200ps from bga.tx0.p to conn.tx0.p
```

Time 223.953 ps and Loss 1.007 dB, against 211.953 ps and 0.907 dB with the
8 ps, 0.05 dB model: on this runtime the placeholder measured as 20 ps and
0.15 dB. That is an observation, not a documented default. The measurement
exists but is not the design's number, which is why the reference checks treat
`placeholder model` as unresolved.

## Commands and observed output

From the jitx-skills repository root:

```text
$ python -m pyright skills/jitx-interconnect-constraints/evals/cases/reference/si-channel-bga-to-connector/*.py
0 errors, 0 warnings, 0 informations

$ python3 ~/projects/jitx-knowledge/skills/skillify/scripts/run_cases.py skills/jitx-interconnect-constraints --case si-channel-bga-to-connector --venv <wave-venv>
5 deterministic assertions: 5 pass, 0 fail, 0 could not run, 0 unrunnable
```

`check_si_channel.py main`, model-delta section (each check prints every issue
it saw first):

```text
model deltas:
  ok  terminations UnmetTime bga.tx0.p: 2.11953e-10 - 1.61953e-10 = 5e-11, expected 5e-11
  ok  terminations UnmetLoss bga.tx0.p: 0.9073 - 0.6573 = 0.25, expected 0.25
  ok  via model UnmetTime bga.tx0.p: 2.11953e-10 - 2.03953e-10 = 8e-12, expected 8e-12
  ok  via model UnmetLoss bga.tx0.p: 0.9073 - 0.8573 = 0.05, expected 0.05
  (the same for tx0.n, tx1.p, tx1.n)
PASS variant=main problems=0
```

Each mutation first prints the problems the reference checks found in it (6
for `cap-no-model`, 37 for `no-routes`, 16 for `no-via-model`), then
`PASS variant=<name> problems=0`. A whole `main` run took 7.8 s wall time,
runtime start and stop included.
