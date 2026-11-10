# Build outputs: what `jitx build` writes

## Result

`jitx build build_outputs_ref.build_outputs_design.BuildOutputsDesign` prints
`status: ok` and writes `designs/build_outputs_ref.build_outputs_design.BuildOutputsDesign/`.
Its `cache/` holds `design-explorer.json` and no `netlist.json`.

`design-explorer.json` is the module tree, not a netlist:

- `module` is the top circuit. Its `nets` list only the nets made at that
  level (`LINK`, with `load.a` and the child's boundary port), its
  `component-instances` list its own parts, and `module-instances` list its
  children, each with the same keys.
- The child's `MID` net sits under `module-instances[stage].nets`, with pins
  named by full path (`stage.first.b`, `stage.second.a`), and not under the
  top module's `nets`.
- A net is a `TreeNet` with a `pins` list of `TreePin` entries (`ref` is the
  pin's path); a bundle net is a `TreeNetBundle` whose own `nets` hold the
  member nets.
- Every `component-instances` entry carries `mpn`, `manufacturer` and its
  `pins`.

So a connectivity question ("which pins are on this net", "is this pin on any
net") is answered by walking every module, not by reading one list. A scan that
takes a component pin on no listed net as unconnected flags pins that are
connected: pin-assigned GPIOs, which join their net only once the assignment
resolves, and bundle pins listed under the bundle's type name. The base skill
points connectivity checks at tests instead.

## How to run it

From the jitx-skills repository root, with python3 resolving to the
interpreter of a venv that has jitx installed:

```text
$ python3 skills/jitx/evals/cases/reference/build-outputs/check_build_outputs.py
```

The check stages a project under the system temp directory (`pyproject.toml`
plus a `build_outputs_ref` package holding a copy of
`build_outputs_design.py`), runs `jitx runtime start --background --project <tmp>`,
`jitx build build_outputs_ref.build_outputs_design.BuildOutputsDesign --project <tmp>`
with `PYTHONPATH=<tmp>`, and `jitx runtime stop --project <tmp>` in a
`finally`, then reads the design folder.
