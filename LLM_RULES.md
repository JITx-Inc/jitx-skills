# LLM Rules for JITX (Concise)

These rules apply to **any** LLM-assisted JITX work (Cline, Codex, Claude Code, etc.).

## Tier 0: Universal Rules (never violated)

### Environment + verification
- **MUST** run any verification (build, tests, scripts) inside an **activated virtual environment**.
  - If a venv is not active, **STOP and ask**.

### Code correctness
- **NEVER** use `=` for electrical connections.
  - Use `+`, `+=` for nets; use `>>` for high‑speed topologies.
- **MUST** use real components/APIs.
  - **NEVER** invent import paths, ports, or methods; inspect source/docstrings first.
- **MUST** define ports/bundles as **class attributes**, not in `__init__`.
- **MUST** keep `require()` results as **local variables**, not `self.*`.

### Quality gates
- **MUST** produce code with **zero type checking errors** (Pylance/Pyright or equivalent).
- **MUST** produce code that is **formatted** (ruff or equivalent).

### Uncertainty
- If any of: bundle direction, protocol wiring, pin mapping, or component API is unclear → **STOP and ask**.

---

## Tier 1: Draft (Exploration)

Goal: move fast while staying structurally correct.

Allowed:
- Partial designs, placeholders, missing constraints.

Required (in addition to Tier 0):
- Clearly label output as **DRAFT (not built)**.
- Do not claim runtime/build success.

---

## Tier 2: Production (Verified)

Goal: code that can be committed/shared as working.

Required (in addition to Tier 0):
- **MUST** run:
  - `python -m jitx build-all`
- **MUST** fix errors until build passes.
- Output may be labeled **VERIFIED** only if all checks pass.

### Production verification checklist
- [ ] venv activated
- [ ] type check clean (Pylance/Pyright)
- [ ] formatted (ruff)
- [ ] `python -m jitx build-all` passes
