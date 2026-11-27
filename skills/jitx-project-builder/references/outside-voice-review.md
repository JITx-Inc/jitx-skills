# Outside-Voice Review

An independent reviewer, codex by default, after a same-model pass. Complete-board only.

## Same-model passes precede codex (two distinct pre-passes, two distinct scopes)

- Per task: `jitx-code-review` (`task-execution.md` Part A Step 4), then, for a trigger-list task, the outside voice at acceptance (Part B).
- Phase 3b: the four-pass audit, then the outside-voice passes. `jitx-code-review` does not rerun there.

## Per task

Trigger classes, each with its evidence packet and focus:

- MCU / FPGA components: `<ns>/components/<part>.py` and its PDF; pin coverage, power domains, reset, boot straps, programming and debug, footprint against the mechanical drawing.
- RF components and circuits: the circuit and component files, the RF part's PDF and reference design; impedance, return-plane keepout, ESD, antenna feed, matching.
- Power converters: the circuit and regulator PDF; divider math against Vref, bootstrap, enable, compensation, dissipation against package, sequencing.
- Safety-critical circuits: the circuit and its spec; isolation, creepage, fail-safe state, behaviour on component failure.
- High-speed or controlled-impedance interfaces (DDR, PCIe, USB, Ethernet, HDMI, DisplayPort, MIPI, SerDes): the circuit, substrate file and protocol spec; constraints, topology, plain nets with pin models, termination, return path.
- Battery charging and protection: the circuit, charger PDF and pack spec; charger setup, fuel gauge, thermistor, power path, fault response.

A mixed-signal frontend triggers only where precision, protection, leakage, filtering or ADC reference integrity carries the task. Another task may get a pass on a red flag, with the reason in the block. No pass reruns on a loopback fix that left the flagged code untouched.

## Phase 3b

A trigger-list task is covered when its per-task pass completed and nothing since has changed a file that pass read, decided from PLAN.md `Modifications` and the files' history; undecidable means not covered. The passes, concurrent where independent, each with its own output:

- Integration: one pass over the top-level design and constraint files, checking how the assembly connects, supplies and constrains every covered task against its trigger focus. Cite the covered tasks in the audit block.
- Each uncovered trigger-list task: its block, the files it owns or touches, its PDF, checked against its focus in the assembly.
- Cross-cutting, always: `Power Tree`, the regulator, protection and load files and their PDFs; power arithmetic, sequencing, hot-plug, absolute maximums.

## Prompt and invocation

Name the readable directory, the exact files and PDFs (never the spec notes), the failure modes, and the output format. Never send the whole project. End every prompt with: "Also flag any directly observable blocking electrical or geometry mismatch in the reviewed files."

Invoke the installed `codex` skill with one project-local output file per pass; any read-only reviewer that returns severity-tagged findings may stand in, named in the block. A pass completes only when it leaves non-empty findings output. A finding without file:line, and a page or `inference` where it cites a datasheet, drops to NOTE.

A pass with no reviewer available, a nonzero exit or no output reads `skipped: <reason>`. It carries no findings and leaves the verdict as it is, but the Phase 3b gate blocks until the user approves going on without it.

## Precedence and combined verdict

Any CRITICAL or WARNING finding from `jitx-code-review`, the audit or the outside voice makes the combined verdict `issues-pending` until each is settled:

- CRITICAL: fixed, the fix confirmed by re-review.
- WARNING: fixed, or accepted with a recorded rationale for the risk; a deferral to later refactoring is not one.
- NOTE: recorded; fixed only inside a fix task that already changes its file.
- Lowering a reviewer's severity is the user's call, recorded with the deferred items.
- Deferred to place and route, at any severity: a finding only a layout can meet (where a part sits, how a path routes, a loop's area), unless the user asked for layout in code. List it in the block that raised it and record it with its source in PLAN.md, as a note on the task's `Status` until the next gate's `Gate status` row carries it. What it needs in code (a width, clearance, keepout, stitching, fencing, an SI constraint) is still fixed.
