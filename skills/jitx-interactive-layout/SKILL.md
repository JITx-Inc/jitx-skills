---
name: jitx-interactive-layout
description: "Use when the user asks to place components, route nets, drop vias, add pair insertions or route points, or draw pours in the open board layout from a script, so the result stays editable in the board editor: place and route a board or circuit, fan out a BGA, route DDR byte lanes, change a layout the user has been editing by hand, fix blocked routes, report layout issues or skew margin. Runs Python against a live design through jitx design session and exec, with the rd.layout requests (place, route, via, route_point, pair_insertion, region, modify, delete), and reads the result back through route status, rd.issues() and the bundled checks. Assumes the layout constraints are already in the design. Design rules, net classes, tags and escape-width rules in code belong to jitx-layout-constraints; decoupling modules to jitx-circuit-builder; copper, code-placed vias, code Route objects and control points in code to jitx-code-layout; topology, timing and skew constraints to jitx-interconnect-constraints."
---

# JITX Interactive Layout

Place and route from a script, as edits to the open layout. Everything made
here (placements, routes, vias, control points, pours, keepouts) is an
ordinary layout object the user can edit in the board editor. A `Route` in
the design's Python is not: the editor cannot change what its code sets.

The runtime saves the layout under `designs/<design>/design-info/`. That is
the work; commit it with the source.

There are two ways in, and most work alternates between them:

- Build: the user asks for a board, a circuit or an interface laid out.
  Follow "Build" below.
- Edit: the user has changed the layout in the board editor and asks for
  something on top. Follow "Edit" below.

## Scope

| Task | Skill |
|---|---|
| Place, route, vias, pair insertions, route points, pours, keepouts in the open layout; read back status, issues, margins; floorplan and routing solvers | this skill |
| Design rules, net classes, tags, power widths, escape widths | `jitx-layout-constraints` |
| Decoupling modules | `jitx-circuit-builder` |
| Copper, code vias, code `Route`s, control points in code; drawing the realized geometry | `jitx-code-layout` |
| Topology, timing, skew, loss constraints | `jitx-interconnect-constraints` |
| provide/require pools, swapping | `jitx-pin-assignment` |
| Stackup, via definitions, routing structures | `jitx-substrate-modeler` |

The base `jitx` skill owns setup. `jitx.run` is experimental: check a
refused call's signature with `help(jitx.run.layout.SyncLayout)`.

## Limitations

Work around these and say where they affected the result.

- No query for a route's possible ends. The capture's pin assignment is
  often poor. Derive the eligible pads from the source's `provide`/`require`
  and route to the ones you choose.
- No query for constraints. Read rules, net classes, routing structures,
  topologies and bounds from the source.
- No tags. Route without the tag and list the route for the user to tag.
- Net labels lag a pin assignment change: after the assignment moves, the
  nets read from Python (`rd.nets`, a pad's or control point's net) can
  still show the old assignment until a fresh capture. Check connectivity
  after a re-solve from the copper and the pads you chose, or from a fresh
  capture (restart the session), not from those labels.
- One copy of a thing loaded at a time: a second load breaks the
  session's Python state. If `exec` starts failing unexplained, restart the
  session.
- A large batch can stall the session long enough that its connection
  drops: a batch of a thousand or more deletes can do this, and every
  `exec` after it fails with `message could not be delivered`. Send large work
  in batches of tens of objects, deletes included, with a `sync` between.
  To recover, stop the session (`jitx design session --stop`), confirm no
  session process is left, then start one. Never
  start a second session while one is alive, and never run two `exec`s at
  once.

## Session

```bash
mkdir -p .jitx
jitx design build my_pkg.main.MyDesign        # once, if exec reports the board outdated
jitx design session my_pkg.main.MyDesign > .jitx/session.log 2>&1 &
jitx design exec my_pkg.main.MyDesign scripts/place.py        # runs main(rd)
jitx design exec my_pkg.main.MyDesign scripts/place.py -f fix # runs fix(rd)
jitx design session --stop my_pkg.main.MyDesign
```

- Needs `jitx runtime start --background`. One session per design.
- `exec` fails with `message could not be delivered` until the session is
  up: retry for a minute, then read `.jitx/session.log`.
- Place the circuit before its parts. A component inside a circuit with
  no placement of its own (`.at(floating=True)`) has no frame for its
  position, and its placement is lost when the session restarts. Give
  each block's circuit a placement in the source (`.at(x, y)` at the
  block's floorplan origin), rebuild, then place its parts; their
  placements and the user's moves then survive restarts. Say which
  circuits you placed.
- `rd.root` is the design tree, `rd.layout` takes requests, `rd.query(T)`
  yields `(trace, obj)`, `rd.nets.find(pad)` gives a net, `rd.issues()` the
  report. The return value prints as JSON; keep it small.
- `exec` does not put the script's folder on the import path; add it with
  `sys.path.insert`.

## Requests

Board-absolute mm and degrees CCW; layer 0 is top, `-1` is bottom.

| Request | Does |
|---|---|
| `place(comp, (x, y), rot, on=Side.Top)` | Move a component |
| `route(a, b, layer, turns=, width=, space=, pour=)` | Route two endpoints; `turns=None` autoroutes, a list guides it, `[]` is a straight sketch |
| `via(defn, pad, (x, y), layer, force=False)` | Via routed from `pad`, nudged to a free spot unless `force` |
| `route_point(origin, (x, y), layer)` | Control point routed from `origin` |
| `pair_insertion((p, n), (x, y), rot, layer)`, `drop_pair_insertion`, `pair_point` | Diff-pair merge point and coupled continuation |
| `region(Pour(ConvexHull([...], expand=), layer, rank=), net=)` | Pour, keepout, cutout |
| `modify`, `update_via`, `update_control`, `update_region`, `delete` | Change or remove |
| `sync(timeout)` | Wait for routing and checks to settle |

- Endpoints: a pad, a single-pad port, a via, a control point.
- `place` and `delete` do not wait; `sync` after them.
- `with rd.layout.batch() as b:` applies in order, all or nothing. A via or
  control point made in a batch can be used from the next batch.
- A refused request raises `RequestRejected`; read its `message`.

Signatures, handles, rejection kinds, read-back paths: `references/api.md`.

## Read back and check after every batch

Accepted is not done: routes realize in the background, can come out
blocked, and later copper can push earlier routes into blocked.

```bash
jitx design exec my_pkg.main.MyDesign <skill>/scripts/layout_report.py              # state.json
jitx design exec my_pkg.main.MyDesign <skill>/scripts/layout_report.py -f issues_all
jitx design exec my_pkg.main.MyDesign <skill>/scripts/layout_checks.py              # checks.json
```

| Read | Tells you |
|---|---|
| report summary | ideal and unplaced parts, courtyard overlaps, parts off the board, blocked routes, split, empty and `fill_unknown` pours (sync and rerun), issue counts, tightest skew and loss margins; a pending category means rerun |
| report `changed` | what moved, appeared or went away since the previous report, the user's editor changes included |
| `connectivity` | nets whose pads are not all joined by routes, vias and pour fills; `rd.issues()` does not report an unrouted plain net |
| `vias` | per pad-to-pad connection, its vias: one its ends did not need (`redundant`), or one farther than `via_reach_mm` from the end it serves (`far_from_end`); every via joined on fewer than two layers (`dangling`), and every via in a pad whose definition does not allow it (`via_in_pad`) |
| `sanity` | parts past the board edge (except those named in `overhang`), courtyard overlaps, vias outside the board |
| `circuitousness`, `loops`, `decap_vias`, `power`, `power_paths` | placement and routing quality (`references/general-pnr.md`) |
| `issues_all` | every constraint result with its margin; SI passes or fails here, never on your own estimates (`references/si-pnr.md`) |

`rd.issues()` does not check trace clearance; measure it from the copper
where a rule matters. Write a scorer for anything else you are optimizing
and run it every batch.

## Build

1. Read the constraints from the source. Write down what you plan against
   (widths, clearances, power nets, `ShortTrace` pairs, routing structures,
   bounds, vias, stackup), each with its source file. If the constraints a
   task needs are missing, hand off to `jitx-layout-constraints` or
   `jitx-interconnect-constraints`. `ideal_parts` in the report: tell the
   user and place around them only if they agree. A plane pour the stackup
   leaves open is the user's call; if you cannot ask, add one and say so.
2. Floorplan by blocks, connectors on their edges facing out
   (`general-pnr.md`, Floorplan by blocks). Place each block's circuit at
   its region's origin (Session, above).
3. Via plan: every connection's layer and its 0, 1 or 2 vias, each at
   the end pad it serves (`general-pnr.md`, Via plan). For an interface
   under SI constraints, one pin assignment for the whole interface first
   (`si-pnr.md`).
4. Block by block: place, route its tight connections and plane vias, then
   its pours and local routes; check the block (`scope` in the checks
   config) before the next.
5. Between blocks, then the bulk, to the via plan.
6. Sanity pass, below.

## Edit

The user's changes are the brief. Treat everything they placed, moved,
routed or deleted as fixed unless they ask otherwise.

1. Start the session, run `layout_report.py`, and read
   `changed` and the checks to see what the user did and what it broke.
2. Change only what was asked, plus what the request forces (a route
   blocked by a part the user moved). Do not rerun the build scripts: they
   would undo the user's work. Write a small script for the change.
3. Do not delete or move objects you did not make in this task: ask.
4. Read back, and tell the user what changed, what their
   edit broke that you did not fix, and any check that got worse.

## Sanity pass

Before calling a build or an edit done, look at the board the way a
reviewer would. Draw it if that helps: the realized geometry (courtyards,
pads, route copper, vias, pour fills, the board outline) is readable from
Python, and `jitx-code-layout` covers reading it. Answer each:

- Is anything past the board edge, and is it meant to be? Name each
  intended overhang in the checks config `overhang` with its reason.
- Does each connector sit on an edge with its mating face pointing off the
  board?
- Does any via join nothing, or sit mid-route instead of at a pad?
- Does any route wander, double back or take a layer its plan did not give
  it?
- Is any block crowded or any part stranded far from what it connects to?
- Would a reviewer redo any of it? If so, redo it now or list it.

## Done

- `connectivity`, `vias` and `sanity` met; no blocked route.
- `issues_all`: no error-severity issue and every category complete; for
  SI designs every skew, delay and loss check met with margins, and every
  differential pair coupled on its structure.
- No courtyard overlap; each pour one piece.
- Report shortfalls first. Do not say done while anything the user asked
  for is unrouted, unmeasured or failing; say what is left and what blocks
  it. Then: the rules planned against with their files, requests that set a
  width or space, pads that share a via, what each pour joins and why,
  ideal parts the user accepted, routes left for tags, limitations that
  applied, and what you checked and what you did not.

Do not write rules or tags in the source from here.
