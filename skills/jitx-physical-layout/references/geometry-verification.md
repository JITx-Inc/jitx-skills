# Geometry verification evidence

Capture, query/visit, and net lookup: installed `jitx.run.runtime.RuntimeDesign`,
`jitx.query`, and `jitx.inspect`; executable loop:
[check_realization.py](../scripts/check_realization.py). Export-presence checks
belong to the [skill verification gate](../SKILL.md#verification).

## Coordinate frames

Read `jitx/landpattern.py::_pad_to_copper` for composed pad frames;
`jitx/circuit.py::_route_to_copper` and `jitx/controlpoint.py::_control_point_to_copper`
for route/control-point frames;
the realization checker for hole-preserving conversion, captured pours, local
keepouts, and board geometry.

Unowned measurement: a composite's second landpattern at `(5, 3)` held a pad
authored at `(2, 0)`. Its local transform read `(2.0, 0.0)`, composed position
`(7.0, 3.0)`, and realized copper bbox centre `(7.0027, 3.0)`. The `0.0027`
discrepancy was the circle-to-polygon bbox artifact. Flat-landpattern
coordinates agreed either way.

## Construction and placement

Deferred-construction observation: a module-level landpattern generator is an
`Instantiable`, its `thermal_pad` an `InstantiableAttribute`, and `visit` finds
no pads. The thermal-via helper needs an instantiated `Landpattern` in the
active design/substrate context; reconfiguring the thermal pad rebuilds its
objects. Follow the [skill's construction sequencing](../SKILL.md#verification).

Floating-circuit observation: an unplaced floating circuit was parked off-board,
with no route traces, missing stitch vias, and board-wide pours captured as
`Empty()` despite `status: ok`. An explicitly anchored control capture
distinguishes placement failure from geometry failure. Capture has no "unplaced"
predicate and cannot prove placement provenance; follow [placement
sequencing](../SKILL.md#workflow-and-owners).

## Other observations without a code owner

These are unverified observations.

| Observation | Measurement or failure |
|---|---|
| Capture iteration | Approximately 10–15 s per design round-trip; one or two 15-second probe runs. |
| Missing routes | A real board had 48 missing legs caught by realization checks. |
| Capture overwrites authored pour | Authored `rectangle(20, 20)` became a `MultiPolygon` of area `399.9976` after capture. |
| Route sketch | Intermediate `Route(..., sketch=[...])` points were dropped; the route realized straight between endpoints. Use `RoutePoint`s and assert bounds. |
| Stored placement encoding | Changing py-jitx/runtime pairing made `design-info/` unreadable: `No field with key '$_...' under O.../C...`. Restoring compatible state from git and restarting the project runtime was the remedy. |
