# JITX Sample Project Prompt

Use the JITX workflow skill at the start of any substantial JITX design session.

- Claude Code: invoke `/jitx-skills:jitx` when the plugin is installed from the Claude marketplace.
- Codex/GPT: invoke `$jitx` or ask naturally for a JITX PCB design workflow when the plugin is installed in Codex.

The base skill handles environment setup, sub-skill routing, and the project builder workflow for complete board designs.

## Routing

- Single task: one component, one circuit, one substrate, one constraint set, or one pin-assignment wrapper routes to the matching skill directly.
- Complete board design: multiple components, circuits, and substrate work routes through the Project Builder workflow. Start with Phase 0 to create `PLAN.md` and `ARCHITECTURE.md` before writing code.

## Example

```text
I want to build a JITX PCB design for [requirements]. Use the JITX workflow skill, decompose the work, and validate the design before declaring it complete.
```
