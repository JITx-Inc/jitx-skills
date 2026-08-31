# Verifying SI Constraint Binding

This reference owns the post-build binding check for topology and SI
constraints. `jitx-layout-constraints` checks rule effects on copper, and
`jitx-physical-layout` owns physical-layout verification. Neither
can prove that a `Topology(begin, end)` reached an emitted `>>` chain.

## What a clean build does not prove

`status: ok` does not prove that a constraint bound to a topology. A constraint
whose endpoint is absent from the `>>` chain can translate without a diagnostic.
A missing `BridgingPinModel` can also leave the chains on the two sides of a
series part disconnected while the build remains clean.

The Verification step refuses to write the task completion block until the
emitted span check exits 0. If the artifact is unavailable or its schema is not
supported, the completion block states only that the constraint translated and
records binding as an open item. It does not say that the constraint applies.

## The emitted evidence

Each build writes `cache/load-cache.json`. On the supported `v1` schema, its
module records contain:

- `topologySegments`, the emitted `>>` edges;
- `pinModels`, the edges that join a signal path across modeled parts;
- `structures` and `differentialStructures`, the routing-structure spans;
- `constrainInsertionLosses`, the emitted insertion-loss spans.

The endpoints are numeric local-id paths. `scripts/check_si_spans.py` resolves
those paths against the same file's module, component, bundle, port, and
instance tables. It prefixes nested module paths, joins topology segments and
pin models into one board graph, then walks every emitted constraint from its
begin endpoint to its end endpoint for the supported fields above.

The helper fails when no SI spans were emitted, when either endpoint is absent
from the graph, when no continuous path joins the endpoints, or when the same
connected chain contains a segment outside the declared span. The last check
catches a reachable endpoint that stops short of the intended end. A design
that intentionally constrains only part of a chain can pass `--allow-partial`,
but the Verification completion block must name the excluded span and the
reason before that option is used.

The cache is an internal build artifact rather than a published Python API.
The helper validates the field names and exits 2 on an unsupported schema, so
a format change becomes an open item instead of a false pass.

## Project gate

The helper is copied into the project so its command and result ship with the
design check:

```bash
python scripts/check_si_spans.py path/to/Design/cache/load-cache.json
```

An exit of 0 proves that the build emitted each reported constraint span and
that its endpoints walk a continuous chain of `>>` segments and pin-model
edges. The printed dotted names and hop list are the evidence. The check does
not prove that impedance was met or that a timing, skew, or loss limit was
satisfied. Those claims require the appropriate router, UI issue, or SI export
evidence and stay open when that evidence is unavailable.

When a task has both a module harness and an assembly integration, the
Verification step runs the helper on both build artifacts. It refuses the
completion block until the recorded begin endpoint, end endpoint, and intended
path match in both contexts, or until an intentional difference is named with
its reason. The existence or clean build of the harness is not parity evidence.

## Negative control

The helper's unit suite includes a constraint whose end is a valid port but is
not a member of the topology graph. The fixture is structurally valid and the
check exits 1 with `NO PATH`. A second negative removes the bridging pin-model
edge between two topology segments and also requires `NO PATH`. The suite also
covers a reachable endpoint that leaves one segment outside the constraint
span.

```bash
python skills/jitx-interconnect-constraints/scripts/test_check_si_spans.py
```

For a new JITX cache schema, the schema adapter and these negative controls
must pass before the Verification step accepts a real design's exit 0.
