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

Both yield `(trace, obj)` where `trace.path` is the ref path and
`trace.transform` the accumulated transform. Two frame rules that will bite you:

- **`Route.Trace.shapes` are already DESIGN-GLOBAL** (verified against export
  output) — do not re-apply the query transform to them.
- **`ControlPoint.traces` shapes are LOCAL to the control point** — apply the
  query `trace.transform` (it correctly composes nested-circuit placements).
- For `visit` generally, `trace.transform` excludes the found element's own
  transform (`Via`, `Component`): compose `trace.transform * element.transform`.

`query` also takes `opaque=` to stop transformers from firing (e.g.
`query(root, Copper, opaque=Via | Pad)` to get non-pad copper only) and
`through=` / `filter=` / `refs=` like `visit`.

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
   net `<NO-NET>`; primitive bboxes are in meters).

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
