#!/bin/sh
# sim-core must contain zero floating-point.
#
# Float arithmetic can differ in the last bits between CPU architectures. In a
# simulation one such difference changes which target a unit picks, and from there
# an iPhone and a Linux server disagree about who won the battle. That would break
# the server-side validation the whole V2 architecture depends on. Fixed-point
# integer maths only — see sim/sim-core/src/lib.rs.
#
# Added in Phase 0, before sim-core had any content, so there has never been an
# existing violation to grandfather in with an #[allow].
#
# ponytail: plain grep, so it also flags f32/f64 inside comments and string
# literals. That is the right trade for a check nobody can misread or quietly
# weaken. Upgrade to a syn-based AST walk only if it genuinely becomes annoying.

set -eu

TARGET="sim/sim-core/src"

if [ ! -d "$TARGET" ]; then
    echo "no-floats: $TARGET not found. Run from the repository root."
    exit 2
fi

if grep -rnE '\b(f32|f64)\b' "$TARGET"; then
    echo ""
    echo "FAIL: floating-point found in sim-core (listed above)."
    echo "      Fixed-point integer maths only. See docs/ARCHITECTURE.md."
    exit 1
fi

echo "OK: no floating-point in $TARGET"
