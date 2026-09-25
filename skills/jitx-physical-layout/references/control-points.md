# Control-point routing owners

- Installed `jitx.circuit.Route` owns its signature, endpoint arguments, sketch,
  and captured trace fields; `jitx.controlpoint` owns `RoutePoint`,
  `PairInsertion`, `PairPoint`, and their coupled-connection rules.
- `jitxexamples.patterns.control_points` owns pad-to-point escapes, segment
  tags versus differential net tags, attachment binding, derived chirality,
  coupled trunks, and the crossover. Its receipt names the measured versions;
  it does not verify deskew. For deskew geometry, read
  `jitxexamples.demos.si_bga_optimization`'s `deskew.py` against installed APIs.
- [Physical-layout verification](../SKILL.md#verification) owns capture,
  route realization, two-trace trunks, polarity/net membership, and bounds.

Hoist routes to the common ancestor of their endpoints; store `PortAttachment`
objects structurally, not foreign component ports that would acquire a second parent.

## Observations without a worked owner

These retain historical failures, not fresh verification. The hub pattern
does not exercise either case.

- `PairPoint` to `PairInsertion` observation, JITX 4.3 reference with exact
  test version unrecorded: attaching both control points to the same port
  pair left the trunk unrealized under every tried order/rotation combination.
  Attaching one endpoint to the far component's pair on the unified net was
  required. Recheck this case on the target runtime.
- Child-circuit fan observation, runtime 4.3.0-develop.25 with py-jitx develop
  (exact package version unrecorded): one leg per pair dropped despite local,
  bound-correct legs and realized insertion copper; identical geometry realized
  at root level. Author fans where capture proves they realize and assert every
  route's traces.
