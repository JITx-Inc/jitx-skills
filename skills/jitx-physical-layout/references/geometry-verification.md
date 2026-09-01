# Inspecting & Verifying Concrete Geometry (JITX 4.3 reverse flow)

> **New in 4.3.** After a design is submitted to the runtime and **captured**,
> python holds the *realized* physical design: every route's copper, control-point
> transitions, computed pours, vias, placements, and net assignments. Checks written
> against this data are how hard geometric code gets debugged — not screenshots, not
> matplotlib stand-ins, not `status: ok`. Write the checks first; iterate the
> geometry until they pass (~10–15 s per design round-trip).

## The loop

```python
import jitx
from jitx import Copper

with jitx.runtime as r:          # connects to this project's runtime
    rd = r.submit(MyDesign)      # instantiate + evaluate (r.submit takes the CLASS)
    rd.capture()                 # pull realized layout back into the python objects
    circ = rd.root.circuit

    # 1) realization: every authored route must have traces
    for route in circ.routes:
        assert route.traces, f"unrealized route: {route}"

    # 2) concrete geometry: bounds of the realized copper
    for tr in circ.se_route.traces:
        for shape in tr.shapes:
            minx, miny, maxx, maxy = shape.to_shapely().g.bounds
            ...

    # 3) net identity, element- or trace-level
    nets = rd.nets()
    assert nets.find(circ.gnd_pour[0]).name == nets.find(circ.c1.gnd).name
    for tr in circ.trunk.traces:                  # which net rides each trunk line
        print(nets.find(tr).name)

    # 4) everything as query results
    for trace, copper in rd.query(Copper):
        ...
```

Notes on the loop:
- **The runtime is per-project**, discovered by walking up from CWD to the nearest
  project (`pyproject.toml` that declares `jitx` as a dependency) with a started
  runtime (`jitx runtime start --background`; state in `<project>/.jitx/`). Run
  probe/check scripts from their own project dir — running them from a parent JITX
  project silently uses (and pollutes the `designs/` of) that project.
- No `jitx build` CLI, no TTY prompts, no design-dir management: this python loop
  IS the iteration workflow for geometry work.
- A function-local `Design` subclass needs `Cls.__qualname__ = Cls.__name__` —
  the runtime rejects design names containing `<locals>`.
- **Everything below requires `capture()` first.** Before it, `route.traces`,
  `controlpoint.traces`, and computed pour shapes are `None`/empty, and the
  route/control-point query transformers silently yield nothing.

## Placement state is a prerequisite

Top-level subsystem circuits need two distinct placement modes. A circuit intended
for interactive placement uses `.at(floating=True)` so multiple subsystems do not
pile up at the parent origin. A headless probe or geometry check gives every
subsystem an explicit position. An interactively placed design may use floating
circuits only after their placements have been stored in `design-info/`.

An unplaced floating circuit is parked off the board. Its routes have no realized
traces, stitch vias disappear, and board-wide pours come back as `Empty()`, all
while the build may report `status: ok`. Those results look the same as real route,
stitching, and pour failures. The geometry check therefore starts with a placement
gate: it requires explicit positions or confirmed stored interactive placements and
stops before interpreting geometry if neither is present. When diagnosing an
existing ambiguous failure, an explicitly anchored control capture distinguishes
placement state from broken geometry: if the copper returns, placement was the
failed prerequisite.

Capture cannot supply an "unplaced" predicate. It reports positions produced by
auto-placement or stored state even for components with no `.at()` in the source.
Placement checks run only after placement and compare realized pad extents for
collisions and board bounds; they cannot prove which positions were authored.

## `query` vs `visit`

`jitx.inspect.visit(root, Type)` walks the structural tree and yields objects that
*already are* the requested type. `jitx.query.query(root, Type)` (or the
`rd.query(Type)` convenience) additionally walks a **transformer graph** that
converts what it finds:

| Source | Target(s) | Notes |
|---|---|---|
| `Pad` | `Copper` | per-layer pad shapes |
| `Via` | `Copper` / `Cutout` / `Soldermask` | pad rings per layer; TH cutout |
| `OverlappableCopper` | `Copper` | |
| `Route` | `Copper` / `Pour` / `Feature` | from `traces` / `derived`, post-capture |
| `ControlPoint` | `Copper` | from `traces`, post-capture |
| `ComputedFenceVia` / `ComputedStitchVia` | `Via` | solver-generated fence/stitch vias |

So: **`visit(design, Copper)` does NOT see route/pad/via copper — use `query`.**
Use `visit` when you want the authored objects themselves (e.g. every `Route` to
assert realization: `for trace, route in visit(rd.root, Route)`).

Both yield `(trace, obj)` where `trace.path` is the ref path and `trace.transform`
the accumulated transform — read "Coordinate frames" below before you use it.

`query` also takes `opaque=` to stop transformers from firing (e.g.
`query(root, Copper, opaque=Via | Pad)` to get non-pad copper only) and
`through=` / `filter=` / `refs=` like `visit`.

## Coordinate frames

**An element's own `transform` is not a position.** `pad.transform`,
`component.transform`, `via.transform` are each local to that element's *immediate
container* — read in isolation they are neither board coordinates nor coordinates in
whatever frame you actually asked for. To get a position, walk to the element and
compose:

```python
from jitx import visit
from jitx.landpattern import Pad

pad_xy: dict[Pad, tuple[float, float]] = {}
for trace, pad in visit(component, Pad):     # or visit(rd.root, Pad) for design-global
    if trace.transform is None or pad.transform is None:
        raise ValueError(f"unresolved frame for pad {trace.path}")
    pad_xy[pad] = (trace.transform * pad.transform).translation
```

**Raise, don't skip, on an unresolved frame.** A `continue` here silently drops pads, and
the consumers of these coordinates are positional — `zip(ports, self.sig_vias)` in an
escape fan will happily pair port *n* with the via for port *n+1*. Key the result by the
`Pad` object, not by an assembled name (see the base skill's anti-string-hacking rules),
and let `PadMapping` carry you from port → pad → coordinate.

`trace.transform` is everything *above* the element and excludes the element's own, so
the composition is always `trace.transform * element.transform`. The frame you land in
is the frame of **the root you passed to `visit`**. This is exactly what the framework
does internally (`jitx/landpattern.py::_pad_to_copper`).

**Pads specifically.** `PadMapping` (`component.mappings`) resolves port → pad and is
the right tool for that half; the *coordinate* is the half that needs composing. A
`Component` declaring more than one landpattern is silently combined into a single
**composite landpattern**, and each `Pad.transform` is then local to its own
sub-landpattern. Verified on a two-landpattern component whose second landpattern sits
at `(5, 3)`: for a pad authored `.at(2, 0)` inside it, `pad.transform` alone reads
`(2.0, 0.0)` while the composed frame is `(7.0, 3.0)` — and the pad's realized copper
lands there too (`rd.query(Copper)` bbox centre `(7.0027, 3.0)`; the 0.0027 is the
circle-to-polygon bbox artifact, not a frame difference). Pads in the *flat*
landpattern read identically either way. So `pad.transform` alone is right for a single flat landpattern and
silently wrong for a composite, which is exactly what makes it dangerous: it passes
every test you write against a simple part. Don't special-case it — always compose.

`trace.transform` may be a `Placement` (a `Transform` carrying `side`), which already
accounts for bottom-side mirroring — don't hand-roll that. Either transform may be
`None` when the frame couldn't be determined; guard before composing.

Two realized-geometry frames that will also bite you:

- **`Route.Trace.shapes` are already DESIGN-GLOBAL** (verified against export
  output) — do not re-apply the query transform to them.
- **`ControlPoint.traces` shapes are LOCAL to the control point** — apply the
  query `trace.transform` (it correctly composes nested-circuit placements).

## Net resolution

`rd.nets()` returns an index; `.find(element)` resolves any design object — a
port, a pour added via `net += Pour(...)` / `net.connected.extend(...)`, or an
individual realized `Route.Trace` — to its connected net (`.name`). Per-trace net
lookup is how you verify a coupled trunk's polarity (which physical line carries
`p`). `rd.layers().normalize(i)` normalizes negative layer indices.

## What checks to write

For any authored layout, the minimum battery (each is 1–3 lines):

1. **Realization** — every `Route` has non-empty `traces` (2 for a coupled trunk);
   every control point involved has `traces`. This is non-negotiable: routes fail
   silently, and a real board shipped 48 missing legs that only this check caught.
2. **Polarity** — per-trace `nets().find(tr).name` on differential trunks.
3. **Position/extent** — shapely bounds of realized shapes vs expected coordinates
   (pad-to-pad span, leg-doesn't-wrap sanity, clearance eyeballs as inequalities).
4. **Net membership** — pours/vias/copper added to nets resolve to the right net.
5. **Presence in export** (when exporting to EDB/HFSS via jitxlib-ansys): reopen the
   `.aedb` read-only and assert the geometry survived (netless copper lands as
   net `<NO-NET>`; primitive bboxes are in meters; count `layout.padstack_instances`
   for vias). The known drop: any via/copper reachable only through a `Net` or
   `PortAttachment` (build warning "not assigned to a circuit … deprecated") is
   SILENTLY ABSENT from the EDB — store instances structurally on the circuit.

Structure them as a plain script (`python -m myproj.checks`) or pytest module in
the design project; print `[PASS]/[FAIL]` per check and exit nonzero on failure.
When exploring an unfamiliar behavior, write a probe design *per hypothesis* and
let the checks discriminate — geometry questions that used to take a screenshot
loop resolve in one or two 15-second runs.

## Shapes → shapely (both directions)

Any jitx `Shape` converts with `shape.to_shapely()` (a `ShapelyGeometry`; the raw
shapely geometry is its `.g`) — bounds, area, distance, intersection checks all
work from there. Authoring in the other direction (shapely → jitx features) is
covered in the main skill page ("Custom shapes with shapely").

Three traps that produce confident wrong numbers: query-returned pad and via
copper is in the source's local frame (compose `trace.transform`, see
"Coordinate frames"; without it every distance reads 0.0000), and
`PolygonSet.to_shapely()` turns a computed pour's cutout rings into solid
polygons, so rebuild pour geometry ring by ring before measuring against it.
`capture()` also overwrites an authored `Pour.shape` in place with reverse-flow
runtime output. An authored `rectangle(20, 20)` was observed as a `MultiPolygon`
of area `399.9976` after capture, so `rd.query(Pour)` is not a preserved authored
outline. On the 4.4 line that mutated result still omits keepout voids, thermal
reliefs, and edge pullback. The check reads the raw `LayoutOutput.computed_shape`
or legacy ODB++ layer features for voiding, and ODB++ for final edge spacing. A
removed pour instead returns `Empty()`;
calling `.to_shapely()` on it raises
`ValueError: Unhandled primitive geometry type: Empty()`, so the realization check
stops on `Empty()` before any conversion.
One more: `Route(..., sketch=[...])` intermediate points are dropped on runtime
4.4.0-rc.9 and the route realizes straight between its endpoints, so a probe
that relies on a sketch to bend a route passes vacuously; author turns with
`RoutePoint`s and assert the realized bounds. And a circuit placed with
`.at(floating=True)` but never placed interactively fails the placement gate above.

## Interop notes

- The export CLI (`jitx design export <plugin> <module.Class>`) runs this same
  submit→capture→query path; plugins (e.g. jitxlib-ansys's `hfss`) consume the
  captured `RuntimeDesign`. When driving an export plugin from python yourself,
  replicate the CLI scaffold: `instantiation.require()` → `instantiation.frame()`
  (disposable) → `DesignContext(rd.root)` → `SubstrateContext(rd.root.substrate)` —
  entering a plugin context without an active frame raises "Structure not active"
  (see `jitx/_cli/design/export.py::_run_export` for the canonical sequence).
- Legacy exporters (`legacy-odb++` etc.) remain available and are a useful
  *runtime-side* cross-check of realized copper (ODB `features` files are plain
  text, `UNITS=MM`).
- `design-info/` state is **encoding-versioned**: state written by one
  py-jitx/runtime pairing can be unreadable by another, failing builds/submits with
  a cryptic `No field with key '$_...' under O.../C...`. Remedy: restore
  `design-info/` from git and restart the project runtime.
