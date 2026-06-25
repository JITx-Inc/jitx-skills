# Control Points & Code-Based Routes

> **Stable as of JITX 4.2.0.** `Route` lives in `jitx.circuit`; the control-point
> classes live in `jitx.controlpoint` (`RoutePoint`, `PairInsertion`, `PairPoint` —
> also re-exported from top-level `jitx`). The classes were **renamed in 4.2.0**:
> pre-release alphas called them `SingleControl` / `InsertionControl` /
> `PairControl` — if those names appear in existing code, they are the old names
> for the same three classes and will no longer import. On a runtime other than
> 4.2.x, confirm the surface against the installed source:
>
> Read the first ~130 lines of the installed source with your **Read** tool — `.venv/lib/python*/site-packages/jitx/controlpoint.py` (Windows: `.venv\Lib\site-packages\jitx\controlpoint.py`); it's OS-agnostic. Shell fallback: bash `sed -n '1,130p' .venv/lib/python*/site-packages/jitx/controlpoint.py` (macOS/Linux); on Windows use the Read tool, or `Get-Content .venv\Lib\site-packages\jitx\controlpoint.py -TotalCount 130`.

## When to use

Use code-based routes and control points when you need to author the **physical
route path** from code rather than leaving it to the autorouter or the interactive
UI — escape lanes out of a dense package, differential-pair deskew, or forcing a pair
to a specific insertion geometry. For ordinary connectivity, wire nets with `+`
(`jitx-circuit-builder`); for timing/skew/impedance *constraints*, use
`jitx-interconnect-constraints`.

## `Route` — code-based route between two endpoints

```python
from jitx.circuit import Route

# Route(source, destination, layer, sketch=None)
#   source / destination : Port | Pad | Via   (not directional)
#   layer                : int
#   sketch               : optional list of (x, y) points hinting the routing engine
r = Route(self.driver.OUT_p, self.rx.IN_p, layer=0)
self.routes = [r]                      # store on self so the structural walk sees it
```

- **`Via` endpoints** — a placed via instance is a valid route end, so you can route
  from a pad into a code-placed via (see the BGA example below for placing vias with
  `PortAttachment`).
- **No per-route width/clearance overrides.** `Route` carries no configuration —
  to control width, clearance, or structure of a code route, tag it and write a
  `design_constraint(...)` rule (rule mechanics in `jitx-substrate-modeler`):

  ```python
  from jitx.constraints import Tags
  Tags(PinFanoutTag()).assign(r)       # the rule for PinFanoutTag is defined elsewhere
  ```

- **`require`-provided ports cannot be route ends.** A port obtained through a
  `require(...)` pin-assignment raises
  `NotImplementedError: Using require ports as route ends ... is not implemented`
  at build time — route the component-side port or the pad instead.

## Control points — `RoutePoint` / `PairInsertion` / `PairPoint`

All three subclass `ControlPoint` (don't use the base directly), take a keyword-only
`layer=`, and are placed with `.at(point, rotate=)`:

- **`RoutePoint(layer=..., shape=None, bundle=Port)`** — the single-ended control
  point; its `.port` is the routable endpoint (`Route(some_port, rp.port, layer)`).
  `shape` optionally gives the control point a geometric shape; `bundle=` types
  `.port` with a `Port` subclass of your choice.
- **`PairInsertion(layer=..., bundle=DiffPair)`** — a differential-pair *insertion*
  point: transitions two individual, uncoupled traces into a coupled pair. Its
  `.coupled` and `.uncoupled` are each a `DiffPair`. It cannot currently be placed
  in a `Net`/`TopologyNet` directly — connect it with `PortAttachment` and `Route`.
- **`PairPoint(layer=..., bundle=DiffPair)`** — connects two segments of a
  differential pair *while still paired*, so each segment can be configured
  independently. Its `.pair` is the routable `DiffPair`.

Attach ports to a control point with `PortAttachment` (a control point is a valid
attachment target alongside `Copper` and `Via`), passing a pair of ports as a list:

```python
from jitx.net import PortAttachment
pair_point = PairPoint(layer=deskew_layer).at(xy, rotate=90)
self.attachments = [PortAttachment([tx.n, tx.p], pair_point)]
```

Control-point and signal-escape-via bindings like these are exactly the
**signal-topology scope `PortAttachment` is reserved for** — ground/power
stitching vias join their `Net` directly instead (`self.GND += via`); see
`jitx-physical-layout` "Explicit placement & via attachment".

### Chirality — port order in `PortAttachment`

For `PairInsertion`, the **order** of the two ports in `PortAttachment` is
geometric, not just logical: the first port connects to the **left** side and the
second to the **right**, looking from the *uncoupled* side toward the insertion
point. On the uncoupled side, `uncoupled.n` is the left leg and `uncoupled.p` the
right leg — when making code routes you may need to connect `n` and `p`
"crosswise" to make the geometry work, because the two legs are routed in-plane
and cannot cross. The `coupled` side always routes as a pair; never access
`coupled.n` / `coupled.p` individually.

Flip a control point's chirality by **reversing the port order**:

```python
self.insertion1 = PairInsertion(layer=0).at(-2, 0)
self.insertion2 = PairInsertion(layer=0).at(2, 0, rotate=180)
self.nets = [
    Net([self.c1.p1, self.c2.p1]),
    Net([self.c1.p2, self.c2.p2]),
]
self.attachments = [
    PortAttachment([self.c1.p1, self.c1.p2], self.insertion1),
    PortAttachment([self.c2.p2, self.c2.p1], self.insertion2),  # flipped order — opposite chirality
]
self.routes = [
    Route(self.insertion1.coupled, self.insertion2.coupled, 0),  # coupled span between the insertions
]
```

(The runtime docstring shows passing the control points themselves to `Route`;
the typed signature is `Port | Pad | Via`, so route the control point's *ports* —
`.coupled` / `.pair` / `.port` — and pyright stays clean.)

## Worked example — BGA escape lane deskew

Per TX lane: drop signal vias at the BGA pads, place a `PairPoint` at the deskew
exit and a `PairInsertion` further out, then route the coupled pair into the
insertion point and the two uncoupled legs out to the test-point pair. Attachments and
routes accumulate in plain **lists** (not string-keyed dicts).

```python
from jitx.controlpoint import RoutePoint, PairInsertion, PairPoint
from jitx.circuit import Route
from jitx.net import PortAttachment

self.attachments = []
self.routes = []
for index, lane in enumerate(self.escape_lanes):     # escape_lanes is a list
    via_cls = substrate.signal_via[lane.spec.signal_layer]    # via from the substrate
    self.attachments.append(PortAttachment(lane.tx_pair.p, via_cls().at(*lane.p_pad)))
    self.attachments.append(PortAttachment(lane.tx_pair.n, via_cls().at(*lane.n_pad)))

    pair_xy = (
        0.5 * (lane.deskew.left_exit[0] + lane.deskew.right_exit[0]),
        0.5 * (lane.deskew.left_exit[1] + lane.deskew.right_exit[1]),
    )
    insertion_xy = (pair_xy[0], -15)
    pair_point = PairPoint(layer=lane.spec.deskew_layer).at(pair_xy, rotate=90)
    insertion = PairInsertion(layer=lane.spec.deskew_layer).at(insertion_xy, rotate=90)

    self.attachments.extend([
        PortAttachment([lane.tx_pair.n, lane.tx_pair.p], pair_point),
        PortAttachment([self.tx_tps[index].pair.n, self.tx_tps[index].pair.p], insertion),
    ])
    self.routes.extend([
        Route(pair_point.pair, insertion.coupled, lane.spec.deskew_layer),
        Route(insertion.uncoupled.n, self.tx_tps[index].pair.n, lane.spec.deskew_layer),
        Route(insertion.uncoupled.p, self.tx_tps[index].pair.p, lane.spec.deskew_layer),
    ])
```

Note the discipline: vias come from the substrate (`substrate.signal_via[...]`),
lanes are iterated as a list with `enumerate`, and results are collected into
`self.attachments` / `self.routes` lists — no `getattr(self, f"lane_{i}")`, no
string-keyed parallel model.

## Verification

`pyright` catches a wrong accessor or constructor immediately. Then **build-test**:
the runtime ships no test exercising control points, so a successful `jitx build`
of a small harness design is the only confirmation that your control-point
geometry (placement, chirality, layer) is accepted end to end.
