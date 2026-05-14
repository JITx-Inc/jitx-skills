# Export Verification — auditing a built design for silent wiring errors

A `python -m jitx build` that prints `status: ok` is **necessary but not
sufficient** evidence that the design is correct. Builds catch type errors,
missing pin mappings, and unconnected `require()` providers; they do not catch
wiring errors where every port is in *some* net but the wrong net. The
TEC-example pilot built cleanly with four distinct categories of silent
netlist errors (swapped connector pins, wrong PVDD source, an entire output
filter section missing, mis-wired control signals).

Walk this six-section checklist on any design before declaring it ready.
Sections A–F apply to any greenfield 4.x design; the porting workflow layers
two additional comparison checks (B 1-based↔0-based connector indexing and
E passive-count delta) on top — see
`jitx-skills:jitx-port-3-to-4/references/verification.md` for those.

## Inputs

After a successful build, the relevant artifacts are:

- `designs/<design_name>/cache/netlist.json` — JSON net list with every port
  on every net. This is the authoritative connectivity record.
- `designs/<design_name>/design-info/stable.design` — the stable design
  snapshot, useful for diffs across runs.

For each check below, the inputs come from grepping the source `.py` files
against `netlist.json`.

## A. Net inventory

1. Grep every `Net(name="<NAME>")` declaration and every `self.<NAME>` net
   storage attribute in the design.
2. For each, verify a correspondingly-named net exists in `netlist.json`.
3. Anonymous `self.foo = port_a + port_b` results DO survive in the
   netlist — connectivity is preserved — but get synthesized names like
   `circuit.member.sub_port`. Those names don't text-match anything you'd
   grep for and make the diff noisier.

> **Tip for readable netlists**: prefer
> `self.NAME = Net(name="NAME") + a + b` over anonymous
> `self.foo = a + b` for any net that should appear in the netlist with a
> stable, greppable name. A real design with 80 nets had ~15 synthesized
> names — enough to make the netlist substantially harder to audit than
> necessary.

## B. Connector pin assignment

For every connector / pin-header in the design:

1. List every `conn.p[i]` assignment in source.
2. Verify the net name on each pin matches the design intent (`VCC`,
   `GND`, `EN`, `SCL`, `SDA`, etc.).
3. Cross-check against the connector's datasheet pin numbering — JITX
   `conn.p[0]` corresponds to the first port declared on the connector
   `Component`, which is *not always* datasheet pin 1 (a port-order
   mistake here silently swaps connector pins).

## C. Power topology

This is the most-inverted check in practice. JITX has no built-in voltage
domain consistency check, and rail-naming inversions produce clean builds
with wrong voltages on PVDD / I²C pullups / copper pours.

1. Identify the **external input net** (connected to the power connector
   and to the regulator's VIN). Conventionally named `VCC` or `V_BAT` or
   similar — the raw, unregulated supply.
2. Identify the **regulated output net** (connected to the regulator's
   VOUT). Conventionally named `VDD` or `V3P3` / `V1P8` / etc. — the
   regulated rail that powers the digital side.
3. For each sub-circuit, verify its power ports connect to the correct
   rail:
   - High-current / output-stage components (class-D amps, motor drivers)
     typically connect their power supply to the **raw external** rail.
   - MCU / sensor / digital-side DVDD / AVDD connects to the
     **regulated** rail.
4. Write down the mapping explicitly before naming any Python net — a
   table like:

   | Net | Source | Type | Wired to |
   |---|---|---|---|
   | `VCC` | `conn.p[1]` | raw input | regulator VIN, amp PVDD |
   | `VDD` | `vreg.VOUT` | regulated | MCU DVDD, sensor VCC, I²C pullups |

   prevents the `VCC = regulated 3.3 V` inversion that is the natural
   instinct when "VCC" is the most prominent rail in the design.

## D. Component output pins

A floating output pin is **always wrong** — there is no design intent that
leaves an output dangling. For every IC in the design:

1. Grep the component class for every output-typed pin (`OUT_x`, `BST_x`,
   `SW`, `FB`, `DAC_*`, etc. — anything the datasheet flags as an output).
2. Verify each is wired to a real net in `netlist.json`.
3. **Anti-pattern**: an `OUT_*` / `BST_*` / `SW` pin appearing only in
   its component's GND / DVDD / PVDD net is a sign that the output
   filter / bootstrap / switching network was never added — the bare
   component made it into the design but the surrounding application
   circuit didn't.

A common pattern that gets missed: a buck converter's `SW` (switch node)
must connect to an inductor, not directly to VOUT. A class-D amp's
`OUT_+` / `OUT_-` must connect to an LC output filter, not directly to
the speaker. If the netlist shows the output going straight to the load
without the prescribed passives, the application circuit is incomplete.

## E. Passive count sanity

Count `Capacitor`, `Resistor`, `Inductor` instances per `Circuit` and
compare against the datasheet's recommended-application schematic. An
order-of-magnitude discrepancy (e.g. 4 capacitors where the datasheet
calls for 14) usually indicates a missing application-circuit wrapper —
the bare component was instantiated but its decoupling / filtering /
snubber networks weren't.

For ICs with rich application circuits (switchmode converters, class-D
amps, RF transceivers), prefer constructing the application circuit from
the datasheet's "Typical Application" figure rather than wiring the bare
component pin-by-pin. The `jitx-component-modeler` skill's Step 5
("Capture Application Circuit") is the right entry point.

## F. Control-signal completeness

For every control / GPIO / status net in the design:

1. List the design intent for each net (MCU-driven? tied off to a rail?
   pulled up via resistor? jumper-configurable?).
2. Verify each control net's `netlist.json` entry has the expected
   number of ports.
3. **Anti-pattern**: a net like `(VDD amp.PDN_NOT)` — wiring an
   active-low power-down pin straight to VDD — keeps the amp permanently
   enabled, which is sometimes the intent (production design) and
   sometimes not (intended to be MCU-controlled but the GPIO wiring was
   forgotten). Distinguish intended tie-offs from forgotten wiring; if
   the schematic *should* expose the pin to an MCU GPIO, the netlist
   must show a path from MCU → pin, not from VDD → pin.

## Verification hygiene

- Capture both the source (`.py` files) and the build output
  (`netlist.json`, build stdout/stderr) into a known location per check
  pass. This makes "did the netlist change between runs?" answerable
  later. The porting workflow uses
  `/tmp/jitx-port/<design>/{baseline-3.x,ported-4.x}/` for this; a
  greenfield design can use `artifacts/<timestamp>/` or similar.
- `status: ok` is not a substitute for any of the six checks above.
- If a check is hard to perform mechanically (E and F often are), record
  *that* the check was attempted and what was inspected — an
  unverifiable check that a co-reviewer later confirms is still useful;
  a silently-skipped one is invisible in PR review.
