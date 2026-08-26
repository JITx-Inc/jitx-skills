# QFN Power Fanout Reference Notes

The requested home-directory scratch location was not writable in this
sandbox. The reference was translated from `/private/tmp/qfn-power-fanout`.
This is a scratch-location deviation only. Shipped files remain under the eval
case directory.

## Sources and derived geometry

- Package: generated QFN (skill default: 32 leads) at `0.5 mm` pitch (skill
  default: `0.5 mm` pitch), using `DensityLevel.C`.
- Class trunk: `0.5 mm` width (skill default: `0.5 mm` power-class width).
- Pad width: `0.250000 mm`, read from placed pad copper with `jitx.query`.
- Adjacent gap: `0.250000 mm`, computed as the queried `0.500000 mm` row pitch
  minus the queried `0.250000 mm` pad width.
- Fabrication floor: `0.090000 mm` copper-to-copper space from
  `FabricationConstraints.min_copper_copper_space` on `JLC04161H_7628`
  (`jitxlib/jlcpcb/rules.py:4-11`).
- Escape width: `0.250000 mm`, derived as the largest width that preserves the
  fabrication floor at adjacent pads and is capped by the queried pad width.
- Escape clearance: `0.100000 mm`, the `0.090000 mm` fabrication floor from
  `FabricationConstraints.min_copper_copper_space` plus a `0.010000 mm` margin
  (skill default: `0.010000 mm` clearance margin).
- Measured trunk and escape widths after capture: unavailable. The runtime was
  unavailable for capture, so no realized widths are reported.

## Verification output

Pyright needed the installed JITX interpreter passed explicitly. Without
`--pythonpath`, the pyright process resolved a different environment and ended
with this real summary:

```text
7 errors, 0 warnings, 0 informations
```

The interpreter-aligned command passed:

```text
$ python -m pyright --pythonpath "$VIRTUAL_ENV/bin/python" skills/jitx-layout-constraints/evals/cases/reference/qfn-power-fanout/*.py
(node:42768) Warning: The 'NO_COLOR' env is ignored due to the 'FORCE_COLOR' env being set.
(Use `node --trace-warnings ...` to show where the warning was created)
0 errors, 0 warnings, 0 informations
```

Dry translation ran against the current reference module. This is not a
runtime build and is not capture evidence:

```text
$ PYTHONPATH=/private/tmp/qfn-power-fanout python -m jitx build --dry qfn_power_fanout.qfn_power_fanout.QfnPowerFanoutDesign
/usr/local/Homebrew/Library/Homebrew/cmd/shellenv.sh: line 18: /bin/ps: Operation not permitted
Dependencies recently checked, skipping. Will check again in 49 minutes.
QFN escape geometry: pad_width=0.250000 mm, adjacent_gap=0.250000 mm, row_pitch=0.500000 mm, escape_width=0.250000 mm, escape_clearance=0.100000 mm
qfn_power_fanout.qfn_power_fanout.QfnPowerFanoutDesign:
  design: qfn_power_fanout.qfn_power_fanout.QfnPowerFanoutDesign
  status: ok
```

The full build did not run because no runtime was reachable:

```text
$ PYTHONPATH=/private/tmp/qfn-power-fanout python -m jitx build qfn_power_fanout.qfn_power_fanout.QfnPowerFanoutDesign
/usr/local/Homebrew/Library/Homebrew/cmd/shellenv.sh: line 18: /bin/ps: Operation not permitted
Error: no runtime reachable in this project. Start one with `jitx runtime start --background`, or run with `--dry` to skip the build step.
```

The capture and assertion script exited nonzero before build or capture:

```text
$ python skills/jitx-layout-constraints/evals/cases/reference/qfn-power-fanout/check_fanout.py
$ python -m jitx runtime start --background
Error: launcher exited (rc=1) before announcing itself; see <temporary-project>/.jitx/logs/runtime.log for output.
[runtime.log] Error occurred when attempting to open file $HOME/.jitx/.stats.txt. Operation not permitted.
[FAIL] command exited 1: python -m jitx runtime start --background
```

An isolated deployment-root retry passed the statistics-file step, then the
runtime log repeated this socket error:

```text
lws_socket_bind: ERROR on binding fd 6 to port 0 (-1 1)
```

The em-dash check printed nothing, as required:

```text
$ grep -n "—" skills/jitx-layout-constraints/references/fanout.md
```

The prohibited-mechanism spelling appears only in the explanatory note:

```text
$ grep -n "NeckDown" skills/jitx-layout-constraints/references/fanout.md skills/jitx-layout-constraints/evals/cases/reference/qfn-power-fanout/*.py
skills/jitx-layout-constraints/references/fanout.md:405:## Not NeckDown
skills/jitx-layout-constraints/references/fanout.md:407:`RoutingStructure.NeckDown` only supplies parameters for a neckdown region;
```

## Decisions

The generated QFN needed a minimal placeholder component and symbol. The
reference maps the power rail to the first generated peripheral pad (skill
default: pad `1`) and uses the next generated peripheral pad for ground (skill
default: pad `2`). The escape route is tagged, while the power-class tag stays
on the net. The broader skill-eval receipts and routing fixtures required by
the skill-development lifecycle were outside the owned file set and were not
changed.
