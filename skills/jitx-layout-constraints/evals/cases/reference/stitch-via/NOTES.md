# Stitch-via class discovery, JITX 4.4.0rc5

The Python package under test reports `4.4.0rc5.dev2`. The required job scratch
root was read-only in this sandbox, so the isolated project was staged under a
writable transient root instead. Runtime startup was attempted there serially.

Startup command:

```text
JITX_ROOT=<writable-transient-root> .venv/bin/python -m jitx runtime start --background
```

Real status and runtime-log output after the required retry:

```text
Runtime: not running
lws_socket_bind: ERROR on binding fd 6 to port 0 (-1 1)
```

The sandbox denied the runtime's local WebSocket bind. Runtime unavailable.
No dry build was substituted for a build or capture.

## Mixin-reached class

Code shape: `JLC04161H_7628.StdViaPreferred`, inherited by the predefined
substrate through `JLCPCBVias`, is passed directly to `stitch_via`.

```text
.venv/bin/python -m jitx build thermal_stitch_wp4.stitch_via_design.MixinViaDesign
.venv/bin/python -m thermal_stitch_wp4.check_stitch_via mixin
```

Runtime unavailable. Build and capture commands were not run. Via count:
unavailable.

## Direct substrate attribute

Code shape: `DirectAttributeSubstrate.DirectStitchVia` aliases the same
`JLC04161H_7628.StdViaPreferred` class as a direct substrate-subclass attribute
and is passed to `stitch_via`.

```text
.venv/bin/python -m jitx build thermal_stitch_wp4.stitch_via_design.DirectAttributeViaDesign
.venv/bin/python -m thermal_stitch_wp4.check_stitch_via direct
```

Runtime unavailable. Build and capture commands were not run. Via count:
unavailable.

## Module-scope class

Code shape: `ModuleScopeStitchVia` is a module-scope subclass of
`JLC04161H_7628.StdViaPreferred` and is passed to `stitch_via`.

```text
.venv/bin/python -m jitx build thermal_stitch_wp4.stitch_via_design.ModuleScopeViaDesign
.venv/bin/python -m thermal_stitch_wp4.check_stitch_via module
```

Runtime unavailable. Build and capture commands were not run. Via count:
unavailable.
