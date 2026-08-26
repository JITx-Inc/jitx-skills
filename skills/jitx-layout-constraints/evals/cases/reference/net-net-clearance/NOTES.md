# Net-to-net clearance reference notes

This probe is designed to measure realized trace-to-trace clearance on the top
conductor. The main request is 0.25 mm, source: skill example 0.25 mm above the
JLCPCB floor. The below-floor request is 0.05 mm, source: skill test value 0.05
mm intentionally below the floor. The JLCPCB copper-to-copper floor is 0.09
mm, source: `jitxlib/jlcpcb/rules.py:9`.

## Capture status

Runtime unavailable for capture. The requested job scratch root was not
writable in this sandbox (`Operation not permitted`), so the isolated project
was created under the sandbox's writable temporary root. The launcher then
could not bind its project-local WebSocket. Its real log output ended with:

```text
lws_socket_bind: ERROR on binding fd 6 to port 0 (-1 1)
```

No captured copper was observed. The question of whether the 0.09 mm
fabrication floor or the 0.05 mm rule wins is not settled by this run.

## Commands and real output

The executable and scratch roots below are normalized because customer-shipped
files cannot contain machine-specific paths.

```text
$ jitx build layout_constraints_wp5.net_net_clearance.NetNetClearanceDesign
Error: no runtime reachable in this project. Start one with `jitx runtime start --background`, or run with `--dry` to skip the build step.

$ jitx build layout_constraints_wp5.net_net_clearance.BelowFloorClearanceDesign
Error: no runtime reachable in this project. Start one with `jitx runtime start --background`, or run with `--dry` to skip the build step.

$ python3 net-net-clearance/check.py
Exception: Unable to find an active JITX runtime for this project
```

Translation-only diagnostics were run after the full build failed. They are
not substitutes for a build or capture:

```text
$ jitx build --dry layout_constraints_wp5.net_net_clearance.NetNetClearanceDesign
layout_constraints_wp5.net_net_clearance.NetNetClearanceDesign:
  design: layout_constraints_wp5.net_net_clearance.NetNetClearanceDesign
  status: ok

$ jitx build --dry layout_constraints_wp5.net_net_clearance.BelowFloorClearanceDesign
layout_constraints_wp5.net_net_clearance.BelowFloorClearanceDesign:
  design: layout_constraints_wp5.net_net_clearance.BelowFloorClearanceDesign
  status: ok
```

## Pour limit

A captured `Pour` on this JITX line returns its input outline before voiding.
The primary capture check therefore uses trace-to-trace copper and excludes
pours. The legacy ODB++ cross-check was not run because it also requires the
runtime that was unavailable here.
