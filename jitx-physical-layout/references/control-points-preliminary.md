# Control Points & Code-Based Routes (PRELIMINARY)

> ⚠️ **Preliminary, unstable API.** The control-point module is `jitx.controlpoint`
> (singular — verified in jitx 4.2.0a4 and 4.3.0a1; `jitx.control_points` does NOT
> exist there). It is marked `# PRELIMINARY`, and its accessor surface has **changed
> between JITX versions** (4.1.0a7's docstring mentions `.a` / `.b` / `.pair`;
> 4.2.0a4 / 4.3.0a1 use `.coupled` / `.uncoupled.{n,p}` (`InsertionControl`), `.pair`
> (`PairControl`), `.port` (`SingleControl`)). Before using any of this:
>
> 1. Read the installed source — `jitx/controlpoint.py` and `jitx.circuit.Route` —
>    to confirm the actual module, constructor, and accessor names for *your* version:
>    ```bash
>    sed -n '1,120p' .venv/lib/python*/site-packages/jitx/controlpoint.py
>    grep -n "class Route" .venv/lib/python*/site-packages/jitx/circuit.py
>    ```
> 2. Run `pyright` (it will catch a wrong accessor as an attribute error).
> 3. **Build-test** — preliminary APIs can pass type-check and still fail at build.
>
> Do not hard-code an accessor name from memory or from this page.

## When to use

Use code-based routes and control points when you need to author the **physical
route path** from code rather than leaving it to the autorouter or the interactive
UI — escape lanes out of a dense package, differential-pair deskew, or forcing a pair
to a specific insertion geometry. For ordinary connectivity, wire nets with `+`
(`jitx-circuit-builder`); for timing/skew/impedance *constraints*, use
`jitx-interconnect-constraints`.

## `Route` — code-based route between two endpoints

`Route` lives in `jitx.circuit` and is the most stable piece here:

```python
from jitx.circuit import Route

# Route(source, destination, layer, sketch=None)
#   source / destination : Port | Pad   (not directional)
#   layer                : int
#   sketch               : optional list[Point] hint for the routing engine
r = Route(self.driver.OUT_p, self.rx.IN_p, layer=0)
self.routes = [r]                      # store on self so the structural walk sees it
```

`Route` is one of the object types `Tags(...).assign(...)` accepts, so the
"route two pads, then apply a fanout/escape tag" workflow is:

```python
from jitx.constraints import Tags
Tags(PinFanoutTag()).assign(r)         # the rule for PinFanoutTag is defined elsewhere
```

## Control points — `SingleControl` / `InsertionControl` / `PairControl`

All subclass `ControlPoint(layer=...)` and are placed with `.at(point, rotate=)`:

- **`SingleControl(layer=..., shape=None)`** — the single-ended control point. Its
  `.port` is the routable endpoint (`Route(some_port, sc.port, layer)`).
- **`InsertionControl(layer=...)`** — a differential-pair *insertion* point. One side
  is a coupled pair, the other side is the two single-ended legs. By convention the
  pair's `p`/`n` are the "left"/"right" of the pair looking toward the pair side;
  chirality matters geometrically (the legs must not cross in-plane).
- **`PairControl(layer=...)`** — connects two segments of a differential pair *while
  still paired*, so each segment can be configured independently.

Attach ports to a control point with `PortAttachment` (a control point is a valid
attachment target alongside `Copper` and `Via`), passing the pair of ports as a list:

```python
from jitx.net import PortAttachment
pair_control = PairControl(layer=deskew_layer).at(pair_point, rotate=90)
self.attachments = [PortAttachment([tx.n, tx.p], pair_control)]
```

### Two connection styles

The 4.1.0a7 docstring connects control points with the **`>>` topology operator**:

```python
# Accessor names per the 4.1.0a7 docstring — VERIFY against your installed source.
insertion1 = InsertionControl(layer=0).at(-2, 0)
insertion2 = InsertionControl(layer=0).at(2, 0)
self.nets = [
    c1.p1 >> insertion1.a,
    c1.p2 >> insertion1.b,
    insertion1.pair >> insertion2.pair,
    insertion2.a >> c2.p1,
    insertion2.b >> c2.p2,
]
```

A later example connects them with explicit **`Route`** objects and uses
**different accessor names** (`.coupled`, `.uncoupled.n/.p`, `.pair`). Same idea, two
vocabularies — which is exactly why you must read the installed source.

## Worked example — BGA escape lane deskew

Per TX lane: drop signal vias at the BGA pads, place a `PairControl` at the deskew
exit and an `InsertionControl` further out, then route the coupled pair into the
insertion point and the two uncoupled legs out to the test-point pair. Attachments and
routes accumulate in plain **lists** (not string-keyed dicts).

```python
# The control-point module is jitx.controlpoint (verified in 4.2.0a4 / 4.3.0a1);
# some builds also re-export from top-level `jitx`. Read your installed source; let
# pyright confirm.
from jitx.controlpoint import SingleControl, InsertionControl, PairControl
from jitx.circuit import Route
from jitx.net import PortAttachment

self.attachments = []
self.routes = []
for index, lane in enumerate(self.escape_lanes):     # escape_lanes is a list
    via_cls = substrate.signal_via[lane.spec.signal_layer]    # via from the substrate
    self.attachments.append(PortAttachment(lane.tx_pair.p, via_cls().at(*lane.p_pad)))
    self.attachments.append(PortAttachment(lane.tx_pair.n, via_cls().at(*lane.n_pad)))

    pair_point = (
        0.5 * (lane.deskew.left_exit[0] + lane.deskew.right_exit[0]),
        0.5 * (lane.deskew.left_exit[1] + lane.deskew.right_exit[1]),
    )
    insertion_point = (pair_point[0], -15)
    pair_control = PairControl(layer=lane.spec.deskew_layer).at(pair_point, rotate=90)
    insertion_control = InsertionControl(layer=lane.spec.deskew_layer).at(insertion_point, rotate=90)

    self.attachments.extend([
        PortAttachment([lane.tx_pair.n, lane.tx_pair.p], pair_control),
        PortAttachment([self.tx_tps[index].pair.n, self.tx_tps[index].pair.p], insertion_control),
    ])
    # Accessor names below (.pair / .coupled / .uncoupled.{n,p}) are VERSION-SPECIFIC.
    self.routes.extend([
        Route(pair_control.pair, insertion_control.coupled, lane.spec.deskew_layer),
        Route(insertion_control.uncoupled.n, self.tx_tps[index].pair.n, lane.spec.deskew_layer),
        Route(insertion_control.uncoupled.p, self.tx_tps[index].pair.p, lane.spec.deskew_layer),
    ])
```

Note the discipline that survives even in preliminary code: vias come from the
substrate (`substrate.signal_via[...]`), lanes are iterated as a list with `enumerate`,
and results are collected into `self.attachments` / `self.routes` lists — no
`getattr(self, f"lane_{i}")`, no string-keyed parallel model.
