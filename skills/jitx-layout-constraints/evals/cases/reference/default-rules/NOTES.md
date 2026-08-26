# Default-rule scope reference notes

This probe stores the four board defaults on the `Design`. Its tagged width
rule is stored only on one child `Circuit`, while the named tagged net spans
that child and a sibling. The child rule asks for 0.30 mm, source: skill test
value 0.30 mm. The competing board default is 0.12 mm, source: skill default
0.12 mm.

## Capture status

Runtime unavailable for capture. The requested job scratch root was not
writable in this sandbox (`Operation not permitted`), so the isolated project
was created under the sandbox's writable temporary root. The launcher then
could not bind its project-local WebSocket. Its real log output ended with:

```text
lws_socket_bind: ERROR on binding fd 6 to port 0 (-1 1)
```

No captured copper was observed. Whether a rule declared on a child `Circuit`
is board-wide or child-local is not settled by this run.

## Commands and real output

The executable and scratch roots below are normalized because customer-shipped
files cannot contain machine-specific paths.

```text
$ jitx build layout_constraints_wp5.default_rules.DefaultRulesDesign
Error: no runtime reachable in this project. Start one with `jitx runtime start --background`, or run with `--dry` to skip the build step.

$ python3 default-rules/check.py
Exception: Unable to find an active JITX runtime for this project
```

The translation-only diagnostic was run after the full build failed. It is not
a substitute for a build or capture:

```text
$ jitx build --dry layout_constraints_wp5.default_rules.DefaultRulesDesign
layout_constraints_wp5.default_rules.DefaultRulesDesign:
  design: layout_constraints_wp5.default_rules.DefaultRulesDesign
  status: ok
```
