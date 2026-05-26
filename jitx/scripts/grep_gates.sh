#!/usr/bin/env bash
# grep_gates.sh — JITX skill grep-gate enforcement
#
# Runs the pattern set defined in jitx/references/completion-blocks.md.
# Reports hard-fail and review-required hits in the project's Python source.
#
# Usage:
#   bash grep_gates.sh <src-dir>
#   TOP_LEVEL_PATH=designs bash grep_gates.sh <src-dir>   # default — top-level designs in `designs/`
#   TOP_LEVEL_PATH=top     bash grep_gates.sh <src-dir>   # override for non-standard project layouts
#
# Exit codes:
#   0  — no hard-fail hits (review-required hits don't fail; they need disposition in task acceptance block)
#   1  — at least one hard-fail hit
#   2  — usage error
#
# Output format mirrors completion-blocks.md "Grep gates" reporting:
#   ok    no hits: <label>
#   HIT N <label>
#       <file:line:match>

set -u

SRC_DIR="${1:-}"
if [[ -z "$SRC_DIR" || ! -d "$SRC_DIR" ]]; then
    echo "Usage: bash $0 <src-dir>" >&2
    echo "  TOP_LEVEL_PATH (env, default 'designs'): top-level design dir name to exclude from top-level-only checks" >&2
    exit 2
fi

TOP_LEVEL_PATH="${TOP_LEVEL_PATH:-designs}"

if command -v rg >/dev/null 2>&1; then
    HAS_RG=1
else
    HAS_RG=0
fi

run_search() {
    local pattern="$1"
    local exclude_top="$2"  # "yes" or "no"

    if [[ $HAS_RG -eq 1 ]]; then
        if [[ "$exclude_top" == "yes" ]]; then
            rg --type py -n --glob "!**/${TOP_LEVEL_PATH}/**" -e "$pattern" "$SRC_DIR" 2>/dev/null || true
        else
            rg --type py -n -e "$pattern" "$SRC_DIR" 2>/dev/null || true
        fi
    else
        if [[ "$exclude_top" == "yes" ]]; then
            grep -rEn --include='*.py' --exclude-dir="$TOP_LEVEL_PATH" -- "$pattern" "$SRC_DIR" 2>/dev/null || true
        else
            grep -rEn --include='*.py' -- "$pattern" "$SRC_DIR" 2>/dev/null || true
        fi
    fi
}

HARD_FAIL=0
REVIEW=0

run_check() {
    local label="$1"
    local pattern="$2"
    local exclude_top="$3"
    local severity="$4"  # "hard-fail" or "review"

    local hits
    hits=$(run_search "$pattern" "$exclude_top")

    if [[ -z "$hits" ]]; then
        echo "  ok    no hits: $label"
    else
        local count
        count=$(echo "$hits" | wc -l | tr -d ' ')
        echo "  HIT $count $label"
        echo "$hits" | sed 's/^/      /'
        if [[ "$severity" == "hard-fail" ]]; then
            HARD_FAIL=$((HARD_FAIL + count))
        else
            REVIEW=$((REVIEW + count))
        fi
    fi
}

echo "grep_gates: scanning $SRC_DIR (top-level dir = $TOP_LEVEL_PATH)"
echo ""
echo "=== hard-fail patterns ==="

# SI / top-level applications outside designs/
# Catches calls like `with ReferencePlanes(...)`, `ConstrainDiffPair(...)`. Imports are not caught (no \( after the name).
run_check "SI/top-level applications outside ${TOP_LEVEL_PATH}/" \
    '\b(ReferencePlanes|Constrain|ConstrainDiffPair|ConstrainReferenceDifference)\s*\(' \
    "yes" "hard-fail"

# Net symbols outside designs/
run_check "Net symbols (GroundSymbol/PowerSymbol) outside ${TOP_LEVEL_PATH}/" \
    '\b(GroundSymbol|PowerSymbol)\s*\(' \
    "yes" "hard-fail"

# setattr/getattr on self anywhere — JITX convention violation
run_check "setattr/getattr on self (JITX convention)" \
    '\b(setattr|getattr)\s*\(\s*self\b' \
    "no" "hard-fail"

# Anonymous structural insert anywhere — silent-drop pattern 1
# Misses nested constructor args (e.g., Resistor(resistance=Toleranced.percent(...)).insert(...))
# but catches the most common form.
run_check "Anonymous structural .insert(...) — silent-drop pattern 1" \
    '\b(Capacitor|Resistor|Inductor)\s*\([^)]*\)\s*\.insert\s*\(' \
    "no" "hard-fail"

echo ""
echo "=== review-required patterns ==="

# Module-scope for-loops — anti-string-hacking theme 9. Module-import-time
# logic populating global tables is the named failure mode (see
# jitx/SKILL.md Don'ts and references/architectural-patterns.md
# § "No code at module-import time"). Legitimate uses (dispatch
# registration, static data generation) exist; review-required with
# disposition keeps the door open while flagging the smell.
run_check "Module-scope for-loop — review for module-import-time logic" \
    '^for\s+\w+\s+in\s+' \
    "no" "review"

# Pour(..., isolate=...) — legacy parameter, Pass 3 deprecates in favor of design_constraint with Tags
run_check "Pour(..., isolate=...) — legacy parameter (see Pass 3 deprecation)" \
    '\bPour\s*\([^)]*\bisolate\s*=' \
    "no" "review"

# Bare net/topology expression — silent-drop pattern 2
# Allows trailing comments and bracket indexes (self.mcu.PA[5]).
run_check "Bare net/topology expression — silent-drop pattern 2" \
    '^\s*self\.\w+(\.\w+|\[[^]]+\])*\s*(\+|>>)\s*self\.\w+(\.\w+|\[[^]]+\])*(\s*#.*)?$' \
    "no" "review"

# Dynamic type(...) call — JITX disallows runtime type construction; isinstance is the right check
run_check "type(...) call — verify not used for runtime type construction" \
    '\btype\s*\(' \
    "no" "review"

# Tag-like f-string construction — anti-string-hacking theme 1. f-strings
# starting with an uppercase letter and building names with a
# brace-substitution (f"TX_b{i}", f"L{n}_via", f"X{lane}_{pol}",
# f"GND_via_{i}") are the canonical string-keyed-name failure mode. Some
# legitimate uses exist (log messages, error formatting) — disposition
# each hit with rationale or fix per jitx/SKILL.md Don'ts and
# references/architectural-patterns.md § "String-keyed dicts →
# structural objects".
run_check "Tag-like f-string (anti-string-hacking — string-keyed names)" \
    '[fF]["'"'"'][A-Z][A-Za-z0-9_]*\{' \
    "no" "review"

# Broader getattr( call — narrower hard-fail above catches getattr(self,
# ...). This wider review-required catches getattr(other, "...") cases
# where strings are still being used as the indirection mechanism. Most
# are still smells; legitimate framework uses (e.g., hasattr/getattr on a
# known-typed external object) are dispositioned per-hit.
run_check "getattr( — review for string-keyed indirection on non-self objects" \
    '\bgetattr\s*\(' \
    "no" "review"

# I2C pull-ups outside designs/ — shared-bus components belong at the
# bus-aggregation level (the circuit that composes master + slaves). Usually
# the top-level design; hits here flag for review so the agent confirms the
# pull-up sits at a bus-composition level, not local to a single participant.
run_check "I2C pull-up (r_sda/r_scl) outside ${TOP_LEVEL_PATH}/ — review bus-aggregation level" \
    '\br_(sda|scl)\b' \
    "yes" "review"

# .insert(...) calls missing short_trace= — Phase 2 power-rail cap gate.
# False positives on resistor/inductor inserts and on non-power-rail caps
# (AC coupling, RC, RF, crystal load) — agent dispositions each per
# `jitx-circuit-builder/SKILL.md` "short_trace=True is the default for
# power-rail capacitors".
INSERT_HITS=$(run_search '\.insert\s*\(' "no" | grep -v 'short_trace' || true)
if [[ -z "$INSERT_HITS" ]]; then
    echo "  ok    no hits: .insert(...) missing short_trace= (power-rail cap default)"
else
    insert_count=$(echo "$INSERT_HITS" | wc -l | tr -d ' ')
    echo "  HIT $insert_count .insert(...) calls missing short_trace= (power-rail cap default)"
    echo "$INSERT_HITS" | sed 's/^/      /'
    REVIEW=$((REVIEW + insert_count))
fi

echo ""
echo "=== summary ==="
echo "hard-fail hits: $HARD_FAIL"
echo "review-required hits: $REVIEW (need disposition in task acceptance block)"

if [[ $HARD_FAIL -gt 0 ]]; then
    echo ""
    echo "FAIL — fix hard-fail hits before emitting the task acceptance block."
    exit 1
fi

echo ""
echo "PASS (hard-fail set clean)"
exit 0
